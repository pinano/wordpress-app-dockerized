"""
fecha_handler.py — ConversationHandler for the /fecha command.

Allows changing the publication date of the last post created by the bot.
The user sends the date as free text in the format DD/MM/YYYY HH:MM.
The UTC offset is read dynamically from WordPress options (gmt_offset).
"""
import logging
from datetime import datetime, timedelta, timezone

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import wp_cli

logger = logging.getLogger(__name__)

# Conversation states
WAITING_DATE = 0

DATE_FORMAT_LOCAL = "%d/%m/%Y %H:%M"
DATE_FORMAT_WP = "%Y-%m-%d %H:%M:%S"

STRING_ENTER_DATE = (
    "📅 Introduce la nueva fecha y hora de publicación con el formato:\n"
    "<code>DD/MM/AAAA HH:MM</code>\n\n"
    "Ejemplo: <code>01/01/2024 10:30</code>"
)


def _get_wp_gmt_offset() -> float:
    """Read gmt_offset from WordPress options. Returns hours as float (e.g. 1.0, -5.0)."""
    try:
        raw = wp_cli.run("option", "get", "gmt_offset")
        return float(raw) if raw else 0.0
    except Exception as exc:
        logger.warning("Could not read gmt_offset from WP, defaulting to 0: %s", exc)
        return 0.0


async def fecha_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point — /fecha command."""
    from blog_handler import _allowed  # local import to avoid circular deps

    user_id = update.effective_user.id
    if not _allowed(user_id):
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return ConversationHandler.END

    last_pub = context.user_data.get("last_published")
    if not last_pub or not last_pub.get("post_id"):
        await update.message.reply_text(
            "❌ No se ha encontrado ninguna publicación reciente para modificar.\n"
            "Publica primero una entrada con /blog."
        )
        return ConversationHandler.END

    await update.message.reply_text(STRING_ENTER_DATE, parse_mode="HTML")
    return WAITING_DATE


async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State WAITING_DATE — parse and apply the new date."""
    raw_text = update.message.text.strip()

    # Parse the date
    try:
        local_dt = datetime.strptime(raw_text, DATE_FORMAT_LOCAL)
    except ValueError:
        await update.message.reply_text(
            "⚠️ Formato incorrecto. Inténtalo de nuevo:\n"
            "<code>DD/MM/AAAA HH:MM</code>\n\n"
            "Ejemplo: <code>01/01/2024 10:30</code>",
            parse_mode="HTML",
        )
        return WAITING_DATE

    # Get WP timezone offset to compute GMT date
    gmt_offset_hours = _get_wp_gmt_offset()
    offset_seconds = int(gmt_offset_hours * 3600)
    wp_tz = timezone(timedelta(seconds=offset_seconds))

    # local_dt is naive — treat it as local WP time
    local_aware = local_dt.replace(tzinfo=wp_tz)
    gmt_dt = local_aware.astimezone(timezone.utc)

    post_date_str = local_dt.strftime(DATE_FORMAT_WP)
    post_date_gmt_str = gmt_dt.strftime(DATE_FORMAT_WP)

    last_pub = context.user_data.get("last_published", {})
    post_id = last_pub.get("post_id")

    status_msg = await update.message.reply_text(
        "⏳ Actualizando fecha en WordPress...", reply_markup=ReplyKeyboardRemove()
    )

    try:
        wp_cli.run(
            "post", "update", post_id,
            f"--post_date={post_date_str}",
            f"--post_date_gmt={post_date_gmt_str}",
        )
    except Exception as exc:
        logger.exception("wp post update date failed for post %s: %s", post_id, exc)
        await status_msg.edit_text("❌ Error al actualizar la fecha en WordPress.")
        return ConversationHandler.END

    # Clean WP Rocket cache
    try:
        wp_cli.run("rocket", "clean", "--confirm", "--path=/var/www/html/public/")
    except Exception as exc:
        logger.warning("WP Rocket cache clean failed (non-fatal): %s", exc)

    # Get post URL for confirmation message
    try:
        post_url = wp_cli.run("post", "get", post_id, "--field=guid")
    except Exception:
        post_url = None

    friendly_date = local_dt.strftime("%-d de %B de %Y a las %H:%M").replace(
        "January", "enero").replace("February", "febrero").replace("March", "marzo"
        ).replace("April", "abril").replace("May", "mayo").replace("June", "junio"
        ).replace("July", "julio").replace("August", "agosto").replace("September", "septiembre"
        ).replace("October", "octubre").replace("November", "noviembre").replace("December", "diciembre")

    lines = [f"✅ <b>Fecha actualizada correctamente</b>"]
    lines.append(f"🗓️ Nueva fecha: <b>{friendly_date}</b>")
    lines.append(f"📌 <b>Post ID:</b> {post_id}")
    if post_url:
        lines.append(f"🔗 <a href='{post_url}'>Ver entrada</a>")

    await status_msg.edit_text("\n".join(lines), parse_mode="HTML")
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Comando /fecha cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def build_fecha_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("fecha", fecha_start)],
        states={
            WAITING_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_input),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
        ],
        allow_reentry=True,
        per_message=False,
    )
