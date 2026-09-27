"""Configuration constants and defaults for Google Classroom to Calendar & Tasks Sync."""

from pathlib import Path
import os

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Auto-load .env if present
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# OAuth and Credentials paths
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
DATABASE_FILE = BASE_DIR / "sync_state.sqlite"

# Valid Google API Scopes
SCOPES = [
    # Classroom scopes
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    # Drive scope for reading attached PDFs
    "https://www.googleapis.com/auth/drive.readonly",
    # Calendar scopes for creating/updating events
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    # Tasks scope for creating/updating Google Tasks
    "https://www.googleapis.com/auth/tasks",
    # Gmail scope for emailing solved assignment answers
    "https://www.googleapis.com/auth/gmail.send",
]

# Default Calendar Configuration
DEFAULT_CALENDAR_NAME = "Google Classroom Deadlines"
DEFAULT_EVENT_COLOR_ID = "5"  # Yellow/Banana in Google Calendar

# Reminders Configuration (Popups + Email Notifications)
DEFAULT_REMINDER_MINUTES = [1440, 120]  # 24 hours (1440m) and 2 hours (120m) before deadline
DEFAULT_REMINDER_METHODS = ["popup", "email"]  # Sends BOTH popups and Email notifications

# Default Google Tasks Configuration
DEFAULT_TASKLIST_NAME = "Google Classroom Deadlines"

# Default sync interval for watch mode in minutes
DEFAULT_WATCH_INTERVAL_MINUTES = 30

# User Timezone fallback
DEFAULT_TIMEZONE = os.environ.get("SYNC_TIMEZONE", "auto")

# Default Email Recipient (for sending AI solutions)
DEFAULT_RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
