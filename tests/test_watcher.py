from unittest.mock import patch, MagicMock
from pathlib import Path
from src.config import Config, VolumeConfig, UploadConfig
from src.db import Database
from src.watcher import check_and_process_volumes

def test_check_and_process_volumes_whitelist(tmp_path):
    cfg = Config(
        volumes={
            "EOS_DIGITAL": VolumeConfig(
                upload=UploadConfig(enabled=True, google_account="default")
            )
        },
        db_path=str(tmp_path / "test.db")
    )
    db = Database(tmp_path / "test.db")
    active_volumes = set()

    mock_eos = Path("/Volumes/EOS_DIGITAL")
    mock_other = Path("/Volumes/USB_STICK")

    with patch("src.watcher.find_available_volumes", return_value=[
        (mock_eos, True),
        (mock_other, False)
    ]), \
    patch("src.watcher.is_sd_card_volume", side_effect=lambda p: p.name == "EOS_DIGITAL"), \
    patch("src.watcher.process_volume") as mock_process:

        check_and_process_volumes(cfg, db, active_volumes)

        # Should process EOS_DIGITAL only
        assert mock_process.call_count == 1
        mock_process.assert_called_once_with(mock_eos, cfg, db)
        assert mock_eos in active_volumes
        assert mock_other in active_volumes
