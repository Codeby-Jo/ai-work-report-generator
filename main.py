"""
main.py — CLI for AI Work Report Generator

Commands:
    python main.py --start      Start the background activity tracker
    python main.py --stop       Stop the tracker
    python main.py --pause      Pause tracking (privacy control)
    python main.py --resume     Resume tracking
    python main.py --status     Show today's activity log
    python main.py --generate   Generate the AI EOD report (Phase 2)
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


def cmd_generate():
    """Trigger the OpenAI report generator."""
    import generator
    print("\n[INFO] Starting Phase 2: AI Report Generation...")
    
    # Check if GROQ_API_KEY is available
    if not os.getenv("GROQ_API_KEY"):
        print("[ERROR] GROQ_API_KEY is not set!")
        print("Please create a .env file and add your API key like this:")
        print("GROQ_API_KEY=gsk_your_key_here")
        return

    report = generator.generate_report()
    if report:
        print("\n" + "="*50)
        print(f"📄 REPORT: {report['report_title']}")
        print("="*50)
        print(f"\n📝 Summary:\n{report['summary']}\n")
        print("✅ Key Tasks:")
        for task in report['key_tasks']:
            print(f"  - {task}")
        print(f"\n🛑 Blockers:\n  {report['blockers']}")
        print("="*50 + "\n")
        
        # --- PHASE 3: Template Filling ---
        import template_filler
        template_filler.fill_template(report)
        
    else:
        print("[ERROR] Could not generate report. Check logs above.")



def main():
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="AI Work Report Generator CLI",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--start",  action="store_true", help="Start the tracker")
    group.add_argument("--stop",   action="store_true", help="Stop the tracker")
    group.add_argument("--pause",  action="store_true", help="Pause tracking")
    group.add_argument("--resume", action="store_true", help="Resume tracking")
    group.add_argument("--status", action="store_true", help="Show today's activity")
    group.add_argument("--generate", action="store_true", help="Generate AI work report")

    args = parser.parse_args()

    if args.start:   cmd_start()
    elif args.stop:  cmd_stop()
    elif args.pause: cmd_pause()
    elif args.resume: cmd_resume()
    elif args.status: cmd_status()
    elif args.generate: cmd_generate()
    else:            parser.print_help()


if __name__ == "__main__":
    main()
