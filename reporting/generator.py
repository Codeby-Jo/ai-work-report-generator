import os
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from core import database

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client to point to Groq's Free API instead!
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Define the expected JSON schema for the AI response
REPORT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "work_report",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "report_title": {
                    "type": "string",
                    "description": "A catchy, professional title for the day's work"
                },
                "summary": {
                    "type": "string",
                    "description": "A 2-3 sentence summary of what was accomplished today"
                },
                "key_tasks": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "3-5 bullet points detailing the specific technical tasks completed"
                },
                "tools_used": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of tools, languages, or technologies used today e.g. Python, VS Code, Git"
                },
                "blockers": {
                    "type": "string",
                    "description": "Any blockers or issues faced. Say 'None' if nothing obvious."
                },
                "next_steps": {
                    "type": "string",
                    "description": "What the developer plans to work on next — tomorrow's priorities"
                }
            },
            "required": ["report_title", "summary", "key_tasks", "tools_used", "blockers", "next_steps"],
            "additionalProperties": False
        }
    }
}

def compress_logs(logs: list[dict]) -> str:
    """
    Compress raw logs into a concise summary string to save tokens.
    Groups file modifications and counts application usage.
    """
    if not logs:
        return "No activity logged today."

    files_modified = set()
    apps_used = {}
    
    for log in logs:
        if log['event_type'] == 'file_change':
            # Extract just the filename from the details
            details = log['details']
            if 'file: ' in details:
                filename = details.split('file: ')[1].split(' ')[0]
                files_modified.add(filename)
        elif log['event_type'] == 'active_app':
            app = log['details'].replace('Active application: ', '')
            apps_used[app] = apps_used.get(app, 0) + 1

    # Sort apps by frequency
    sorted_apps = sorted(apps_used.items(), key=lambda x: x[1], reverse=True)
    top_apps = [f"{app} ({count} mins)" for app, count in sorted_apps if count > 2] # Only show if used more than 2 mins

    compressed = "Today's Activity Data:\n"
    compressed += f"Files Modified: {', '.join(files_modified) if files_modified else 'None'}\n"
    compressed += f"Main Applications Used: {', '.join(top_apps) if top_apps else 'None'}\n"
    
    return compressed

def generate_report() -> dict | None:
    """
    Fetch today's logs, send to OpenAI, and return the generated JSON report.
    """
    print("[GENERATOR] Fetching recent logs from database...")
    logs = database.get_week_logs()
    
    if not logs:
        print("[GENERATOR] No logs found for today. Cannot generate a report.")
        return None

    compressed_data = compress_logs(logs)
    print(f"[GENERATOR] Data compressed successfully.\n{compressed_data}\n")
    
    # NEW FEATURE: Pull git diff to get exact code changes!
    git_diff = ""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "diff", "HEAD"], 
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Limit to last 3000 characters so we don't blow up the AI token limit
            git_diff = result.stdout.strip()[-3000:]
            print("[GENERATOR] Successfully pulled Git Diffs for exact code details!")
    except Exception:
        pass

    print("[GENERATOR] Sending to AI (Llama 3.1)...")

    prompt = f"""
    You are an AI assistant tasked with generating a professional End-of-Day (EOD) work report for a software developer.
    
    Based on the following raw activity tracking data, generate a structured JSON report. 
    Deduce the high-level project or topic the developer is working on based on the file names and applications used.
    
    You MUST output valid JSON matching this exact structure:
    {{
      "report_title": "A catchy, professional title",
      "summary": "A 2-3 sentence summary of the work",
      "key_tasks": ["task 1", "task 2", "task 3"],
      "tools_used": ["Python", "VS Code", "Git"],
      "blockers": "Any blockers or issues faced. Say 'None' if nothing obvious.",
      "next_steps": "What to work on tomorrow or next session."
    }}
    
    Raw Data:
    {compressed_data}
    
    Exact Code Changes (Git Diff):
    {git_diff if git_diff else "No git diff available."}
    
    Important: Use the Exact Code Changes to describe *specifically* what the developer coded, not just the file names.
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a professional technical writer. Always output valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        # Parse the JSON response
        report_json = json.loads(response.choices[0].message.content)
        return report_json
        
    except Exception as e:
        print(f"[ERROR] Failed to generate report: {e}")
        return None

if __name__ == "__main__":
    report = generate_report()
    if report:
        print("\n" + "="*50)
        print(f"📄 REPORT: {report['report_title']}")
        print("="*50)
        print(f"\n📝 Summary:\n{report['summary']}\n")
        print("✅ Key Tasks:")
        for task in report['key_tasks']:
            print(f"  - {task}")
        print("\n🔧 Tools Used:")
        for tool in report.get('tools_used', []):
            print(f"  - {tool}")
        print(f"\n🛑 Blockers:\n  {report['blockers']}")
        print(f"\n➡️  Next Steps:\n  {report['next_steps']}")
        print("="*50 + "\n")
