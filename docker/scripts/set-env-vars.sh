#!/bin/bash
# Evaluates APP_ENV and exports variables for docker-compose to use

# Save current APP_ENV if passed inline
CURRENT_APP_ENV="${APP_ENV:-}"

# Resolve PROJECT_ROOT and ENV_PATH
if [ -f ".env" ]; then
  # If .env is in the current directory, assume we are at the project root
  PROJECT_ROOT="."
  ENV_PATH="./.env"
elif [ -n "$BASH_SOURCE" ]; then
  SCRIPT_PATH="${BASH_SOURCE[0]}"
  PROJECT_ROOT="$(cd "$(dirname "$(dirname "$(dirname "$SCRIPT_PATH")")")" && pwd)"
  ENV_PATH="${PROJECT_ROOT}/.env"
else
  # Fallback for shells like dash which don't support BASH_SOURCE
  SCRIPT_PATH="$0"
  if [ -f "$SCRIPT_PATH" ]; then
    PROJECT_ROOT="$(cd "$(dirname "$(dirname "$(dirname "$SCRIPT_PATH")")")" && pwd)"
    ENV_PATH="${PROJECT_ROOT}/.env"
  else
    # Last resort fallback to current directory
    PROJECT_ROOT="."
    ENV_PATH="./.env"
  fi
fi

if [ -f "$ENV_PATH" ]; then
  # Parse .env safely line by line — avoids dash interpreting & | ; etc. in values
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip blank lines and comments
    case "$line" in
      ''|'#'*) continue ;;
    esac
    # Split on first '=' only, preserving everything after it as the value
    key="${line%%=*}"
    val="${line#*=}"
    # Skip malformed lines (no key or key contains spaces)
    case "$key" in
      *' '*|*'	'*|'') continue ;;
    esac
    export "$key=$val"
  done < "$ENV_PATH"
fi

# Override with inline if it existed
if [ -n "$CURRENT_APP_ENV" ]; then
  export APP_ENV="$CURRENT_APP_ENV"
fi

if [ "$APP_ENV" = "development" ]; then
    export APP_ENV_PHP_OPCACHE_VALIDATE_TIMESTAMPS=1
    export APP_ENV_PHP_OPCACHE_REVALIDATE_FREQ=0
    # display_errors=Off even in development: errors go to the log file instead
    # of being printed in the HTTP response. This avoids leaking stack traces
    # while still capturing all errors via error_log / Zend Logger.
    export APP_ENV_PHP_DISPLAY_ERRORS="Off"
    export APP_ENV_PHP_DISPLAY_STARTUP_ERRORS="On"
else
    export APP_ENV_PHP_OPCACHE_VALIDATE_TIMESTAMPS=0
    export APP_ENV_PHP_OPCACHE_REVALIDATE_FREQ=60
    export APP_ENV_PHP_DISPLAY_ERRORS="Off"
    export APP_ENV_PHP_DISPLAY_STARTUP_ERRORS="Off"
fi
