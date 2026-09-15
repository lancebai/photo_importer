import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT UNIQUE NOT NULL,
                    original_filename TEXT NOT NULL,
                    source_path TEXT,
                    local_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    capture_time TEXT,
                    imported_at TEXT NOT NULL,
                    upload_status TEXT NOT NULL DEFAULT 'PENDING',
                    google_photo_id TEXT,
                    google_account TEXT DEFAULT 'default',
                    volume_name TEXT,
                    uploaded_at TEXT,
                    error_message TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON media_files(file_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_upload_status ON media_files(upload_status)")
            
            # Auto-migrate columns if missing in existing database
            cursor.execute("PRAGMA table_info(media_files)")
            existing_columns = {row["name"] for row in cursor.fetchall()}
            if "google_account" not in existing_columns:
                cursor.execute("ALTER TABLE media_files ADD COLUMN google_account TEXT DEFAULT 'default'")
            if "volume_name" not in existing_columns:
                cursor.execute("ALTER TABLE media_files ADD COLUMN volume_name TEXT")

            conn.commit()

    def has_file_hash(self, file_hash: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM media_files WHERE file_hash = ?", (file_hash,))
            return cursor.fetchone() is not None

    def get_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM media_files WHERE file_hash = ?", (file_hash,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_imported_file(
        self,
        file_hash: str,
        original_filename: str,
        source_path: str,
        local_path: str,
        file_size: int,
        capture_time: Optional[datetime],
        upload_status: str = "PENDING",
        google_account: str = "default",
        volume_name: Optional[str] = None
    ) -> int:
        imported_at = datetime.now().isoformat()
        cap_str = capture_time.isoformat() if capture_time else None
        
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO media_files (
                        file_hash, original_filename, source_path, local_path,
                        file_size, capture_time, imported_at, upload_status,
                        google_account, volume_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_hash) DO UPDATE SET
                        local_path = excluded.local_path,
                        original_filename = excluded.original_filename,
                        google_account = excluded.google_account,
                        volume_name = excluded.volume_name
                """, (file_hash, original_filename, source_path, local_path, file_size, cap_str, imported_at, upload_status, google_account, volume_name))
                conn.commit()
                return cursor.lastrowid or 0

    def get_pending_uploads(self, google_account: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM media_files WHERE upload_status IN ('PENDING', 'FAILED')"
                params = []
                if google_account:
                    query += " AND google_account = ?"
                    params.append(google_account)
                query += " ORDER BY COALESCE(capture_time, imported_at) ASC, id ASC"
                if limit:
                    query += f" LIMIT {int(limit)}"
                cursor.execute(query, tuple(params))
                return [dict(row) for row in cursor.fetchall()]

    def mark_uploading(self, file_id: int) -> None:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE media_files SET upload_status = 'UPLOADING' WHERE id = ?", (file_id,))
                conn.commit()

    def mark_uploaded(self, file_id: int, google_photo_id: str) -> None:
        now_str = datetime.now().isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE media_files 
                    SET upload_status = 'UPLOADED', 
                        google_photo_id = ?, 
                        uploaded_at = ?, 
                        error_message = NULL 
                    WHERE id = ?
                """, (google_photo_id, now_str, file_id))
                conn.commit()

    def mark_upload_failed(self, file_id: int, error_message: str) -> None:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE media_files 
                    SET upload_status = 'FAILED', 
                        error_message = ? 
                    WHERE id = ?
                """, (error_message, file_id))
                conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM media_files")
            total_count, total_bytes = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM media_files WHERE upload_status = 'UPLOADED'")
            uploaded_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM media_files WHERE upload_status IN ('PENDING', 'UPLOADING')")
            pending_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM media_files WHERE upload_status = 'FAILED'")
            failed_count = cursor.fetchone()[0]

            # Breakdown by volume and account
            cursor.execute("SELECT DISTINCT google_account FROM media_files")
            accounts = [r[0] for r in cursor.fetchall() if r[0]]

            return {
                "total_files": total_count,
                "total_size_mb": round(total_bytes / (1024 * 1024), 2),
                "uploaded_count": uploaded_count,
                "pending_count": pending_count,
                "failed_count": failed_count,
                "accounts": accounts
            }
