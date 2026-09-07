from datetime import datetime
from src.metadata import compute_sha256, parse_exif_date_string, extract_file_info

def test_parse_exif_date_string():
    res = parse_exif_date_string("2026:09:07 15:45:30")
    assert res == datetime(2026, 9, 7, 15, 45, 30)

    res2 = parse_exif_date_string("2026-09-07 15:45:30")
    assert res2 == datetime(2026, 9, 7, 15, 45, 30)

    assert parse_exif_date_string("invalid-date") is None

def test_file_info_and_sha256(tmp_path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"HELLO_PHOTO_IMPORTER_DATA_STREAM")

    cap_date, sha, size = extract_file_info(dummy_file)
    assert size == len(b"HELLO_PHOTO_IMPORTER_DATA_STREAM")
    assert isinstance(sha, str)
    assert len(sha) == 64
    assert isinstance(cap_date, datetime)
