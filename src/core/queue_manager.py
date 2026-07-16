import queue
import threading
import time
from core.downloader import Downloader
from core.database import DatabaseManager
from core.config_manager import ConfigManager

class QueueManager:
    def __init__(self, ui_callbacks=None):
        self.db = DatabaseManager()
        self.download_queue = queue.PriorityQueue()
        self.jobs = {}  # Store job metadata and status
        self.downloader = Downloader()
        self.ui_callbacks = ui_callbacks or {}
        # ui_callbacks dict can optionally contain: on_start, on_progress, on_finish, on_error
        
        # Load persistent jobs
        unfinished = self.db.get_unfinished_jobs()
        for j in unfinished:
            job_id = j['id']
            # Put job dict in self.jobs
            # Metadata is lost on restart currently, we might need a dummy metadata
            # For UI, it'll need to reconstruct cards. We'll handle this from main_window via a getter
            self.jobs[job_id] = {
                'url': j['url'],
                'metadata': {'id': job_id, 'title': j['title']},
                'status': j['status'],
                'priority': j['priority'],
                'format': j['format'],
                'platform': j['platform']
            }
            # Re-queue if it was paused or queued or error etc
            if j['status'] == 'queued':
                self.download_queue.put((j['priority'], job_id))
            elif j['status'] in ('downloading', 'error'):
                # Automatically reset 'downloading' back to queued on restart
                self.jobs[job_id]['status'] = 'queued'
                self.db.update_status(job_id, 'queued')
                self.db.update_status(job_id, 'queued')
                self.download_queue.put((j['priority'], job_id))

        self.config = ConfigManager()
        self.active_workers = []
        self.worker_lock = threading.Lock()
        self._adjust_workers()

    def _adjust_workers(self):
        with self.worker_lock:
            target_workers = self.config.get("max_concurrent_downloads", 2)
            # Remove dead workers from list
            self.active_workers = [w for w in self.active_workers if w.is_alive()]
            current_workers = len(self.active_workers)
            
            if current_workers < target_workers:
                for _ in range(target_workers - current_workers):
                    t = threading.Thread(target=self._process_queue, daemon=True)
                    t.start()
                    self.active_workers.append(t)
            # If target_workers < current_workers, we could send poison pills, 
            # but for simplicity we let them naturally die in _process_queue.

    def apply_settings_change(self):
        """Called when settings are updated to adjust worker count."""
        self._adjust_workers()

    def cancel_job(self, job_id):
        """Cancel a job by ID."""
        job = self.jobs.get(job_id)
        if job:
            job['status'] = 'cancelled'
            self.db.update_status(job_id, 'cancelled')

    def pause_job(self, job_id):
        """Pause a job by ID."""
        job = self.jobs.get(job_id)
        if job:
            job['status'] = 'paused'
            self.db.update_status(job_id, 'paused')

    def resume_job(self, job_id):
        job = self.jobs.get(job_id)
        if job and job['status'] == 'paused':
            job['status'] = 'queued'
            self.db.update_status(job_id, 'queued')
            self.download_queue.put((job.get('priority', 1), job_id))

    def delete_job(self, job_id):
        """Completely remove a job from queue and database."""
        # Cancel first if running
        self.cancel_job(job_id)
        if job_id in self.jobs:
            del self.jobs[job_id]
        self.db.delete_job(job_id)

    def add_job(self, url, metadata, priority=1, format_str=None, platform="Unknown"):
        """
        Add a URL to the download queue.
        metadata should contain at least an 'id' to track it in UI.
        priority: 0=High, 1=Normal, 2=Low
        """
        job_id = metadata.get('id', url)
        title = metadata.get('title', 'Unknown')
        self.jobs[job_id] = {
            'url': url,
            'metadata': metadata,
            'status': 'queued',
            'priority': priority,
            'format': format_str,
            'platform': platform
        }
        self.db.add_job(job_id, url, title, platform, 'queued', priority, format_str)
        self.download_queue.put((priority, job_id))
        return job_id
        
    def _process_queue(self):
        while True:
            with self.worker_lock:
                target_workers = self.config.get("max_concurrent_downloads", 2)
                if len([w for w in self.active_workers if w.is_alive()]) > target_workers:
                    break # Kill this thread to reduce concurrency

            try:
                priority, job_id = self.download_queue.get()
                if job_id is None:
                    break
                    
                job = self.jobs.get(job_id)
                if not job:
                    self.download_queue.task_done()
                    continue
                    
                if job['status'] == 'cancelled' or job['status'] == 'paused':
                    self.download_queue.task_done()
                    continue

                url = job['url']
                job['status'] = 'downloading'
                self.db.update_status(job_id, 'downloading')
                
                if 'on_start' in self.ui_callbacks:
                    self.ui_callbacks['on_start'](job_id)
                
                # Progress hook for yt-dlp
                def progress_hook(d):
                    if job['status'] == 'cancelled':
                        raise Exception("Download cancelled by user")
                    if job['status'] == 'paused':
                        raise Exception("Download paused by user")
                    if 'on_progress' in self.ui_callbacks:
                        self.ui_callbacks['on_progress'](job_id, d)
                
                try:
                    format_str = job.get('format')
                    self.downloader.download_video(url, format_str=format_str, progress_callback=progress_hook, metadata=job.get('metadata'))
                    job['status'] = 'finished'
                    self.db.update_status(job_id, 'finished')
                    if 'on_finish' in self.ui_callbacks:
                        self.ui_callbacks['on_finish'](job_id)
                except Exception as e:
                    if str(e) == "Download cancelled by user":
                        self.db.update_status(job_id, 'cancelled')
                        if 'on_error' in self.ui_callbacks:
                            self.ui_callbacks['on_error'](job_id, "Cancelled")
                    elif str(e) == "Download paused by user":
                        self.db.update_status(job_id, 'paused')
                        if 'on_error' in self.ui_callbacks:
                            self.ui_callbacks['on_error'](job_id, "Paused")
                    else:
                        job['status'] = 'error'
                        job['error'] = str(e)
                        self.db.update_status(job_id, 'error', error=str(e))
                        if 'on_error' in self.ui_callbacks:
                            self.ui_callbacks['on_error'](job_id, str(e))
                
                self.download_queue.task_done()
            except Exception as e:
                print(f"Queue worker error: {e}")
                time.sleep(1)

    def fetch_info_async(self, url, callback, status_callback=None):
        """
        Fetches info asynchronously to avoid freezing the UI.
        callback(success: bool, data: dict or string)
        """
        def _fetch():
            try:
                info = self.downloader.fetch_info(url, status_callback=status_callback)
                callback(True, info)
            except Exception as e:
                callback(False, str(e))
                
        threading.Thread(target=_fetch, daemon=True).start()
