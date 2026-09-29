import time
from pathlib import Path
from typing import Set

from .config import Config, VolumeConfig
from .db import Database
from .importer import find_available_volumes, import_photos
from .gphotos_uploader import upload_pending_photos

def process_volume(volume_path: Path, config: Config, db: Database) -> None:
    """Process a detected volume: import photos and optionally upload to Google Photos."""
    vol_name = volume_path.name
    vol_cfg: VolumeConfig = config.get_resolved_volume_config(vol_name)

    print(f"\n==========================================")
    print(f"📷 Processing SD Card / Volume: {volume_path}")
    print(f"📁 Target Base Dir: {vol_cfg.dest_base_dir or config.defaults.dest_base_dir}")
    print(f"☁️ Upload Config: Enabled={vol_cfg.upload.enabled}, Account={vol_cfg.upload.google_account}, Album={vol_cfg.upload.album or '(None)'}")
    print(f"==========================================")

    # 1. Run local import
    import_result = import_photos(
        source_dir=volume_path,
        config=config,
        db=db,
        volume_name=vol_name,
        progress_callback=lambda curr, total, name: print(f"[{curr}/{total}] Importing {name}..."),
        notify=True
    )

    print(f"Import Summary: {import_result.imported_count} imported, {import_result.skipped_count} skipped, {import_result.failed_count} failed.")

    # 2. Trigger Google Photos upload if configured for this volume
    if vol_cfg.upload and vol_cfg.upload.enabled and import_result.imported_count > 0:
        target_account = vol_cfg.upload.google_account
        print(f"\n☁️ Triggering Google Photos upload via account '{target_account}'...")
        upload_result = upload_pending_photos(
            config=config,
            db=db,
            google_account=target_account,
            interactive=False,  # Non-interactive in background watcher
            notify=True
        )
        print(f"Upload Summary: {upload_result['uploaded']} uploaded, {upload_result['failed']} failed.")
    elif not vol_cfg.upload or not vol_cfg.upload.enabled:
        print("ℹ️  Google Photos upload is disabled for this volume. Finished.")

def check_and_process_volumes(config: Config, db: Database, active_volumes: Set[Path]) -> None:
    """Check /Volumes once and process any new matching SD cards."""
    available = find_available_volumes(config.monitored_volumes)
    current_mounts = {vol for vol, _ in available}

    # Find newly mounted volumes
    new_mounts = current_mounts - active_volumes
    for vol in new_mounts:
        # Check if matched in config whitelist
        is_whitelisted = vol.name in config.monitored_volumes

        if is_whitelisted:
            print(f"🎯 Detected monitored volume: '{vol.name}'")
            process_volume(vol, config, db)
        else:
            print(f"ℹ️  Ignoring non-monitored volume: '{vol.name}'")

    # Update active tracking set
    active_volumes.clear()
    active_volumes.update(current_mounts)

def run_watcher(config: Config, db: Database, poll_interval: int = 3) -> None:
    """Continuous polling watcher for SD card insertions."""
    print("==================================================")
    print("👀 Photo Importer Matrix Watcher Service Active")
    print(f"📁 Monitored Volumes Matrix: {list(config.volumes.keys())}")
    for name, v in config.volumes.items():
        print(f"   • {name}: Dest={v.dest_base_dir or config.defaults.dest_base_dir} | Upload={v.upload.enabled} (Account: {v.upload.google_account})")
    print("Waiting for SD card insertion... (Press Ctrl+C to stop)")
    print("==================================================")

    active_volumes: Set[Path] = set()
    
    # Initialize with already connected volumes to avoid double-processing on startup
    for vol, is_matched in find_available_volumes(config.monitored_volumes):
        active_volumes.add(vol)

    try:
        while True:
            time.sleep(poll_interval)
            check_and_process_volumes(config, db, active_volumes)
    except KeyboardInterrupt:
        print("\nWatcher service stopped.")
