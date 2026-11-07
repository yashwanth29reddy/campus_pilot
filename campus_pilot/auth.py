"""OAuth 2.0 handling for Gmail + Google Calendar.

On first use this opens a browser window to authorize with your Google
account. The refresh token is stored in token.json so later runs are
automatic and don't need re-authorization.
"""

from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_DIR / "credentials.json"
TOKEN_PATH = PROJECT_DIR / "token.json"

# Gmail read-only + Calendar event read/write. We deliberately avoid full
# Gmail write/delete scopes to keep the token least-privileged.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def _get_credentials() -> Credentials:
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {CREDENTIALS_PATH}. "
            "Download it from Google Cloud Console > Credentials > OAuth client (Desktop app)."
        )

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
            if not creds or not creds.valid:
                raise RuntimeError("Authorization failed — no credentials returned.")
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def _build(service_name: str, version: str):
    from googleapiclient.discovery import build

    return build(service_name, version, credentials=_get_credentials())


def get_gmail_service():
    """Return an authenticated Gmail API service object."""
    return _build("gmail", "v1")


def get_calendar_service():
    """Return an authenticated Google Calendar API service object."""
    return _build("calendar", "v3")


def ensure_authorized() -> None:
    """Force the OAuth flow so we fail fast with a clear message."""
    _get_credentials()
    print("Authorized. Token saved to token.json")


if __name__ == "__main__":
    try:
        ensure_authorized()
    except Exception as e:  # noqa: BLE001 - show the user what went wrong
        print(f"ERROR: {e}")