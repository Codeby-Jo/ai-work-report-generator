"""
dashboard/app.py — Phase 4 Web Dashboard
FastAPI-powered web UI for AI Work Report Generator.

Run with:
    uvicorn dashboard.app:app --reload --port 8000
Or:
    python3 -m dashboard.app
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from core import database
from reporting import generator, template_filler

app = FastAPI(title="AI Work Report Generator", version="1.0.0")

# ── Static files & templates ──────────────────────────────────────────────────
DASHBOARD_DIR = Path(__file__).parent
STATIC_DIR    = DASHBOARD_DIR / "static"
TEMPLATES_DIR = DASHBOARD_DIR / "templates"

STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Disable Jinja2 cache — required for Python 3.14 compatibility
from jinja2 import Environment, FileSystemLoader
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    auto_reload=True,
    cache_size=0,          # disables the LRU cache that breaks on Python 3.14
)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env = _jinja_env


# ── Startup banner ────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_banner():
    api_key_status = "✅ Found" if os.getenv("GROQ_API_KEY") else "❌ NOT SET (add to .env)"
    print("\n" + "=" * 60)
    print("  🤖 AI Work Report Generator — Dashboard is LIVE!")
    print("=" * 60)
    print(f"  🌐 Open your browser and go to:")
    print(f"     👉  http://127.0.0.1:8000")
    print(f"  🔑 GROQ_API_KEY : {api_key_status}")
    print("=" * 60 + "\n")



# ── Helper ────────────────────────────────────────────────────────────────────

def _category_color(category: str) -> str:
    colors = {
        "Coding":        "#6366f1",
        "Research":      "#06b6d4",
        "Meeting":       "#f59e0b",
        "Documentation": "#10b981",
        "Debugging":     "#ef4444",
        "Code Review":   "#8b5cf6",
        "Uncategorised": "#6b7280",
    }
    return colors.get(category, "#6b7280")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    database.init_db()
    logs      = database.get_today_logs()
    state     = database.get_tracker_state()

    CAT_COLORS = {
        "Coding":        "#6366f1",
        "Research":      "#06b6d4",
        "Meeting":       "#f59e0b",
        "Documentation": "#10b981",
        "Debugging":     "#ef4444",
        "Code Review":   "#8b5cf6",
        "Uncategorised": "#6b7280",
    }
    CAT_TEXT_COLORS = {
        "Coding":        "#818cf8",
        "Research":      "#67e8f9",
        "Meeting":       "#fcd34d",
        "Documentation": "#6ee7b7",
        "Debugging":     "#fca5a5",
        "Code Review":   "#c4b5fd",
        "Uncategorised": "#9ca3af",
    }

    # Category breakdown
    from collections import defaultdict
    by_category = defaultdict(list)
    for log in logs:
        by_category[log["category"]].append(log)

    category_stats = sorted(
        [
            {
                "name":  cat,
                "count": len(events),
                "color": CAT_COLORS.get(cat, "#6b7280"),
            }
            for cat, events in by_category.items()
        ],
        key=lambda x: -x["count"]
    )

    max_count = category_stats[0]["count"] if category_stats else 1

    # Recent events (last 10) with pre-computed colors
    recent = []
    for evt in reversed(logs[-10:]):
        cat = evt.get("category", "Uncategorised")
        recent.append({
            **evt,
            "dot_color":  CAT_COLORS.get(cat, "#6b7280"),
            "text_color": CAT_TEXT_COLORS.get(cat, "#9ca3af"),
        })

    # Find past reports
    import glob
    project_root = os.path.join(os.path.dirname(__file__), "..")
    report_files = glob.glob(os.path.join(project_root, "EOD_Report_*.docx"))
    past_reports = [os.path.basename(f) for f in sorted(report_files, reverse=True)]

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "tracker_state":   state,
            "total_events":    len(logs),
            "category_stats":  category_stats,
            "max_count":       max_count,
            "recent_events":   recent,
            "today":           datetime.now().strftime("%A, %d %B %Y"),
            "has_api_key":     bool(os.getenv("GROQ_API_KEY")),
            "past_reports":    past_reports,
        }
    )


@app.get("/api/status")
async def api_status():
    """Live tracker status — polled every 10 s by the dashboard."""
    database.init_db()
    logs  = database.get_today_logs()
    state = database.get_tracker_state()

    from collections import defaultdict
    by_category = defaultdict(int)
    for log in logs:
        by_category[log["category"]] += 1

    return JSONResponse({
        "tracker_state":  state,
        "total_events":   len(logs),
        "by_category":    dict(by_category),
        "last_updated":   datetime.now().strftime("%H:%M:%S"),
    })


@app.post("/api/generate")
async def api_generate():
    """Generate AI report + fill template. Returns the report JSON."""
    if not os.getenv("GROQ_API_KEY"):
        return JSONResponse({"error": "GROQ_API_KEY not set in .env"}, status_code=400)

    report = generator.generate_report()
    if not report:
        return JSONResponse({"error": "No activity logs found. Work for a while first!"}, status_code=400)

    # Fill template
    template_filler.fill_template(report)

    return JSONResponse({"success": True, "report": report})


@app.get("/api/download")
async def api_download(file: str = None):
    """Download the most recently generated EOD report, or a specific past report."""
    if file and file.startswith("EOD_Report_") and file.endswith(".docx"):
        filename = file
    else:
        today_str = datetime.now().strftime("%Y-%m-%d")
        filename  = f"EOD_Report_{today_str}.docx"
        
    filepath  = Path(__file__).parent.parent / filename

    if not filepath.exists():
        return JSONResponse({"error": f"File {filename} not found."}, status_code=404)

    from fastapi import Response
    try:
        with open(filepath, "rb") as f:
            content = f.read()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/logs")
async def api_logs():
    """Return all today's logs as JSON."""
    database.init_db()
    logs = database.get_today_logs()
    return JSONResponse({"logs": logs})


@app.post("/api/log")
async def api_receive_log(request: Request):
    """Receive a tracking event directly from the VS Code Extension."""
    try:
        data = await request.json()
        filename = data.get("filename", "Unknown")
        category = data.get("category", "Coding")
        event_type = data.get("event_type", "vscode_event")
        details = data.get("details", f"VS Code activity: {filename}")
        
        database.init_db()
        database.log_event(event_type, details, category)
        return JSONResponse({"status": "success"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/settings/idle")
async def api_set_idle_timeout(request: Request):
    """Update the IDLE_THRESHOLD_MINUTES variable inside core/tracker.py."""
    try:
        data = await request.json()
        new_timeout = int(data.get("timeout", 15))
        
        tracker_path = Path(__file__).parent.parent / "core" / "tracker.py"
        with open(tracker_path, "r") as f:
            content = f.read()
            
        import re
        new_content = re.sub(
            r"IDLE_THRESHOLD_MINUTES\s*=\s*\d+",
            f"IDLE_THRESHOLD_MINUTES = {new_timeout}",
            content
        )
        
        with open(tracker_path, "w") as f:
            f.write(new_content)
            
        return JSONResponse({"status": "success", "timeout": new_timeout})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8000, reload=True)
