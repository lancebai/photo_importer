import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import exifread

def compute_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA256 hash of a file with streaming chunks."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()

def get_file_fallback_time(file_path: Path) -> datetime:
    """Get birthtime or mtime from filesystem."""
    stat = file_path.stat()
    try:
        ts = stat.st_birthtime
    except AttributeError:
        ts = stat.st_mtime
    return datetime.fromtimestamp(ts)

def parse_exif_date_string(date_str: str) -> Optional[datetime]:
    """Parse EXIF date string formatted like 'YYYY:MM:DD HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS'."""
    clean_str = str(date_str).strip()
    match = re.search(r"(\d{4})[:\-](\d{2})[:\-](\d{2})\s+(\d{2}):(\d{2}):(\d{2})", clean_str)
    if match:
        year, month, day, hour, minute, second = map(int, match.groups())
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass
    return None

def extract_capture_date(file_path: Path) -> datetime:
    """
    Extract the actual capture date from EXIF metadata.
    Falls back to file creation/modification time if EXIF is unavailable.
    """
    suffix = file_path.suffix.lower()
    
    # Try reading EXIF tags using exifread for supported image/RAW formats
    if suffix in [".cr2", ".crw", ".jpg", ".jpeg", ".tiff", ".tif", ".dng", ".nef", ".arw"]:
        try:
            with open(file_path, "rb") as f:
                tags = exifread.process_file(f, stop_tag="DateTimeOriginal", details=False)
                for tag_key in ["EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"]:
                    if tag_key in tags:
                        parsed = parse_exif_date_string(str(tags[tag_key]))
                        if parsed:
                            return parsed
        except Exception:
            pass

    # For CR3 or fallback files, try quick binary scan for EXIF or ISO box timestamp
    if suffix in [".cr3", ".mp4", ".mov"]:
        try:
            with open(file_path, "rb") as f:
                header_data = f.read(131072)  # First 128KB
                # Look for standard EXIF date format 'YYYY:MM:DD HH:MM:SS'
                matches = re.findall(rb"(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2})", header_data)
                for m in matches:
                    parsed = parse_exif_date_string(m.decode("ascii", errors="ignore"))
                    if parsed and 1990 <= parsed.year <= 2100:
                        return parsed
        except Exception:
            pass

    return get_file_fallback_time(file_path)

def extract_file_info(file_path: Path) -> Tuple[datetime, str, int]:
    """Returns (capture_date, sha256_hash, file_size_bytes)."""
    cap_date = extract_capture_date(file_path)
    file_hash = compute_sha256(file_path)
    file_size = file_path.stat().st_size
    return cap_date, file_hash, file_size
