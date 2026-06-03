#!/bin/bash
# maintenance.sh - Periodic cleanup for tmpfs logs and WordPress debug log
# This script is intended to run inside the cron container.
# Runs every 15 minutes via the crontab.

TMP_DIR="/var/www/html/tmp"
WP_DEBUG_LOG="/var/www/html/public/wp-content/debug.log"

echo "--- [$(date)] Starting Maintenance Task ---"

# Truncate logs if they are too big (> 5MB)
# Using :> to truncate preserves the file descriptor for the tail processes.
# Prevents logs from filling the tmpfs RAM disk or persistent host storage.
LOG_FILES=("$TMP_DIR"/*.log "$WP_DEBUG_LOG")
for log in "${LOG_FILES[@]}"; do
    if [ -f "$log" ] && [ $(stat -c%s "$log") -gt 5242880 ]; then
        echo "Truncating large log file: $log"
        : > "$log"
    fi
done
echo "✅ Checked and truncated large log files."

echo "--- [$(date)] Maintenance Task Complete ---"
