import queue
import threading
import time

from core.config_manager import ConfigManager
from core.database import DatabaseManager
from core.downloader import Downloader
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

        unfinished = self.db.get_unfinished_jobs()
        for j in unfinished:
            job_id = j["id"]
            self.jobs[job_id] = {
                "url": j["url"],
                "metadata": {"id": job_id, "title": j["title"]},
                "status": j["status"],
                "priority": j["priority"],
                "format": j["format"],
                "platform": j["platform"],
            }
            if j["status"] == "queued":
                self.download_queue.put((j["priority"], job_id))
            elif j["status"] in ("downloading", "error"):
                self.jobs[job_id]["status"] = "queued"
                self.db.update_status(job_id, "queued")
                self.download_queue.put((j["priority"], job_id))

        self.active_workers = []
        self.worker_lock = threading.Lock()
        self._adjust_workers()

    def _target_workers(self) -> int:
        # License caps free tier; settings further cap Pro
        lic_max = self.license.max_concurrent()
        cfg = int(self.config.get("max_concurrent_downloads", lic_max) or lic_max)
        return max(1, min(cfg, lic_max))

    def _adjust_workers(self):
        with self.worker_lock:
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
            self.db.update_status(job_id, "cancelled")

    def pause_job(self, job_id):
        job = self.jobs.get(job_id)
        if job:
            job["status"] = "paused"
            self.db.update_status(job_id, "paused")

    def resume_job(self, job_id):
        job = self.jobs.get(job_id)
        if job and job["status"] == "paused":
            job["status"] = "queued"
            self.db.update_status(job_id, "queued")
            self.download_queue.put((job.get("priority", 1), job_id))

    def delete_job(self, job_id):
        self.cancel_job(job_id)
        if job_id in self.jobs:
            del self.jobs[job_id]
        self.db.delete_job(job_id)

    def add_job(self, url, metadata, priority=1, format_str=None, platform="Unknown"):
        """
        Add a URL to the download queue.
        Enforces Free/Pro quality limits.
        Returns (job_id, warning_or_None)
        """
        clamped, warning = self.license.clamp_format(format_str)
        job_id = metadata.get("id", url)
        title = metadata.get("title", "Unknown")
        self.jobs[job_id] = {
            "url": url,
            "metadata": metadata,
            "status": "queued",
            "priority": priority,
            "format": clamped,
            "platform": platform,
        }
        self.db.add_job(job_id, url, title, platform, "queued", priority, clamped)
        self.download_queue.put((priority, job_id))
        log.info("Queued job %s platform=%s format=%s", job_id[:8], platform, clamped)
        return job_id, warning

    def _process_queue(self):
        while True:
            with self.worker_lock:
                target_workers = self._target_workers()
                if len([w for w in self.active_workers if w.is_alive()]) > target_workers:
                    break

            try:
                priority, job_id = self.download_queue.get()
                if job_id is None:
                    break

                job = self.jobs.get(job_id)
                if not job:
                    self.download_queue.task_done()
                    continue

                if job["status"] in ("cancelled", "paused"):
                    self.download_queue.task_done()
                    continue

                url = job["url"]
                job["status"] = "downloading"
                self.db.update_status(job_id, "downloading")

                if "on_start" in self.ui_callbacks:
                    self.ui_callbacks["on_start"](job_id)

                def progress_hook(d):
                    if job["status"] == "cancelled":
                        raise Exception("Download cancelled by user")
                    if job["status"] == "paused":
                        raise Exception("Download paused by user")
                    if "on_progress" in self.ui_callbacks:
                        self.ui_callbacks["on_progress"](job_id, d)

                try:
                    format_str = job.get("format")
                    self.downloader.download_video(
                        url,
                        format_str=format_str,
                        progress_callback=progress_hook,
                        metadata=job.get("metadata"),
                    )
                    job["status"] = "finished"
                    self.db.update_status(job_id, "finished")
                    if "on_finish" in self.ui_callbacks:
                        self.ui_callbacks["on_finish"](job_id)
                except Exception as e:
                    msg = str(e)
                    log.error("Job %s failed: %s", job_id[:8], msg)
                    if msg == "Download cancelled by user":
                        self.db.update_status(job_id, "cancelled")
                        if "on_error" in self.ui_callbacks:
                            self.ui_callbacks["on_error"](job_id, "Cancelled")
                    elif msg == "Download paused by user":
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
                time.sleep(1)

    def fetch_info_async(self, url, callback, status_callback=None):
        def _fetch():
            try:
                info = self.downloader.fetch_info(url, status_callback=status_callback)
                callback(True, info)
            except Exception as e:
                log.error("fetch_info failed: %s", e)
                callback(False, str(e))

        threading.Thread(target=_fetch, daemon=True).start()
