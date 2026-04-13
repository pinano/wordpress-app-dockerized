"""
fecha_handler.py — ConversationHandler for the /fecha command.

Allows changing the publication date of the last post created by the bot.
The user sends the date as free text in the format DD/MM/YYYY HH:MM.
The UTC offset is read dynamically from WordPress options (gmt_offset).
"""
import html
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

_MONTHS_ES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _friendly_date(dt: datetime) -> str:
    """Return a human-readable Spanish date string, e.g. '1 de marzo de 2024 a las 10:30'."""
    return f"{dt.day} de {_MONTHS_ES[dt.month]} de {dt.year} a las {dt.strftime('%H:%M')}"

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

    if context.args:
        raw_text = " ".join(context.args)
        return await _process_date_update(update, context, raw_text)

    await update.message.reply_text(STRING_ENTER_DATE, parse_mode="HTML")
    return WAITING_DATE


async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State WAITING_DATE — parse and apply the new date."""
    raw_text = update.message.text.strip()
    return await _process_date_update(update, context, raw_text)


async def _process_date_update(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text: str) -> int:
    """Parse raw text as date and apply updates to WordPress."""
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

    # Update dates on associated media attachments (non-fatal)
    media_ids_to_update: list[str] = []
    
    # Support for both single media (old/legacy) and gallery lists
    m_ids = last_pub.get("media_ids", [])
    if last_pub.get("media_id"):
        m_ids.append(last_pub["media_id"])
    
    for mid in set(m_ids):
        if mid and str(mid).isdigit():
            media_ids_to_update.append(str(mid))

    if last_pub.get("thumbnail_id") and str(last_pub["thumbnail_id"]).isdigit():
        media_ids_to_update.append(str(last_pub["thumbnail_id"]))

    for mid in media_ids_to_update:
        try:
            wp_cli.run(
                "post", "update", mid,
                f"--post_date={post_date_str}",
                f"--post_date_gmt={post_date_gmt_str}",
            )
            logger.info("Updated date for attachment %s", mid)
        except Exception as exc:
            logger.warning("Could not update date for attachment %s (non-fatal): %s", mid, exc)

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

    friendly_date = _friendly_date(local_dt)

    lines = ["✅ <b>Fecha actualizada correctamente</b>"]
    lines.append(f"🗓️ Nueva fecha: <b>{html.escape(friendly_date)}</b>")
    lines.append(f"📌 <b>Post ID:</b> {html.escape(str(post_id))}")
    if post_url:
        lines.append(f"🔗 <a href='{html.escape(post_url)}'>Ver entrada</a>")

    msg_text = "\n".join(lines)
    try:
        await status_msg.edit_text(msg_text, parse_mode="HTML")
    except Exception as exc:
        logger.warning("edit_text failed, falling back to reply_text: %s", exc)
        try:
            await update.message.reply_text(msg_text, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as exc2:
            logger.error("reply_text fallback also failed: %s", exc2)
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
