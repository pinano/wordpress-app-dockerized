#!/bin/sh
# init-app.sh
# Initialization script for the Wordpress Docker container.
# Runs automatically via the entrypoint system (/etc/entrypoint.d/)

# --- TMP DIRECTORY STRUCTURE ---
# Required because /var/www/html/tmp is mounted as tmpfs (wiped on restart)
echo "📁 Initializing /var/www/html/tmp ownership and permissions..."
mkdir -p /var/www/html/tmp
chown -R www-data:www-data /var/www/html/tmp
chmod -R 775 /var/www/html/tmp

# --- PHP ERROR LOG FORWARDER ---
# Workaround for S6 overlay masking FPM worker stderr output.
# PHP writes errors to a file, and this tail process forwards them to PID 1 (Docker logs).
PHP_ERROR_LOG=/var/www/html/tmp/php_errors.log
touch "$PHP_ERROR_LOG"
chown www-data:www-data "$PHP_ERROR_LOG"
chmod 664 "$PHP_ERROR_LOG"
tail -F "$PHP_ERROR_LOG" > /proc/1/fd/2 2>/dev/null &
echo "✅ PHP error log forwarder started (→ Docker logs)"

# --- PHP-FPM SLOW LOG ---
# Pre-creates the slow log file with correct ownership so FPM workers can write to it.
PHP_FPM_SLOW_LOG=/var/www/html/tmp/php-fpm-slow.log
touch "$PHP_FPM_SLOW_LOG"
chown www-data:www-data "$PHP_FPM_SLOW_LOG"
chmod 664 "$PHP_FPM_SLOW_LOG"
echo "✅ PHP-FPM slow log file pre-created"

# --- HEALTHCHECK ---
# Auto-generate a healthcheck.php that validates both PHP-FPM and database connectivity.
# This allows Docker healthchecks and Traefik to detect actual service availability,
# not just that PHP-FPM is responding.
HEALTHCHECK_FILE="${APACHE_DOCUMENT_ROOT:-/var/www/html/public}/healthcheck.php"
mkdir -p "$(dirname "$HEALTHCHECK_FILE")"
if [ ! -f "$HEALTHCHECK_FILE" ]; then
    cat > "$HEALTHCHECK_FILE" <<'HEALTHCHECK_EOF'
<?php
// Auto-generated healthcheck — validates PHP-FPM + MariaDB connectivity.
// Docker healthcheck interval is typically 60s, so one DB connection per minute is negligible.
try {
    $pdo = new PDO(
        'mysql:host=' . getenv('DB_HOST') . ';dbname=' . getenv('DB_NAME'),
        getenv('DB_USER'),
        getenv('DB_PASS'),
        [PDO::ATTR_TIMEOUT => 3, PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );
    $pdo->query('SELECT 1');
    $pdo = null;
    http_response_code(200);
    echo 'ok';
} catch (Exception $e) {
    http_response_code(503);
    echo 'db_error';
}
HEALTHCHECK_EOF
    chown www-data:www-data "$HEALTHCHECK_FILE"
    echo "✅ Healthcheck created at $HEALTHCHECK_FILE (with DB validation)"
else
    echo "ℹ️  Healthcheck already exists at $HEALTHCHECK_FILE, skipping."
fi

# --- DYNAMIC PHP ERROR REPORTING ---
# Convert string values (like "E_ALL & ~E_NOTICE") to an integer for FPM pool.
# FPM cannot parse PHP language constants natively via env vars.
if [ -n "$PHP_ERROR_REPORTING" ]; then
    echo "⚙️  Evaluating PHP_ERROR_REPORTING to integer for FPM pool..."
    INT_VAL=$(php -r "echo ($PHP_ERROR_REPORTING);")
    if [ -d "/usr/local/etc/php-fpm.d" ]; then
        cat > /usr/local/etc/php-fpm.d/99-dynamic-error-reporting.conf <<EOF
[www]
php_admin_value[error_reporting] = $INT_VAL
EOF
        echo "✅ PHP error reporting configured dynamically for FPM ($INT_VAL)."
    else
        echo "ℹ️  FPM config directory not found, skipping FPM worker dynamic error reporting."
    fi
fi

# --- CRON ENVIRONMENT INJECTION ---
# The vanilla 'cron' daemon strips out all Docker-injected environment variables.
# We must manually dump them into /etc/environment so scheduled PHP scripts
# can connect to MariaDB and respect the APP_ENV.
if [ "$IS_CRON" = "1" ]; then
    echo "⚙️  Saving environment variables to /etc/environment (cron daemon requires explicit env exports)..."
    # /etc/environment format: KEY=value (no 'export', no multiline values)
    # We explicitly list only the variables that cron scripts need.
    {
        printenv | grep -E "^(DB_HOST|DB_NAME|DB_USER|DB_PASS|APP_ENV|TZ|PHP_|USER_ID|GROUP_ID)=" \
            | sed "s/'/'\\\\''/g"
    } > /etc/environment
    echo "✅ Created /etc/environment with Docker variables."
fi
