"""
main.py — Phase 1 CLI for AI Work Report Generator

Phase 1 commands only:
    python main.py --start      Start the background activity tracker
    python main.py --stop       Stop the tracker
    python main.py --pause      Pause tracking (privacy control)
    python main.py --resume     Resume tracking
    python main.py --status     Show today's activity log
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))

import database
import tracker as tracker_module

_tracker = tracker_module.Tracker()


def cmd_start():
    _tracker.start()
    print("\n[INFO] Tracker is running. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping tracker...")
        _tracker.stop()
        print("[INFO] Done. Run 'python main.py --status' to see your activity.")


def cmd_stop():
    database.init_db()
    database.set_tracker_state("stopped")
    print("[TRACKER] Stopped.")


def cmd_pause():
    database.init_db()
    if database.get_tracker_state() == "stopped":
        print("[INFO] Tracker is not running. Start it with: python main.py --start")
    else:
        database.set_tracker_state("paused")
        print("[TRACKER] Paused. Resume with: python main.py --resume")


def cmd_resume():
    database.init_db()
    database.set_tracker_state("running")
    print("[TRACKER] Resumed.")


def cmd_status():
    database.init_db()
    logs = database.get_today_logs()
    state = database.get_tracker_state()

    from collections import defaultdict
    print(f"\n📊 Today's Activity  |  Tracker: {state.upper()}  |  Events: {len(logs)}")
    print("━" * 60)

    if not logs:
        print("  No activity logged yet. Run: python main.py --start\n")
        return

    by_category = defaultdict(list)
    for log in logs:
        by_category[log["category"]].append(log)

    for category, events in by_category.items():
        print(f"\n  [{category}]  ({len(events)} events)")
        for evt in events[-5:]:
            ts = evt["timestamp"][11:16]
            print(f"    {ts}  {evt['details']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="AI Work Report Generator — Phase 1 (Tracker)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--start",  action="store_true", help="Start the tracker")
    group.add_argument("--stop",   action="store_true", help="Stop the tracker")
    group.add_argument("--pause",  action="store_true", help="Pause tracking")
    group.add_argument("--resume", action="store_true", help="Resume tracking")
    group.add_argument("--status", action="store_true", help="Show today's activity")

    args = parser.parse_args()

    if args.start:   cmd_start()
    elif args.stop:  cmd_stop()
    elif args.pause: cmd_pause()
    elif args.resume: cmd_resume()
    elif args.status: cmd_status()
    else:            parser.print_help()


if __name__ == "__main__":
    main()
