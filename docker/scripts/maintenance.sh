#!/bin/bash
# maintenance.sh - Periodic cleanup for tmpfs shared volume and WordPress logs
# This script is intended to run inside the cron container.
# Runs every 15 minutes via the crontab.

TMP_DIR="/var/www/html/tmp"
WP_DEBUG_LOG="/var/www/html/public/wp-content/debug.log"

echo "--- [$(date)] Starting Maintenance Task ---"

# 1. Truncate logs if they are too big (> 5MB)
# Using :> to truncate preserves the file descriptor for the tail process.
shopt -s nullglob 2>/dev/null || true
LOG_FILES=("$TMP_DIR"/*.log "$TMP_DIR"/*/*.log "$WP_DEBUG_LOG")
shopt -u nullglob 2>/dev/null || true
for log in "${LOG_FILES[@]}"; do
    if [ -f "$log" ]; then
        log_size=$(stat -c%s "$log" 2>/dev/null || echo 0)
        if [ "$log_size" -gt 5242880 ]; then
            echo "Truncating large log file: $log"
            : > "$log"
        fi
    fi
done
echo "✅ Checked and truncated large log files."

# 2. Clean up old PHP sessions in tmpfs (older than 24h)
if [ -d "$TMP_DIR/sessions" ]; then
    find "$TMP_DIR/sessions" -mindepth 1 -type f -mmin +1440 -delete
    find "$TMP_DIR/sessions" -mindepth 1 -type d -empty -delete 2>/dev/null || true
    echo "✅ Cleaned up PHP sessions older than 24h."
fi

# 3. Clean up stale WP-CLI cache files (older than 14 days)
for wp_cache in "/var/www/.wp-cli/cache" "/tmp/.wp-cli"; do
    if [ -d "$wp_cache" ]; then
        find "$wp_cache" -mindepth 1 -type f -mtime +14 -delete 2>/dev/null || true
        find "$wp_cache" -mindepth 1 -type d -empty -delete 2>/dev/null || true
        echo "✅ Cleaned up WP-CLI cache files older than 14 days in $wp_cache."
    fi
done

echo "--- [$(date)] Maintenance Task Complete ---"
