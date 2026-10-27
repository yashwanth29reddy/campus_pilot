"""Read emails from Gmail.

We fetch the most recent messages (optionally filtering by a lookback
window), decode the subject/sender/body into plain text, and return a
lightweight list of dicts for the extractor to process.
"""

from __future__ import annotations

import base64
import html
import re
from datetime import datetime, timedelta

from googleapiclient.errors import HttpError

MAX_BODY_CHARS = 3000


def _decode_data(data: str) -> str:
    try:
        raw = data.encode("ascii")
        return base64.urlsafe_b64decode(raw).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - never let one bad message kill the run
        return ""


def _plain_text_from_payload(payload: dict) -> str:
    mime = payload.get("mimeType", "").lower()
    body = payload.get("body", {}).get("data", "")

    if "text/plain" in mime and body:
        return _decode_data(body)

    if "text/html" in mime and body:
        raw = _decode_data(body)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        return html.unescape(re.sub(r"\s+", " ", text)).strip()

    for part in payload.get("parts", []):
        result = _plain_text_from_payload(part)
        if result:
            return result

    return ""


def fetch_emails(service, lookback_days: int = 14, max_results: int = 30) -> list[dict]:
    """Return up to `max_results` recent emails as dicts.

    Each dict: {message_id, subject, sender, date, snippet, body, thread_id}
    """
    newer_than = max(1, int(lookback_days))

    try:
        listing = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max_results, q=f"newer_than:{newer_than}d")
            .execute()
        )
    except HttpError as e:
        print(f"Gmail list failed: {e.status_code} {e.reason}")
        raise

    messages = listing.get("messages", [])
    emails = []

    for item in messages:
        msg_id = item["id"]
        try:
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except HttpError:
            continue

        headers = {h["name"].lower(): h["value"] for h in detail.get("payload", {}).get("headers", [])}
        payload = detail.get("payload", {})

        body = _plain_text_from_payload(payload)
        if not body:
            body = detail.get("snippet", "")

        emails.append(
            {
                "message_id": msg_id,
                "thread_id": detail.get("threadId", ""),
                "subject": headers.get("subject", "(no subject)"),
                "sender": headers.get("from", "unknown"),
                "date": headers.get("date", ""),
                "snippet": detail.get("snippet", ""),
                "body": body[:MAX_BODY_CHARS],
            }
        )

    return emails


def lookback_bounds(lookback_days: int) -> tuple[str, str]:
    """ISO start/end timestamps for the lookback window (for logs/debug)."""
    now = datetime.now()
    start = now - timedelta(days=lookback_days)
    return start.isoformat(), now.isoformat()