#!/bin/bash
# Google Classroom to Google Calendar Automation Runner

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

MODE="${1:-sync}"
FILTER="${2:-5th Sem}"
MAX_AGE="${3:-30}"

case "$MODE" in
    "sync")
        echo "🚀 Syncing Google Classroom (Filter: '$FILTER', Max Age: ${MAX_AGE} days)..."
        .venv/bin/python main.py sync --filter "$FILTER" --max-age-days "$MAX_AGE"
        ;;
    "watch")
        # 4 days in minutes = 4 * 24 * 60 = 5760 minutes
        INTERVAL="${4:-5760}"
        echo "🔄 Starting continuous automation every 4 days ($INTERVAL minutes)..."
        .venv/bin/python main.py watch --interval "$INTERVAL" --filter "$FILTER" --max-age-days "$MAX_AGE"
        ;;
    "autostart")
        echo "⚙️ Installing background periodic Mac LaunchAgent..."
        mkdir -p ~/Library/LaunchAgents
        PLIST_PATH="$HOME/Library/LaunchAgents/com.classroom.sync.plist"
        cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.classroom.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>$DIR/.venv/bin/python</string>
        <string>$DIR/main.py</string>
        <string>sync</string>
        <string>--filter</string>
        <string>$FILTER</string>
        <string>--max-age-days</string>
        <string>$MAX_AGE</string>
    </array>
    <key>StartInterval</key>
    <!-- Run every 4 days: 4 days * 24h * 60m * 60s = 345600 seconds -->
    <integer>345600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$DIR/sync.log</string>
    <key>StandardErrorPath</key>
    <string>$DIR/sync_error.log</string>
</dict>
</plist>
EOF
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        launchctl load "$PLIST_PATH"
        echo "✅ Installed! Your Mac will now automatically sync Classroom every 4 days in the background silently."
        ;;
    "stop-autostart")
        echo "🛑 Disabling background LaunchAgent..."
        PLIST_PATH="$HOME/Library/LaunchAgents/com.classroom.sync.plist"
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        rm -f "$PLIST_PATH"
        echo "Disabled."
        ;;
    "status")
        .venv/bin/python main.py status
        ;;
    "setup")
        .venv/bin/python main.py setup
        ;;
    *)
        echo "Usage: ./run.sh [sync|watch|autostart|stop-autostart|status|setup]"
        exit 1
        ;;
esac
