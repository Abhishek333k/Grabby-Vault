"""SQLite job store with lightweight schema migration."""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from core.paths import db_path

SCHEMA_VERSION = 2


class DatabaseManager:
    def __init__(self, path: str | None = None):
        self.lock = threading.Lock()
        self.path = path or db_path()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.lock:
            with self.conn:
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        title TEXT,
                        platform TEXT,
                        status TEXT,
                        priority INTEGER,
                        format TEXT,
                        error TEXT,
                        filepath TEXT,
                        metadata_json TEXT,
                        created_at REAL,
                        updated_at REAL
                    )
                    """
                )
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                    """
                )
                self._migrate_locked()

    def _columns(self) -> set[str]:
        cur = self.conn.execute("PRAGMA table_info(jobs)")
        return {row[1] for row in cur.fetchall()}

    def _migrate_locked(self):
        cols = self._columns()
        alters = []
        if "filepath" not in cols:
            alters.append("ALTER TABLE jobs ADD COLUMN filepath TEXT")
        if "metadata_json" not in cols:
            alters.append("ALTER TABLE jobs ADD COLUMN metadata_json TEXT")
        if "created_at" not in cols:
            alters.append("ALTER TABLE jobs ADD COLUMN created_at REAL")
        if "updated_at" not in cols:
            alters.append("ALTER TABLE jobs ADD COLUMN updated_at REAL")
        for sql in alters:
            self.conn.execute(sql)
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
            (str(SCHEMA_VERSION),),
        )

    def add_job(
        self,
        job_id,
        url,
        title,
        platform,
        status,
        priority,
        format_str,
        metadata: dict | None = None,
        filepath: str | None = None,
    ):
        import time

        now = time.time()
        meta_s = json.dumps(metadata or {}, ensure_ascii=False, default=str)
        with self.lock:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO jobs
                    (id, url, title, platform, status, priority, format, error,
                     filepath, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?,
                            COALESCE((SELECT created_at FROM jobs WHERE id = ?), ?), ?)
                    """,
                    (
                        job_id,
                        url,
                        title,
                        platform,
                        status,
                        priority,
                        format_str,
                        filepath,
                        meta_s,
                        job_id,
                        now,
                        now,
                    ),
                )

    def update_status(self, job_id, status, error=None):
        import time

        with self.lock:
            with self.conn:
                self.conn.execute(
                    """
                    UPDATE jobs SET status = ?, error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, error, time.time(), job_id),
                )

    def update_filepath(self, job_id: str, filepath: str | None):
        import time

        with self.lock:
            with self.conn:
                self.conn.execute(
                    "UPDATE jobs SET filepath = ?, updated_at = ? WHERE id = ?",
                    (filepath, time.time(), job_id),
                )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            raw = d.get("metadata_json")
            if raw:
                try:
                    d["metadata"] = json.loads(raw)
                except json.JSONDecodeError:
                    d["metadata"] = {}
            else:
                d["metadata"] = {}
            return d

    def get_unfinished_jobs(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM jobs WHERE status NOT IN ('finished', 'cancelled')"
            )
            out = []
            for row in cursor.fetchall():
                d = dict(row)
                raw = d.get("metadata_json")
                if raw:
                    try:
                        d["metadata"] = json.loads(raw)
                    except json.JSONDecodeError:
                        d["metadata"] = {}
                else:
                    d["metadata"] = {}
                out.append(d)
            return out

    def delete_job(self, job_id):
        with self.lock:
            with self.conn:
                self.conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def close(self):
        with self.lock:
            try:
                self.conn.close()
            except Exception:
                pass
