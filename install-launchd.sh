#!/usr/bin/env bash
# Add a macOS launchd job to refresh the Plane Eisenhower matrix wallpaper.
# Run from the repo directory: ./install-launchd.sh [interval_minutes]
# Example: ./install-launchd.sh 30  → every 30 minutes

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERVAL="${1:-30}"
LABEL="com.plane.eisenhower-matrix-wallpaper"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PYTHON="$(command -v python3 || command -v python)"

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -lt 1 ]]; then
  echo "Usage: $0 [interval_minutes]"
  echo "  interval_minutes: how often to run (default 30)"
  exit 1
fi

if [ -z "$PYTHON" ]; then
  echo "Error: python3 not found in PATH."
  exit 1
fi

INTERVAL_SECONDS=$((INTERVAL * 60))

# Unload existing job if present
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${DIR}/desktop_background.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${DIR}</string>
    <key>StartInterval</key>
    <integer>${INTERVAL_SECONDS}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/plane-matrix-wallpaper.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/plane-matrix-wallpaper.log</string>
</dict>
</plist>
PLIST_EOF

launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Launch agent installed: runs every $INTERVAL minute(s)."
echo "  Plist : $PLIST"
echo "  Python: $PYTHON"
echo "  Log   : /tmp/plane-matrix-wallpaper.log"
echo ""
echo "To remove later:"
echo "  launchctl bootout gui/$(id -u)/$LABEL"
echo "  rm $PLIST"
