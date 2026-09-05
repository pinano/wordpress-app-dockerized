"""
bot.py — Main entry point for the Telegram bot.

Runs in long-polling mode (no webhook needed).
"""
import logging
import os
import sys

from telegram.ext import Application, CommandHandler

import config
from blog_handler import (
    ayuda_command,
    borrar_command,
    build_blog_conversation_handler,
)
from fecha_handler import build_fecha_conversation_handler

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
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN is not configured or uses placeholder value. Bot cannot start.")
        sys.exit(1)

    logger.info("Starting bot (polling mode)…")

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .build()
    )

    # /start & /ayuda / /help
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["ayuda", "help"], ayuda_command))

    # /borrar / /delete / /undo
    app.add_handler(CommandHandler(["borrar", "delete", "undo"], borrar_command))

    # /fecha conversation
    app.add_handler(build_fecha_conversation_handler())

    # /blog conversation
    app.add_handler(build_blog_conversation_handler())

    logger.info("Bot ready — listening for updates")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
