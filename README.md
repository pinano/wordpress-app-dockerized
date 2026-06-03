<p align="center">
  <img src="docs/badge.webp" alt="Dockerized WordPress App Logo" width="220" />
</p>

<h1 align="center">Dockerized WordPress Application</h1>

<p align="center">
  <strong>🚀 Modernizing WordPress Delivery: A performance-tuned, secure-by-default Docker orchestration with integrated Telegram Bot publishing.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/WordPress-21759B?style=for-the-badge&logo=wordpress&logoColor=white" alt="WordPress" />
  <img src="https://img.shields.io/badge/PHP-8.x-777BB4?style=for-the-badge&logo=php&logoColor=white" alt="PHP Versions" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/MariaDB-003545?style=for-the-badge&logo=mariadb&logoColor=white" alt="MariaDB" />
  <img src="https://img.shields.io/badge/Valkey%20/%20Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Valkey/Redis" />
  <img src="https://img.shields.io/badge/Telegram%20Bot-26A69A?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram Bot" />
  <img src="https://img.shields.io/badge/GNU%20Make-000000?style=for-the-badge&logo=gnu&logoColor=white" alt="GNU Make" />
</p>

A modernized Docker stack for running WordPress applications, featuring optimized performance, secure defaults, an interactive Telegram publishing interface, and easy management via `make`.

---

## Features
- **Configurable PHP Version**: Switch between PHP versions (e.g., 8.1, 8.3, 8.5) via `.env`.
- **MariaDB 12**: Latest stable database version with resource limitations and performance tuning.
- **Performance Tuned**: Optimized `opcache` and `realpath_cache` settings specifically for WordPress.
- **Tmpfs Integration**: High-performance, ephemeral storage for WordPress sessions and temp caches.
- **Secure by Default**: SFTP restricted to localhost, DB restricted to Docker bridge IP, and read-only WP core file locking.
- **Traefik Ready**: Integrated labels for Traefik reverse proxy.
- **Telegram Bot Interface**: Publishing posts directly from your mobile phone without using the REST API (executes commands via `wp-cli`).
- **Advanced Flexibility**: Built-in support for Redis/Valkey object cache, Xdebug, Cronjobs, and custom PHP/Apache overrides.
- **Unified Management**: Comprehensive, colorized `Makefile` with detailed target-specific help and environment diagnostics.

---

## Quickstart

1.  **Start the Stack**
    ```bash
    make start
    ```
    This will automatically copy `.env.dist` to `.env` if it doesn't exist, sync missing variables, and start the containers.

2.  **Access the Application**
    The application is configured to run behind Traefik (a reverse proxy).
    
    **If you have Traefik running on your host:**
    1. Ensure Traefik has an external Docker network named `traefik`.
    2. Access the app via your configured domain (e.g., `http://app-project.localhost`).
    
    **If you DON'T have Traefik:**
    1. Comment out the `traefik` network block in `docker-compose.yml`.
    2. Map the app's port explicitly (`ports: ["8080:8080"]`).
    3. Access the app via: `http://127.0.0.1:8080`.

3.  **Database Access**
    Connect to the MariaDB console using regular user credentials:
    ```bash
    make db
    ```
    You can also import and export database snapshots easily:
    ```bash
    make db export
    make db import <file.sql>
    ```

---

## Configuration

Configuration is managed via the `.env` file. Key variables include:

- `PROJECT_NAME`: Used for container naming and network isolation.
- `APP_ENV`: Application environment (`production` or `development`). **[Read the APP_ENV Guide here](docs/app_env.md).**
- `PHP_VERSION`: The PHP version tag for `serversideup/php` (e.g., `8.5`).
- `APACHE_DOCUMENT_ROOT`: Path to the public web root (default: `/var/www/html/public`).
- `DB_*`: Database credentials, table prefix, and bind IP settings.
- `SFTP_*`: SFTP user credentials.
- `COMPOSE_PROFILES`: Comma-separated list of services to enable (e.g. `db,cron,redis,sftp,wpcli`).

### Scalability and Capacity Profiles

The stack is designed to scale from low-traffic dev environments to large applications. You can apply pre-defined sizing parameters directly:

- `make size-small`: Allocates low RAM and CPU. Ideal for local dev or low-memory servers (< 500 visits/day).
- `make size-medium`: Balanced resources (500 - 5000 visits/day).
- `make size-large`: High-performance setup (> 5000 visits/day). Allocates higher DB buffer pools and PHP worker processes.

For details, see the **[Sizing Guide](docs/sizing.md)**.

---

## Security & Hardening (Permissions)

To prevent core file hijacking (e.g., malware modifying WordPress core assets), this stack features a built-in hardening command system:

- **Locked (Safe default)**: Run `make secure` to make all core WordPress files Read-Only for the web server. Folders like `uploads`, `cache`, and `languages` remain writable for standard operation.
- **Unlocked (Maintenance)**: Run `make insecure` when you need to upgrade WordPress or install/update plugins from the administrator dashboard.
- **Permissions Repair**: If permission issues arise after manual file uploads, use `make fix-permissions` to restore the standard UID/GID and permission levels.

*Always keep the site in **secure** mode during normal operation.*

---

## Management Commands

| Command | Description |
|---------|-------------|
| `make help` | Show general colorized help menu |
| `make <target> help` | Show target-specific detailed explanation |
| `make doctor` | Run diagnostic checks (ports conflict, host Transparent Huge Pages status) |
| `make start` | Start the stack (initializes, syncs, and validates `.env` if missing) |
| `make stop` | Stop the stack and cleanup orphans |
| `make restart` | Perform clean restart (equivalent to stop + start) |
| `make rebuild <service>` | Rebuild Docker images for the stack (e.g. `make rebuild app`) |
| `make status` | Show stack status (`docker compose ps`) |
| `make logs [service]` | Follow logs for all containers or a specific service (e.g. `make logs bot`) |
| `make logs wordpress` | Tail WordPress application debug log directly |
| `make shell [service]` | Open terminal inside container (defaults to `app`) |
| `make db` | Access MariaDB console as regular user |
| `make db-root` | Access database console as `root` user |
| `make db import <file>` | Import a SQL file into the database (supports `pv` progress bar) |
| `make db export` | Export a timestamped SQL snapshot from the database |
| `make opcache-clear` | Clear OPcache bytecode cache for the PHP pool (zero-downtime flush) |
| `make php-info` | Display active PHP configuration settings in the running container |
| `make ctop` | Monitor project containers in real-time using ctop |
| `make open-ports` / `close-ports` | Open/close DB and SFTP ports externally (0.0.0.0 vs restricted) |
| `make release` | Generate a new CalVer release, update CHANGELOG.md, and create a git tag |
| `make update [version=X]` | Checkout and upgrade codebase to a specific version or latest tag |
| `make rollback` | Interactively select and roll back codebase to a prior tag |
| `make size-small` / `medium` / `large` | Apply sizing resource profiles |
| `make size-show` | Show active sizing resource allocations |
| `make secure` / `insecure` | Lock (Read-only) / Unlock (Writable) WordPress core files |
| `make fix-permissions` | Restore standard file ownership and permissions |

---

## Services

- **app**: PHP-FPM + Apache (serversideup/php image).
- **bot** (Optional): Telegram bot for remote blogging (Python + FFmpeg).
- **cron**: CLI container to run scheduled WordPress cron tasks.
- **db**: MariaDB 12.1.2.
- **redis** (Optional): In-memory cache store (Powered by Valkey).
- **sftp** (Optional): SFTP server for file access.
- **wpcli** (On-demand): WordPress CLI tools.
