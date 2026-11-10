"""macOS notifications so Campus Pilot can ping you when it adds events."""

from __future__ import annotations

import subprocess


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')