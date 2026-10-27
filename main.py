#!/usr/bin/env python3
"""Campus Pilot CLI.

Usage:
    python main.py setup                  # first run: preferences + Google login
    python main.py check                  # scan mail, add events to calendar
    python main.py status                 # show what was processed so far
    python main.py calendar               # open this machine's default calendar app
    python main.py install-service        # auto-check mail every 4 hours (launchd)
    python main.py uninstall-service      # stop auto-checking
"""

from __future__ import annotations

import argparse
import sys


def cmd_setup() -> None:
    from campus_pilot import config as config_mod
    from campus_pilot import auth

    print("\n[Step 1/2] Preferences\n")
    config_mod.setup_wizard()

    print("\n[Step 2/2] Google authorization\n")
    auth.ensure_authorized()

    print("\nAll set! Run 'python main.py check' to scan your mail.")


def cmd_check() -> None:
    from campus_pilot import config as config_mod
    from campus_pilot.pipeline import run_check

    try:
        cfg = config_mod.load_config()
    except FileNotFoundError as e:
        print(e)
        print("Run 'python main.py setup' first.")
        sys.exit(1)
    run_check(cfg)


def cmd_status() -> None:
    from campus_pilot import store

    rows = store.summary()
    if not rows:
        print("Nothing processed yet. Run 'python main.py check'.")
        return
    print(f"{'status':<12} {'category':<16} {'event':<30} {'calendar id':<30}")
    print("-" * 100)
    for status, category, event_name, cal_id, processed_at in rows:
        print(f"{status:<12} {category:<16} {(event_name or '')[:28]:<30} {(cal_id or '')[:28]:<30}")


def cmd_calendar() -> None:
    import subprocess

    subprocess.run(["open", "-a", "Calendar"])


def cmd_install_service() -> None:
    from campus_pilot import scheduler

    scheduler.install()


def cmd_uninstall_service() -> None:
    from campus_pilot import scheduler

    scheduler.uninstall()


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Pilot — AI mail-to-calendar")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="first-run wizard + Google login")
    sub.add_parser("check", help="scan mail and add events to Google Calendar")
    sub.add_parser("status", help="show processed history")
    sub.add_parser("calendar", help="open the Calendar app")
    sub.add_parser("install-service", help="auto-check mail every 4 hours (launchd)")
    sub.add_parser("uninstall-service", help="stop auto-checking")

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "check": cmd_check,
        "status": cmd_status,
        "calendar": cmd_calendar,
        "install-service": cmd_install_service,
        "uninstall-service": cmd_uninstall_service,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()