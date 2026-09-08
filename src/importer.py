import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .config import Config, VolumeConfig
from .db import Database
from .metadata import compute_sha256, extract_file_info
from .notifications import send_notification

@dataclass
class ImportResult:
    imported_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    total_bytes: int = 0
    imported_files: List[dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

def is_sd_card_volume(volume_path: Path) -> bool:
    """Check if a volume is removable media on macOS."""
    try:
        result = subprocess.run(["diskutil", "info", str(volume_path)], capture_output=True, text=True, check=True)
        return "Removable Media:           Removable" in result.stdout
    except Exception:
        return False

def find_available_volumes(monitored_names: Optional[List[str]] = None) -> List[Tuple[Path, bool]]:
    """
    Find all volumes under /Volumes.
    Returns list of (volume_path, is_whitelisted).
    """
    volumes_dir = Path("/Volumes")
    if not volumes_dir.exists():
        return []

    system_vols = {"Macintosh HD", "Macintosh HD - Data", "Recovery", "VM"}
    results = []
    
    names_set = set(monitored_names or [])

    for vol in volumes_dir.iterdir():
        if not vol.is_dir() or vol.name in system_vols:
            continue
        
        is_matched = vol.name in names_set or is_sd_card_volume(vol)
        results.append((vol, is_matched))

    return results

def scan_directory_for_media(source_dir: Path, extensions: List[str]) -> List[Path]:
    """Recursively search for supported media files ignoring hidden and system files."""
    ext_set = {e.lower() for e in extensions}
    media_files = []

    for root, _, files in os.walk(source_dir):
        for fname in files:
            if fname.startswith("."):
                continue
            fpath = Path(root) / fname
            if fpath.suffix.lower() in ext_set:
                media_files.append(fpath)

    return sorted(media_files)

def get_unique_destination_path(target_dir: Path, original_filename: str, source_hash: str) -> Tuple[Path, bool]:
    """
    Find safe destination path. If destination file exists with the SAME hash, returns (path, True) for skipping.
    If different file with same name exists, increments counter (e.g. IMG_0001_1.CR3).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / original_filename

    if not target_file.exists():
        return target_file, False

    # Check if existing file is identical
    if compute_sha256(target_file) == source_hash:
        return target_file, True

    # Collision with different content -> generate unique name
    stem = Path(original_filename).stem
    suffix = Path(original_filename).suffix
    counter = 1
    while True:
        candidate = target_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate, False
        if compute_sha256(candidate) == source_hash:
            return candidate, True
        counter += 1

def import_photos(
    source_dir: Path,
    config: Config,
    db: Database,
    volume_name: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    notify: bool = True
) -> ImportResult:
    """
    Import photos from source directory into organized local destination directory.
    """
    source_path = Path(source_dir).expanduser().resolve()
    v_name = volume_name or source_path.name
    vol_cfg: VolumeConfig = config.get_resolved_volume_config(v_name)

    dest_base_path = Path(vol_cfg.dest_base_dir or config.defaults.dest_base_dir).expanduser()
    result = ImportResult()

    if not source_path.exists() or not source_path.is_dir():
        err = f"Source directory '{source_path}' does not exist or is not a directory."
        result.errors.append(err)
        return result

    media_files = scan_directory_for_media(source_path, vol_cfg.supported_extensions or config.defaults.supported_extensions)
    total_files = len(media_files)

    if total_files == 0:
        return result

    if notify:
        send_notification(
            title="📷 Photo Importer",
            subtitle=f"Found {total_files} media files on {v_name}",
            message=f"Starting import to {dest_base_path}..."
        )

    for idx, file_path in enumerate(media_files, start=1):
        try:
            if progress_callback:
                progress_callback(idx, total_files, file_path.name)

            # Extract EXIF capture date and SHA256
            capture_date, file_hash, file_size = extract_file_info(file_path)

            # Check if file is already tracked in DB with identical hash and exists locally
            existing_record = db.get_by_hash(file_hash)
            if existing_record and Path(existing_record["local_path"]).exists():
                result.skipped_count += 1
                continue

            # Determine date folder based on volume config format
            date_folder_name = capture_date.strftime(vol_cfg.folder_structure or config.defaults.folder_structure)
            target_dir = dest_base_path / date_folder_name
            target_file_path, is_identical = get_unique_destination_path(target_dir, file_path.name, file_hash)

            if not is_identical:
                # Copy file safely
                shutil.copy2(str(file_path), str(target_file_path))

                # Verify SHA256 integrity
                dest_hash = compute_sha256(target_file_path)
                if dest_hash != file_hash:
                    target_file_path.unlink(missing_ok=True)
                    raise IOError(f"Checksum mismatch on copy for {file_path.name}")

                # Optional delete from source if move mode or delete_after_import is enabled
                if vol_cfg.use_move or vol_cfg.delete_after_import:
                    file_path.unlink(missing_ok=True)

            # Record in SQLite database with volume and assigned Google account
            g_account = vol_cfg.upload.google_account if (vol_cfg.upload and vol_cfg.upload.enabled) else "none"
            upload_status = "PENDING" if (vol_cfg.upload and vol_cfg.upload.enabled) else "SKIPPED"

            db_id = db.add_imported_file(
                file_hash=file_hash,
                original_filename=file_path.name,
                source_path=str(file_path),
                local_path=str(target_file_path),
                file_size=file_size,
                capture_time=capture_date,
                upload_status=upload_status,
                google_account=g_account,
                volume_name=v_name
            )

            result.imported_count += 1
            result.total_bytes += file_size
            result.imported_files.append({
                "id": db_id,
                "filename": file_path.name,
                "local_path": str(target_file_path),
                "hash": file_hash,
                "size": file_size,
                "capture_time": capture_date.isoformat(),
                "volume_name": v_name,
                "google_account": g_account
            })

        except Exception as e:
            err_msg = f"Failed to import {file_path.name}: {e}"
            result.failed_count += 1
            result.errors.append(err_msg)
            print(f"Error: {err_msg}")

    if notify and result.imported_count > 0:
        size_mb = round(result.total_bytes / (1024 * 1024), 1)
        send_notification(
            title="✅ Photo Import Complete",
            subtitle=f"{result.imported_count} files ({size_mb} MB) imported from {v_name}",
            message=f"Saved to {dest_base_path}"
        )

    return result
