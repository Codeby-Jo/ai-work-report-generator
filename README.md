# 🤖 AI Work Report Generator

An automated end-of-day work report generator that silently tracks your activity in the background and uses AI to write a professional report for you — with one command.

Built with Python, SQLite, Groq (Llama 3.1), and python-docx.

---

## ✨ Features

- **📁 File Watcher** — Automatically detects which files you edit in real-time
- **💻 App Tracker** — Logs which applications you use and for how long
- **😴 Idle Detection** — Auto-pauses when you step away, auto-resumes when you return
- **🤖 AI Summary** — Sends compressed logs to Llama 3.1 AI to write a professional summary
- **📄 Word Document** — Automatically fills your company's `.docx` report template
- **🔒 Privacy First** — Only tracks file *names*, never reads the content of your files

---

## 🏗️ Project Architecture

```
ai-work-report-generator/
│
├── core/                     # Phase 1: Background Tracker
│   ├── tracker.py            # File watcher + App poller + Idle monitor
│   ├── database.py           # SQLite read/write operations
│   └── check_db.py           # CLI tool to inspect logged data
│
├── reporting/                # Phase 2 & 3: AI + Document Generation
│   ├── generator.py          # Fetches logs, calls Groq AI, returns JSON
│   └── template_filler.py    # Injects AI output into Word template
│
├── main.py                   # Single entry point — all CLI commands
├── requirements.txt          # All Python dependencies
├── .env                      # Secret API key (NOT committed to GitHub)
└── EOD_Report_Template.docx  # Blank company Word template
```

---

## ⚙️ Setup

### 1. Clone the repository
```bash
git clone https://github.com/Codeby-Jo/ai-work-report-generator.git
cd ai-work-report-generator
```

### 2. Create a virtual environment and install dependencies
```bash
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip3 install -r requirements.txt
```

### 3. Get a free API key
Go to [console.groq.com/keys](https://console.groq.com/keys) and create a free API key.

### 4. Create a `.env` file
```bash
GROQ_API_KEY=gsk_your_key_here
```

### 5. Add your Word template
Place your blank company `.docx` report template in the project folder and name it exactly:
```
EOD_Report_Template.docx
```

---

## 🚀 How to Use

### Start tracking your work
```bash
python3 main.py --start
```
Run this in **Terminal 1** and leave it running in the background all day.

### Control the tracker (from Terminal 2)
```bash
python3 main.py --pause     # Pause tracking (e.g., lunch break)
python3 main.py --resume    # Resume tracking
python3 main.py --status    # See what has been logged today
python3 main.py --stop      # Stop the tracker
```

### Generate your End-of-Day report
```bash
python3 main.py --generate
```
This single command will:
1. Fetch all activity from the database
2. Send it to the Groq AI (Llama 3.1)
3. Fill your Word template with the AI summary
4. Save `EOD_Report_YYYY-MM-DD.docx`

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| `watchdog` | Real-time file system monitoring |
| `psutil` | Active application detection |
| `sqlite3` | Local database storage |
| `threading` | Concurrent background tasks |
| `openai` SDK | API communication with Groq |
| `python-dotenv` | Secure environment variable management |
| `python-docx` | Microsoft Word document manipulation |

---

## 👨‍💻 Author

**Joshua Raja R**  
Internship Project — June 2026
