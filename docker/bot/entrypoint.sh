#!/bin/bash
set -e

# Ensure the shared bot-media volume has correct ownership.
# The volume may have been created by a previous container running as root,
# so we fix permissions at startup before dropping to the bot user.
BOT_MEDIA_DIR="/var/bot-media"
if [ -d "$BOT_MEDIA_DIR" ]; then
    mkdir -p \
        "$BOT_MEDIA_DIR/photos" \
        "$BOT_MEDIA_DIR/videos" \
        "$BOT_MEDIA_DIR/animations" \
        "$BOT_MEDIA_DIR/audio" \
        "$BOT_MEDIA_DIR/voice" \
        "$BOT_MEDIA_DIR/documents" \
        "$BOT_MEDIA_DIR/thumbnails"
    chown -R "$(id -u):$(id -g)" "$BOT_MEDIA_DIR"
fi

exec "$@"
