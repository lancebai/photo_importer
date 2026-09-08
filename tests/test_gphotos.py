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
