# AGENTS.md — Persistent Project Context & Guidelines

This file serves as a knowledge base for any AI model (Antigravity, Gemini, Cursor, etc.) assisting with this project. It defines the preferred style, behavior, and technical details for the user.

## 🏗️ Technical Stack

- **Core**: Dockerized WordPress (PHP 8.1+).
- **Database**: MariaDB 12 (specified in `docker-compose.yml`).
- **Reverse Proxy**: Traefik (configured with dynamic labels).
- **Automation**: `Makefile` as the single entry point for management (start, stop, db, logs).
- **Telegram Bot**: Python 3.12 using `python-telegram-bot` (v21+).
  - Mode: Long-polling.
  - Integration: `wp-cli` bridge via `docker exec`.

## 🎨 Style & Behavior

### 1. Language Policy
- **Code & Technical Docs**: English. All variables, code comments, and internal technical documentation must be in English.
- **User Interface**: Spanish. Bot messages to the user, and chat interactions should be in Spanish.

### 2. Workflow Patterns
- **Makefile First**: Do not execute Docker Compose commands directly if a `Makefile` alias exists. If new functionality is needed, add it to the `Makefile` first.
- **Proactive Debugging**: If something fails, take responsibility for investigating logs (`make logs`) and validating the environment (`make validate`) before asking the user.
- **Security-First**: In the Telegram bot, always maintain access control via `BOT_ALLOWED_USERS`. Do not expose database ports outside `localhost` unless strictly necessary (and use `make open-ports` for that).

### 3. Coding Standards
- **Python**: Clean style, asynchronous (`async/await`), organized import management (`isort` style), and strict typing where possible.
- **Docker**: Keep images lightweight and centralize environment variables in `.env`.
- **Logging**: Use descriptive logging instead of `print()`. Silence noisy logs from external libraries (like `httpx`).

## 🧠 Historical Context & Preferences
- The user prefers robust and secure solutions over quick fixes.
- The Telegram bot is a "content creator" that handles heavy multimedia (video, audio) using FFmpeg.
- Consistency in the output format of bot commands is valued (e.g., `/today`, `/week`, `/month`, `/year` must be coherent).

---
*Last Updated: 2026-03-13*
