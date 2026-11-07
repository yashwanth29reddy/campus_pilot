"""The end-to-end pipeline: mail -> classify -> extract -> calendar.

run_check() is the single entry point used by the CLI and can later be
wrapped in a scheduler (launchd / cron / a polling loop).
"""

from __future__ import annotations

from openai import OpenAI

from . import calendar_client, config as config_mod, extractor, gmail_client, notify, store
from .auth import get_calendar_service, get_gmail_service


def _warm_up(client, cfg: dict) -> None:
    """Force-load the model into RAM before the batch so the first email
    doesn't eat a cold-start timeout."""
    try:
        client.chat.completions.create(
            model=cfg["ollama_model"],
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0.0,
            extra_body={"keep_alive": "2h"},
            timeout=600,
        )
        print("  Model warmed up.")
    except Exception as e:  # noqa: BLE001 - warm-up is best-effort
        print(f"  Warm-up failed (will try anyway): {e}")


def run_check(cfg: dict | None = None) -> dict:
    cfg = cfg or config_mod.load_config()

    print(f"\nHi {cfg['name']}! Scanning your last {cfg['lookback_days']} days of mail...")

    gmail = get_gmail_service()
    emails = gmail_client.fetch_emails(
        gmail, lookback_days=cfg["lookback_days"], max_results=cfg["max_emails"]
    )
    print(f"  Found {len(emails)} message(s) to examine.\n")

    new_emails = [e for e in emails if not store.is_processed(e["message_id"])]
    skipped_dupes = len(emails) - len(new_emails)
    if skipped_dupes:
        print(f"  {skipped_dupes} already processed — skipping.")

    if not new_emails:
        print("Nothing new to process.")
        return {"added": 0, "skipped": 0, "irrelevant": 0, "failed": 0}

    calendar = get_calendar_service()
    client = OpenAI(base_url=cfg["ollama_url"], api_key="ollama", timeout=900)
    allowed = set(cfg["categories"])

    _warm_up(client, cfg)

    added = failed = caught = irrelevant = skipped = 0

    for email in new_emails:
        print(f"\n• {email['subject'][:80]}")
        print(f"  from {email['sender'][:60]}")

        parsed = extractor.classify_email(email, cfg, client=client)
        if parsed is None:
            store.mark_processed(email["message_id"], email["thread_id"], "failed")
            failed += 1
            continue

        if not extractor.categorize_raw(parsed, allowed):
            store.mark_processed(email["message_id"], email["thread_id"], "irrelevant")
            irrelevant += 1
            print(f"  → ignored ({parsed.get('reason', 'not in selected categories')})")
            continue

        # Dedup on event name + date so repeated mails for the same event
        # don't double-book.
        event_key = f"{parsed.get('date')}|{parsed.get('event_name','').lower().strip()}"
        if store.event_key_exists(event_key):
            store.mark_processed(email["message_id"], email["thread_id"], "duplicate",
                                 category=parsed.get("category", ""))
            skipped += 1
            print("  → duplicate event already in calendar, skipped")
            continue

        event_id = calendar_client.create_event(calendar, parsed, email["message_id"], cfg)
        if event_id:
            store.record_event(event_key, email["message_id"])
            store.mark_processed(
                email["message_id"],
                email["thread_id"],
                "added",
                category=parsed.get("category", ""),
                event_name=parsed.get("event_name", ""),
                calendar_event_id=event_id,
            )
            added += 1
            print(
                f"  ✓ ADDED → '{parsed.get('event_name')}' "
                f"({parsed.get('date')} {parsed.get('time_start', 'all-day')})"
            )
        else:
            store.mark_processed(email["message_id"], email["thread_id"], "failed",
                                 category=parsed.get("category", ""))
            failed += 1

    print("\n" + "=" * 60)
    print(f"SUMMARY — {added} added | {irrelevant} ignored | {skipped} dupes | {failed} failed | {caught}")

    # Only fire a notification when something actionable happened.
    if added or failed:
        msg = f"{added} event(s) added to Google Calendar"
        if failed:
            msg += f", {failed} failed (check logs)"
        notify.mac_notify("Campus Pilot", msg)

    return {"added": added, "ignored": irrelevant, "dupes": skipped, "failed": failed}