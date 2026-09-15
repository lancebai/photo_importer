from unittest.mock import MagicMock, patch
from pathlib import Path
from src.config import Config, GoogleAccountConfig
from src.db import Database
from src.gphotos_uploader import upload_pending_photos

def test_upload_pending_photos_mocked(tmp_path):
    db = Database(tmp_path / "test.db")
    dummy_photo = tmp_path / "IMG_1234.CR3"
    dummy_photo.write_bytes(b"dummy canon raw 1234")

    file_id = db.add_imported_file(
        file_hash="hash999",
        original_filename="IMG_1234.CR3",
        source_path=str(dummy_photo),
        local_path=str(dummy_photo),
        file_size=len(b"dummy canon raw 1234"),
        capture_time=None,
        google_account="work"
    )

    cfg = Config(
        google_accounts={
            "work": GoogleAccountConfig(
                credentials_path=str(tmp_path / "work_creds.json"),
                token_path=str(tmp_path / "work_token.json")
            )
        },
        db_path=str(tmp_path / "test.db")
    )

    mock_creds = MagicMock()
    mock_creds.valid = True

    with patch("src.gphotos_uploader.get_credentials", return_value=mock_creds), \
         patch("src.gphotos_uploader.upload_file_bytes", return_value="dummy_upload_token_abc"), \
         patch("src.gphotos_uploader.batch_create_media_items", return_value=[
             {"status": {"message": "Success"}, "mediaItem": {"id": "gphotos_item_123"}}
         ]), \
         patch("src.gphotos_uploader.send_notification"):

        res = upload_pending_photos(cfg, db, google_account="work", interactive=False, notify=True)
        assert res["uploaded"] == 1
        assert res["failed"] == 0

        # DB status should now be UPLOADED
        record = db.get_by_hash("hash999")
        assert record["upload_status"] == "UPLOADED"
        assert record["google_photo_id"] == "gphotos_item_123"

def test_concurrent_multithreaded_uploads(tmp_path):
    db = Database(tmp_path / "test_concurrent.db")
    
    # Create 5 dummy photos
    for i in range(1, 6):
        p = tmp_path / f"IMG_{i:04d}.CR3"
        p.write_bytes(f"raw data content {i}".encode())
        db.add_imported_file(
            file_hash=f"hash_{i}",
            original_filename=p.name,
            source_path=str(p),
            local_path=str(p),
            file_size=len(f"raw data content {i}"),
            capture_time=None,
            google_account="default"
        )

    cfg = Config(
        google_accounts={
            "default": GoogleAccountConfig(
                credentials_path=str(tmp_path / "creds.json"),
                token_path=str(tmp_path / "token.json")
            )
        },
        db_path=str(tmp_path / "test_concurrent.db")
    )

    mock_creds = MagicMock()
    mock_creds.valid = True

    with patch("src.gphotos_uploader.get_credentials", return_value=mock_creds), \
         patch("src.gphotos_uploader.upload_file_bytes", side_effect=lambda path, creds: f"tok_{path.stem}"), \
         patch("src.gphotos_uploader.batch_create_media_items", side_effect=lambda items, creds, album_id=None: [
             {"status": {"message": "Success"}, "mediaItem": {"id": f"g_id_{fn}"}} for _, _, fn in items
         ]), \
         patch("src.gphotos_uploader.send_notification"):

        res = upload_pending_photos(cfg, db, google_account="default", max_workers=4, interactive=False, notify=True)
        assert res["uploaded"] == 5
        assert res["failed"] == 0

        # Verify all 5 are marked UPLOADED
        for i in range(1, 6):
            rec = db.get_by_hash(f"hash_{i}")
            assert rec["upload_status"] == "UPLOADED"
            assert rec["google_photo_id"] == f"g_id_IMG_{i:04d}.CR3"
