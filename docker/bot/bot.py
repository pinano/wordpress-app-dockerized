"""
bot.py — Main entry point for the Telegram bot.

Runs in long-polling mode (no webhook needed).
"""
import logging
import os

from telegram.ext import Application, CommandHandler

import config
from blog_handler import (
    ayuda_command,
    build_blog_conversation_handler,
    deshacer_command,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Silence noisy httpx logs
logging.getLogger("httpx").setLevel(logging.WARNING)


async def start(update, context) -> None:
    await update.message.reply_text(
        "¡Hola! Usa /blog para crear una entrada en el blog."
    )


def main() -> None:
    logger.info("Starting bot (polling mode)…")

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .build()
    )

    # /start & /ayuda
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda_command))

    # /deshacer
    app.add_handler(CommandHandler("deshacer", deshacer_command))

    # /blog conversation
    app.add_handler(build_blog_conversation_handler())

    logger.info("Bot ready — listening for updates")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
