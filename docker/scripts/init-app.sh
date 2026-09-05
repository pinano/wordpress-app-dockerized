#!/bin/sh
# init-app.sh
# Initialization script for the WordPress Docker container.
# Runs automatically via the entrypoint system (/etc/entrypoint.d/)

# Default slowlog timeout fallback if not passed from environment
export PHP_FPM_SLOWLOG_TIMEOUT="${PHP_FPM_SLOWLOG_TIMEOUT:-10s}"

# --- TMP DIRECTORY STRUCTURE ---
# Required because /var/www/html/tmp is mounted as tmpfs (wiped on restart)
echo "📁 Initializing /var/www/html/tmp structure..."
mkdir -p /var/www/html/tmp/sessions
chown -R www-data:www-data /var/www/html/tmp
chmod -R 775 /var/www/html/tmp

# --- LOG FILES INITIALIZATION ---
# Pre-creates log files with correct ownership for separate tailing.

# 1. PHP Error Log (Generic PHP errors)
PHP_ERROR_LOG=/var/www/html/tmp/php_errors.log
touch "$PHP_ERROR_LOG"
chown www-data:www-data "$PHP_ERROR_LOG"
chmod 664 "$PHP_ERROR_LOG"

# 2. PHP-FPM Slow Log (Performance debugging)
PHP_FPM_SLOW_LOG=/var/www/html/tmp/php-fpm-slow.log
touch "$PHP_FPM_SLOW_LOG"
chown www-data:www-data "$PHP_FPM_SLOW_LOG"
chmod 664 "$PHP_FPM_SLOW_LOG"
echo "✅ Log files initialized."

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
$dbHost = getenv('DB_HOST');
$dbName = getenv('DB_NAME');
$dbUser = getenv('DB_USER');
$dbPass = getenv('DB_PASS');

if ($dbHost && $dbName && $dbUser) {
    try {
        $pdo = new PDO(
            'mysql:host=' . $dbHost . ';dbname=' . $dbName,
            $dbUser,
            $dbPass,
            [PDO::ATTR_TIMEOUT => 3, PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
        );
        $pdo->query('SELECT 1');
        $pdo = null;
    } catch (Exception $e) {
        http_response_code(503);
        echo 'db_error';
        exit;
    }
}
http_response_code(200);
echo 'ok';
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
    INT_VAL=$(php -r '
        $expr = trim(getenv("PHP_ERROR_REPORTING"));
        $expr = trim($expr, "\"\x27");
        $expr = trim($expr);
        if (empty($expr)) {
            echo E_ALL & ~E_WARNING & ~E_NOTICE & ~E_DEPRECATED;
            exit;
        }
        if (preg_match("/^[a-zA-Z0-9_\\s&~|()]+$/", $expr)) {
            $val = eval("return $expr;");
            if ($val !== false) {
                echo $val;
                exit;
            }
        }
        echo E_ALL & ~E_NOTICE & ~E_DEPRECATED;
    ' 2>/dev/null)

    # Robust fallback: check if INT_VAL is a valid number to prevent PHP-FPM boot crashes.
    case "$INT_VAL" in
        "" | *[!0-9]*)
            echo "⚠️  Failed to evaluate PHP_ERROR_REPORTING expression. Using default error reporting."
            INT_VAL=$(php -r 'echo E_ALL & ~E_WARNING & ~E_NOTICE & ~E_DEPRECATED;')
            ;;
    esac

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
if [ "$IS_CRON" = "1" ]; then
    echo "⚙️  Saving environment variables to /etc/environment (cron daemon requires explicit env exports)..."
    {
        printenv | grep -v -E '^(PATH|HOME|HOSTNAME|PWD|SHLVL|OLDPWD)=' \
            | sed "s/'/'\\\\''/g"
    } > /etc/environment
    echo "✅ Created /etc/environment with Docker variables."
fi
