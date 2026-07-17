import queue
import threading
import time
import json

from core.config_manager import ConfigManager
from core.database import DatabaseManager
from core.downloader import Downloader, DownloadAborted
from core.license_manager import LicenseManager
from core.logging_setup import get_logger

log = get_logger("grabbyvault.queue")


class QueueManager:
    def __init__(self, ui_callbacks=None):
        self.db = DatabaseManager()
        self.download_queue = queue.PriorityQueue()
        self.jobs = {}
        self.downloader = Downloader()
        self.ui_callbacks = ui_callbacks or {}
        self.license = LicenseManager()
        self.config = ConfigManager()
        self._seq = 0  # stable tie-break for PriorityQueue
        self._seq_lock = threading.Lock()

        unfinished = self.db.get_unfinished_jobs()
        for j in unfinished:
            job_id = j["id"]
            meta = j.get("metadata") or {"id": job_id, "title": j.get("title")}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {"id": job_id, "title": j.get("title")}
            meta.setdefault("id", job_id)
            meta.setdefault("title", j.get("title") or "Unknown")

            status = j["status"]
            # P0: do NOT auto-requeue permanent errors — user must retry
            if status == "error":
                self.jobs[job_id] = {
                    "url": j["url"],
                    "metadata": meta,
                    "status": "error",
                    "priority": j["priority"] if j["priority"] is not None else 1,
                    "format": j["format"],
                    "platform": j.get("platform") or "Unknown",
                    "filepath": j.get("filepath"),
                    "error": j.get("error"),
                }
                continue

            # Interrupted mid-download → re-queue once
            if status == "downloading":
                status = "queued"
                self.db.update_status(job_id, "queued")

            self.jobs[job_id] = {
                "url": j["url"],
                "metadata": meta,
                "status": status,
                "priority": j["priority"] if j["priority"] is not None else 1,
                "format": j["format"],
                "platform": j.get("platform") or "Unknown",
                "filepath": j.get("filepath"),
            }
            if status in ("queued",):
                self._enqueue(job_id, self.jobs[job_id]["priority"])
            elif status == "paused":
                pass  # wait for user resume

        self.active_workers = []
        self.worker_lock = threading.Lock()
        self._shutdown = False
        self._adjust_workers()

    def _next_seq(self) -> int:
        with self._seq_lock:
            self._seq += 1
            return self._seq

    def _enqueue(self, job_id: str, priority: int = 1):
        # (priority, seq, job_id) — never compare job_ids as secondary alone
        self.download_queue.put((int(priority), self._next_seq(), job_id))

    def _target_workers(self) -> int:
        lic_max = self.license.max_concurrent()
        try:
            cfg = int(self.config.get("max_concurrent_downloads", lic_max) or lic_max)
        except (TypeError, ValueError):
            cfg = lic_max
        return max(1, min(cfg, lic_max))

    def _adjust_workers(self):
        with self.worker_lock:
            if self._shutdown:
                return
            target_workers = self._target_workers()
            self.active_workers = [w for w in self.active_workers if w.is_alive()]
            current_workers = len(self.active_workers)

            if current_workers < target_workers:
                for _ in range(target_workers - current_workers):
                    t = threading.Thread(target=self._process_queue, daemon=True)
                    t.start()
                    self.active_workers.append(t)

    def apply_settings_change(self):
        self.config.load_config()
        self.license.refresh()
        self.downloader.config = self.config
        self.downloader._rebuild_base_opts()
        self._adjust_workers()

    def cancel_job(self, job_id):
        job = self.jobs.get(job_id)
        if job:
            job["status"] = "cancelled"
            job["abort"] = "cancelled"
            self.db.update_status(job_id, "cancelled")
            self._kill_active_download()

    def pause_job(self, job_id):
        job = self.jobs.get(job_id)
        if job:
            # Active download: abort process then mark paused (re-queue on resume)
            if job["status"] == "downloading":
                job["abort"] = "paused"
            job["status"] = "paused"
            self.db.update_status(job_id, "paused")
            self._kill_active_download()

    def _kill_active_download(self):
        runner = getattr(self.downloader, "_active_runner", None)
        if runner is not None:
            try:
                runner.kill()
            except Exception:
                pass

    def resume_job(self, job_id):
        job = self.jobs.get(job_id)
        if job and job["status"] in ("paused", "error"):
            job["status"] = "queued"
            job["abort"] = None
            job["error"] = None
            self.db.update_status(job_id, "queued")
            self._enqueue(job_id, job.get("priority", 1))

    def retry_job(self, job_id):
        self.resume_job(job_id)

    def delete_job(self, job_id):
        self.cancel_job(job_id)
        if job_id in self.jobs:
            del self.jobs[job_id]
        self.db.delete_job(job_id)

    def add_job(self, url, metadata, priority=1, format_str=None, platform="Unknown"):
        clamped, warning = self.license.clamp_format(format_str)
        job_id = metadata.get("id", url)
        title = metadata.get("title", "Unknown")
        # Strip non-serializable / huge blobs for DB
        meta_store = {
            k: v
            for k, v in (metadata or {}).items()
            if k
            not in (
                "formats",
                "thumbnails",
                "automatic_captions",
                "subtitles",
                "requested_formats",
            )
            and not callable(v)
        }
        self.jobs[job_id] = {
            "url": url,
            "metadata": metadata,
            "status": "queued",
            "priority": priority,
            "format": clamped,
            "platform": platform,
            "filepath": None,
            "abort": None,
        }
        self.db.add_job(
            job_id,
            url,
            title,
            platform,
            "queued",
            priority,
            clamped,
            metadata=meta_store,
        )
        self._enqueue(job_id, priority)
        log.info("Queued job %s platform=%s format=%s", str(job_id)[:8], platform, clamped)
        return job_id, warning

    def shutdown(self):
        self._shutdown = True
        for _ in self.active_workers:
            self.download_queue.put((99, self._next_seq(), None))
        try:
            self.db.close()
        except Exception:
            pass

    def _process_queue(self):
        while not self._shutdown:
            with self.worker_lock:
                target_workers = self._target_workers()
                alive = [w for w in self.active_workers if w.is_alive()]
                self.active_workers = alive
                if len(alive) > target_workers:
                    break

            try:
                item = self.download_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                if len(item) == 3:
                    _priority, _seq, job_id = item
                else:
                    # legacy 2-tuple
                    _priority, job_id = item[0], item[1]

                if job_id is None:
                    self.download_queue.task_done()
                    break

                job = self.jobs.get(job_id)
                if not job:
                    self.download_queue.task_done()
                    continue

                if job["status"] in ("cancelled", "paused", "error", "finished"):
                    self.download_queue.task_done()
                    continue

                url = job["url"]
                job["status"] = "downloading"
                job["abort"] = None
                self.db.update_status(job_id, "downloading")

                if "on_start" in self.ui_callbacks:
                    self.ui_callbacks["on_start"](job_id)

                def abort_check():
                    return job.get("abort")

                def progress_hook(d):
                    reason = job.get("abort")
                    if reason in ("cancelled", "paused"):
                        raise DownloadAborted(reason)
                    if "on_progress" in self.ui_callbacks:
                        self.ui_callbacks["on_progress"](job_id, d)

                try:
                    format_str = job.get("format")
                    filepath = self.downloader.download_video(
                        url,
                        format_str=format_str,
                        progress_callback=progress_hook,
                        metadata=job.get("metadata"),
                        abort_check=abort_check,
                    )
                    # Re-check abort after return
                    if job.get("abort") == "cancelled":
                        job["status"] = "cancelled"
                        self.db.update_status(job_id, "cancelled")
                        if "on_error" in self.ui_callbacks:
                            self.ui_callbacks["on_error"](job_id, "Cancelled")
                    elif job.get("abort") == "paused" or job["status"] == "paused":
                        job["status"] = "paused"
                        self.db.update_status(job_id, "paused")
                        if "on_error" in self.ui_callbacks:
                            self.ui_callbacks["on_error"](job_id, "Paused")
                    else:
                        job["status"] = "finished"
                        job["filepath"] = filepath
                        self.db.update_status(job_id, "finished")
                        if filepath:
                            self.db.update_filepath(job_id, filepath)
                        if "on_finish" in self.ui_callbacks:
                            self.ui_callbacks["on_finish"](job_id, filepath)
                except DownloadAborted as e:
                    if e.reason == "paused" or job.get("abort") == "paused":
                        job["status"] = "paused"
                        self.db.update_status(job_id, "paused")
                        if "on_error" in self.ui_callbacks:
                            self.ui_callbacks["on_error"](job_id, "Paused")
                    else:
                        job["status"] = "cancelled"
                        self.db.update_status(job_id, "cancelled")
                        if "on_error" in self.ui_callbacks:
                            self.ui_callbacks["on_error"](job_id, "Cancelled")
                except Exception as e:
                    msg = str(e)
                    log.error("Job %s failed: %s", str(job_id)[:8], msg)
                    if "cancelled by user" in msg.lower():
                        job["status"] = "cancelled"
                        self.db.update_status(job_id, "cancelled")
                        if "on_error" in self.ui_callbacks:
                            self.ui_callbacks["on_error"](job_id, "Cancelled")
                    elif "paused by user" in msg.lower():
                        job["status"] = "paused"
                        self.db.update_status(job_id, "paused")
                        if "on_error" in self.ui_callbacks:
                            self.ui_callbacks["on_error"](job_id, "Paused")
                    else:
                        job["status"] = "error"
                        job["error"] = msg
                        self.db.update_status(job_id, "error", error=msg)
                        if "on_error" in self.ui_callbacks:
                            self.ui_callbacks["on_error"](job_id, msg)

                self.download_queue.task_done()
            except Exception as e:
                log.exception("Queue worker error: %s", e)
                try:
                    self.download_queue.task_done()
                except Exception:
                    pass
                time.sleep(0.5)

    def fetch_info_async(self, url, callback, status_callback=None):
        def _fetch():
            try:
                info = self.downloader.fetch_info(url, status_callback=status_callback)
                callback(True, info)
            except Exception as e:
                log.error("fetch_info failed: %s", e)
                callback(False, str(e))

        threading.Thread(target=_fetch, daemon=True).start()
