from datetime import datetime
from pathlib import Path
from src.config import Config
from src.db import Database
from src.importer import import_photos, scan_directory_for_media, get_unique_destination_path

def test_scan_directory(tmp_path):
    (tmp_path / "IMG_0001.CR3").write_bytes(b"raw data 1")
    (tmp_path / "IMG_0002.JPG").write_bytes(b"jpg data 2")
    (tmp_path / "notes.txt").write_text("ignore me")
    (tmp_path / ".hidden.CR2").write_bytes(b"ignore hidden")

    found = scan_directory_for_media(tmp_path, [".cr3", ".jpg", ".cr2"])
    names = [f.name for f in found]
    assert "IMG_0001.CR3" in names
    assert "IMG_0002.JPG" in names
    assert "notes.txt" not in names
    assert ".hidden.CR2" not in names

def test_import_and_collision_handling(tmp_path):
    src_dir = tmp_path / "sd_card"
    src_dir.mkdir()
    dest_dir = tmp_path / "photos"
    dest_dir.mkdir()

    file1 = src_dir / "IMG_0001.CR3"
    file1.write_bytes(b"canon raw content 1")
    file2 = src_dir / "IMG_0002.CR2"
    file2.write_bytes(b"canon raw content 2")

    cfg = Config(
        dest_base_dir=str(dest_dir),
        monitored_volumes=["sd_card"],
        auto_upload_to_gphotos=False,
        use_move=False
    )
    db = Database(tmp_path / "test.db")

    # First import
    res1 = import_photos(src_dir, cfg, db, notify=False)
    assert res1.imported_count == 2
    assert res1.skipped_count == 0

    # Second import of same SD card should skip already imported files
    res2 = import_photos(src_dir, cfg, db, notify=False)
    assert res2.imported_count == 0
    assert res2.skipped_count == 2
