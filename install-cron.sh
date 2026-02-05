#!/usr/bin/env bash
# Add a cron job to refresh the Plane Eisenhower matrix wallpaper.
# Run from the repo directory: ./install-cron.sh [interval_minutes]
# Example: ./install-cron.sh 30  → every 30 minutes

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERVAL="${1:-30}"

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -lt 1 ]]; then
  echo "Usage: $0 [interval_minutes]"
  echo "  interval_minutes: how often to run (default 30)"
  exit 1
fi

# Build cron schedule: every N minutes
if [[ "$INTERVAL" -eq 1 ]]; then
  CRON_SCHEDULE="* * * * *"
elif [[ "$INTERVAL" -lt 60 ]]; then
  CRON_SCHEDULE="*/$INTERVAL * * * *"
else
  H=$((INTERVAL / 60))
  CRON_SCHEDULE="0 * * * *"  # every hour; for "every N hours" we'd need a different pattern
  echo "Note: interval >= 60 not fully supported; using hourly. For custom intervals use crontab -e."
fi

LINE="${CRON_SCHEDULE} cd \"$DIR\" && python3 desktop_background.py"
( crontab -l 2>/dev/null | grep -v "desktop_background.py" || true; echo "$LINE" ) | crontab -
echo "Cron job added: run every $INTERVAL minute(s)"
echo "  $LINE"
echo "Current crontab:"
crontab -l
