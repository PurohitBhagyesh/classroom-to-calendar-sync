# Google Classroom to Google Calendar & AI Automation 📅🤖

[![CI](https://github.com/purohitbhagyesh/classroom-to-calendar-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/purohitbhagyesh/classroom-to-calendar-sync/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

An end-to-end intelligent automation suite that synchronizes **Google Classroom** assignments, announcements, and course materials directly to **Google Calendar** and **Google Tasks**. Features smart **PDF deadline extraction** from syllabus/rubric attachments, **AI-powered homework solving** via Google Gemini, printable **Solution PDF compilation**, and automated **Gmail dispatching**.

---

## 🌟 Key Features

```
  ┌───────────────────────┐
  │   Google Classroom    │  (Courses, Coursework, Announcements, PDF Attachments)
  └──────────┬────────────┘
             │
             ▼
  ┌───────────────────────┐
  │ PDF Deadline Parser   │  (Regex + NLP: extracts submission dates, times & milestones)
  └──────────┬────────────┘
             ├─────────────────────────────────────────────────┐
             ▼                                                 ▼
  ┌───────────────────────┐                         ┌───────────────────────┐
  │ Google Calendar Sync  │                         │   Google Tasks Sync   │
  │ • Popups & Email Alerts                         │ • Actionable Checklists
  │ • Direct Links & Notes                          │ • RFC3339 Deadlines
  └──────────┬────────────┘                         └───────────────────────┘
             │
             ▼
  ┌───────────────────────┐
  │  Gemini AI Solver     │  (Solves assignment questions step-by-step)
  └──────────┬────────────┘
             │
             ├────────────────────────────────┐
             ▼                                ▼
  ┌───────────────────────┐        ┌───────────────────────┐
  │ ReportLab PDF Builder │        │   Gmail Dispatcher    │
  │ • Generates Solution  │        │ • Delivers solutions  │
  │   PDF Document        │        │   & PDF to inbox      │
  └───────────────────────┘        └───────────────────────┘
```

1. **Intelligent PDF Deadline & Date Extraction**:
   - Downloads attached assignment PDFs from Google Drive.
   - Extracts text and scans for submission deadlines (`"Submission Date: Oct 28 at 11:59 PM"`, `"Due on or before 15/11/2026"`).
   - Accurately distinguishes between timed deadlines and all-day submissions.

2. **Google Calendar & Tasks Synchronization**:
   - Automatically provisions a dedicated **"Google Classroom Deadlines"** calendar and Google Tasks list.
   - Sets multi-stage notifications: popup reminder **24 hours** and **2 hours** prior, plus email reminders.
   - Embeds direct links to the Google Classroom assignment and Google Drive PDF attachment.

3. **Gemini AI Assignment Solver**:
   - Analyzes questions from assignment PDFs using Gemini models.
   - Generates formatted markdown answers with step-by-step explanations, text diagrams, and code blocks.

4. **Printable PDF Generator & Gmail Dispatcher**:
   - Converts AI solutions into beautifully styled, printable PDF documents.
   - Automatically emails the solutions and PDF attachment to your inbox via Gmail API.

5. **Deduplication & State Persistence**:
   - Stores tracking hashes in local SQLite database (`sync_state.sqlite`).
   - Automatically patches and updates calendar events if an instructor changes the deadline.

6. **Continuous Watch & macOS Background Daemon**:
   - Run in watch mode (`python main.py watch --interval 30`) or install a silent background LaunchAgent (`./run.sh autostart`).

---

## 📋 Prerequisites & Permissions Guide

To allow the automation to access your Google Classroom, Drive, Calendar, Tasks, and Gmail, set up OAuth 2.0 Desktop Credentials:

### 1. Enable Google APIs
1. Visit the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new Google Cloud Project (e.g. `Classroom-Automation`).
3. Navigate to **APIs & Services > Library** and enable:
   - **Google Classroom API**
   - **Google Drive API**
   - **Google Calendar API**
   - **Google Tasks API**
   - **Gmail API** (for solution dispatching)

### 2. Configure OAuth Consent Screen
1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** user type and click **Create**.
3. Fill in the App Name (e.g., `Classroom Automation`) and your developer email.
4. Under **Test Users**, click **Add Users** and add your Google account email address.

### 3. Create OAuth 2.0 Client Credentials
1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. Set Application type to **Desktop app** and name it `Classroom Sync Desktop`.
4. Click **Create**, then click **Download JSON**.
5. Save the file as `credentials.json` in the project root:
   ```bash
   cp ~/Downloads/client_secret_*.json ./credentials.json
   ```

---

## 🚀 Quickstart Installation

### 1. Clone the Repository
```bash
git clone https://github.com/purohitbhagyesh/classroom-to-calendar-sync.git
cd classroom-to-calendar-sync
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables (Optional)
Copy `.env.example` to `.env` and configure your API keys and preferences:
```bash
cp .env.example .env
```
Edit `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
RECIPIENT_EMAIL=your_email@example.com
SYNC_TIMEZONE=auto
```

### 4. Authenticate
Run the one-time OAuth authentication flow:
```bash
python main.py setup
```
*A browser window will open asking you to sign in with your Google Account and approve the requested permissions.*

---

## 💻 CLI Usage & Commands

### 1. One-Time Synchronization
```bash
# Sync all courses (last 30 days)
python main.py sync

# Perform a dry-run (simulation without writing to Calendar/Tasks)
python main.py sync --dry-run

# Filter by course name
python main.py sync --filter "Computer Networks"

# Target a specific Google Calendar
python main.py sync --calendar-name "primary"
```

### 2. Continuous Background Watch Mode
```bash
# Run continuous sync every 30 minutes
python main.py watch --interval 30
```

### 3. Test PDF Deadline Extraction on Local Files
```bash
# Test extraction against any syllabus or assignment PDF
python main.py test-pdf path/to/assignment.pdf
```

### 4. Solve Assignment PDF with Gemini AI
```bash
# Solve questions, compile PDF solution, and email it
python main.py solve path/to/assignment.pdf \
    --course "Operating Systems" \
    --title "Process Scheduling Lab" \
    --email "your_email@example.com"
```

### 5. Check Local Sync Database Status
```bash
python main.py status
```

---

## 🍎 macOS Background Daemon (LaunchAgent)

Automate synchronization in the background on macOS:

```bash
# Install and activate background sync daemon (runs every 4 days)
./run.sh autostart

# Check status
./run.sh status

# Stop and remove background daemon
./run.sh stop-autostart
```

---

## 📁 Repository Structure

```
classroom-to-calendar-sync/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated CI test workflow
├── config.py                      # Global configurations, scopes, and defaults
├── auth.py                        # Google OAuth 2.0 token management
├── classroom_client.py            # Classroom & Drive API client
├── calendar_client.py             # Google Calendar event & notification manager
├── tasks_client.py                # Google Tasks synchronization client
├── pdf_extractor.py               # Regex & dateparser deadline extraction engine
├── gemini_solver.py               # Gemini AI assignment solution engine
├── pdf_generator.py               # ReportLab styled solution PDF builder
├── email_dispatcher.py            # Gmail API solution dispatcher
├── sync_manager.py                # Orchestration pipeline and SQLite state store
├── main.py                        # Rich CLI entrypoint
├── run.sh                         # Shell automation & LaunchAgent installer
├── requirements.txt               # Dependencies
├── pytest.ini                     # Pytest test configuration
├── tests/                         # Automated unit & integration tests
│   ├── test_pdf_extractor.py
│   └── test_sync_manager.py
├── .env.example                   # Environment configuration template
├── credentials.example.json       # OAuth client credentials template
├── .gitignore                     # Git ignore rules for tokens, secrets & caches
├── LICENSE                        # MIT License
├── CONTRIBUTING.md                # Contribution guidelines
└── SECURITY.md                    # Security policy
```

---

## 🧪 Running Tests

Execute the complete test suite:

```bash
pytest -v
```

---

## 🔒 Security and Privacy

- **Never commit `credentials.json`, `token.json`, or `.env` files.**
- Tokens and personal data are stored only locally in your private workspace.
- This application communicates directly with official Google APIs over HTTPS.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) - open for everyone to use, modify, and distribute freely.
