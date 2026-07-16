import sqlite3
import os
import threading

DB_PATH = "queue.db"

class DatabaseManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.lock:
            with self.conn:
                self.conn.execute('''
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        title TEXT,
                        platform TEXT,
                        status TEXT,
                        priority INTEGER,
                        format TEXT,
                        error TEXT
                    )
                ''')

    def add_job(self, job_id, url, title, platform, status, priority, format_str):
        with self.lock:
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO jobs (id, url, title, platform, status, priority, format, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                ''', (job_id, url, title, platform, status, priority, format_str))

    def update_status(self, job_id, status, error=None):
        with self.lock:
            with self.conn:
                self.conn.execute('UPDATE jobs SET status = ?, error = ? WHERE id = ?', (status, error, job_id))

    def get_unfinished_jobs(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE status NOT IN ('finished', 'cancelled')")
            return [dict(row) for row in cursor.fetchall()]

    def delete_job(self, job_id):
        with self.lock:
            with self.conn:
                self.conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))

    def close(self):
        with self.lock:
            self.conn.close()
