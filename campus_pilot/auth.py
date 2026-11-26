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