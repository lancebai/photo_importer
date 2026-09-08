import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .config import Config, GoogleAccountConfig, VolumeConfig, UploadConfig
from .db import Database
from .gphotos_auth import get_credentials
from .gphotos_uploader import upload_pending_photos
from .importer import find_available_volumes, import_photos
from .service import get_service_status, install_service, start_service, stop_service, uninstall_service
from .watcher import run_watcher

def print_banner():
    print("""
=====================================================
   📷 Photo Importer & Google Photos Matrix Sync
=====================================================
""")

def cmd_import(args, config: Config, db: Database):
    src = args.src
    volume_name = args.volume_name
    if not src:
        # Check if there is an auto-detected SD card
        vols = find_available_volumes(config.monitored_volumes)
        whitelisted = [v for v, is_m in vols if is_m]
        
        if len(whitelisted) == 1:
            src = str(whitelisted[0])
            volume_name = whitelisted[0].name
            print(f"ℹ️  Auto-selected detected SD card: {src}")
        else:
            print("Please provide a source directory using --src.")
            print("\nAvailable Volumes in /Volumes:")
            for v, is_m in vols:
                status = " (Configured in Matrix)" if is_m else ""
                print(f"  - {v}{status}")
            print("\nExample: python3 import_photos.py import --src /Volumes/EOS_DIGITAL")
            return

    v_name = volume_name or Path(src).name
    vol_cfg = config.get_resolved_volume_config(v_name)

    if args.dest:
        vol_cfg.dest_base_dir = args.dest
    if args.move:
        vol_cfg.use_move = True
    if args.copy:
        vol_cfg.use_move = False

    print(f"Scanning '{src}' (Volume: {v_name})...")
    print(f"Destination base directory: {vol_cfg.dest_base_dir}")
    print(f"Mode: {'MOVE' if vol_cfg.use_move else 'COPY + SHA256 Verify'}")
    print(f"Upload Config: Enabled={vol_cfg.upload.enabled}, Account={vol_cfg.upload.google_account}")

    res = import_photos(
        source_dir=Path(src),
        config=config,
        db=db,
        volume_name=v_name,
        progress_callback=lambda curr, total, name: print(f"[{curr}/{total}] Importing {name}...")
    )

    print(f"\nImport Complete!")
    print(f"  - Successfully imported: {res.imported_count} files ({round(res.total_bytes / (1024*1024), 2)} MB)")
    print(f"  - Skipped (already imported): {res.skipped_count}")
    print(f"  - Failed: {res.failed_count}")

    # Check upload condition
    should_upload = args.upload or (vol_cfg.upload.enabled and not args.no_upload)
    if should_upload and res.imported_count > 0:
        target_account = vol_cfg.upload.google_account
        print(f"\n☁️ Starting Google Photos upload for account '{target_account}'...")
        upload_pending_photos(config, db, google_account=target_account, interactive=True)

def cmd_upload(args, config: Config, db: Database):
    account = args.account
    upload_pending_photos(config, db, google_account=account, limit=args.limit, interactive=True)

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
        print("==================================================")
        print("⚙️  Photo Importer Matrix Configuration (~/.config/photo_importer/config.json)")
        print("==================================================")
        print("\n[Global Defaults]")
        print(f"  • Base Directory:   {config.defaults.dest_base_dir}")
        print(f"  • Folder Structure: {config.defaults.folder_structure}")
        print(f"  • Use Move:         {config.defaults.use_move}")
        
        print("\n[Google Accounts Matrix]")
        for acc_name, acc in config.google_accounts.items():
            tok_exists = " (Authenticated ✅)" if acc.expanded_token_path.exists() else " (Not authenticated ⚠️)"
            print(f"  • Account: '{acc_name}'{tok_exists}")
            print(f"    - Credentials: {acc.credentials_path}")
            print(f"    - Token:       {acc.token_path}")

        print("\n[Monitored Volumes Matrix]")
        for v_name, vol in config.volumes.items():
            up = vol.upload
            status_up = f"Enabled -> Account: '{up.google_account}'" if up.enabled else "Disabled"
            album_str = f" | Album: '{up.album}'" if (up.enabled and up.album) else ""
            dest_str = vol.dest_base_dir or f"(Default: {config.defaults.dest_base_dir})"
            print(f"  • Volume: '{v_name}'")
            print(f"    - Local Dest: {dest_str}")
            print(f"    - Upload:     {status_up}{album_str}")
        print("==================================================")

    elif sub == "set-volume":
        if not args.name:
            print("Error: Specify volume name. Example: photo-import config set-volume EOS_DIGITAL --dest ~/local/photos/canon --account personal --album 'Canon RAW'")
            return
        upload_en = None
        if args.upload:
            upload_en = True
        elif args.no_upload:
            upload_en = False

        use_mv = None
        if args.move:
            use_mv = True
        elif args.copy:
            use_mv = False

        config.set_volume_config(
            volume_name=args.name,
            dest_base_dir=args.dest,
            folder_structure=args.folder_structure,
            use_move=use_mv,
            delete_after_import=args.delete_after_import,
            upload_enabled=upload_en,
            google_account=args.account,
            album=args.album
        )
        print(f"✅ Updated configuration for volume '{args.name}'.")

    elif sub == "remove-volume":
        if not args.name:
            print("Error: Specify volume name. Example: photo-import config remove-volume EOS_DIGITAL")
            return
        if config.remove_volume(args.name):
            print(f"✅ Removed volume '{args.name}' from configuration matrix.")
        else:
            print(f"ℹ️  Volume '{args.name}' was not found.")

    elif sub == "add-account":
        acc_name = args.account_name or args.name
        if not acc_name:
            print("Error: Specify account name. Example: photo-import config add-account work --creds ~/Downloads/client_secret_work.json")
            return
        config.add_google_account(acc_name, credentials_path=args.creds, token_path=args.token)
        print(f"✅ Added Google account '{acc_name}' to configuration matrix.")

    elif sub == "remove-account":
        acc_name = args.account_name or args.name
        if not acc_name:
            print("Error: Specify account name. Example: photo-import config remove-account work")
            return
        if acc_name in config.google_accounts:
            del config.google_accounts[acc_name]
            config.save()
            print(f"✅ Removed Google account '{acc_name}'.")
        else:
            print(f"ℹ️  Account '{acc_name}' was not found.")

def cmd_status(args, config: Config, db: Database):
    stats = db.get_stats()
    srv = get_service_status()
    print("==================================================")
    print("📊 Photo Library & Matrix Sync Status")
    print("==================================================")
    print(f"📁 Default Library:      {config.defaults.dest_base_dir}")
    print(f"📦 Total Tracked Files:  {stats['total_files']} ({stats['total_size_mb']} MB)")
    print(f"☁️ Uploaded to GPhotos: {stats['uploaded_count']}")
    print(f"⏳ Pending Upload:       {stats['pending_count']}")
    print(f"⚠️ Failed Uploads:       {stats['failed_count']}")
    if stats.get("accounts"):
        print(f"🔑 Active Accounts:      {', '.join(stats['accounts'])}")
    print(f"⚙️ Background Watcher:   {'Running (PID ' + str(srv['pid']) + ')' if srv['running'] else ('Installed' if srv['installed'] else 'Not Installed')}")
    print("==================================================")

def cmd_auth(args, config: Config, db: Database):
    acc_name = args.account or "default"
    acc_cfg = config.get_google_account(acc_name)
    print(f"Checking Google Photos OAuth2 Authentication for account '{acc_name}'...")
    creds = get_credentials(
        credentials_path=acc_cfg.expanded_credentials_path,
        token_path=acc_cfg.expanded_token_path,
        account_name=acc_name,
        interactive=True
    )
    if creds:
        print(f"✅ Google Account '{acc_name}' is authenticated and ready to upload!")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo_importer",
        description="Canon RAW Photo Importer & Multi-Account Google Photos Sync for macOS"
    )
    
    # Top level optional flags for backward compatibility
    parser.add_argument("--src", help="Source directory (e.g., /Volumes/EOS_DIGITAL)")
    parser.add_argument("--dest", help="Destination base directory")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying")
    parser.add_argument("--copy", action="store_true", help="Copy files (default)")
    parser.add_argument("--upload", action="store_true", help="Trigger Google Photos upload")
    parser.add_argument("--no-upload", action="store_true", help="Disable Google Photos upload")
    parser.add_argument("--volume-name", help="Volume profile name from matrix")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # import
    p_import = subparsers.add_parser("import", help="Import photos from source directory or SD card")
    p_import.add_argument("--src", help="Source directory (e.g., /Volumes/EOS_DIGITAL)")
    p_import.add_argument("--dest", help="Destination base directory")
    p_import.add_argument("--volume-name", help="Volume profile name in config matrix")
    p_import.add_argument("--move", action="store_true", help="Move files instead of copying")
    p_import.add_argument("--copy", action="store_true", help="Copy files (default)")
    p_import.add_argument("--upload", action="store_true", help="Trigger Google Photos upload")
    p_import.add_argument("--no-upload", action="store_true", help="Disable Google Photos upload")

    # upload
    p_upload = subparsers.add_parser("upload", help="Upload pending photos to Google Photos")
    p_upload.add_argument("--account", help="Specific Google account name to upload for")
    p_upload.add_argument("--limit", type=int, help="Maximum number of files to upload")

    # sync
    p_sync = subparsers.add_parser("sync", help="Import from SD card and upload to Google Photos")
    p_sync.add_argument("--src", help="Source directory (e.g., /Volumes/EOS_DIGITAL)")
    p_sync.add_argument("--dest", help="Destination base directory")
    p_sync.add_argument("--volume-name", help="Volume profile name in config matrix")
    p_sync.add_argument("--move", action="store_true", help="Move files instead of copying")
    p_sync.add_argument("--copy", action="store_true", help="Copy files (default)")

    # watch
    p_watch = subparsers.add_parser("watch", help="Run SD card watcher daemon in foreground")
    p_watch.add_argument("--interval", type=int, default=3, help="Polling interval in seconds (default: 3)")

    # service
    p_service = subparsers.add_parser("service", help="Manage background macOS launchd service")
    p_service.add_argument("action", choices=["install", "uninstall", "start", "stop", "status"], help="Service action")

    # config
    p_config = subparsers.add_parser("config", help="View or update configuration matrix")
    p_config.add_argument("config_action", nargs="?", choices=["show", "set-volume", "remove-volume", "add-account", "remove-account"], default="show")
    p_config.add_argument("name", nargs="?", help="Volume name for set-volume / remove-volume")
    p_config.add_argument("--account-name", help="Account name for add-account / remove-account")
    p_config.add_argument("--creds", help="Credentials JSON path for add-account")
    p_config.add_argument("--token", help="Token JSON path for add-account")
    p_config.add_argument("--dest", help="Destination path for volume")
    p_config.add_argument("--folder-structure", help="Date folder format for volume (e.g. %%Y/%%Y-%%m-%%d)")
    p_config.add_argument("--account", help="Google account name to bind to volume")
    p_config.add_argument("--album", help="Google Photos album name to bind to volume")
    p_config.add_argument("--upload", action="store_true", help="Enable upload for volume")
    p_config.add_argument("--no-upload", action="store_true", help="Disable upload for volume")
    p_config.add_argument("--move", action="store_true", help="Use move for volume")
    p_config.add_argument("--copy", action="store_true", help="Use copy for volume")
    p_config.add_argument("--delete-after-import", action="store_true", help="Delete from source after import")

    # status
    subparsers.add_parser("status", help="Show photo library statistics and upload status")

    # auth
    p_auth = subparsers.add_parser("auth", help="Authorize a Google Photos account in browser")
    p_auth.add_argument("--account", default="default", help="Google account identifier (default: 'default')")

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
                status = " [Configured in Matrix]" if is_m else ""
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
