# AGENTS.md — Persistent Project Context

> Read this **before** touching anything. It's brief. No excuses for ignoring it.

---

## 🗺️ What is this

Custom dockerized personal blog. WordPress serving content, with a Telegram bot as the publishing interface. Orchestrated with Docker Compose and managed via `Makefile`. Traefik sits in front as a reverse proxy and CrowdSec as the security layer.

---

## 🏗️ Stack (by order of importance)

| Component | Detail |
|---|---|
| **App** | WordPress on PHP 8.5 + Apache/FPM, custom image (`docker/Dockerfile`) |
| **Bot** | Python 3.12, `python-telegram-bot` v21+, long-polling, custom image (`docker/Dockerfile.bot`) |
| **DB** | MariaDB 12.1.2 (`mariadb:12.1.2`), port `33{PROJECT_ID}` on localhost |
| **Reverse Proxy** | External Traefik (`traefik` network), configured via labels in `docker-compose.yml` |
| **Cache** | Valkey 9 (Redis-compatible), `redis` profile, "Redis Object Cache" plugin in WP |
| **Cron** | Separate PHP-CLI container, `cron` profile, reads `docker/scripts/crontab` |
| **SFTP** | `linuxserver/openssh-server`, `sftp` profile, port `22{PROJECT_ID}` |
| **Security** | CrowdSec + Traefik Bouncer. Watchdog script with Telegram alerts. |

Optional services (`bot`, `cron`, `db`, `sftp`, `redis`) use **Docker Compose profiles**. They don't start automatically.

---

## ⚙️ How everything is managed

**The `Makefile` is the only management interface. Never use `docker compose` directly.**

```bash
make start / stop / restart       # Main stack
make rebuild [service]            # Rebuild without bringing everything down
make logs [service]               # Logs. No service = all. 'wordpress' = WP debug.log
make shell [service]              # Interactive shell (default: app)
make db                            # MariaDB console
make db import file.sql            # Import dump
make db export                     # Export dump (automatic timestamped filename)
make validate                      # Validate .env before starting
make sync                          # Sync .env with .env.dist (adds missing keys)
make open-ports / close-ports      # Open/close DB+SFTP to the outside (0.0.0.0 vs 127.0.0.1)
make size-small/medium/large       # Apply resource profiles to .env
```

### 🛡️ WordPress Hardening & Permissions
To prevent unauthorized file modifications (e.g., from vulnerable plugins), the site core can be locked:

- `make secure` — **Lock the site**. Core files become Read-Only. Uploads/cache remain writable.
- `make insecure` — **Unlock the site**. Enable write access for updates or maintenance.
- `make fix-permissions` — Restore standard owner/base permissions (644/755).

*Always keep the site in `secure` mode unless you are actively updating it.*

---

If you need to add new functionality, **add it to the `Makefile` first**.

---

## 🤖 The Telegram Bot

The bot is the heart of the project. It allows posting entries to WP from a mobile phone.

### Architecture
- The bot **does not use the WP REST API**. It talks to WordPress using `docker exec` → `wp-cli` (see `docker/bot/wp_cli.py`).
- Downloaded files go to `/var/bot-media/` (shared volume `bot-media` between bot and app).
- FFmpeg processes media before importing into WP.

### `/blog` Flow (ConversationHandler in `blog_handler.py`)
```
NORMAL MODE:  TITLE → CONTENT (optional, SKIP) → LOCATION_STATE → MEDIA (mandatory, single) → DONE
GALLERY MODE: TITLE → CONTENT (optional, SKIP) → LOCATION_STATE → MEDIA (mandatory, multiple) → DONE
```

### Processed Media Types
| Type | Processing | Result in WP |
|---|---|---|
| Photo | Direct | Featured image + `post-format-image` |
| Gallery | Multiple Photos | `[gallery]` shortcode + `post-format-gallery` |
| Video (MP4/MOV) | FFmpeg: thumbnail + transcode if MOV | `[video]` shortcode + `post-format-video` |
| Audio / Voice | FFmpeg: convert to MP3 VBR | `<audio>` tag in content + `post-format-audio` |
| Document | Direct | Generic attachment, fixed thumbnail (media ID 307) |

### Hardcoded Special IDs in WP
- `306` → Generic audio thumbnail
- `307` → Generic document thumbnail

### Bot Commands
- `/blog` — Interactive publisher (4-step flow). Instant publish for single media.
- `/blog gallery` — Special mode for galleries (up to 15 photos). Requires manual finish button.
- `/fecha` | `/date` — Updates the publication date of the last post and all its associated media.
- `/borrar` | `/delete` | `/undo` — Deletes the last published post (post + media(s) + thumbnail). Auto-consumes.
- `/ayuda` | `/help` — Help. `/start` — Welcome.
- `/cancel` | `/cancelar` — Cancel current conversation.

### Bot Security
- `BOT_ALLOWED_USERS` in `.env`: Comma-separated Telegram IDs. Only these users can use the bot.
- `BOT_WP_USER_MAP`: `telegram_id:wp_user_id,...` mapping to assign correct authorship in WP.

---

## 📁 Relevant Structure

```
/
├── Makefile                    # Single entry point for management
├── docker-compose.yml          # Defines all services and profiles
├── .env                        # Local config (do not commit, see .env.dist)
├── .env.dist                   # Variables template
├── docker/
│   ├── Dockerfile              # App image (WordPress/PHP)
│   ├── Dockerfile.bot          # Bot image (Python+FFmpeg)
│   ├── Dockerfile.cron         # Cron image (PHP-CLI)
│   ├── apache/httpd.conf       # Apache config
│   ├── php/custom.ini          # PHP tweaks
│   ├── bot/
│   │   ├── bot.py              # Bot entrypoint
│   │   ├── blog_handler.py     # Main ConversationHandler (/blog flow)
│   │   ├── config.py           # Bot config from env vars
│   │   ├── media_processor.py  # FFmpeg (thumb, transcode, audio)
│   │   └── wp_cli.py           # docker exec → wp-cli bridge
│   └── scripts/
│       ├── crontab             # Scheduled tasks for cron container
│       └── check-crowdsec.sh   # CrowdSec watchdog with Telegram alerts
├── docroot/                    # WordPress (public/ is the document root)
└── mariadb_data/               # MariaDB data (do not commit)
```

---

## 🎨 Code Style

### Python (Most Important)
- `async/await` always. The bot is 100% asynchronous.
- Strict typing where reasonable (`str`, `int`, `dict[int, int]`, etc.).
- Imports organized `isort` style (stdlib → third-party → local).
- Descriptive `logging` instead of `print()`. Silence noisy libs: `logging.getLogger("httpx").setLevel(logging.WARNING)`.
- UI strings to the user in **Spanish**. Code, comments, and logs in **English**.
- Errors are **not fatal by default**. If something fails in a non-critical step, log and continue.

### Docker / DevOps
- Lightweight images. Centralized environment variables in `.env`.
- Resources (CPU/RAM) always limited in `docker-compose.yml` with `deploy.resources`.
- Sensitive ports (DB, SFTP) bound to `127.0.0.1` by default.

---

## 🧠 Historical Context & Preferences

- **Robust > Fast**: I prefer solid solutions even if they take longer. Quick hacks are not okay.
- **Consistent Formatting**: Bot commands showing statistics (`/today`, `/week`, `/month`, `/year`) must have coherent output.
- **Proactive Debugging**: If something fails, investigate first (`make logs`, `make validate`) before asking me. Take ownership.
- **Security Always Present**: Bot access controlled by `BOT_ALLOWED_USERS`. DB never exposed without reason. CrowdSec active.
- **Chat Language**: Talk to me in Spanish, direct and without fluff.

---

*Last Updated: 2026-04-17*
