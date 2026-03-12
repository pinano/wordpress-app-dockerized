"""
bot.py — Main entry point for the Telegram bot.

Runs in long-polling mode (no webhook needed).
"""
import logging
import os

from telegram.ext import Application, CommandHandler

import config
from blog_handler import build_blog_conversation_handler

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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

    # /start
    app.add_handler(CommandHandler("start", start))

    # /blog conversation
    app.add_handler(build_blog_conversation_handler())

    logger.info("Bot ready — listening for updates")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
