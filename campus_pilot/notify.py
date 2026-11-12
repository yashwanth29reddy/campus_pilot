"""macOS notifications so Campus Pilot can ping you when it adds events."""

from __future__ import annotations

import subprocess


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def mac_notify(title: str, message: str) -> None:
    """Fire a macOS notification (no-op if osascript is unavailable)."""
    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except Exception:  # noqa: BLE001 - notifications are best-effort
        pass