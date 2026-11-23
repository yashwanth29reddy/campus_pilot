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

    date_str = parsed.get("date", "").strip()
    if not date_str:
        print("  No date extracted — skipping calendar write.")
        return None

    time_start = parsed.get("time_start", "").strip()
    time_end = parsed.get("time_end", "").strip()

    start = _iso(date_str, time_start, cfg["timezone"])
    if time_end:
        end = {"dateTime": f"{date_str}T{time_end}:00", "timeZone": cfg["timezone"]}
    elif time_start:
        # Default to 1 hour if the sender only gave a start time.
        st = dt.datetime.strptime(f"{date_str}T{time_start}", "%Y-%m-%dT%H:%M")
        end = {"dateTime": f"{(st + dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')}:00", "timeZone": cfg["timezone"]}
    else:
        end = {"date": date_str}

    body = {
        "summary": parsed.get("event_name", "University event").strip(),
        "description": parsed.get("description", ""),
        "start": start,
        "end": end,
        "location": parsed.get("location", "").strip(),
        "extendedProperties": {"private": {"campusPilotMessageId": message_id}},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": cfg.get("reminder_minutes", 60)}
            ],
        },
    }

    try:
        event = (
            service.events()
            .insert(calendarId=cfg.get("calendar_id", "primary"), body=body)
            .execute()
        )
        return event.get("id")
    except HttpError as e:
        print(f"  Calendar insert failed: {e.status_code} {e.reason}")
        return None