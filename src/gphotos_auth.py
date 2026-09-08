import os
from pathlib import Path
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary.appendonly",
    "https://www.googleapis.com/auth/photoslibrary.sharing"
]

def get_credentials(
    credentials_path: Path,
    token_path: Path,
    account_name: str = "default",
    interactive: bool = True
) -> Optional[Credentials]:
    """
    Load or request Google Photos API OAuth 2.0 credentials for a specific account.
    """
    creds = None
    cred_file = Path(credentials_path).expanduser()
    tok_file = Path(token_path).expanduser()

    if tok_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(tok_file), SCOPES)
        except Exception as e:
            print(f"Warning: Failed to load existing token for account '{account_name}' from {tok_file}: {e}")
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            print(f"Refreshing expired Google OAuth token for account '{account_name}'...")
            creds.refresh(Request())
            tok_file.parent.mkdir(parents=True, exist_ok=True)
            with open(tok_file, "w") as f:
                f.write(creds.to_json())
            return creds
        except Exception as e:
            print(f"Warning: Token refresh failed for '{account_name}' ({e}). Re-authorizing...")
            creds = None

    if not interactive:
        return None

    if not cred_file.exists():
        print(f"\n[Google Photos Setup Required for account: '{account_name}']")
        print(f"Credentials file not found at: {cred_file}")
        print("Please follow these steps to enable Google Photos upload:")
        print("  1. Go to Google Cloud Console (https://console.cloud.google.com/)")
        print("  2. Create a project and enable the 'Photos Library API'")
        print("  3. Create an 'OAuth 2.0 Client ID' (Desktop App)")
        print(f"  4. Download the JSON file and save it to: {cred_file}\n")
        return None

    print(f"\nInitiating Google Photos authorization for account '{account_name}' in your browser...")
    flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), SCOPES)
    creds = flow.run_local_server(port=0)

    tok_file.parent.mkdir(parents=True, exist_ok=True)
    with open(tok_file, "w") as f:
        f.write(creds.to_json())

    print(f"✅ Google Photos authentication successful for account '{account_name}'! Token saved.\n")
    return creds
