# 📷 Canon RAW Photo Importer & Google Photos Sync (macOS)

An automated tool designed for macOS to automatically import Canon RAW photos (`.CR2`, `.CR3`, `.CRW`) and companion media from SD cards into an organized local directory structure, verified with SHA256 checksums, and sync them seamlessly to Google Photos.

---

## 🚀 Key Features

- **SD Card Auto-Detection & Whitelist**: Automatically triggers when your specified Canon SD card (e.g. `EOS_DIGITAL`) is plugged in.
- **Background Automation (macOS `launchd`)**: Runs silently with 0% CPU/RAM idle overhead using macOS native launch agents.
- **Canon RAW & Media Support**: Handles `.CR2`, `.CR3`, `.CRW`, `.JPG`, `.PNG`, `.HEIC`, `.MP4`, `.MOV`.
- **EXIF Capture Date Organization**: Sorts media into structured folders (`YYYY-MM-DD/` or `YYYY/YYYY-MM-DD/`) using true capture timestamps (`DateTimeOriginal`).
- **Integrity Verification**: Verifies transfers using SHA256 checksums before updating sync records.
- **Deduplication Engine**: Built-in SQLite database prevents duplicate local imports and duplicate Google Photos uploads.
- **Google Photos Upload**: High-performance chunked uploads directly to your Google Photos library with album support and auto-retry.
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

## ⚙️ Configuration

View and customize your configuration at `~/.config/photo_importer/config.json`:

```bash
# View current settings
./import_photos.py config show

# Add your SD card volume label to whitelist
./import_photos.py config add-sd EOS_DIGITAL
./import_photos.py config add-sd CANON_64GB

# Remove an SD card volume label from whitelist
./import_photos.py config remove-sd CANON_64GB
```

### Config Options (`~/.config/photo_importer/config.json`)
```json
{
  "monitored_volumes": ["EOS_DIGITAL", "CANON_SD"],
  "dest_base_dir": "~/local/photos",
  "folder_structure": "%Y-%m-%d",
  "delete_after_import": false,
  "use_move": false,
  "auto_upload_to_gphotos": true,
  "gphotos_album": null,
  "google_credentials_path": "~/.config/photo_importer/credentials.json",
  "google_token_path": "~/.config/photo_importer/token.json",
  "db_path": "~/.config/photo_importer/library.db"
}
```

---

## ☁️ Setting Up Google Photos Upload

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `My-Photo-Importer`).
3. Navigate to **APIs & Services > Library** and enable **Photos Library API**.
4. Navigate to **APIs & Services > OAuth consent screen**:
   - User Type: **External** (or Internal for Workspace).
   - Add your own Google account email under **Test Users**.
5. Navigate to **APIs & Services > Credentials**:
   - Click **Create Credentials > OAuth client ID**.
   - Application Type: **Desktop App**.
   - Download the client credentials JSON.
6. Save the downloaded JSON file to:
   ```bash
   mkdir -p ~/.config/photo_importer
   cp ~/Downloads/client_secret_*.json ~/.config/photo_importer/credentials.json
   ```
7. Authorize your account:
   ```bash
   ./import_photos.py auth
   ```
   *(A browser window will open asking you to sign in and grant access. The token will be saved and auto-refreshed thereafter.)*

---

## 💻 CLI Commands & Usage

### 1. Manual Import
```bash
# Import from specific source folder or SD card
./import_photos.py import --src /Volumes/EOS_DIGITAL --dest ~/local/photos

# Import and immediately trigger Google Photos upload
./import_photos.py sync --src /Volumes/EOS_DIGITAL

# Move files instead of copying (deletes from SD card after verified copy)
./import_photos.py import --src /Volumes/EOS_DIGITAL --move
```

### 2. Google Photos Upload
```bash
# Upload all pending files in the SQLite queue
./import_photos.py upload

# Upload into a specific album
./import_photos.py upload --album "2026 Canon Shots"
```

### 3. Check Status
```bash
./import_photos.py status
```

### 4. Background Watcher Service
```bash
# Run watcher in foreground (useful for testing)
./import_photos.py watch

# Install as macOS background LaunchAgent (runs automatically on login)
./import_photos.py service install

# Check background service status
./import_photos.py service status

# Start / Stop / Uninstall service
./import_photos.py service stop
./import_photos.py service start
./import_photos.py service uninstall
```

---

## 🧪 Running Tests

```bash
./venv/bin/pytest
```
