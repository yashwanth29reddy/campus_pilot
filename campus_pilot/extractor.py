"""Classification + extraction using Qwen 3.5 9B served by local Ollama.

For each email we ask the model to return ONE structured JSON object:
whether the email is relevant to the user's chosen categories, and if so
the calendar-worthy details (name, date, time, location, category).

The prompt is deterministic (temperature 0) and pinned to JSON output so
we can parse results reliably.
"""

from __future__ import annotations

import json
import re

from openai import OpenAI
from openai import OpenAIError

CATEGORY_LABELS = {
    "exams": "Exams / quiz / tests",
    "assignments": "Assignments / deadlines",
    "events": "Campus events / fests",
    "placements": "Placements / internships",
    "higher-studies": "Masters / study abroad info",
    "sports": "Sports / clubs",
    "workshops": "Workshops / hackathons",
    "other": "Other academic notices",
}

SYSTEM_PROMPT = """You are CampusPilot, a precise calendar assistant for an Indian university student.
You read an email and decide if it contains a schedule-worthy event (exam, quiz, assignment
deadline, lecture, fest, placement drive, etc.).

Decide relevance against the user's SELECTED CATEGORIES first:
{selected_categories}

Rules:
- If the email is irrelevant to the selected categories, set "relevant": false.
- If relevant, extract the SINGLE most important event in it.
- Dates/times must be normalized: date as YYYY-MM-DD, times as 24h HH:MM.
- If no time is given, set time_start to "" and it becomes an all-day event.
- If the email mentions a date in context of being optional marketing
  ("register if interested") but IS in a selected category, still extract it.
  The category filter has already been applied by the user.
- Reason must be 1 short sentence explaining the choice.

Respond with ONLY a JSON object (no markdown fences):
{{
  "relevant": true,
  "category": "one of: exams, assignments, events, placements, higher-studies, sports, workshops, other",
  "event_name": "short event title",
  "date": "YYYY-MM-DD or empty",
  "time_start": "HH:MM or empty",
  "time_end": "HH:MM or empty",
  "location": "venue, campus building, or empty",
  "description": "1-2 sentence summary for the calendar",
  "reason": "short justification"
}}"""


def _make_client(cfg: dict) -> OpenAI:
    """Create an Ollama-compatible client. keep_alive keeps Qwen warm in RAM
    across the whole batch so we don't reload the model per email."""
    return OpenAI(base_url=cfg["ollama_url"], api_key="ollama", timeout=300)


def _clean_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.IGNORECASE).strip()
    if text.startswith("```"):
        text = text[3:].strip()
    if text.startswith("```"):
        text = text[3:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _log_debug(message_id: str, content: str) -> None:
    """Persist unparseable raw output so we can inspect model behaviour."""
    try:
        from pathlib import Path

        log = Path(__file__).resolve().parent.parent / "unparseable.log"
        with log.open("a") as f:
            f.write(f"--- message {message_id} ---\n{content[:4000]}\n\n")
    except Exception:  # noqa: BLE001 - logging must never break the pipeline
        pass


def classify_email(email: dict, cfg: dict, client: OpenAI | None = None) -> dict | None:
    """Run Qwen on one email and return the parsed classification dict.

    Retries once on unparseable output. Returns None on final failure.
    """

    selected_categories = ", ".join(CATEGORY_LABELS[c] for c in cfg.get("categories", []))
    system = SYSTEM_PROMPT.format(selected_categories=selected_categories)

    user = (
        f"EMAIL FROM: {email['sender']}\n"
        f"SUBJECT: {email['subject']}\n"
        f"DATE SENT: {email['date']}\n"
        f"BODY:\n{email['body']}\n"
        f"\nExtract the event from this email, if it is relevant to: {selected_categories}"
    )

    client = client or _make_client(cfg)

    last_was_json_fail = False
    for attempt in range(2):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if last_was_json_fail:
            messages.append({"role": "assistant", "content": "Here is my response:"})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous answer was NOT valid JSON. "
                        "Repeat it as a SINGLE raw JSON object only — no fences, "
                        "no text before or after the JSON."
                    ),
                }
            )
        try:
            resp = client.chat.completions.create(
                model=cfg["ollama_model"],
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout=300,
                extra_body={"keep_alive": "2h"},
            )
        except OpenAIError as e:
            print(f"  Qwen call failed (attempt {attempt + 1}): {e}")
            if attempt == 1:
                return None
            continue

        content = resp.choices[0].message.content or ""
        parsed = _clean_json(content)
        if parsed is not None:
            return parsed
        _log_debug(email["message_id"], content)
        last_was_json_fail = True

    print("  Qwen returned unparseable JSON after retry, skipping this email.")
    return None


def classify_email(email: dict, cfg: dict, client: OpenAI | None = None) -> dict | None:
    """Run Qwen on one email and return the parsed classification dict.

    Returns None on failure (network, invalid JSON, model error).
    """

    selected_categories = ", ".join(CATEGORY_LABELS[c] for c in cfg.get("categories", []))
    system = SYSTEM_PROMPT.format(selected_categories=selected_categories)

    user = (
        f"EMAIL FROM: {email['sender']}\n"
        f"SUBJECT: {email['subject']}\n"
        f"DATE SENT: {email['date']}\n"
        f"BODY:\n{email['body']}\n"
        f"\nExtract the event from this email, if it is relevant to: {selected_categories}"
    )

    try:
        client = client or _make_client(cfg)
        resp = client.chat.completions.create(
            model=cfg["ollama_model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            timeout=300,
        )
    except OpenAIError as e:
        print(f"  Qwen call failed: {e}")
        return None

    content = resp.choices[0].message.content or ""
    parsed = _clean_json(content)
    if parsed is None:
        print("  Qwen returned unparseable JSON, skipping this email.")
        return None

    return parsed


def categorize_raw(parsed: dict, allowed: set[str]) -> bool:
    """True if the parsed result is relevant AND in the user's categories."""
    if not parsed.get("relevant"):
        return False
    return parsed.get("category", "other") in allowed