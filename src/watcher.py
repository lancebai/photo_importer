import time
from pathlib import Path
from typing import Set

from .config import Config
from .db import Database
from .importer import find_available_volumes, import_photos, is_sd_card_volume
from .gphotos_uploader import upload_pending_photos

def process_volume(volume_path: Path, config: Config, db: Database) -> None:
    """Process a detected volume: import photos and optionally upload to Google Photos."""
    print(f"\n==========================================")
    print(f"📷 Processing SD Card / Volume: {volume_path}")
    print(f"==========================================")

    # 1. Run local import
    import_result = import_photos(
        source_dir=volume_path,
        config=config,
        db=db,
        progress_callback=lambda curr, total, name: print(f"[{curr}/{total}] Importing {name}..."),
        notify=True
    )

    print(f"Import Summary: {import_result.imported_count} imported, {import_result.skipped_count} skipped, {import_result.failed_count} failed.")

    # 2. Trigger Google Photos upload if configured
    if config.auto_upload_to_gphotos and import_result.imported_count > 0:
        print("\n☁️ Starting Google Photos upload...")
        upload_result = upload_pending_photos(
            config=config,
            db=db,
            interactive=False,  # Non-interactive in background watcher
            notify=True
        )
        print(f"Upload Summary: {upload_result['uploaded']} uploaded, {upload_result['failed']} failed.")

def check_and_process_volumes(config: Config, db: Database, active_volumes: Set[Path]) -> None:
    """Check /Volumes once and process any new matching SD cards."""
    available = find_available_volumes(config.monitored_volumes)
    current_mounts = {vol for vol, _ in available}

    # Find newly mounted volumes
    new_mounts = current_mounts - active_volumes
    for vol in new_mounts:
        # Check if matched in config whitelist or is an SD card
        is_whitelisted = vol.name in config.monitored_volumes
        is_sd = is_sd_card_volume(vol)

        if is_whitelisted or is_sd:
            print(f"🎯 Detected matching card: '{vol.name}' (Whitelisted: {is_whitelisted}, SD: {is_sd})")
            process_volume(vol, config, db)
        else:
            print(f"ℹ️  Ignoring non-monitored volume: '{vol.name}'")

    # Update active tracking set
    active_volumes.clear()
    active_volumes.update(current_mounts)

def run_watcher(config: Config, db: Database, poll_interval: int = 3) -> None:
    """Continuous polling watcher for SD card insertions."""
    print("==================================================")
    print("👀 Photo Importer Watcher Service Active")
    print(f"📁 Monitored SD Cards: {config.monitored_volumes}")
    print(f"💾 Destination: {config.expanded_dest_dir}")
    print(f"☁️ Auto Upload: {'Enabled' if config.auto_upload_to_gphotos else 'Disabled'}")
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
