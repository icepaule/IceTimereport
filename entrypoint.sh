#!/bin/bash
set -e

# Export env vars for cron (cron doesn't inherit environment)
printenv | grep -v "no_proxy" >> /etc/environment

# If arguments passed, run as CLI
if [ "$1" != "" ] && [ "$1" != "cron" ]; then
    exec python3 /app/main.py "$@"
fi

# Start cron in foreground
echo "Starting overtime-report cron scheduler..."
echo "Schedule: generate daily 06:00, email 1st of month 07:00"
cron -f
