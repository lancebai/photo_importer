import os
import subprocess
from pathlib import Path
from typing import Dict, Any

SERVICE_NAME = "com.photoimporter.watcher"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_NAME}.plist"
LOG_DIR = Path.home() / ".config" / "photo_importer" / "logs"

def get_plist_content(python_bin: str, script_path: str) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_log = LOG_DIR / "watcher.stdout.log"
    stderr_log = LOG_DIR / "watcher.stderr.log"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{script_path}</string>
        <string>watch</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{stdout_log}</string>
    <key>StandardErrorPath</key>
    <string>{stderr_log}</string>
</dict>
</plist>
"""

def install_service(python_bin: str, script_path: str) -> bool:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = get_plist_content(python_bin, script_path)

    # If already installed, unload first
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)

    with open(PLIST_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    res = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"✅ Service installed and loaded: {PLIST_PATH}")
        print(f"📝 Logs will be written to: {LOG_DIR}")
        return True
    else:
        print(f"❌ Failed to load service via launchctl: {res.stderr}")
        return False

def uninstall_service() -> bool:
    if not PLIST_PATH.exists():
        print("Service is not installed.")
        return True

    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    PLIST_PATH.unlink(missing_ok=True)
    print(f"✅ Service uninstalled ({SERVICE_NAME}).")
    return True

def start_service() -> bool:
    if not PLIST_PATH.exists():
        print("Error: Service is not installed. Run 'photo-import service install' first.")
        return False
    res = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True, text=True)
    return res.returncode == 0

def stop_service() -> bool:
    if not PLIST_PATH.exists():
        return True
    res = subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True, text=True)
    return res.returncode == 0

def get_service_status() -> Dict[str, Any]:
    installed = PLIST_PATH.exists()
    running = False
    pid = None

    if installed:
        res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if SERVICE_NAME in line:
                parts = line.split()
                if len(parts) >= 3:
                    running = True
                    pid = parts[0] if parts[0] != "-" else None

    return {
        "installed": installed,
        "running": running,
        "pid": pid,
        "plist_path": str(PLIST_PATH) if installed else None,
        "log_dir": str(LOG_DIR)
    }
