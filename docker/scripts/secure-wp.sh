#!/bin/bash

# Script to manage WordPress security permissions
# Usage: ./secure-wp.sh [lock|unlock|fix] [user_id:group_id]

ACTION=$1
IDS=$2
DOCROOT="docroot/public"

if [ -z "$ACTION" ]; then
    echo "Usage: $0 [lock|unlock|fix] [user_id:group_id]"
    exit 1
fi

# Directories that ALWAYS need write access
WRITEABLE_DIRS=(
    "$DOCROOT/wp-content/uploads"
    "$DOCROOT/wp-content/cache"
    "$DOCROOT/wp-content/languages"
    "$DOCROOT/wp-content/upgrade"
    "$DOCROOT/wp-content/wp-rocket-config"
    "$DOCROOT/wp-content/upgrade-temp-backup"
)

# Files that might need write access (caching plugins often use these)
WRITEABLE_FILES=(
    "$DOCROOT/wp-content/advanced-cache.php"
    "$DOCROOT/wp-content/object-cache.php"
    "$DOCROOT/wp-content/debug.log"
    "$DOCROOT/.htaccess"
)

fix_permissions() {
    echo "🔧 Fixing base permissions..."
    # Only try chown if we are root or if ownership is completely wrong
    # Silencing errors to avoid terminal flood in macOS/Docker environments
    if [ "$(id -u)" = "0" ] && [ -n "$IDS" ]; then
        chown -R "$IDS" "$DOCROOT" 2>/dev/null
    fi
    
    # Use -f to silence errors during chmod (useful for tmpfs mounts)
    find "$DOCROOT" -type d -exec chmod -f 755 {} +
    find "$DOCROOT" -type f -exec chmod -f 644 {} +
    
    # Secure wp-config.php specifically
    if [ -f "$DOCROOT/wp-config.php" ]; then
        chmod -f 640 "$DOCROOT/wp-config.php"
    fi
}

lock_site() {
    echo "🔒 Locking WordPress core (Read-Only for web server)..."
    
    # 1. Start with standard fix to ensure clean state
    fix_permissions
    
    # 2. Make EVERYTHING Read-Only first
    echo "  -> Setting all files to 444..."
    find "$DOCROOT" -type f -exec chmod -f 444 {} +
    
    # 3. Restore write access to specific directories
    for dir in "${WRITEABLE_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            echo "  -> Allowing write to directory: $dir"
            # Directory needs 755 (rwx)
            chmod -f 755 "$dir"
            # Contents need 644 (rw-) for files and 755 for subdirs
            find "$dir" -type d -exec chmod -f 755 {} +
            find "$dir" -type f -exec chmod -f 644 {} +
        fi
    done
    
    # 4. Restore write access to specific files
    for file in "${WRITEABLE_FILES[@]}"; do
        if [ -f "$file" ]; then
            echo "  -> Allowing write to file: $file"
            chmod -f 644 "$file"
        fi
    done

    # 5. Extra security for wp-config.php
    if [ -f "$DOCROOT/wp-config.php" ]; then
        chmod -f 440 "$DOCROOT/wp-config.php"
    fi
}

unlock_site() {
    echo "🔓 Unlocking WordPress core (Write access enabled for maintenance)..."
    fix_permissions
}

case "$ACTION" in
    lock)
        lock_site
        ;;
    unlock)
        unlock_site
        ;;
    fix)
        fix_permissions
        ;;
    *)
        echo "Invalid action: $ACTION"
        exit 1
        ;;
esac

echo "✅ Done!"
