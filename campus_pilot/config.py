"""User preferences: which email categories to track, model settings, etc.

First run triggers setup_wizard() which interactively collects preferences
and writes them to config.json next to this package.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config.json"

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

DEFAULT_CONFIG = {
    "name": "",
    "categories": ["exams", "assignments", "events"],
    "categories_have_zones": True,
    "max_emails": 30,
    "lookback_days": 14,
    "timezone": "Asia/Kolkata",
    "calendar_id": "primary",
    "ollama_url": "http://localhost:11434/v1",
    "ollama_model": "qwen3.5:9b",
    "reminder_minutes": 60,
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json not found at {CONFIG_PATH}. Run 'python main.py setup' first."
        )
    with CONFIG_PATH.open() as f:
        cfg = json.load(f)
    merged = {**DEFAULT_CONFIG, **cfg}
    return merged


def save_config(cfg: dict) -> None:
    with CONFIG_PATH.open("w") as f:
        json.dump(cfg, f, indent=2)
    print(f"\nSaved preferences to {CONFIG_PATH}\n")


def setup_wizard() -> dict:
    print("=" * 60)
    print("  CAMPUS PILOT SETUP WIZARD")
    print("=" * 60)

    name = input("\nWhat should I call you? ").strip() or "student"

    print("\nWhich email categories should I track for your calendar?")
    print("(Enter numbers separated by commas, e.g. 1,2,3 — or 'all')")
    keys = list(CATEGORY_LABELS)
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {CATEGORY_LABELS[key]}")

    answer = input("\nYour selection: ").strip().lower()
    selected = []
    if answer == "all":
        selected = keys
    else:
        try:
            nums = [int(x.strip()) for x in answer.split(",") if x.strip()]
            for n in nums:
                if 1 <= n <= len(keys):
                    selected.append(keys[n - 1])
        except ValueError:
            pass
    if not selected:
        print("No valid selection — keeping default categories.")
        selected = list(DEFAULT_CONFIG["categories"])

    print(f"\nCategories you'll track: {', '.join(CATEGORY_LABELS[k] for k in selected)}")

    days = input("\nHow many days of past mail should I scan on first run? [14] ").strip()
    try:
        days = int(days)
    except ValueError:
        days = 14

    cfg = dict(DEFAULT_CONFIG)
    cfg["name"] = name
    cfg["categories"] = selected
    cfg["lookback_days"] = days
    save_config(cfg)
    return cfg


def has_config() -> bool:
    return CONFIG_PATH.exists()