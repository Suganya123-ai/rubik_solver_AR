#!/usr/bin/env bash
# Starts autolearn/run_weekly.sh every night at 03:00 (launchd; a night the laptop was asleep runs when it
# wakes). The script itself makes it weekly and skips nights on battery or with a demo running.
#   ./autolearn/install_schedule.sh            install (or update)
#   ./autolearn/install_schedule.sh --remove   stop it
set -euo pipefail
cd "$(dirname "$0")/.."
LABEL=com.cubetutor.autolearn
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [ "${1:-}" = "--remove" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"; echo "removed: no more weekly retraining"; exit 0
fi
mkdir -p "$HOME/Library/LaunchAgents" data/autolearn/logs
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$PWD/autolearn/run_weekly.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$PWD/data/autolearn/logs/launchd.log</string>
  <key>StandardErrorPath</key><string>$PWD/data/autolearn/logs/launchd.log</string>
  <key>LowPriorityIO</key><true/>
  <key>Nice</key><integer>10</integer>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed: autolearn/run_weekly.sh runs nightly at 03:00 (weekly work; skips on battery or with a demo running)"
