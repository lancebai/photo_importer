from datetime import datetime
from src.db import Database

def test_db_crud_and_status(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)

    now = datetime(2026, 9, 7, 14, 30, 0)
    
    # Check hash not exists
    assert db.has_file_hash("hash123") is False

    # Insert file
    file_id = db.add_imported_file(
        file_hash="hash123",
        original_filename="IMG_0001.CR3",
        source_path="/Volumes/SD/IMG_0001.CR3",
        local_path="/photos/2026-09-07/IMG_0001.CR3",
        file_size=35000000,
        capture_time=now
    )
    assert file_id > 0
    assert db.has_file_hash("hash123") is True

    # Pending uploads
    pending = db.get_pending_uploads()
    assert len(pending) == 1
    assert pending[0]["file_hash"] == "hash123"
    assert pending[0]["upload_status"] == "PENDING"

    # Mark uploading
    db.mark_uploading(file_id)
    rec = db.get_by_hash("hash123")
    assert rec["upload_status"] == "UPLOADING"

    # Mark uploaded
    db.mark_uploaded(file_id, "gphotos_item_abc987")
    rec = db.get_by_hash("hash123")
    assert rec["upload_status"] == "UPLOADED"
    assert rec["google_photo_id"] == "gphotos_item_abc987"

    # Stats
    stats = db.get_stats()
    assert stats["total_files"] == 1
    assert stats["uploaded_count"] == 1
    assert stats["pending_count"] == 0
    assert stats["failed_count"] == 0
