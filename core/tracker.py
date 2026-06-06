"""
tracker.py — Background activity tracker for AI Work Report Generator

Three concurrent background jobs:
  1. File Watcher    — uses watchdog to monitor my_tracked_workspace/ for
                       file create/modify events
  2. App Poller      — uses psutil to poll the active window every 60 seconds
  3. Idle Monitor    — detects if user is away and auto-pauses/resumes tracking

Both write to SQLite via database.py.
Includes start / stop / pause / resume controls.
Auto-pauses after IDLE_THRESHOLD_MINUTES of no keyboard/mouse activity.
"""

import os
import threading
import time
import platform
from datetime import datetime

import subprocess
import ctypes
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import defaultdict
from core import database

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), "..", "my_tracked_workspace")
APP_POLL_INTERVAL = 60        # seconds between active-app polls
IDLE_THRESHOLD_MINUTES = 15   # auto-pause after 15 minutes of inactivity
IDLE_CHECK_INTERVAL = 60      # how often to check idle state (seconds)

# File extensions considered coding activity
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".cs",
    ".go", ".rb", ".php", ".html", ".css", ".scss", ".json", ".yaml",
    ".yml", ".toml", ".sh", ".md", ".sql", ".rs", ".kt", ".swift",
}

# App names → activity category mapping
APP_CATEGORY_MAP = {
    # Meetings (High priority - check before generic browsers)
    "zoom":         "Meeting",
    "meet":         "Meeting",
    "teams":        "Meeting",
    "slack":        "Meeting",
    
    # Documentation
    "notion":       "Documentation",
    "obsidian":     "Documentation",
    "libreoffice":  "Documentation",
    "word":         "Documentation",

    # Coding
    "code":         "Coding",
    "vscode":       "Coding",
    "pycharm":      "Coding",
    "intellij":     "Coding",
    "webstorm":     "Coding",
    "vim":          "Coding",
    "nvim":         "Coding",
    "terminal":     "Coding",
    "konsole":      "Coding",
    "gnome-terminal": "Coding",
    
    # Browsers (Low priority - check last)
    "chrome":       "Research",
    "chromium":     "Research",
    "firefox":      "Research",
    "brave":        "Research",
    "safari":       "Research",
}


# ──────────────────────────────────────────────────────────────────────────────
# Idle Time Detection
# ──────────────────────────────────────────────────────────────────────────────

def get_idle_seconds() -> float:
    """
    Return how many seconds the user has been idle (no keyboard/mouse activity).
    Supports Linux (xprintidle) and Windows (GetLastInputInfo).
    Falls back to 0 (assume active) if unavailable.
    """
    system = platform.system()

    if system == "Linux":
        # Try Wayland (GNOME) first
        try:
            import subprocess
            result = subprocess.run(
                ["dbus-send", "--print-reply", "--dest=org.gnome.Mutter.IdleMonitor", 
                 "/org/gnome/Mutter/IdleMonitor/Core", "org.gnome.Mutter.IdleMonitor.GetIdletime"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                # Output looks like: uint64 13049
                ms = int(result.stdout.strip().split()[-1])
                return ms / 1000.0
        except Exception:
            pass

        # Fallback to X11 xprintidle
        try:
            import subprocess
            result = subprocess.run(
                ["xprintidle"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                return int(result.stdout.strip()) / 1000.0  # ms → seconds
        except (FileNotFoundError, Exception):
            pass

    elif system == "Windows":
        try:
            import ctypes
            
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint),
                    ("dwTime", ctypes.c_uint)
                ]
                
            lastInputInfo = LASTINPUTINFO()
            lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
            
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo)):
                # GetTickCount returns time since system started in ms
                millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
                return millis / 1000.0
        except Exception:
            pass

    return 0.0  # fallback: assume user is active


def _idle_monitor_loop(
    stop_event: threading.Event,
    manual_pause_flag: threading.Event,
    paused_flag: threading.Event,
):
    """
    Monitors user idle time every IDLE_CHECK_INTERVAL seconds.

    - If idle > IDLE_THRESHOLD_MINUTES → auto-pause (sets paused_flag)
    - If user comes back (idle drops) → auto-resume (clears paused_flag)
    - Does NOT interfere if user manually paused via --pause
    """
    threshold_seconds = IDLE_THRESHOLD_MINUTES * 60
    was_auto_paused = False

    while not stop_event.is_set():
        stop_event.wait(timeout=IDLE_CHECK_INTERVAL)
        if stop_event.is_set():
            break

        # Don't interfere with manual pause
        if manual_pause_flag.is_set():
            was_auto_paused = False
            continue

        idle_secs = get_idle_seconds()

        if idle_secs >= threshold_seconds and not paused_flag.is_set():
            # User has been idle too long — auto-pause
            paused_flag.set()
            was_auto_paused = True
            idle_mins = int(idle_secs // 60)
            database.log_event(
                "tracker_state",
                f"Auto-paused: no activity for {idle_mins} minutes",
                "Uncategorised"
            )
            print(f"[TRACKER] Auto-paused — no activity for {idle_mins} min")

        elif idle_secs < threshold_seconds and was_auto_paused and paused_flag.is_set():
            # User is back — auto-resume
            paused_flag.clear()
            was_auto_paused = False
            database.log_event(
                "tracker_state",
                "Auto-resumed: user activity detected",
                "Uncategorised"
            )
            print("[TRACKER] Auto-resumed — user activity detected")


def _db_sync_loop(
    stop_event: threading.Event,
    manual_pause_flag: threading.Event,
    paused_flag: threading.Event,
):
    """
    Checks the database 'tracker_state' every 2 seconds.
    This allows a command from Terminal 2 (main.py --pause) to communicate
    with the running process in Terminal 1.
    """
    while not stop_event.is_set():
        state = database.get_tracker_state()
        if state == "paused" and not manual_pause_flag.is_set():
            manual_pause_flag.set()
            paused_flag.set()
        elif state == "running" and manual_pause_flag.is_set():
            manual_pause_flag.clear()
            # We clear paused_flag ONLY if we are resuming from a manual pause
            # (Idle monitor might still keep it paused if idle, but this is simple enough)
            paused_flag.clear()
        stop_event.wait(timeout=2.0)


def _classify_extension(filepath: str) -> str:
    """Return activity category based on file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in CODE_EXTENSIONS:
        return "Coding"
    if ext in {".md", ".txt", ".rst", ".docx", ".pdf"}:
        return "Documentation"
    return "Uncategorised"


def _classify_app(app_name: str) -> str:
    """Return activity category based on active application name."""
    name_lower = app_name.lower()
    for keyword, category in APP_CATEGORY_MAP.items():
        if keyword in name_lower:
            return category
    return "Uncategorised"


# ──────────────────────────────────────────────────────────────────────────────
# Active Window Detection (cross-platform)
# ──────────────────────────────────────────────────────────────────────────────

def get_active_window_name() -> str:
    """
    Return the name of the currently active/focused application.
    Works on Linux (via xdotool or wmctrl), macOS, and Windows.
    Falls back to 'Unknown' if detection fails.
    """
    system = platform.system()

    if system == "Linux":
        # Try xdotool first (most common on Linux)
        try:
            import subprocess
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, Exception):
            pass

        # Fallback: try wmctrl
        try:
            import subprocess
            result = subprocess.run(
                ["wmctrl", "-a", ":ACTIVE:", "-v"],
                capture_output=True, text=True, timeout=2
            )
            if result.stdout:
                return result.stdout.strip()
        except (FileNotFoundError, Exception):
            pass

        # Fallback: use psutil to get a list of running app names
        try:
            import psutil
            important_apps = []
            known_apps = ["zoom", "teams", "slack", "chrome", "firefox", "brave", "code", "pycharm", "terminal"]
            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info["name"].lower()
                    if any(app in name for app in known_apps):
                        important_apps.append(name)
                except Exception:
                    pass
            if important_apps:
                return ", ".join(set(important_apps[:3]))
        except Exception:
            pass

    elif system == "Darwin":  # macOS
        try:
            import subprocess
            script = 'tell application "System Events" to get name of first application process whose frontmost is true'
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    elif system == "Windows":
        try:
            import ctypes
            import psutil
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc = psutil.Process(pid.value)
            return proc.name()
        except Exception:
            pass

    return "Unknown"


# ──────────────────────────────────────────────────────────────────────────────
# File System Watcher
# ──────────────────────────────────────────────────────────────────────────────

class WorkspaceEventHandler(FileSystemEventHandler):
    """Handles file system events inside the tracked workspace directory."""

    def __init__(self, paused_flag: threading.Event):
        super().__init__()
        self._paused = paused_flag
        self._last_logged: dict[str, str] = {}  # filepath → last logged timestamp

    def _should_log(self, filepath: str) -> bool:
        """Debounce: only log same file again after 30 seconds."""
        now = datetime.now().isoformat()
        last = self._last_logged.get(filepath)
        if last is None:
            self._last_logged[filepath] = now
            return True
        elapsed = (datetime.fromisoformat(now) - datetime.fromisoformat(last)).total_seconds()
        if elapsed >= 30:
            self._last_logged[filepath] = now
            return True
        return False

    def on_modified(self, event):
        if self._paused.is_set() or event.is_directory:
            return
        filepath = event.src_path
        if self._should_log(filepath):
            filename = os.path.basename(filepath)
            category = _classify_extension(filepath)
            details = f"Modified file: {filename} (in workspace)"
            database.log_event("file_change", details, category)
            print(f"[TRACKER] {category} — {details}")

    def on_created(self, event):
        if self._paused.is_set() or event.is_directory:
            return
        filepath = event.src_path
        filename = os.path.basename(filepath)
        category = _classify_extension(filepath)
        details = f"Created file: {filename} (in workspace)"
        database.log_event("file_change", details, category)
        print(f"[TRACKER] {category} — {details}")


# ──────────────────────────────────────────────────────────────────────────────
# App Poller Thread
# ──────────────────────────────────────────────────────────────────────────────

def _app_poll_loop(stop_event: threading.Event, paused_flag: threading.Event):
    """
    Polls the active window every APP_POLL_INTERVAL seconds.
    Logs the active application to the database.
    """
    last_app = None
    while not stop_event.is_set():
        if not paused_flag.is_set():
            app_name = get_active_window_name()
            if app_name and app_name != "Unknown" and app_name != last_app:
                category = _classify_app(app_name)
                details = f"Active application: {app_name}"
                database.log_event("active_app", details, category)
                print(f"[TRACKER] {category} — {details}")
                last_app = app_name
        stop_event.wait(timeout=APP_POLL_INTERVAL)

# ──────────────────────────────────────────────────────────────────────────────
# Tracker Controller
# ──────────────────────────────────────────────────────────────────────────────

class Tracker:
    """
    Controls the background tracker.

    Three background threads:
      1. File Watcher  — detects file edits in my_tracked_workspace/
      2. App Poller    — logs active application every 60 seconds
      3. Idle Monitor  — auto-pauses after IDLE_THRESHOLD_MINUTES of inactivity
                         auto-resumes when user comes back

    Usage:
        tracker = Tracker()
        tracker.start()
        # ... user works ...
        tracker.pause()
        tracker.resume()
        tracker.stop()
    """

    def __init__(self):
        self._stop_event = threading.Event()
        self._paused_flag = threading.Event()
        self._manual_pause_flag = threading.Event()
        self._observer = None
        self._poll_thread = None
        self._idle_thread = None
        self._sync_thread = None

    def start(self):
        """Start the file watcher and app poller."""
        # Ensure workspace directory exists
        os.makedirs(WORKSPACE_DIR, exist_ok=True)

        # Initialise database
        database.init_db()
        database.set_tracker_state("running")

        # Reset events
        self._stop_event.clear()
        self._paused_flag.clear()

        # Start watchdog file observer
        event_handler = WorkspaceEventHandler(self._paused_flag)
        self._observer = Observer()
        self._observer.schedule(event_handler, WORKSPACE_DIR, recursive=True)
        self._observer.start()

        # 2. App Poller thread
        self._poll_thread = threading.Thread(
            target=_app_poll_loop,
            args=(self._stop_event, self._paused_flag),
            daemon=True,
            name="AppPoller",
        )
        self._poll_thread.start()

        # 3. Idle monitor thread
        self._idle_thread = threading.Thread(
            target=_idle_monitor_loop,
            args=(self._stop_event, self._manual_pause_flag, self._paused_flag),
            daemon=True,
            name="IdleMonitor",
        )
        self._idle_thread.start()

        # 4. DB Sync thread (Inter-Process Communication)
        self._sync_thread = threading.Thread(
            target=_db_sync_loop,
            args=(self._stop_event, self._manual_pause_flag, self._paused_flag),
            daemon=True,
            name="DbSync",
        )
        self._sync_thread.start()

        print(f"[TRACKER] Started. Watching: {WORKSPACE_DIR}")
        print(f"[TRACKER] App polling every {APP_POLL_INTERVAL}s")
        print("[TRACKER] Press Ctrl+C to stop, or use 'python main.py --stop'")

    def pause(self):
        """Pause tracking — no events are logged while paused."""
        self._paused_flag.set()
        database.set_tracker_state("paused")
        print("[TRACKER] Paused. Your activity is no longer being tracked.")

    def resume(self):
        """Resume tracking after a pause."""
        self._paused_flag.clear()
        database.set_tracker_state("running")
        print("[TRACKER] Resumed. Tracking is active again.")

    def stop(self):
        """Stop all tracking threads and observers."""
        self._stop_event.set()
        self._paused_flag.set()  # unblock the poll loop wait

        if self._observer:
            self._observer.stop()
            self._observer.join()

        if self._poll_thread:
            self._poll_thread.join(timeout=5)

        database.set_tracker_state("stopped")
        print("[TRACKER] Stopped.")

    def is_running(self) -> bool:
        return not self._stop_event.is_set() and not self._paused_flag.is_set()

    def status(self) -> str:
        return database.get_tracker_state()


# ──────────────────────────────────────────────────────────────────────────────
# Standalone run (for testing)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tracker = Tracker()
    tracker.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        tracker.stop()
