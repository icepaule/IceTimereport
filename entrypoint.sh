#!/bin/bash
set -e

# Export env vars for cron (cron doesn't inherit environment)
# Quote values to handle spaces in SMTP_PASS, EMPLOYEE_NAME etc.
printenv | grep -v "no_proxy" | sed "s/=\(.*\)/='\1'/" >> /etc/environment

# If arguments passed, run as CLI
if [ "$1" != "" ] && [ "$1" != "cron" ]; then
    exec python3 /app/main.py "$@"
fi

# Start cron in foreground
echo "Starting overtime-report cron scheduler..."
echo "Schedule: generate daily 06:00, email 1st of month 07:00"
cron -f
