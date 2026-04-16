#!/usr/bin/with-contenv bash

# This script runs on SFTP container startup (LSIO openssh-server)
# It changes the user's 'home' directory so clients land directly in /config/upload

if [ -n "$USER_NAME" ]; then
    echo "[custom-init] Changing home directory for '$USER_NAME' to /config/upload..."
    usermod -d /config/upload "$USER_NAME"
else
    echo "[custom-init] Error: USER_NAME is not defined."
fi
