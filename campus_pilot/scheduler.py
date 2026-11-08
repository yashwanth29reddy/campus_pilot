"""Schedule Campus Pilot to run automatically via a macOS launchd agent.

Every N hours (default 4) the agent runs 'main.py check', so new VIT mail
keeps flowing into your Google Calendar without you touching anything.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
MAIN_SCRIPT = PROJECT_DIR / "main.py"
LOG_DIR = PROJECT_DIR / "logs"

LAUNCH_AGENT_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENT_DIR / "com.campuspilot.agent.plist"

CHECK_INTERVAL_SECONDS = 4 * 60 * 60  # every 4 hours
LABEL = "com.campuspilot.agent"

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{main}</string>
        <string>check</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/service.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/service-error.log</string>
</dict>
</plist>
"""


def install() -> None:
    LAUNCH_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    plist = PLIST_TEMPLATE.format(
        label=LABEL,
        python=VENV_PYTHON,
        main=MAIN_SCRIPT,
        interval=CHECK_INTERVAL_SECONDS,
        log_dir=LOG_DIR,
    )
    PLIST_PATH.write_text(plist)

    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True)

    print(f"Installed launchd agent: {PLIST_PATH}")
    print("Campus Pilot will now auto-check your mail every 4 hours.")
    print(f"Logs: {LOG_DIR / 'service.log'}")


def uninstall() -> None:
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    print("Removed launchd agent. Campus Pilot will no longer auto-run.")


def status() -> str:
    if not PLIST_PATH.exists():
        return "not installed"
    result = subprocess.run(
        ["launchctl", "print", f"gui/{__import__('os').getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
    )
    return "loaded & running" if result.returncode == 0 else "loaded (not running)"