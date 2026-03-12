"""
config.py — Bot configuration loaded from environment variables.
"""
import os


def _parse_user_map(raw: str) -> dict[int, int]:
    """Parse 'telegram_id:wp_id,telegram_id:wp_id' into a dict."""
    result = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        tg, wp = pair.split(":")
        result[int(tg.strip())] = int(wp.strip())
    return result


def _parse_allowed_users(raw: str) -> set[int]:
    return {int(uid.strip()) for uid in raw.split(",") if uid.strip()}


# Telegram
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

# Comma-separated list of allowed Telegram user IDs
ALLOWED_USERS: set[int] = _parse_allowed_users(
    os.environ.get("BOT_ALLOWED_USERS", "")
)

# Mapping of Telegram user ID → WordPress author ID
# Format: "6888739:3,12642481:2"
USER_WP_MAP: dict[int, int] = _parse_user_map(
    os.environ.get("BOT_WP_USER_MAP", "")
)

# Name of the WordPress app container (used for docker exec)
WP_CONTAINER: str = os.environ.get("BOT_CONTAINER_NAME", "app")

# Local path (inside the bot container) where downloaded media is stored.
# This must also be mounted at the same path inside the WordPress container.
DOWNLOAD_PATH: str = os.environ.get("BOT_DOWNLOAD_PATH", "/var/bot-media")

# WP-CLI path inside the app container
WP_CLI_PATH: str = os.environ.get("BOT_WP_CLI_PATH", "/usr/local/bin/wp")

# ffmpeg binary path inside the bot container
FFMPEG_PATH: str = os.environ.get("BOT_FFMPEG_PATH", "/usr/bin/ffmpeg")
