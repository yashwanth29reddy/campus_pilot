"""OAuth 2.0 handling for Gmail + Google Calendar.

On first use this opens a browser window to authorize with your Google
account. The refresh token is stored in token.json so later runs are
automatic and don't need re-authorization.
"""

from __future__ import annotations

import os
from pathlib import Path