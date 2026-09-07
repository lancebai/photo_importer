import json
import mimetypes
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Any
import requests
from google.oauth2.credentials import Credentials

from .config import Config
from .db import Database
from .gphotos_auth import get_credentials
from .notifications import send_notification

UPLOAD_URL = "https://photoslibrary.googleapis.com/v1/uploads"
BATCH_CREATE_URL = "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate"
ALBUMS_URL = "https://photoslibrary.googleapis.com/v1/albums"

def get_auth_headers(creds: Credentials) -> Dict[str, str]:
    if not creds.valid and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
    return {
        "Authorization": f"Bearer {creds.token}",
    }

def upload_file_bytes(
    file_path: Path,
    creds: Credentials,
    max_retries: int = 3
) -> str:
    """
    Upload raw media file bytes to Google Photos upload endpoint and return the uploadToken.
    """
    headers = get_auth_headers(creds)
    mime_type, _ = mimetypes.guess_type(str(file_path))
    headers.update({
        "Content-type": "application/octet-stream",
        "X-Goog-Upload-Content-Type": mime_type or "application/octet-stream",
        "X-Goog-Upload-Protocol": "raw",
        "X-Goog-Upload-File-Name": file_path.name
    })

    file_size = file_path.stat().st_size

    for attempt in range(1, max_retries + 1):
        try:
            with open(file_path, "rb") as f:
                response = requests.post(
                    UPLOAD_URL,
                    data=f,
                    headers=headers,
                    timeout=300
                )
            if response.status_code == 200:
                return response.text.strip()
            else:
                error_text = response.text
                if attempt == max_retries:
                    raise IOError(f"HTTP {response.status_code}: {error_text}")
        except Exception as e:
            if attempt == max_retries:
                raise e
            time.sleep(2 ** attempt)

    raise IOError("Failed to obtain upload token from Google Photos.")

def batch_create_media_items(
    items: List[Tuple[int, str, str]],  # List of (db_id, upload_token, filename)
    creds: Credentials,
    album_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Register uploaded tokens into Google Photos library (and optional album).
    """
    headers = get_auth_headers(creds)
    headers["Content-Type"] = "application/json"

    new_media_items = []
    for db_id, token, filename in items:
        new_media_items.append({
            "description": f"Imported: {filename}",
            "simpleMediaItem": {
                "uploadToken": token,
                "fileName": filename
            }
        })

    payload = {"newMediaItems": new_media_items}
    if album_id:
        payload["albumId"] = album_id

    response = requests.post(BATCH_CREATE_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise IOError(f"batchCreate failed ({response.status_code}): {response.text}")

    data = response.json()
    return data.get("newMediaItemResults", [])

def get_or_create_album(album_title: str, creds: Credentials) -> Optional[str]:
    """Find or create an album by title in Google Photos."""
    headers = get_auth_headers(creds)
    try:
        # Check existing albums
        res = requests.get(ALBUMS_URL, headers=headers, params={"pageSize": 50}, timeout=30)
        if res.status_code == 200:
            albums = res.json().get("albums", [])
            for alb in albums:
                if alb.get("title") == album_title:
                    return alb.get("id")
        
        # Create album
        create_res = requests.post(
            ALBUMS_URL,
            headers=headers,
            json={"album": {"title": album_title}},
            timeout=30
        )
        if create_res.status_code == 200:
            return create_res.json().get("id")
    except Exception as e:
        print(f"Warning: Failed to get/create album '{album_title}': {e}")
    return None

def upload_pending_photos(
    config: Config,
    db: Database,
    limit: Optional[int] = None,
    interactive: bool = True,
    notify: bool = True
) -> Dict[str, Any]:
    """
    Upload all pending media files in the database to Google Photos.
    """
    pending = db.get_pending_uploads(limit=limit)
    if not pending:
        return {"uploaded": 0, "failed": 0, "skipped": 0}

    creds = get_credentials(
        credentials_path=config.expanded_credentials_path,
        token_path=config.expanded_token_path,
        interactive=interactive
    )

    if not creds:
        print("Skipping Google Photos upload: Google account is not authenticated.")
        return {"uploaded": 0, "failed": 0, "skipped": len(pending), "error": "Unauthenticated"}

    album_id = None
    if config.gphotos_album:
        album_id = get_or_create_album(config.gphotos_album, creds)

    uploaded_count = 0
    failed_count = 0

    print(f"Uploading {len(pending)} pending file(s) to Google Photos...")

    # Upload files in batches of up to 50 (Google Photos API limit for batchCreate)
    BATCH_SIZE = 10
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        upload_tokens = []

        for record in batch:
            file_id = record["id"]
            file_path = Path(record["local_path"])
            fname = record["original_filename"]

            if not file_path.exists():
                db.mark_upload_failed(file_id, "Local file not found")
                failed_count += 1
                continue

            try:
                db.mark_uploading(file_id)
                print(f"  Uploading ({record['id']}) {fname} ({round(record['file_size'] / (1024*1024), 2)} MB)...")
                token = upload_file_bytes(file_path, creds)
                upload_tokens.append((file_id, token, fname))
            except Exception as e:
                db.mark_upload_failed(file_id, str(e))
                failed_count += 1
                print(f"  ❌ Upload failed for {fname}: {e}")

        if upload_tokens:
            try:
                results = batch_create_media_items(upload_tokens, creds, album_id=album_id)
                for (db_id, _, fname), res_item in zip(upload_tokens, results):
                    status = res_item.get("status", {})
                    if status.get("message") in ("Success", "OK", None) and "mediaItem" in res_item:
                        g_id = res_item["mediaItem"].get("id", "")
                        db.mark_uploaded(db_id, g_id)
                        uploaded_count += 1
                        print(f"  ✅ Registered {fname} in Google Photos.")
                    else:
                        err_msg = status.get("message", "Unknown batch error")
                        db.mark_upload_failed(db_id, err_msg)
                        failed_count += 1
                        print(f"  ❌ Registration failed for {fname}: {err_msg}")
            except Exception as e:
                print(f"  ❌ Batch creation error: {e}")
                for db_id, _, _ in upload_tokens:
                    db.mark_upload_failed(db_id, str(e))
                    failed_count += 1

    if notify and uploaded_count > 0:
        send_notification(
            title="☁️ Google Photos Upload Complete",
            subtitle=f"{uploaded_count} file(s) uploaded",
            message=f"Uploaded to your Google Photos library"
        )

    return {"uploaded": uploaded_count, "failed": failed_count, "skipped": 0}
