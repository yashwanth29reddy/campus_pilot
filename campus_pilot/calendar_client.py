"""Write events to Google Calendar.

Creates timed or all-day events from the Qwen-extracted details, tagged
with the source Gmail message id so we can trace/maintain them.
"""

from __future__ import annotations

import datetime as dt

from googleapiclient.errors import HttpError


def _iso(d: str, t: str, timezone: str) -> dict:
    """Build an RFC3339 start/end dict for the Calendar API."""
    if t:
        return {"dateTime": f"{d}T{t}:00", "timeZone": timezone}
    return {"date": d}


def create_event(service, parsed: dict, message_id: str, cfg: dict) -> str | None:
    """Insert one event; returns its calendar event id or None on failure."""