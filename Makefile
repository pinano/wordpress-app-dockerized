# Makefile for Dockerized Zend Framework 1.x App

# Default target
.PHONY: help
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  help          Show this help message"
	@echo "  init          Initialize environment (.env)"
	@echo "  start         Start the stack (creates & validates .env if missing)"
	@echo "  stop          Stop the stack and remove orphans"
	@echo "  restart       Restart the stack"
	@echo "  rebuild       Rebuild services from Dockerfile (usage: make rebuild [service])"
	@echo "  status        Show stack status (docker compose ps)"
	@echo "  services      List available services"
	@echo "  validate      Validate .env against minimum requirements"
	@echo "  sync          Synchronize .env with .env.dist (Add missing keys)"
	@echo "  logs          Follow logs for all containers or a specific service (usage: make logs [service])"
	@echo "  shell         Open a shell in a container (usage: make shell [service], default: app)"
	@echo "  pull          Pull latest images"
	@echo "  clean         Clean up everything, removing volumes (Requires confirmation)"
	@echo "  config        Validate Docker Compose configuration"
	@echo "  php-info      Show active PHP configuration in the container (OPcache, Memory, Errors...)"
	@echo "  db            DB Tools (console, import, export). Run 'make db', 'make db import <file>', 'make db export'"
	@echo "  ctop          Monitor containers using ctop"
	@echo ""
	@echo "Port Management:"
	@echo "  open-ports    Open DB & SFTP ports to the outside world (0.0.0.0)"
	@echo "  close-ports   Close DB & SFTP ports (restrict to 127.0.0.1)"
	@echo "  open-db       Open only DB port"
	@echo "  close-db      Close only DB port"
	@echo "  open-sftp     Open only SFTP port"
	@echo "  close-sftp    Close only SFTP port"
	@if docker compose config --services 2>/dev/null | grep -q 'redis'; then \
		echo ""; \
		echo "Redis Management:"; \
		echo "  redis-info    Show Redis server statistics"; \
		echo "  redis-monitor Monitor Redis commands in real-time"; \
		echo "  redis-ping    Ping Redis server"; \
	fi
	@echo ""
	@echo "Cron Management:"
	@echo "  crontab-init Create example crontab file"
	@echo ""
	@echo "Sizing:"
	@echo "  size-small    Configure .env for low-traffic app (< 500 visits/day)"
	@echo "  size-medium   Configure .env for medium-traffic app (500-5000 visits/day)"
	@echo "  size-large    Configure .env for high-traffic app (> 5000 visits/day)"
	@echo "  size-show     Show current sizing configuration"

.PHONY: init
init:
	@if [ ! -f .env ]; then \
		echo "⚙️  Initializing .env from .env.dist..."; \
		cp .env.dist .env; \
		dir_name=$$(basename "$$(pwd)"); \
		pid=$$(echo "$$dir_name" | cut -d'-' -f1); \
		if echo "$$pid" | grep -Eq '^[0-9]+$$'; then \
			pname=$$(echo "$$dir_name" | cut -d'-' -f2-); \
			echo "🔍 Detected PROJECT_ID: $$pid, PROJECT_NAME: $$pname"; \
			if [ "$$(uname)" = "Darwin" ]; then \
				sed -i '' "s|^PROJECT_ID=.*|PROJECT_ID=$$pid|" .env; \
				sed -i '' "s|^PROJECT_NAME=.*|PROJECT_NAME=$$pname|" .env; \
			else \
				sed -i "s|^PROJECT_ID=.*|PROJECT_ID=$$pid|" .env; \
				sed -i "s|^PROJECT_NAME=.*|PROJECT_NAME=$$pname|" .env; \
			fi; \
		else \
			printf "🔢 Enter PROJECT_ID (e.g., 999): " && read pid; \
			if [ -n "$$pid" ]; then \
				if [ "$$(uname)" = "Darwin" ]; then \
					sed -i '' "s|^PROJECT_ID=.*|PROJECT_ID=$$pid|" .env; \
				else \
					sed -i "s|^PROJECT_ID=.*|PROJECT_ID=$$pid|" .env; \
				fi; \
				echo "✅ PROJECT_ID set to $$pid"; \
			fi; \
		fi; \
		echo "✅ .env created. Please review variables before starting."; \
	else \
		echo "ℹ️  .env already exists."; \
	fi

.PHONY: start
start:
	@if [ ! -f .env ]; then \
		$(MAKE) --no-print-directory init || exit 1; \
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
	if [ "$$SERVICE" = "zend" ]; then \
		echo "📋 Tailing Zend application log (/var/www/html/tmp/zend_error.log)..."; \
		. ./docker/scripts/set-env-vars.sh && docker compose exec app tail -n 100 -f /var/www/html/tmp/zend_error.log; \
	else \
		. ./docker/scripts/set-env-vars.sh && docker compose logs -f $$SERVICE; \
	fi

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
		PROJECT_ID=$$(grep '^PROJECT_ID=' .env | cut -d= -f2 | head -1); \
		PROJECT_NAME=$$(grep '^PROJECT_NAME=' .env | cut -d= -f2 | head -1); \
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
		. ./docker/scripts/set-env-vars.sh && docker compose exec db sh -c 'MYSQL_PWD=$${MARIADB_PASSWORD} mariadb -u $${MARIADB_USER} $${MARIADB_DATABASE}'; \
	fi

.PHONY: ctop
ctop:
	@PROJECT_NAME=$$(grep '^PROJECT_NAME=' .env | cut -d= -f2 | head -1); \
	docker run --rm -ti \
		--platform linux/amd64 \
		--name=ctop \
		--volume /var/run/docker.sock:/var/run/docker.sock:ro \
		elswork/ctop:latest -f "$$PROJECT_NAME"

.PHONY: php-info
php-info:
	@echo "🔍 Active PHP Configuration (CLI context):"
	@. ./docker/scripts/set-env-vars.sh && docker compose exec app php -i | grep -E "^(date\.timezone|error_log|error_reporting|display_errors|log_errors|max_input_vars|memory_limit|max_execution_time|opcache\.(enable|validate_timestamps|revalidate_freq)) "

.PHONY: open-ports
open-ports: _ensure_env
	@echo "🌐 Opening DB and SFTP ports externally (0.0.0.0)..."
	$(call set_env,DB_BIND_IP,0.0.0.0)
	$(call set_env,SFTP_BIND_IP,0.0.0.0)
	@echo "⚠️  Ports configured to be open. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: close-ports
close-ports: _ensure_env
	@echo "🔒 Closing DB and SFTP ports (127.0.0.1)..."
	$(call set_env,DB_BIND_IP,127.0.0.1)
	$(call set_env,SFTP_BIND_IP,127.0.0.1)
	@echo "✅ Ports configured to be closed. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: open-db
open-db: _ensure_env
	@echo "🌐 Opening DB port externally (0.0.0.0)..."
	$(call set_env,DB_BIND_IP,0.0.0.0)
	@echo "⚠️  DB port configured to be open. Run 'make restart' or 'docker compose up -d' to apply."

.PHONY: close-db
close-db: _ensure_env
	@echo "🔒 Closing DB port (127.0.0.1)..."
	$(call set_env,DB_BIND_IP,127.0.0.1)
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
	@echo "📊 Current sizing configuration:"
	@echo "─────────────────────────────────"
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