import argparse
import sys
from pathlib import Path
from typing import Optional

from .config import Config
from .db import Database
from .gphotos_auth import get_credentials
from .gphotos_uploader import upload_pending_photos
from .importer import find_available_volumes, import_photos
from .service import get_service_status, install_service, start_service, stop_service, uninstall_service
from .watcher import run_watcher

def print_banner():
    print("""
=====================================================
   📷 Photo Importer & Google Photos Sync (macOS)
=====================================================
""")

def cmd_import(args, config: Config, db: Database):
    src = args.src
    if not src:
        # Check if there is an auto-detected SD card
        vols = find_available_volumes(config.monitored_volumes)
        whitelisted = [v for v, is_m in vols if is_m]
        
        if len(whitelisted) == 1:
            src = str(whitelisted[0])
            print(f"ℹ️  Auto-selected detected SD card: {src}")
        else:
            print("Please provide a source directory using --src.")
            print("\nAvailable Volumes in /Volumes:")
            for v, is_m in vols:
                status = " (Whitelisted SD Card)" if is_m else ""
                print(f"  - {v}{status}")
            print("\nExample: python3 import_photos.py import --src /Volumes/EOS_DIGITAL")
            return

    if args.dest:
        config.dest_base_dir = args.dest
    if args.move:
        config.use_move = True
    if args.copy:
        config.use_move = False

    print(f"Scanning '{src}'...")
    print(f"Destination base directory: {config.expanded_dest_dir}")
    print(f"Mode: {'MOVE' if config.use_move else 'COPY + SHA256 Verify'}")

    res = import_photos(
        source_dir=Path(src),
        config=config,
        db=db,
        progress_callback=lambda curr, total, name: print(f"[{curr}/{total}] Importing {name}...")
    )

    print(f"\nImport Complete!")
    print(f"  - Successfully imported: {res.imported_count} files ({round(res.total_bytes / (1024*1024), 2)} MB)")
    print(f"  - Skipped (already imported): {res.skipped_count}")
    print(f"  - Failed: {res.failed_count}")

    # Check if upload is requested
    should_upload = args.upload or (config.auto_upload_to_gphotos and not args.no_upload)
    if should_upload and res.imported_count > 0:
        print("\n☁️ Starting Google Photos upload for newly imported photos...")
        upload_pending_photos(config, db, interactive=True)

def cmd_upload(args, config: Config, db: Database):
    if args.album:
        config.gphotos_album = args.album
    upload_pending_photos(config, db, limit=args.limit, interactive=True)

def cmd_sync(args, config: Config, db: Database):
    args.upload = True
    args.no_upload = False
    cmd_import(args, config, db)

def cmd_watch(args, config: Config, db: Database):
    run_watcher(config, db, poll_interval=args.interval)

def cmd_service(args, config: Config, db: Database):
    action = args.action
    python_bin = sys.executable
    script_path = str(Path(__file__).resolve().parent.parent / "import_photos.py")

    if action == "install":
        install_service(python_bin, script_path)
    elif action == "uninstall":
        uninstall_service()
    elif action == "start":
        if start_service():
            print("✅ Service started.")
        else:
            print("❌ Failed to start service.")
    elif action == "stop":
        if stop_service():
            print("✅ Service stopped.")
        else:
            print("❌ Failed to stop service.")
    elif action == "status":
        status = get_service_status()
        print("macOS Service Status:")
        print(f"  - Installed: {status['installed']}")
        print(f"  - Running:   {status['running']}")
        if status['pid']:
            print(f"  - PID:       {status['pid']}")
        print(f"  - Plist:     {status['plist_path']}")
        print(f"  - Log Dir:   {status['log_dir']}")

def cmd_config(args, config: Config, db: Database):
    sub = args.config_action
    if sub == "show" or not sub:
        print("Current Configuration:")
        print(f"  - Monitored SD Cards:     {config.monitored_volumes}")
        print(f"  - Destination Directory:  {config.dest_base_dir}")
        print(f"  - Folder Structure:       {config.folder_structure}")
        print(f"  - Auto Upload to GPhotos: {config.auto_upload_to_gphotos}")
        print(f"  - GPhotos Album:          {config.gphotos_album or '(Default Timeline)'}")
        print(f"  - Use Move (vs Copy):     {config.use_move}")
        print(f"  - Supported Extensions:   {', '.join(config.supported_extensions)}")
        print(f"  - Credentials Path:       {config.google_credentials_path}")
        print(f"  - SQLite DB Path:         {config.db_path}")
    elif sub == "add-sd":
        if not args.name:
            print("Error: Specify SD card name. Example: photo-import config add-sd EOS_DIGITAL")
            return
        if config.add_monitored_volume(args.name):
            print(f"✅ Added '{args.name}' to monitored SD cards list.")
        else:
            print(f"ℹ️  '{args.name}' is already in the list.")
    elif sub == "remove-sd":
        if not args.name:
            print("Error: Specify SD card name. Example: photo-import config remove-sd EOS_DIGITAL")
            return
        if config.remove_monitored_volume(args.name):
            print(f"✅ Removed '{args.name}' from monitored SD cards list.")
        else:
            print(f"ℹ️  '{args.name}' was not found in the list.")

def cmd_status(args, config: Config, db: Database):
    stats = db.get_stats()
    srv = get_service_status()
    print("==================================================")
    print("📊 Photo Library & Sync Status")
    print("==================================================")
    print(f"📁 Local Library:        {config.expanded_dest_dir}")
    print(f"📦 Total Tracked Files:  {stats['total_files']} ({stats['total_size_mb']} MB)")
    print(f"☁️ Uploaded to GPhotos: {stats['uploaded_count']}")
    print(f"⏳ Pending Upload:       {stats['pending_count']}")
    print(f"⚠️ Failed Uploads:       {stats['failed_count']}")
    print(f"⚙️ Background Watcher:   {'Running (PID ' + str(srv['pid']) + ')' if srv['running'] else ('Installed' if srv['installed'] else 'Not Installed')}")
    print("==================================================")

def cmd_auth(args, config: Config, db: Database):
    print("Checking Google Photos OAuth2 Authentication...")
    creds = get_credentials(
        credentials_path=config.expanded_credentials_path,
        token_path=config.expanded_token_path,
        interactive=True
    )
    if creds:
        print("✅ Ready to upload to Google Photos!")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo_importer",
        description="Canon RAW Photo Importer & Google Photos Sync for macOS"
    )
    
    # Top level optional flags for backward compatibility
    parser.add_argument("--src", help="Source directory (e.g., /Volumes/EOS_DIGITAL)")
    parser.add_argument("--dest", help="Destination base directory")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying")
    parser.add_argument("--copy", action="store_true", help="Copy files (default)")
    parser.add_argument("--upload", action="store_true", help="Trigger Google Photos upload")
    parser.add_argument("--no-upload", action="store_true", help="Disable Google Photos upload")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # import
    p_import = subparsers.add_parser("import", help="Import photos from source directory or SD card")
    p_import.add_argument("--src", help="Source directory (e.g., /Volumes/EOS_DIGITAL)")
    p_import.add_argument("--dest", help="Destination base directory")
    p_import.add_argument("--move", action="store_true", help="Move files instead of copying")
    p_import.add_argument("--copy", action="store_true", help="Copy files (default)")
    p_import.add_argument("--upload", action="store_true", help="Trigger Google Photos upload")
    p_import.add_argument("--no-upload", action="store_true", help="Disable Google Photos upload")

    # upload
    p_upload = subparsers.add_parser("upload", help="Upload pending photos to Google Photos")
    p_upload.add_argument("--limit", type=int, help="Maximum number of files to upload")
    p_upload.add_argument("--album", help="Google Photos album name to upload into")

    # sync
    p_sync = subparsers.add_parser("sync", help="Import from SD card and upload to Google Photos")
    p_sync.add_argument("--src", help="Source directory (e.g., /Volumes/EOS_DIGITAL)")
    p_sync.add_argument("--dest", help="Destination base directory")
    p_sync.add_argument("--move", action="store_true", help="Move files instead of copying")
    p_sync.add_argument("--copy", action="store_true", help="Copy files (default)")

    # watch
    p_watch = subparsers.add_parser("watch", help="Run SD card watcher daemon in foreground")
    p_watch.add_argument("--interval", type=int, default=3, help="Polling interval in seconds (default: 3)")

    # service
    p_service = subparsers.add_parser("service", help="Manage background macOS launchd service")
    p_service.add_argument("action", choices=["install", "uninstall", "start", "stop", "status"], help="Service action")

    # config
    p_config = subparsers.add_parser("config", help="View or update configuration & SD card whitelist")
    p_config.add_argument("config_action", nargs="?", choices=["show", "add-sd", "remove-sd"], default="show")
    p_config.add_argument("name", nargs="?", help="SD Card volume name for add-sd or remove-sd")

    # status
    subparsers.add_parser("status", help="Show photo library statistics and upload status")

    # auth
    subparsers.add_parser("auth", help="Authorize Google Photos OAuth2 in browser")

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()

    config = Config.load()
    db = Database(config.expanded_db_path)

    # If no subcommand provided but top-level flags are present or no args
    if not args.command:
        if args.src:
            cmd_import(args, config, db)
        else:
            # Display helpful status and available SD cards
            print_banner()
            cmd_status(args, config, db)
            print("\nAvailable Volumes in /Volumes:")
            for vol, is_m in find_available_volumes(config.monitored_volumes):
                status = " [Whitelisted SD Card]" if is_m else ""
                print(f"  - {vol}{status}")
            print("\nRun 'python3 import_photos.py --help' to see all available commands.")
        return

    commands = {
        "import": cmd_import,
        "upload": cmd_upload,
        "sync": cmd_sync,
        "watch": cmd_watch,
        "service": cmd_service,
        "config": cmd_config,
        "status": cmd_status,
        "auth": cmd_auth
    }

    handler = commands.get(args.command)
    if handler:
        handler(args, config, db)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
