# Makefile for Dockerized WordPress App

# Colors for help menu
BOLD  := \033[1m
CYAN  := \033[36m
RESET := \033[0m

# Dynamic port discovery from .env
PROJECT_ID_RAW := $(shell grep '^PROJECT_ID=' .env 2>/dev/null | cut -d= -f2 | tr -d '"'\''\r ')
PROJECT_ID     := $(if $(PROJECT_ID_RAW),$(PROJECT_ID_RAW),999)
DB_PORT        := 33$(PROJECT_ID)
SFTP_PORT      := 22$(PROJECT_ID)

# Detect if 'help' is one of the goals, and there is at least one other goal.
# E.g., 'make start help' or 'make help start'.
SHOW_HELP :=
ifneq ($(filter help,$(MAKECMDGOALS)),)
  ifneq ($(filter-out help,$(MAKECMDGOALS)),)
    SHOW_HELP := 1
  endif
endif

ifeq ($(SHOW_HELP),1)

FIRST_GOAL := $(firstword $(filter-out help,$(MAKECMDGOALS)))

.PHONY: $(MAKECMDGOALS)
$(MAKECMDGOALS):
	@if [ "$@" = "$(FIRST_GOAL)" ]; then \
		case "$@" in \
			"doctor") \
				printf "$(BOLD)make doctor$(RESET)\n" ; \
				printf "  Run diagnostic checks on the Docker environment and port configurations.\n" ; \
				printf "  Checks include:\n" ; \
				printf "    - Docker daemon accessibility.\n" ; \
				printf "    - Host Transparent Huge Pages (THP) status (relevant for OPcache).\n" ; \
				printf "    - Detailed check on database ($(DB_PORT)) and SFTP ($(SFTP_PORT)) ports.\n" ; \
				printf "    - Alert if ports are bound to 0.0.0.0 or 172.17.0.1 and if they are blocked.\n" ; \
				;; \
			"status") \
				printf "$(BOLD)make status$(RESET)\n" ; \
				printf "  Show the status of all containers in the stack.\n" ; \
				printf "  Equivalent to running 'docker compose ps'.\n" ; \
				;; \
			"services") \
				printf "$(BOLD)make services$(RESET)\n" ; \
				printf "  List all services defined in the docker-compose configuration.\n" ; \
				printf "  Use these names for target-specific commands like 'make shell <service>'.\n" ; \
				;; \
			"config") \
				printf "$(BOLD)make config$(RESET)\n" ; \
				printf "  Validate and render the active Docker Compose configuration.\n" ; \
				printf "  Displays the parsed docker-compose file with environment variables expanded.\n" ; \
				;; \
			"start") \
				printf "$(BOLD)make start$(RESET)\n" ; \
				printf "  Start the Docker stack in the background.\n" ; \
				printf "  Before starting, it will automatically:\n" ; \
				printf "    1. Initialize the .env file from .env.dist if missing.\n" ; \
				printf "    2. Sync missing .env keys from .env.dist.\n" ; \
				printf "    3. Run configuration validation to check for security/performance issues.\n" ; \
				;; \
			"stop") \
				printf "$(BOLD)make stop$(RESET)\n" ; \
				printf "  Stop all running containers in the stack.\n" ; \
				printf "  Clears networks and orphaned containers. Safe: does NOT delete database volumes.\n" ; \
				;; \
			"restart") \
				printf "$(BOLD)make restart$(RESET)\n" ; \
				printf "  Perform a clean restart of the stack.\n" ; \
				printf "  Executes 'make stop' followed by 'make start'. Recommended to apply .env changes.\n" ; \
				;; \
			"rebuild") \
				printf "$(BOLD)make rebuild [service]$(RESET)\n" ; \
				printf "  Rebuild Docker images for the stack.\n" ; \
				printf "  Provide an optional service name to rebuild only that service (e.g. 'make rebuild app').\n" ; \
				;; \
			"pull") \
				printf "$(BOLD)make pull$(RESET)\n" ; \
				printf "  Pull latest versions of the base Docker images specified in the compose file.\n" ; \
				;; \
			"clean") \
				printf "$(BOLD)make clean$(RESET)\n" ; \
				printf "  Tear down everything, including persistent volumes.\n" ; \
				printf "  $(BOLD)$(CYAN)WARNING:$(RESET) This deletes all database volumes and data permanently!\n" ; \
				printf "  Requires explicit user confirmation [y/N] before proceeding.\n" ; \
				;; \
			"shell") \
				printf "$(BOLD)make shell [service]$(RESET)\n" ; \
				printf "  Open an interactive terminal/shell inside a running container.\n" ; \
				printf "  Defaults to the 'app' container. Usage: 'make shell [service]' (e.g., 'make shell db').\n" ; \
				;; \
			"logs") \
				printf "$(BOLD)make logs [service|wordpress]$(RESET)\n" ; \
				printf "  Stream real-time log output for all containers or a specific service.\n" ; \
				printf "  Usage: 'make logs' or 'make logs [service]' (e.g., 'make logs app').\n" ; \
				printf "  Special: 'make logs wordpress' tails the WordPress debug log file at\n" ; \
				printf "  /var/www/html/public/wp-content/debug.log.\n" ; \
				;; \
			"logs-slow") \
				printf "$(BOLD)make logs-slow$(RESET)\n" ; \
				printf "  Stream PHP-FPM slow request logs in real-time to identify performance bottlenecks.\n" ; \
				printf "  Tails /var/www/html/tmp/php-fpm-slow.log inside the app container.\n" ; \
				;; \
			"db") \
				printf "$(BOLD)make db [action] [file]$(RESET)\n" ; \
				printf "  Run database management tools.\n" ; \
				printf "  Actions:\n" ; \
				printf "    - (No action): Open an interactive MariaDB console in the 'db' container.\n" ; \
				printf "    - db import <file.sql>: Import a SQL dump file into the database (supports 'pv' progress bar).\n" ; \
				printf "    - db export: Export a timestamped, single-transaction SQL dump to the host.\n" ; \
				;; \
			"db-root") \
				printf "$(BOLD)make db-root$(RESET)\n" ; \
				printf "  Connect to the database console as the 'root' database user.\n" ; \
				;; \
			"php-info") \
				printf "$(BOLD)make php-info$(RESET)\n" ; \
				printf "  Display current PHP configuration settings active in the running container.\n" ; \
				;; \
			"opcache-clear") \
				printf "$(BOLD)make opcache-clear$(RESET)\n" ; \
				printf "  Clear PHP OPcache bytecode cache for the PHP-FPM pool (zero-downtime flush).\n" ; \
				;; \
			"ctop") \
				printf "$(BOLD)make ctop$(RESET)\n" ; \
				printf "  Monitor project containers in real-time using ctop (CPU, MEM, NET statistics).\n" ; \
				;; \
			"open-ports") \
				printf "$(BOLD)make open-ports$(RESET)\n" ; \
				printf "  Configure .env to bind DB ($(DB_PORT)) and SFTP ($(SFTP_PORT)) ports to 0.0.0.0 (accessible externally).\n" ; \
				printf "  $(BOLD)$(CYAN)WARNING:$(RESET) Exposing database ($(DB_PORT)) and SFTP ($(SFTP_PORT)) ports externally is a security risk. Secure your host with a firewall!\n" ; \
				printf "  Note: Run 'make restart' or 'docker compose up -d' to apply.\n" ; \
				;; \
			"close-ports") \
				printf "$(BOLD)make close-ports$(RESET)\n" ; \
				printf "  Configure .env to restrict DB ($(DB_PORT)) to 172.17.0.1 and SFTP ($(SFTP_PORT)) to 127.0.0.1.\n" ; \
				printf "  Note: Run 'make restart' or 'docker compose up -d' to apply.\n" ; \
				;; \
			"open-db") \
				printf "$(BOLD)make open-db$(RESET)\n" ; \
				printf "  Configure .env to bind the DB port ($(DB_PORT)) to 0.0.0.0 (accessible externally).\n" ; \
				printf "  $(BOLD)$(CYAN)WARNING:$(RESET) Exposing the database port ($(DB_PORT)) externally is a security risk. Secure your host with a firewall!\n" ; \
				printf "  Note: Run 'make restart' or 'docker compose up -d' to apply.\n" ; \
				;; \
			"close-db") \
				printf "$(BOLD)make close-db$(RESET)\n" ; \
				printf "  Configure .env to restrict the DB port ($(DB_PORT)) to 172.17.0.1.\n" ; \
				printf "  Note: Run 'make restart' or 'docker compose up -d' to apply.\n" ; \
				;; \
			"open-sftp") \
				printf "$(BOLD)make open-sftp$(RESET)\n" ; \
				printf "  Configure .env to bind the SFTP port ($(SFTP_PORT)) to 0.0.0.0 (accessible externally).\n" ; \
				printf "  $(BOLD)$(CYAN)WARNING:$(RESET) Exposing the SFTP port ($(SFTP_PORT)) externally is a security risk. Secure your host with a firewall!\n" ; \
				printf "  Note: Run 'make restart' or 'docker compose up -d' to apply.\n" ; \
				;; \
			"close-sftp") \
				printf "$(BOLD)make close-sftp$(RESET)\n" ; \
				printf "  Configure .env to restrict the SFTP port ($(SFTP_PORT)) to 127.0.0.1 (localhost only).\n" ; \
				printf "  Note: Run 'make restart' or 'docker compose up -d' to apply.\n" ; \
				;; \
			"size-small") \
				printf "$(BOLD)make size-small$(RESET)\n" ; \
				printf "  Apply SMALL sizing profile to .env (< 500 visits/day).\n" ; \
				printf "  Restricts resource limits. Perfect for local dev and low-memory servers.\n" ; \
				printf "  Note: Run 'make restart' to apply changes.\n" ; \
				;; \
			"size-medium") \
				printf "$(BOLD)make size-medium$(RESET)\n" ; \
				printf "  Apply MEDIUM sizing profile to .env (500 - 5000 visits/day).\n" ; \
				printf "  Balanced resource allocation for moderate production environments.\n" ; \
				printf "  Note: Run 'make restart' to apply changes.\n" ; \
				;; \
			"size-large") \
				printf "$(BOLD)make size-large$(RESET)\n" ; \
				printf "  Apply LARGE sizing profile to .env (> 5000 visits/day).\n" ; \
				printf "  High-performance configuration. Allocates more RAM.\n" ; \
				printf "  Note: Run 'make restart' to apply changes.\n" ; \
				;; \
			"size-show") \
				printf "$(BOLD)make size-show$(RESET)\n" ; \
				printf "  Show current sizing configuration parameters and identify active profile.\n" ; \
				;; \
			"crontab-init") \
				printf "$(BOLD)make crontab-init$(RESET)\n" ; \
				printf "  Create an example crontab file under 'docker/scripts/crontab' if it does not exist.\n" ; \
				;; \
			"secure") \
				printf "$(BOLD)make secure$(RESET)\n" ; \
				printf "  Lock the WordPress site. Core WordPress files become Read-Only.\n" ; \
				printf "  Folder uploads/cache remain writable for standard operations.\n" ; \
				;; \
			"insecure") \
				printf "$(BOLD)make insecure$(RESET)\n" ; \
				printf "  Unlock the WordPress site. Enable write access for updates or maintenance.\n" ; \
				;; \
			"fix-permissions") \
				printf "$(BOLD)make fix-permissions$(RESET)\n" ; \
				printf "  Restore standard ownership and base permissions (644/755) to WordPress files.\n" ; \
				;; \
			"release") \
				printf "$(BOLD)make release$(RESET)\n" ; \
				printf "  Generate a new CalVer release (vYYYY.MM.DD[.micro]), update CHANGELOG.md, and create/push a git tag.\n" ; \
				;; \
			"update") \
				printf "$(BOLD)make update [version=vX]$(RESET)\n" ; \
				printf "  Fetch changes and safely upgrade the codebase to a specific version or latest tag.\n" ; \
				;; \
			"rollback") \
				printf "$(BOLD)make rollback$(RESET)\n" ; \
				printf "  Interactively list recent git tags and roll back codebase to the selected version.\n" ; \
				;; \
			"check-updates") \
				printf "$(BOLD)make check-updates$(RESET)\n" ; \
				printf "  Scan docker-compose files and query Docker registries (Docker Hub, GHCR, Quay) to check\n" ; \
				printf "  for newer image versions matching the active flavors. Offers to auto-apply updates.\n" ; \
				;; \
			"redis-info") \
				printf "$(BOLD)make redis-info$(RESET)\n" ; \
				printf "  Retrieve and display statistics from the Valkey/Redis caching server.\n" ; \
				;; \
			"redis-monitor") \
				printf "$(BOLD)make redis-monitor$(RESET)\n" ; \
				printf "  Stream incoming Redis commands in real-time (useful for debugging cache keys).\n" ; \
				;; \
			"redis-ping") \
				printf "$(BOLD)make redis-ping$(RESET)\n" ; \
				printf "  Ping the Redis container to verify it is responsive.\n" ; \
				;; \
			"help") \
				printf "$(BOLD)make help$(RESET)\n" ; \
				printf "  Show the general help menu listing all available targets.\n" ; \
				;; \
			*) \
				printf "Unknown target: $@\n" ; \
				printf "For a list of all targets, run: make help\n" ; \
				;; \
		esac; \
	fi

else

.PHONY: help
help:
	@printf "$(BOLD)Usage:$(RESET) make [target] [service]\n"
	@printf "For detailed help on any command, run: make <target> help\n\n"
	@printf "$(BOLD)General$(RESET)\n"
	@printf "  $(CYAN)help$(RESET)            Show this help message\n"
	@printf "  $(CYAN)doctor$(RESET)          Run diagnostic checks (port conflicts, host transparent huge pages)\n"
	@printf "  $(CYAN)status$(RESET)          Show stack status (docker compose ps)\n"
	@printf "  $(CYAN)services$(RESET)        List available services\n"
	@printf "  $(CYAN)config$(RESET)          Validate Docker Compose configuration\n\n"
	@printf "$(BOLD)Core Lifecycle$(RESET)\n"
	@printf "  $(CYAN)start$(RESET)           Start the stack (creates, syncs & validates .env if missing)\n"
	@printf "  $(CYAN)stop$(RESET)            Stop the stack and remove orphans\n"
	@printf "  $(CYAN)restart$(RESET)         Restart the stack\n"
	@printf "  $(CYAN)rebuild$(RESET)         Rebuild services from Dockerfile (usage: make rebuild [service])\n"
	@printf "  $(CYAN)pull$(RESET)            Pull latest images\n"
	@printf "  $(CYAN)clean$(RESET)           Clean up everything, removing volumes (requires confirmation)\n\n"
	@printf "$(BOLD)Shell & Logs$(RESET)\n"
	@printf "  $(CYAN)shell$(RESET)           Open a shell in a container (usage: make shell [service], default: app)\n"
	@printf "  $(CYAN)logs$(RESET)            Follow logs for all containers or a specific service (usage: make logs [service])\n"
	@printf "  $(CYAN)logs-slow$(RESET)       Follow PHP-FPM slow request logs in real-time\n\n"
	@printf "$(BOLD)Database & Tools$(RESET)\n"
	@printf "  $(CYAN)db$(RESET)              DB Tools (console, import, export). Run 'make db', 'make db import <file>', 'make db export'\n"
	@printf "  $(CYAN)db-root$(RESET)         Access database console as root user\n"
	@printf "  $(CYAN)php-info$(RESET)        Show active PHP configuration in the container\n"
	@printf "  $(CYAN)opcache-clear$(RESET)   Clear OPcache for PHP-FPM pool (zero-downtime flush)\n"
	@printf "  $(CYAN)ctop$(RESET)            Monitor containers using ctop\n\n"
	@printf "$(BOLD)Port Management$(RESET)\n"
	@printf "  $(CYAN)open-ports$(RESET)      Open DB ($(DB_PORT)) & SFTP ($(SFTP_PORT)) ports to the outside world (0.0.0.0)\n"
	@printf "  $(CYAN)close-ports$(RESET)     Close DB ($(DB_PORT)) & SFTP ($(SFTP_PORT)) ports (restrict DB to 172.17.0.1, SFTP to 127.0.0.1)\n"
	@printf "  $(CYAN)open-db$(RESET)         Open only DB port ($(DB_PORT))\n"
	@printf "  $(CYAN)close-db$(RESET)        Close only DB port ($(DB_PORT))\n"
	@printf "  $(CYAN)open-sftp$(RESET)       Open only SFTP port ($(SFTP_PORT))\n"
	@printf "  $(CYAN)close-sftp$(RESET)      Close only SFTP port ($(SFTP_PORT))\n\n"
	@printf "$(BOLD)Sizing Profiles$(RESET)\n"
	@printf "  $(CYAN)size-small$(RESET)      Configure .env for low-traffic app (< 500 visits/day)\n"
	@printf "  $(CYAN)size-medium$(RESET)     Configure .env for medium-traffic app (500-5000 visits/day)\n"
	@printf "  $(CYAN)size-large$(RESET)      Configure .env for high-traffic app (> 5000 visits/day)\n"
	@printf "  $(CYAN)size-show$(RESET)       Show current sizing configuration\n\n"
	@printf "$(BOLD)Cron Management$(RESET)\n"
	@printf "  $(CYAN)crontab-init$(RESET)    Create example crontab file\n\n"
	@printf "$(BOLD)Security Management$(RESET)\n"
	@printf "  $(CYAN)secure$(RESET)            Lock WordPress core files (Read-Only)\n"
	@printf "  $(CYAN)insecure$(RESET)          Unlock WordPress core files (Write access for maintenance)\n"
	@printf "  $(CYAN)fix-permissions$(RESET)   Fix ownership and base permissions\n\n"
	@printf "$(BOLD)Versioning & Updates$(RESET)\n"
	@printf "  $(CYAN)release$(RESET)         Generate a new CalVer release, update CHANGELOG.md, and create a git tag\n"
	@printf "  $(CYAN)update$(RESET)          Fetch and safely upgrade the codebase (usage: make update [version=vX])\n"
	@printf "  $(CYAN)rollback$(RESET)        Interactively list recent tag versions and rollback to a selected one\n"
	@printf "  $(CYAN)check-updates$(RESET)   Check for Docker image updates in compose files\n"
	@if docker compose config --services 2>/dev/null | grep -q 'redis'; then \
		printf "\n$(BOLD)Redis Management$(RESET)\n"; \
		printf "  $(CYAN)redis-info$(RESET)      Show Redis server statistics\n"; \
		printf "  $(CYAN)redis-monitor$(RESET)   Monitor Redis commands in real-time\n"; \
		printf "  $(CYAN)redis-ping$(RESET)      Ping Redis server\n"; \
	fi
	@printf "\n"

.PHONY: init
init:
	@if [ ! -f .env ]; then \
		chmod +x docker/scripts/init-env.sh; \
		./docker/scripts/init-env.sh; \
	else \
		echo "ℹ️  .env already exists."; \
	fi

.PHONY: start
start:
	@if [ ! -f .env ]; then \
		$(MAKE) --no-print-directory init || exit 1; \
	else \
		$(MAKE) --no-print-directory sync || exit 1; \
	fi
	@$(MAKE) --no-print-directory validate
	@echo "🐳 Starting containers..."
	@. ./docker/scripts/set-env-vars.sh && docker compose up -d --remove-orphans
	@echo "✅ Stack is up!"

.PHONY: validate
validate:
	@echo "Validating .env configuration..."
	@[ -n "$$(grep '^PROJECT_NAME=' .env | cut -d= -f2 | head -1)" ] || \
		(echo "❌ ERROR: PROJECT_NAME is not set!"; exit 1)
	@[ -n "$$(grep '^PROJECT_ID=' .env | cut -d= -f2 | head -1)" ] || \
		(echo "❌ ERROR: PROJECT_ID is not set!"; exit 1)
	@[ -n "$$(grep '^DB_NAME=' .env | cut -d= -f2 | head -1)" ] || \
		(echo "❌ ERROR: DB_NAME is not set!"; exit 1)
	@[ -n "$$(grep '^DB_USER=' .env | cut -d= -f2 | head -1)" ] || \
		(echo "❌ ERROR: DB_USER is not set!"; exit 1)
	@[ -n "$$(grep '^DB_PASS=' .env | cut -d= -f2 | head -1)" ] || \
		(echo "❌ ERROR: DB_PASS is not set!"; exit 1)
	@[ "$$(grep '^USER_ID=' .env | cut -d= -f2 | head -1)" != "0" ] && \
		[ -n "$$(grep '^USER_ID=' .env | cut -d= -f2 | head -1)" ] || \
		(echo "❌ ERROR: USER_ID must be set and non-zero!"; exit 1)
	@[ "$$(grep '^GROUP_ID=' .env | cut -d= -f2 | head -1)" != "0" ] && \
		[ -n "$$(grep '^GROUP_ID=' .env | cut -d= -f2 | head -1)" ] || \
		(echo "❌ ERROR: GROUP_ID must be set and non-zero!"; exit 1)
	@grep -q "^DB_PASS=dbrootpass" .env && \
		echo "⚠️  WARNING: DB_PASS is using default password!" || true
	@grep -q "^DB_ROOT_PASS=dbrootpass" .env && \
		echo "⚠️  WARNING: DB_ROOT_PASS is using default password!" || true
	@grep -q "^SFTP_PASS=sftppass" .env && \
		echo "⚠️  WARNING: SFTP_PASS is using default password!" || true
	@echo "✅ Validation passed successfully!"

.PHONY: stop
stop:
	@echo "🛑 Stopping containers..."
	@. ./docker/scripts/set-env-vars.sh && docker compose down --remove-orphans
	@echo "✅ Stack is down!"

.PHONY: restart
restart:
	@echo "🔄 Restarting stack..."
	@$(MAKE) --no-print-directory stop
	@$(MAKE) --no-print-directory start

.PHONY: status
status:
	@. ./docker/scripts/set-env-vars.sh && docker compose ps

.PHONY: services
services:
	@. ./docker/scripts/set-env-vars.sh && docker compose config --services

.PHONY: sync
sync:
	@echo "🔄 Synchronizing .env with .env.dist..."
	@command -v python3 >/dev/null 2>&1 || (echo "❌ python3 is required for 'make sync'. Install it with: apt install python3 / brew install python3"; exit 1)
	@python3 docker/scripts/sync-env.py

.PHONY: logs
logs:
	@SERVICE="$(filter-out $@,$(MAKECMDGOALS))"; \
	if [ "$$SERVICE" = "wordpress" ]; then \
		echo "📋 Tailing WordPress debug log (/var/www/html/public/wp-content/debug.log)..."; \
		. ./docker/scripts/set-env-vars.sh && docker compose exec app tail -n 100 -f /var/www/html/public/wp-content/debug.log; \
	else \
		. ./docker/scripts/set-env-vars.sh && docker compose logs -f $$SERVICE; \
	fi

.PHONY: logs-slow
logs-slow: _ensure_env
	@echo "📋 Tailing PHP-FPM slow log (/var/www/html/tmp/php-fpm-slow.log)..."
	@. ./docker/scripts/set-env-vars.sh && docker compose exec app tail -n 100 -f /var/www/html/tmp/php-fpm-slow.log

.PHONY: shell
shell:
	@SERVICE="$(filter-out $@,$(MAKECMDGOALS))"; \
	if [ -z "$$SERVICE" ]; then SERVICE="app"; fi; \
	. ./docker/scripts/set-env-vars.sh && docker compose exec $$SERVICE /bin/bash 2>/dev/null || . ./docker/scripts/set-env-vars.sh && docker compose exec $$SERVICE /bin/sh

.PHONY: pull
pull:
	@. ./docker/scripts/set-env-vars.sh && docker compose pull

.PHONY: clean
clean:
	@printf "⚠️  WARNING: This will remove containers, networks, and VOLUMES. Are you sure? [y/N] " && read ans && \
	if [ $${ans:-N} = y ]; then \
		. ./docker/scripts/set-env-vars.sh && docker compose down -v --remove-orphans; \
		echo "🧹 Clean complete."; \
	else \
		echo "Aborting clean."; \
	fi

.PHONY: config
config:
	@. ./docker/scripts/set-env-vars.sh && docker compose config

.PHONY: rebuild
rebuild:
	@. ./docker/scripts/set-env-vars.sh && docker compose build $(filter-out $@,$(MAKECMDGOALS))

.PHONY: db
db: _ensure_env
	@ACTION="$(word 2,$(MAKECMDGOALS))"; \
	if [ "$$ACTION" = "import" ]; then \
		FILE="$(word 3,$(MAKECMDGOALS))"; \
		if [ -z "$$FILE" ]; then \
			echo "❌ ERROR: Please specify a file to import (e.g., make db import file.sql)"; \
			exit 1; \
		fi; \
		if [ ! -f "$$FILE" ]; then \
			echo "❌ ERROR: File $$FILE not found!"; \
			exit 1; \
		fi; \
		echo "📄 Importing $$FILE into database..."; \
		if command -v pv >/dev/null 2>&1; then \
			. ./docker/scripts/set-env-vars.sh && pv "$$FILE" | docker compose exec -T db sh -c 'MYSQL_PWD=$${MARIADB_PASSWORD} mariadb -u $${MARIADB_USER} $${MARIADB_DATABASE}'; \
		else \
			echo "💡 Tip: Install 'pv' (e.g., brew install pv / apt install pv) to see a progress bar during imports."; \
			. ./docker/scripts/set-env-vars.sh && docker compose exec -T db sh -c 'MYSQL_PWD=$${MARIADB_PASSWORD} mariadb -u $${MARIADB_USER} $${MARIADB_DATABASE}' < "$$FILE"; \
		fi; \
		echo "✅ Import complete!"; \
	elif [ "$$ACTION" = "export" ]; then \
		PROJECT_ID=$$(grep '^PROJECT_ID=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
		PROJECT_NAME=$$(grep '^PROJECT_NAME=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
		TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
		FILENAME="$${PROJECT_ID}-$${PROJECT_NAME}-$${TIMESTAMP}.sql"; \
		echo "📤 Exporting database to $$FILENAME..."; \
		if command -v pv >/dev/null 2>&1; then \
			. ./docker/scripts/set-env-vars.sh && docker compose exec -T db sh -c 'MYSQL_PWD=$${MARIADB_PASSWORD} mariadb-dump --single-transaction -u $${MARIADB_USER} $${MARIADB_DATABASE}' | sed 's/DEFINER[[:space:]]*=[[:space:]]*[^*]*\*/\*/g' | pv > "$$FILENAME"; \
		else \
			echo "💡 Tip: Install 'pv' (e.g., brew install pv / apt install pv) to see a progress tracker during exports."; \
			. ./docker/scripts/set-env-vars.sh && docker compose exec -T db sh -c 'MYSQL_PWD=$${MARIADB_PASSWORD} mariadb-dump --single-transaction -u $${MARIADB_USER} $${MARIADB_DATABASE}' | sed 's/DEFINER[[:space:]]*=[[:space:]]*[^*]*\*/\*/g' > "$$FILENAME"; \
		fi; \
		echo "✅ Export complete! Saved to $$FILENAME"; \
	elif [ -n "$$ACTION" ]; then \
		echo "❌ ERROR: Invalid db action: $$ACTION. Use 'import <file>', 'export', or no arguments for console."; \
		exit 1; \
	else \
		echo "🔌 Connecting to database..."; \
		. ./docker/scripts/set-env-vars.sh && docker compose exec -T db sh -c 'MYSQL_PWD=$${MARIADB_PASSWORD} mariadb -u $${MARIADB_USER} $${MARIADB_DATABASE}'; \
	fi

.PHONY: db-root
db-root: _ensure_env
	@echo "🔌 Connecting to database as root..."
	@. ./docker/scripts/set-env-vars.sh && docker compose exec -e MYSQL_PWD=$${DB_ROOT_PASS} db mariadb -u root $${DB_NAME}

.PHONY: ctop
ctop:
	@PROJECT_NAME=$$(grep '^PROJECT_NAME=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	docker run --rm -ti \
		--platform linux/amd64 \
		--name=ctop \
		--volume /var/run/docker.sock:/var/run/docker.sock:ro \
		elswork/ctop:latest -f "$$PROJECT_NAME"

.PHONY: php-info
php-info:
	@echo "🔍 Active PHP Configuration (CLI context):"
	@. ./docker/scripts/set-env-vars.sh && docker compose exec app php -i | grep -E "^(date\.timezone|error_log|error_reporting|display_errors|log_errors|max_input_vars|memory_limit|max_execution_time|opcache\.(enable|validate_timestamps|revalidate_freq)) "

.PHONY: opcache-clear
opcache-clear: _ensure_env
	@echo "🧹 Clearing OPcache (PHP-FPM)..."
	@. ./docker/scripts/set-env-vars.sh && docker compose exec -T app sh -c 'echo "<?php opcache_reset(); echo \"OPcache cleared\n\";" > $${APACHE_DOCUMENT_ROOT:-/var/www/html/public}/opcache_reset_temp.php'
	@. ./docker/scripts/set-env-vars.sh && docker compose exec -T app curl -s http://localhost:8080/opcache_reset_temp.php || echo "❌ Failed to query OPcache reset script"
	@. ./docker/scripts/set-env-vars.sh && docker compose exec -T app rm -f $${APACHE_DOCUMENT_ROOT:-/var/www/html/public}/opcache_reset_temp.php

.PHONY: doctor
doctor: _ensure_env
	@echo "🩺 Running diagnostic checks..."
	@echo "─────────────────────────────────"
	@docker info >/dev/null 2>&1 && echo "✅ Docker daemon is running" || echo "❌ Docker daemon is NOT running or accessible"
	@if [ -f /sys/kernel/mm/transparent_hugepage/enabled ]; then \
		THP_STATUS=$$(cat /sys/kernel/mm/transparent_hugepage/enabled | grep -o '\[.*\]' | tr -d '[]'); \
		echo "ℹ️  Host Transparent Huge Pages: $$THP_STATUS"; \
		if [ "$$THP_STATUS" = "never" ]; then \
			echo "   ⚠️  Note: OPcache Huge Code Pages won't work because THP is disabled on the host."; \
			echo "      (No action needed; OPcache falls back automatically.)"; \
		fi; \
	else \
		echo "ℹ️  Host Transparent Huge Pages: Not supported by OS kernel"; \
	fi
	@PROJECT_ID=$$(grep '^PROJECT_ID=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	DB_PORT="33$$PROJECT_ID"; \
	SFTP_PORT="22$$PROJECT_ID"; \
	DB_BIND=$$(grep '^DB_BIND_IP=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	DB_BIND=$${DB_BIND:-172.17.0.1}; \
	SFTP_BIND=$$(grep '^SFTP_BIND_IP=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	SFTP_BIND=$${SFTP_BIND:-127.0.0.1}; \
	DB_CID=$$(. ./docker/scripts/set-env-vars.sh && docker compose ps -q db 2>/dev/null || true); \
	SFTP_CID=$$(. ./docker/scripts/set-env-vars.sh && docker compose ps -q sftp 2>/dev/null || true); \
	DB_OWNED=0; \
	SFTP_OWNED=0; \
	if [ -n "$$DB_CID" ] && docker port "$$DB_CID" 2>/dev/null | grep -q ":$$DB_PORT"; then DB_OWNED=1; fi; \
	if [ -n "$$SFTP_CID" ] && docker port "$$SFTP_CID" 2>/dev/null | grep -q ":$$SFTP_PORT"; then SFTP_OWNED=1; fi; \
	if command -v ss >/dev/null 2>&1; then \
		DB_PORT_IN_USE=$$(ss -tln | grep -q ":$$DB_PORT " && echo 1 || echo 0); \
		SFTP_PORT_IN_USE=$$(ss -tln | grep -q ":$$SFTP_PORT " && echo 1 || echo 0); \
	elif command -v netstat >/dev/null 2>&1; then \
		DB_PORT_IN_USE=$$(netstat -tln | grep -q ":$$DB_PORT " && echo 1 || echo 0); \
		SFTP_PORT_IN_USE=$$(netstat -tln | grep -q ":$$SFTP_PORT " && echo 1 || echo 0); \
	else \
		DB_PORT_IN_USE=0; \
		SFTP_PORT_IN_USE=0; \
	fi; \
	if [ "$$DB_BIND" = "0.0.0.0" ]; then \
		if [ "$$DB_PORT_IN_USE" -eq 1 ]; then \
			if [ "$$DB_OWNED" -eq 1 ]; then \
				echo "✅ DB Port $$DB_PORT is OPEN externally (0.0.0.0) and in use by this project (normal)"; \
			else \
				echo "⚠️  WARNING: Port $$DB_PORT is configured to be OPEN externally but is occupied by another process/project!"; \
			fi; \
		else \
			echo "✅ DB Port $$DB_PORT is configured to be OPEN externally (0.0.0.0) and is available"; \
		fi; \
	else \
		if [ "$$DB_PORT_IN_USE" -eq 1 ]; then \
			if [ "$$DB_OWNED" -eq 1 ]; then \
				echo "🔒 DB Port $$DB_PORT is RESTRICTED to $$DB_BIND in this project (normal)"; \
			else \
				echo "⚠️  WARNING: Port $$DB_PORT is restricted to $$DB_BIND but is occupied by another process/project!"; \
			fi; \
		else \
			echo "🔒 DB Port $$DB_PORT is not open externally in this project (restricted to $$DB_BIND)"; \
		fi; \
	fi; \
	if [ "$$SFTP_BIND" = "0.0.0.0" ]; then \
		if [ "$$SFTP_PORT_IN_USE" -eq 1 ]; then \
			if [ "$$SFTP_OWNED" -eq 1 ]; then \
				echo "✅ SFTP Port $$SFTP_PORT is OPEN externally (0.0.0.0) and in use by this project (normal)"; \
			else \
				echo "⚠️  WARNING: Port $$SFTP_PORT is configured to be OPEN externally but is occupied by another process/project!"; \
			fi; \
		else \
			echo "✅ SFTP Port $$SFTP_PORT is configured to be OPEN externally (0.0.0.0) and is available"; \
		fi; \
	else \
		if [ "$$SFTP_PORT_IN_USE" -eq 1 ]; then \
			if [ "$$SFTP_OWNED" -eq 1 ]; then \
				echo "🔒 SFTP Port $$SFTP_PORT is RESTRICTED to localhost (127.0.0.1) in this project (normal)"; \
			else \
				echo "⚠️  WARNING: Port $$SFTP_PORT is restricted to localhost but is occupied by another process/project!"; \
			fi; \
		else \
			echo "🔒 SFTP Port $$SFTP_PORT is not open externally in this project (restricted to localhost)"; \
		fi; \
	fi
	@echo "─────────────────────────────────"

.PHONY: open-ports
open-ports: _ensure_env
	@echo "🌐 Opening DB and SFTP ports externally (0.0.0.0)..."
	$(call set_env,DB_BIND_IP,0.0.0.0)
	$(call set_env,SFTP_BIND_IP,0.0.0.0)
	@echo "⚠️  Ports configured to be open. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: close-ports
close-ports: _ensure_env
	@echo "🔒 Closing DB (172.17.0.1) and SFTP (127.0.0.1) ports..."
	$(call set_env,DB_BIND_IP,172.17.0.1)
	$(call set_env,SFTP_BIND_IP,127.0.0.1)
	@echo "✅ Ports configured to be closed. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: open-db
open-db: _ensure_env
	@echo "🌐 Opening DB port externally (0.0.0.0)..."
	$(call set_env,DB_BIND_IP,0.0.0.0)
	@echo "⚠️  DB port configured to be open. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: close-db
close-db: _ensure_env
	@echo "🔒 Closing DB port (172.17.0.1)..."
	$(call set_env,DB_BIND_IP,172.17.0.1)
	@echo "✅ DB port configured to be closed. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: open-sftp
open-sftp: _ensure_env
	@echo "🌐 Opening SFTP port externally (0.0.0.0)..."
	$(call set_env,SFTP_BIND_IP,0.0.0.0)
	@echo "⚠️  SFTP port configured to be open. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: close-sftp
close-sftp: _ensure_env
	@echo "🔒 Closing SFTP port (127.0.0.1)..."
	$(call set_env,SFTP_BIND_IP,127.0.0.1)
	@echo "✅ SFTP port configured to be closed. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: redis-info
redis-info:
	@. ./docker/scripts/set-env-vars.sh && docker compose exec redis valkey-cli info

.PHONY: redis-monitor
redis-monitor:
	@echo "📡 Monitoring Redis commands... (Press Ctrl+C to stop)"
	@. ./docker/scripts/set-env-vars.sh && docker compose exec redis valkey-cli monitor

.PHONY: redis-ping
redis-ping:
	@. ./docker/scripts/set-env-vars.sh && docker compose exec redis valkey-cli ping

# --- Security Management ---
.PHONY: secure
secure: _ensure_env
	@USER_ID=$$(grep '^USER_ID=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	GROUP_ID=$$(grep '^GROUP_ID=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	./docker/scripts/secure-wp.sh lock "$$USER_ID:$$GROUP_ID"

.PHONY: insecure
insecure: _ensure_env
	@USER_ID=$$(grep '^USER_ID=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	GROUP_ID=$$(grep '^GROUP_ID=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	./docker/scripts/secure-wp.sh unlock "$$USER_ID:$$GROUP_ID"

.PHONY: fix-permissions
fix-permissions: _ensure_env
	@USER_ID=$$(grep '^USER_ID=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	GROUP_ID=$$(grep '^GROUP_ID=' .env | cut -d= -f2 | head -1 | tr -d '"'\''\r '); \
	./docker/scripts/secure-wp.sh fix "$$USER_ID:$$GROUP_ID"

# --- Versioning & Updates ---
.PHONY: release
release:
	@./docker/scripts/release.sh

.PHONY: update
update:
	@./docker/scripts/update.sh $(version)

.PHONY: rollback
rollback:
	@./docker/scripts/rollback.sh

.PHONY: check-updates
check-updates:
	@python3 ./docker/scripts/check-image-updates.py

# --- Sizing Profiles ---
# Helper function to update a variable in .env (works on both macOS and Linux)
define set_env
	@if grep -q "^$(1)=" .env; then \
		if [ "$$(uname)" = "Darwin" ]; then \
			sed -i '' 's|^$(1)=.*|$(1)=$(2)|' .env; \
		else \
			sed -i 's|^$(1)=.*|$(1)=$(2)|' .env; \
		fi \
	else \
		awk 'END {if (NR>0 && $$0!="") printf "\n"}' .env >> .env; \
		echo "$(1)=$(2)" >> .env; \
	fi
endef

.PHONY: _ensure_env
_ensure_env:
	@if [ ! -f .env ]; then \
		$(MAKE) --no-print-directory init || exit 1; \
	fi

.PHONY: size-small
size-small: _ensure_env
	@echo "📐 Applying SMALL profile (< 500 visits/day)..."
	$(call set_env,APP_CPUS,0.5)
	$(call set_env,APP_MEMORY,256M)
	$(call set_env,APP_MEMORY_RESERVATION,64M)
	$(call set_env,CRON_CPUS,0.1)
	$(call set_env,CRON_MEMORY,128M)
	$(call set_env,CRON_MEMORY_RESERVATION,32M)
	$(call set_env,CRON_TMPFS_SIZE,64M)
	$(call set_env,DB_CPUS,1.0)
	$(call set_env,DB_MEMORY,512M)
	$(call set_env,DB_MEMORY_RESERVATION,128M)
	$(call set_env,DB_INNODB_BUFFER_POOL_SIZE,128M)
	$(call set_env,DB_INNODB_LOG_FILE_SIZE,32M)
	$(call set_env,DB_MAX_CONNECTIONS,50)
	$(call set_env,PHP_MEMORY_LIMIT,128M)
	$(call set_env,PHP_OPCACHE_MEMORY_CONSUMPTION,128)
	$(call set_env,APP_TMPFS_SIZE,128M)
	$(call set_env,APACHE_MAX_REQUEST_WORKERS,10)
	$(call set_env,PHP_FPM_PM_MAX_CHILDREN,10)
	$(call set_env,PHP_FPM_PM_MAX_REQUESTS,500)
	@echo "✅ SMALL profile applied. Run 'make restart' to apply changes."

.PHONY: size-medium
size-medium: _ensure_env
	@echo "📐 Applying MEDIUM profile (500-5000 visits/day)..."
	$(call set_env,APP_CPUS,1.0)
	$(call set_env,APP_MEMORY,512M)
	$(call set_env,APP_MEMORY_RESERVATION,128M)
	$(call set_env,CRON_CPUS,0.25)
	$(call set_env,CRON_MEMORY,256M)
	$(call set_env,CRON_MEMORY_RESERVATION,64M)
	$(call set_env,CRON_TMPFS_SIZE,128M)
	$(call set_env,DB_CPUS,2.0)
	$(call set_env,DB_MEMORY,1G)
	$(call set_env,DB_MEMORY_RESERVATION,256M)
	$(call set_env,DB_INNODB_BUFFER_POOL_SIZE,256M)
	$(call set_env,DB_INNODB_LOG_FILE_SIZE,64M)
	$(call set_env,DB_MAX_CONNECTIONS,100)
	$(call set_env,PHP_MEMORY_LIMIT,256M)
	$(call set_env,PHP_OPCACHE_MEMORY_CONSUMPTION,256)
	$(call set_env,APP_TMPFS_SIZE,256M)
	$(call set_env,APACHE_MAX_REQUEST_WORKERS,25)
	$(call set_env,PHP_FPM_PM_MAX_CHILDREN,25)
	$(call set_env,PHP_FPM_PM_MAX_REQUESTS,500)
	@echo "✅ MEDIUM profile applied. Run 'make restart' to apply changes."

.PHONY: size-large
size-large: _ensure_env
	@echo "📐 Applying LARGE profile (> 5000 visits/day)..."
	$(call set_env,APP_CPUS,2.0)
	$(call set_env,APP_MEMORY,1G)
	$(call set_env,APP_MEMORY_RESERVATION,256M)
	$(call set_env,CRON_CPUS,0.5)
	$(call set_env,CRON_MEMORY,512M)
	$(call set_env,CRON_MEMORY_RESERVATION,128M)
	$(call set_env,CRON_TMPFS_SIZE,256M)
	$(call set_env,DB_CPUS,4.0)
	$(call set_env,DB_MEMORY,2G)
	$(call set_env,DB_MEMORY_RESERVATION,512M)
	$(call set_env,DB_INNODB_BUFFER_POOL_SIZE,512M)
	$(call set_env,DB_INNODB_LOG_FILE_SIZE,128M)
	$(call set_env,DB_MAX_CONNECTIONS,300)
	$(call set_env,PHP_MEMORY_LIMIT,512M)
	$(call set_env,PHP_OPCACHE_MEMORY_CONSUMPTION,512)
	$(call set_env,APP_TMPFS_SIZE,512M)
	$(call set_env,APACHE_MAX_REQUEST_WORKERS,50)
	$(call set_env,PHP_FPM_PM_MAX_CHILDREN,50)
	$(call set_env,PHP_FPM_PM_MAX_REQUESTS,500)
	@echo "✅ LARGE profile applied. Run 'make restart' to apply changes."

.PHONY: size-show
size-show: _ensure_env
	@APP_MEM=$$(grep '^APP_MEMORY=' .env | cut -d= -f2 | tr -d '"'\''\r '); \
	DB_MEM=$$(grep '^DB_MEMORY=' .env | cut -d= -f2 | tr -d '"'\''\r '); \
	FPM_CHILDREN=$$(grep '^PHP_FPM_PM_MAX_CHILDREN=' .env | cut -d= -f2 | tr -d '"'\''\r '); \
	PROFILE="⚠️  CUSTOM (modified)"; \
	if [ "$$APP_MEM" = "256M" ] && [ "$$DB_MEM" = "512M" ] && [ "$$FPM_CHILDREN" = "10" ]; then \
		PROFILE="🟢 SMALL (Low traffic)"; \
	elif [ "$$APP_MEM" = "512M" ] && [ "$$DB_MEM" = "1G" ] && [ "$$FPM_CHILDREN" = "25" ]; then \
		PROFILE="🟡 MEDIUM (Medium traffic)"; \
	elif [ "$$APP_MEM" = "1G" ] && [ "$$DB_MEM" = "2G" ] && [ "$$FPM_CHILDREN" = "50" ]; then \
		PROFILE="🔴 LARGE (High traffic)"; \
	fi; \
	echo "📊 Current sizing configuration (Profile: $$PROFILE):"; \
	echo "─────────────────────────────────"
	@echo "  App:   CPU=$$(grep '^APP_CPUS=' .env | cut -d= -f2)  MEM=$$(grep '^APP_MEMORY=' .env | cut -d= -f2)  Tmpfs=$$(grep '^APP_TMPFS_SIZE=' .env | cut -d= -f2)"
	@echo "  Cron:  CPU=$$(grep '^CRON_CPUS=' .env | cut -d= -f2)  MEM=$$(grep '^CRON_MEMORY=' .env | cut -d= -f2)  Tmpfs=$$(grep '^CRON_TMPFS_SIZE=' .env | cut -d= -f2)"
	@echo "  DB:    CPU=$$(grep '^DB_CPUS=' .env | cut -d= -f2)  MEM=$$(grep '^DB_MEMORY=' .env | cut -d= -f2)  BufferPool=$$(grep '^DB_INNODB_BUFFER_POOL_SIZE=' .env | cut -d= -f2)  LogFile=$$(grep '^DB_INNODB_LOG_FILE_SIZE=' .env | cut -d= -f2)  MaxConn=$$(grep '^DB_MAX_CONNECTIONS=' .env | cut -d= -f2)"
	@echo "  PHP:   MemLimit=$$(grep '^PHP_MEMORY_LIMIT=' .env | cut -d= -f2)  OPcache=$$(grep '^PHP_OPCACHE_MEMORY_CONSUMPTION=' .env | cut -d= -f2)MB"
	@echo "─────────────────────────────────"

.PHONY: crontab-init
crontab-init:
	@if [ ! -f docker/scripts/crontab ]; then \
		mkdir -p docker/scripts; \
		echo "# m h dom mon dow user  command" > docker/scripts/crontab; \
		echo "# * * * * * www-data php /var/www/html/scripts/cron.php" >> docker/scripts/crontab; \
		echo "✅ Created example crontab at docker/scripts/crontab"; \
	else \
		echo "ℹ️  crontab file already exists."; \
	fi

# Catch-all target for positional arguments
%:
	@:

endif