"""
check_db.py — Database inspection utility for AI Work Report Generator

Quick tool to view the contents of work_activity.db from the terminal.

Usage:
    python check_db.py                    Show today's logs (default)
    python check_db.py --all              Show last 100 logs
    python check_db.py --week             Show last 7 days of logs
    python check_db.py --stats            Show statistics by category
    python check_db.py --clear-today      Clear today's logs (for testing)
"""

import sys
import os
import argparse
from datetime import datetime
from collections import defaultdict
from core import database

sys.path.insert(0, os.path.dirname(__file__))


def print_logs(logs: list[dict], title: str = "Activity Logs"):
    """Pretty-print a list of log dicts."""
    print(f"\n{'━' * 60}")
    print(f"  {title}")
    print(f"{'━' * 60}")

    if not logs:
        print("  No logs found.\n")
        return

    print(f"  Total events: {len(logs)}\n")

    current_date = None
    for log in logs:
        ts = log.get("timestamp", "")
        date_part = ts[:10] if len(ts) >= 10 else "unknown"
        time_part = ts[11:19] if len(ts) >= 19 else ts

        if date_part != current_date:
            print(f"\n  📅 {date_part}")
            print(f"  {'─' * 50}")
            current_date = date_part

        category = log.get("category", "—")
        event_type = log.get("event_type", "—")
        details = log.get("details", "—")
        log_id = log.get("id", "?")

        # Colour-code categories in terminal (ANSI codes)
        colour_map = {
            "Coding":        "\033[94m",   # blue
            "Research":      "\033[96m",   # cyan
            "Meeting":       "\033[93m",   # yellow
            "Debugging":     "\033[91m",   # red
            "Documentation": "\033[95m",   # magenta
            "Code Review":   "\033[92m",   # green
            "Uncategorised": "\033[90m",   # grey
        }
        reset = "\033[0m"
        colour = colour_map.get(category, "\033[0m")

        print(f"  [{log_id:>4}] {time_part}  {colour}{category:<15}{reset}  {event_type:<12}  {details[:60]}")

    print(f"\n{'━' * 60}\n")


def print_stats(logs: list[dict]):
    """Print category statistics from logs."""
    if not logs:
        print("No logs to analyse.\n")
        return

    by_category: dict = defaultdict(int)
    by_type: dict = defaultdict(int)

    for log in logs:
        by_category[log.get("category", "Uncategorised")] += 1
        by_type[log.get("event_type", "unknown")] += 1

    total = len(logs)

    print(f"\n{'━' * 60}")
    print(f"  Activity Statistics")
    print(f"{'━' * 60}")
    print(f"\n  Total events: {total}\n")

    print("  By Category:")
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        pct = (count / total) * 100
        bar = "█" * int(pct / 4)
        print(f"    {cat:<18}  {count:>4} events  {pct:5.1f}%  {bar}")

    print("\n  By Event Type:")
    for etype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        pct = (count / total) * 100
        print(f"    {etype:<18}  {count:>4} events  {pct:5.1f}%")

    # Date range
    timestamps = [l["timestamp"] for l in logs if l.get("timestamp")]
    if timestamps:
        earliest = min(timestamps)[:19]
        latest = max(timestamps)[:19]
        print(f"\n  Date range: {earliest}  →  {latest}")

    print(f"\n{'━' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="python check_db.py",
        description="Inspect the work_activity.db SQLite database",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Show last 100 log entries (all time)"
    )
    parser.add_argument(
        "--week", action="store_true",
        help="Show last 7 days of activity"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show activity statistics by category"
    )
    parser.add_argument(
        "--clear-today", action="store_true",
        help="Delete all logs for today (for testing)"
    )
    parser.add_argument(
        "--state", action="store_true",
        help="Show current tracker state"
    )

    args = parser.parse_args()

    # Initialise DB (creates tables if needed)
    database.init_db()

    if args.clear_today:
        confirm = input("⚠️  Delete all of today's logs? [y/N]: ").strip().lower()
        if confirm == "y":
            database.clear_today_logs()
            print("✅ Today's logs cleared.")
        else:
            print("Cancelled.")

    elif args.state:
        state = database.get_tracker_state()
        print(f"\n  Tracker state: {state.upper()}\n")

    elif args.stats:
        if args.week:
            logs = database.get_week_logs()
            print_stats(logs)
        elif args.all:
            logs = database.get_all_logs(500)
            print_stats(logs)
        else:
            logs = database.get_today_logs()
            print_stats(logs)

    elif args.week:
        logs = database.get_week_logs()
        print_logs(logs, "Last 7 Days — Activity Log")

    elif args.all:
        logs = database.get_all_logs(100)
        print_logs(logs, "Last 100 Events — All Time")

    else:
        # Default: show today's logs
        logs = database.get_today_logs()
        today = datetime.now().strftime("%Y-%m-%d")
        print_logs(logs, f"Today's Activity — {today}")


if __name__ == "__main__":
    main()
