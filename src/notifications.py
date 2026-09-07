import subprocess
from typing import Optional

def send_notification(title: str, message: str, subtitle: Optional[str] = None, sound: str = "default") -> bool:
    """
    Send a native macOS banner notification via AppleScript.
    """
    # Sanitize strings to avoid AppleScript escaping issues
    def clean(s: Optional[str]) -> str:
        if not s:
            return ""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')

    safe_title = clean(title)
    safe_msg = clean(message)
    safe_subtitle = clean(subtitle) if subtitle else ""

    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    if safe_subtitle:
        script += f' subtitle "{safe_subtitle}"'
    if sound:
        script += f' sound name "{clean(sound)}"'

    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Failed to send macOS notification: {e}")
        return False
