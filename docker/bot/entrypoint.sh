#!/bin/bash
set -e

# This entrypoint runs as root so it can fix ownership of the shared
# bot-media volume (which may contain files owned by root from a previous
# container image). After fixing permissions it drops privileges to the
# target user and executes the original CMD.

BOT_MEDIA_DIR="/var/bot-media"
TARGET_UID="${USER_ID:-1000}"
TARGET_GID="${GROUP_ID:-1000}"

if [ -d "$BOT_MEDIA_DIR" ]; then
    mkdir -p \
        "$BOT_MEDIA_DIR/photos" \
        "$BOT_MEDIA_DIR/videos" \
        "$BOT_MEDIA_DIR/animations" \
        "$BOT_MEDIA_DIR/audio" \
        "$BOT_MEDIA_DIR/voice" \
        "$BOT_MEDIA_DIR/documents" \
        "$BOT_MEDIA_DIR/thumbnails"

    # Remove broken directories created by older bot versions that used
    # the full Telegram URL as a relative path (e.g. "https:/api.telegram.org/...").
    find "$BOT_MEDIA_DIR" -maxdepth 2 -type d -name 'https:*' -exec rm -rf {} + 2>/dev/null || true

    chown -R "$TARGET_UID:$TARGET_GID" "$BOT_MEDIA_DIR"
fi

# Drop privileges to the target user and execute the original command.
# setpriv (util-linux) is the cleanest way; fall back to su if unavailable.
if command -v setpriv >/dev/null 2>&1; then
    exec setpriv --reuid="$TARGET_UID" --regid="$TARGET_GID" --init-groups "$@"
else
    TARGET_USER=$(id -un "$TARGET_UID" 2>/dev/null || echo "botuser")
    exec su -s /bin/sh -c 'exec "$0" "$@"' "$TARGET_USER" -- "$@"
fi
