#!/usr/bin/env bash
# ===================================================================================
# Interactive .env File Initializer for WordPress App
# ===================================================================================

set -euo pipefail

# ANSI Color Codes (conditional on interactive TTY)
if [[ -t 1 ]]; then
    BOLD="\033[1m"
    CYAN="\033[36m"
    GREEN="\033[32m"
    YELLOW="\033[33m"
    GRAY="\033[90m"
    RESET="\033[0m"
else
    BOLD=""
    CYAN=""
    GREEN=""
    YELLOW=""
    GRAY=""
    RESET=""
fi

# Clear screen or print header
echo -e "${BOLD}${CYAN}========================================================"
echo -e "      WordPress Stack Environment Initializer"
echo -e "========================================================${RESET}"

ENV_FILE=".env"
DIST_FILE=".env.dist"

# Check if .env.dist exists
if [[ ! -f "$DIST_FILE" ]]; then
    echo -e "${BOLD}${YELLOW}❌ Error: ${DIST_FILE} not found! Please run this script from the project root.${RESET}"
    exit 1
fi

# Check if .env already exists
if [[ -f "$ENV_FILE" ]]; then
    echo -e "${BOLD}${YELLOW}⚠️  A .env file already exists in this directory.${RESET}"
    read -r -p "Do you want to overwrite it and reinitialize? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[yY](es)?$ ]]; then
        echo -e "${GREEN}Aborted. Your existing .env file has been left untouched.${RESET}"
        exit 0
    fi
fi

# Copy dist file to .env
echo -e "${GRAY}Copying ${DIST_FILE} to ${ENV_FILE}...${RESET}"
cp "$DIST_FILE" "$ENV_FILE"

# Helper: Generate random password
generate_random_password() {
    python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || \
    openssl rand -base64 12 | tr -d '+/=' | cut -c1-16 || \
    tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 16
}

# Helper: Update value in .env
set_env_var() {
    local key="$1"
    local val="$2"
    local escaped_val
    escaped_val=$(echo -n "$val" | sed -e 's/[\/&]/\\&/g')
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s|^[[:space:]]*${key}=.*|${key}=${escaped_val}|" "$ENV_FILE"
    else
        sed -i "s|^[[:space:]]*${key}=.*|${key}=${escaped_val}|" "$ENV_FILE"
    fi
}

# Helper: Prompt standard variable
prompt_var() {
    local var_ref="$1"
    local key="$2"
    local default_val="$3"
    local description="$4"
    local user_input
    
    echo -e "\n${BOLD}${CYAN}👉 ${key}${RESET}"
    if [[ -n "$description" ]]; then
        echo -e "${GRAY}${description}${RESET}"
    fi
    
    read -r -p "Enter value [${default_val}]: " user_input
    local final_val="${user_input:-$default_val}"
    
    set_env_var "$key" "$final_val"
    echo -e "${GREEN}✓ ${key} set to: ${final_val}${RESET}"
    
    # Store in variable (via indirect reference)
    eval "${var_ref}=\"\$final_val\""
}

# Helper: Prompt password
prompt_password() {
    local var_ref="$1"
    local key="$2"
    local description="$3"
    local default_val
    default_val=$(generate_random_password)
    local user_input
    
    echo -e "\n${BOLD}${CYAN}👉 ${key}${RESET}"
    if [[ -n "$description" ]]; then
        echo -e "${GRAY}${description}${RESET}"
    fi
    
    read -r -p "Enter password [${default_val}]: " user_input
    local final_val="${user_input:-$default_val}"
    
    set_env_var "$key" "$final_val"
    echo -e "${GREEN}✓ ${key} set to: ${final_val}${RESET}"
    
    eval "${var_ref}=\"\$final_val\""
}

# --- Default Value Calculations ---
dir_name=$(basename "$(pwd)")
default_pid="999"
default_pname="$dir_name"

if [[ "$dir_name" =~ ^([0-9]+)-(.*)$ ]]; then
    default_pid="${BASH_REMATCH[1]}"
    default_pname="${BASH_REMATCH[2]}"
else
    default_pname=$(echo "$dir_name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g')
fi

# Load existing PHP_VERSION in dist as default fallback
dist_php=$(grep '^PHP_VERSION=' "$DIST_FILE" | cut -d'=' -f2 | tr -d '"'\''\r ' || echo "8.5")

# --- Prompts ---

# 1. PROJECT_ID
prompt_var "PROJECT_ID" "PROJECT_ID" "$default_pid" "A unique numeric identifier for the project (e.g. 101, 999). Used to namespace port assignments."

# 2. PROJECT_NAME
prompt_var "PROJECT_NAME" "PROJECT_NAME" "$default_pname" "The name of the project. Used for container hostnaming, service names, and logs."

# 3. APP_ENV
prompt_var "APP_ENV" "APP_ENV" "development" "Application environment mode. Options: development, production."

# 4. PHP_VERSION
prompt_var "PHP_VERSION" "PHP_VERSION" "$dist_php" "The PHP execution engine version to run in the application container (e.g., 8.1, 8.3, 8.5)."

# 5. COMPOSE_PROFILES
prompt_var "COMPOSE_PROFILES" "COMPOSE_PROFILES" "db,cron,redis,sftp,wpcli" "Orchestration profiles to enable. Available optional profiles: db, cron, redis, sftp, wpcli, bot. Comma-separated."

# 6. DB_NAME
prompt_var "DB_NAME" "DB_NAME" "$PROJECT_NAME" "The name of the database schema to automatically create on startup."

# 7. DB_USER
prompt_var "DB_USER" "DB_USER" "$PROJECT_NAME" "The credentials username for application database access."

# 8. DB_PASS
prompt_password "DB_PASS" "DB_PASS" "The secure password for the database user account."

# 9. DB_ROOT_PASS
prompt_password "DB_ROOT_PASS" "DB_ROOT_PASS" "The root superuser administration password for MariaDB."

# 10. SFTP_USER
prompt_var "SFTP_USER" "SFTP_USER" "sftpuser" "The authorized username allowed to log in and upload files via SFTP."

# 11. SFTP_PASS
prompt_password "SFTP_PASS" "SFTP_PASS" "The SFTP authentication credentials password."

echo -e "\n${BOLD}${GREEN}========================================================"
echo -e "   ✓ .env file has been initialized successfully!"
echo -e "========================================================${RESET}"
echo -e "${GRAY}Please review the created .env file before starting the containers.${RESET}\n"
