# 📷 Canon RAW Photo Importer & Google Photos Matrix Sync (macOS)

An automated tool designed for macOS to automatically import Canon RAW photos (`.CR2`, `.CR3`, `.CRW`) and companion media from SD cards into custom local directories, verified with SHA256 checksums, and sync them to Google Photos with **Per-Volume Matrix Configurations** and **Multi-Account Google Authentication**.

---

## 🚀 Key Features

- **JSON Matrix Configuration**: Configure different SD cards with distinct local destinations, date folder rules, upload switches, and target albums.
- **Multiple Google Accounts**: Bind specific SD cards to specific Google accounts (e.g., `default`, `personal`, `work`).
- **Configurable Upload Routing**: Enable or disable Google Photos upload per volume, or route to specific albums.
- **SD Card Auto-Detection**: Automatically detects when a whitelisted Canon SD card (e.g. `EOS_DIGITAL`) is plugged in.
- **Background Automation (macOS `launchd`)**: Runs silently with 0% CPU/RAM idle overhead using native macOS launch agents.
- **Canon RAW & Media Support**: Handles `.CR2`, `.CR3`, `.CRW`, `.JPG`, `.PNG`, `.HEIC`, `.MP4`, `.MOV`.
- **EXIF Capture Date Organization**: Sorts media into structured folders (`YYYY-MM-DD/` or `YYYY/YYYY-MM-DD/`) using true capture timestamps (`DateTimeOriginal`).
- **Integrity Verification**: Verifies transfers using SHA256 checksums before updating sync records.
- **Deduplication Engine**: Built-in SQLite database prevents duplicate local imports and duplicate Google Photos uploads.
- **Native macOS Notifications**: Desktop banner alerts when imports start and complete.

---

## 🛠️ Quick Installation

1. **Clone and enter the directory**:
   ```bash
   cd /Volumes/MacMiniExternal/local/projects/photo_importer
   ```

2. **Set up the virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

---

## ⚙️ Configuration Matrix (`~/.config/photo_importer/config.json`)

### View Matrix Configuration
```bash
./import_photos.py config show
```

### JSON Matrix Structure
```json
{
  "defaults": {
    "dest_base_dir": "~/local/photos",
    "folder_structure": "%Y-%m-%d",
    "delete_after_import": false,
    "use_move": false,
    "supported_extensions": [
      ".cr2", ".cr3", ".crw", ".jpg", ".jpeg", ".png", ".heic", ".tiff", ".mp4", ".mov", ".avi"
    ]
  },
  "google_accounts": {
    "default": {
      "credentials_path": "~/.config/photo_importer/credentials_default.json",
      "token_path": "~/.config/photo_importer/token_default.json"
    },
    "work": {
      "credentials_path": "~/.config/photo_importer/credentials_work.json",
      "token_path": "~/.config/photo_importer/token_work.json"
    }
  },
  "volumes": {
    "EOS_DIGITAL": {
      "dest_base_dir": "~/local/photos/canon",
      "upload": {
        "enabled": true,
        "google_account": "default",
        "album": "Canon RAW"
      }
    },
    "WORK_SD": {
      "dest_base_dir": "~/local/photos/work",
      "upload": {
        "enabled": true,
        "google_account": "work",
        "album": "Work Portfolio"
      }
    },
    "DRONE_SD": {
      "dest_base_dir": "~/local/photos/drone",
      "upload": {
        "enabled": false
      }
    }
  }
}
```

---

## ☁️ Setting Up Google Accounts

1. Obtain your OAuth Client ID JSON from [Google Cloud Console](https://console.cloud.google.com/) with **Photos Library API** enabled.
2. Add the account to your configuration:
   ```bash
   ./import_photos.py config add-account default --creds ~/.config/photo_importer/credentials_default.json
   ./import_photos.py config add-account work --creds ~/.config/photo_importer/credentials_work.json
   ```
3. Authorize each account via your browser:
   ```bash
   ./import_photos.py auth --account default
   ./import_photos.py auth --account work
   ```

---

## 💻 CLI Commands & Usage

### 1. Volume Matrix Configuration
```bash
# Configure volume with specific destination, account, and album
./import_photos.py config set-volume EOS_DIGITAL \
    --dest ~/local/photos/canon \
    --account default \
    --album "Canon RAW" \
    --upload

# Configure pure local import without uploading
./import_photos.py config set-volume DRONE_SD \
    --dest ~/local/photos/drone \
    --no-upload

# Remove volume from matrix
./import_photos.py config remove-volume DRONE_SD
```

### 2. Manual Import & Sync
```bash
# Import from specific source folder or SD card using its matrix profile
./import_photos.py import --src /Volumes/EOS_DIGITAL

# Import and immediately trigger Google Photos upload
./import_photos.py sync --src /Volumes/WORK_SD

# Upload pending files for a specific account
./import_photos.py upload --account work
```

### 3. Background Watcher Service
```bash
# Run watcher in foreground (for testing)
./import_photos.py watch

# Install as macOS background LaunchAgent (runs automatically on login)
./import_photos.py service install

# Check background service status
./import_photos.py service status
```

---

## 🧪 Running Tests

```bash
./venv/bin/pytest
```
