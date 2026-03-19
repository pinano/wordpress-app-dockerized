"""
blog_handler.py — ConversationHandler that replicates BlogCommand.php.

State machine:
  TITLE   → Ask for post title → wp post create → go to CONTENT
  CONTENT → Ask for excerpt   → wp post update  → go to MEDIA
  MEDIA   → Ask for media file (or SALTAR)
              photo   → wp media import --featured_image, set post-format-image
              video   → ffmpeg thumbnail + convert MOV→MP4 + wp media import, set post-format-video
              audio   → ffmpeg →MP3 VBR + wp media import + update content with <audio> tag
              voice   → same as audio
              document→ wp media import + set generic thumbnail
            → go to DONE
  DONE    → wp rocket clean + reply with URL summary → END
"""
import logging
import os
from pathlib import Path

from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    constants,
)
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import media_processor
import wp_cli

logger = logging.getLogger(__name__)

# ── Conversation states ──────────────────────────────────────────────────────
TITLE, CONTENT, MEDIA, DONE = range(4)
TITLE, CONTENT, LOCATION_STATE, MEDIA = range(4)

STRING_SKIP = "SALTAR"
STRING_ENTER_TITLE = "Título de la entrada"
STRING_ENTER_EXCERPT = "Texto de la entrada (o pulsa SALTAR)"
STRING_UPLOAD_MEDIA = "Envía imagen, vídeo o audio (obligatorio)"

SKIP_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton(STRING_SKIP)]],
    resize_keyboard=True,
    one_time_keyboard=True,
    selective=True,
)
REMOVE_KEYBOARD = ReplyKeyboardRemove(selective=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wp_user(telegram_id: int) -> int:
    """Map Telegram user ID → WordPress author ID. Raises ValueError if unknown."""
    try:
        return config.USER_WP_MAP[telegram_id]
    except KeyError:
        raise ValueError(f"Telegram user {telegram_id} is not mapped to any WP user")


def _allowed(telegram_id: int) -> bool:
    return telegram_id in config.ALLOWED_USERS


def _get_data(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "blog" not in context.user_data:
        context.user_data["blog"] = {}
    return context.user_data["blog"]


def _clear_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("blog", None)


async def _download_telegram_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[str, str]:
    """
    Download the media attached to the current message.
    Returns (file_relative_path, local_full_path).

    file_relative_path follows Telegram's convention:  <subdir>/file_XXX.ext
    local_full_path is inside config.DOWNLOAD_PATH.
    """
    msg = update.message
    msg_type = _media_type(msg)

    if msg_type == "photo":
        tg_file_obj = msg.photo[-1]  # best quality
    else:
        tg_file_obj = getattr(msg, msg_type)

    tg_file = await context.bot.get_file(tg_file_obj.file_id)
    # tg_file.file_path looks like "photos/file_XXX.jpg" or "videos/file_XXX.mp4"
    file_relative_path = tg_file.file_path  # e.g. "photos/file_123.jpg"
    local_full_path = os.path.join(config.DOWNLOAD_PATH, file_relative_path)

    Path(local_full_path).parent.mkdir(parents=True, exist_ok=True)
    await tg_file.download_to_drive(local_full_path)

    return file_relative_path, local_full_path


def _media_type(msg) -> str | None:
    if msg.photo:
        return "photo"
    if msg.video:
        return "video"
    if msg.audio:
        return "audio"
    if msg.voice:
        return "voice"
    if msg.document:
        return "document"
    if msg.animation:
        return "animation"
    return None


def _category_for_type(msg_type: str) -> str:
    mapping = {
        "audio": "audios",
        "document": "documentos",
        "photo": "fotos",
        "video": "videos",
        "animation": "videos",
        "voice": "notas-de-voz",
    }
    return mapping.get(msg_type, "sin-categoria")


# ── State handlers ────────────────────────────────────────────────────────────

async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _clear_data(context)
    await update.message.reply_text("❌ Entrada cancelada.", reply_markup=REMOVE_KEYBOARD)
    return ConversationHandler.END


async def blog_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point — /blog command."""
    user_id = update.effective_user.id

    if not _allowed(user_id):
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return ConversationHandler.END

    _clear_data(context)
    await update.message.reply_text(STRING_ENTER_TITLE, reply_markup=REMOVE_KEYBOARD)
    return TITLE


async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State TITLE — receive title, create draft post."""
    user_id = update.effective_user.id
    title = update.message.text.strip()

    if not title:
        await update.message.reply_text(STRING_ENTER_TITLE, reply_markup=REMOVE_KEYBOARD)
        return TITLE

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    try:
        wp_user = _wp_user(user_id)
    except ValueError as exc:
        logger.error(exc)
        await update.message.reply_text("⛔ Error de configuración: usuario no mapeado.")
        return ConversationHandler.END

    data = _get_data(context)
    data["title"] = title
    data["wp_user"] = wp_user

    try:
        post_id = wp_cli.run(
            "post", "create",
            f"--post_title={title}",
            "--post-category=sin-categoria",
            f"--post_author={wp_user}",
            "--post_status=publish",
            "--porcelain",
        )
    except Exception as exc:
        logger.exception("wp post create failed: %s", exc)
        await update.message.reply_text("❌ Error al crear la entrada en WordPress.")
        _clear_data(context)
        return ConversationHandler.END

    data["post_id"] = post_id
    logger.info("Created WP post %s for user %s", post_id, user_id)

    await update.message.reply_text(STRING_ENTER_EXCERPT, reply_markup=SKIP_KEYBOARD)
    return CONTENT


async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State CONTENT — receive excerpt/content (or SALTAR)."""
    data = _get_data(context)
    text = update.message.text.strip()
    post_id = data["post_id"]

    if text and text != STRING_SKIP:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
        try:
            wp_cli.run(
                "post", "update", post_id,
                f"--post_excerpt={text}",
            )
        except Exception as exc:
            logger.exception("wp post update content failed: %s", exc)
            # non-fatal — continue

        data["content"] = text

    await update.message.reply_text("Envía una ubicación (GPS) o pulsa SALTAR", reply_markup=SKIP_KEYBOARD)
    return LOCATION_STATE

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State LOCATION_STATE — receive a location (or SALTAR)."""
    data = _get_data(context)
    post_id = data["post_id"]
    msg = update.message
    
    if msg.location:
        lat = msg.location.latitude
        lon = msg.location.longitude
        map_url = f"https://www.google.com/maps?q={lat},{lon}"
        
        current_content = data.get("content", "")
        loc_wp = f"<p><a href='{map_url}' target='_blank'>📍 Ver ubicación</a></p>"
        loc_tg = f"<a href='{map_url}' target='_blank'>📍 Ver ubicación</a>"
        
        new_excerpt_wp = f"{current_content}\n\n{loc_wp}".strip()
        new_excerpt_tg = f"{current_content}\n\n{loc_tg}".strip()
        
        try:
            # Update ONLY the excerpt with the location link
            wp_cli.run("post", "update", post_id, f"--post_excerpt={new_excerpt_wp}")
            
            # Save for Telegram summary
            data["content_tg"] = new_excerpt_tg
            
            # The actual WP content remains purely the text from Step 2
            data["content_wp"] = current_content

            # Keep post_type untouched as it will be filled by actual media.
        except Exception as exc:
            logger.exception("Location update failed: %s", exc)
    elif msg.text and msg.text.strip() == STRING_SKIP:
        pass
    else:
        await update.message.reply_text("⚠️ Por favor, envía una Ubicación o pulsa SALTAR.", reply_markup=SKIP_KEYBOARD)
        return LOCATION_STATE

    await update.message.reply_text(STRING_UPLOAD_MEDIA, reply_markup=REMOVE_KEYBOARD)
    return MEDIA


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State MEDIA — receive a media file (or SALTAR) and finish."""
    data = _get_data(context)
    post_id = data["post_id"]
    title = data["title"]
    wp_user = data["wp_user"]

    msg = update.message
    text = msg.text.strip() if msg.text else ""
    msg_type = _media_type(msg)

    # ── VERIFICAR MEDIO OBLIGATORIO ─────────────────────────────────────────
    if not msg_type:
        await update.message.reply_text(
            "⚠️ Se requiere adjuntar un archivo. " + STRING_UPLOAD_MEDIA,
            reply_markup=REMOVE_KEYBOARD,
        )
        return MEDIA

    status_msg = await update.message.reply_text("⏳ Descargando y procesando, esto puede tardar unos segundos...", reply_markup=REMOVE_KEYBOARD)
    data["status_msg_id"] = status_msg.message_id

    # ── Download ─────────────────────────────────────────────────────────────
    try:
        file_relative_path, local_full_path = await _download_telegram_file(update, context)
    except Exception as exc:
        logger.exception("Download failed: %s", exc)
        data["post_type"] = "Failed to download file."
        return await _finish(update, context)

    # Animations (GIF videos) → force videos category
    effective_type = msg_type
    if "animations" in file_relative_path:
        effective_type = "animation"

    category = _category_for_type(effective_type)
    file_stem = Path(local_full_path).stem          # e.g. "file_123"
    file_ext = Path(local_full_path).suffix.lower() # e.g. ".mp4"

    try:
        wp_cli.run("post", "update", post_id, f"--post_category={category}")
    except Exception as exc:
        logger.exception("wp post update category failed: %s", exc)

    # ── PHOTO ─────────────────────────────────────────────────────────────────
    if effective_type == "photo":
        try:
            media_id = wp_cli.run(
                "media", "import", local_full_path,
                f"--post_id={post_id}",
                "--featured_image",
                f"--title={title}",
                f"--caption={title}",
                f"--alt={title}",
                f"--user={wp_user}",
                "--preserve-filetime",
                "--porcelain",
            )
            if media_id and media_id.isdigit():
                wp_cli.run("post", "meta", "set", post_id, "_thumbnail_id", media_id)
            wp_cli.run("post", "term", "set", post_id, "post_format", "post-format-image", "--by=slug")

            data["post_type"] = "image"
            data["media_id"] = media_id
            data["thumb_local_path"] = local_full_path
        except Exception as exc:
            logger.exception("Photo import failed: %s", exc)
            data["post_type"] = "Error importing photo."

    # ── VIDEO / ANIMATION ─────────────────────────────────────────────────────
    elif effective_type in ("video", "animation"):
        try:
            # 1. Extract thumbnail
            thumb_path = media_processor.thumbnail_path_for(file_stem)
            media_processor.extract_thumbnail(local_full_path, thumb_path)

            # 2. Import thumbnail as featured image
            thumbnail_id = wp_cli.run(
                "media", "import", thumb_path,
                "--featured_image",
                f"--title={title}",
                f"--caption={title}",
                f"--alt={title}",
                f"--user={wp_user}",
                f"--post_id={post_id}",
                "--preserve-filetime",
                "--porcelain",
            )
            # Guardamos el thumbnail_id crudo para /deshacer
            if thumbnail_id and thumbnail_id.isdigit():
                data["raw_thumbnail_id"] = thumbnail_id
                wp_cli.run("post", "meta", "set", post_id, "_thumbnail_id", thumbnail_id)

            # 3. MOV → MP4 if needed
            if file_ext == ".mov":
                mp4_path = str(Path(local_full_path).with_suffix(".mp4"))
                media_processor.convert_mov_to_mp4(local_full_path, mp4_path)
                local_full_path = mp4_path
                file_relative_path = str(Path(file_relative_path).with_suffix(".mp4"))

            # 4. Import the video
            media_id = wp_cli.run(
                "media", "import", local_full_path,
                f"--title={title}",
                f"--caption={title}",
                f"--alt={title}",
                f"--user={wp_user}",
                f"--post_id={post_id}",
                "--preserve-filetime",
                "--porcelain",
            )

            # Assign the thumbnail to the video attachment so it shows up in the Media Grid
            if thumbnail_id and thumbnail_id.isdigit():
                wp_cli.run("post", "meta", "set", media_id, "_thumbnail_id", thumbnail_id)

            # 5. Build video URL and thumbnail URL for the [video] shortcode
            media_url = wp_cli.run("post", "get", media_id, "--field=guid")
            thumbnail_url = wp_cli.run("post", "get", thumbnail_id, "--field=guid")

            # Strip protocol → "//domain.com/wp-content/..."
            media_stripped = media_url.split(":", 1)[1] if media_url and ":" in media_url else media_url or ""
            stripped_dir = media_stripped.rsplit("/", 1)[0] + "/" if media_stripped else ""

            # Get actual uploaded filename
            video_file_name = wp_cli.run("post", "meta", "get", media_id, "_wp_attached_file")
            video_basename = video_file_name.split("/")[-1] if video_file_name else ""
            video_url = stripped_dir + video_basename

            # Get the full size thumbnail file (the uploaded original)
            thumb_file_name = wp_cli.run("post", "meta", "get", thumbnail_id, "_wp_attached_file")
            thumb_basename = thumb_file_name.split("/")[-1] if thumb_file_name else ""
            thumb_url = stripped_dir + thumb_basename

            # 6. Update post content with [video] shortcode
            shortcode = f"[video src='{video_url}' poster='{thumb_url}']"
            wp_cli.run("post", "update", post_id, f"--post_content={shortcode}")
            wp_cli.run("post", "term", "set", post_id, "post_format", "post-format-video", "--by=slug")

            data["post_type"] = "video"
            data["media_id"] = f"{media_id} (thumb_id = {thumbnail_id})"
            data["thumb_local_path"] = thumb_path
        except Exception as exc:
            logger.exception("Video import failed: %s", exc)
            data["post_type"] = "Error processing video."

    # ── AUDIO / VOICE ─────────────────────────────────────────────────────────
    elif effective_type in ("audio", "voice"):
        try:
            mp3_path = str(Path(local_full_path).with_suffix(".vbr.mp3"))
            media_processor.convert_audio_to_mp3_vbr(local_full_path, mp3_path)

            # Generic audio thumbnail (WP media ID 306 — must exist in WP)
            wp_cli.run("post", "meta", "set", post_id, "_thumbnail_id", "306")

            media_id = wp_cli.run(
                "media", "import", mp3_path,
                f"--title={title}",
                f"--caption={title}",
                f"--user={wp_user}",
                f"--post_id={post_id}",
                "--porcelain",
            )
            media_url = wp_cli.run("post", "get", media_id, "--field=guid")
            stripped = media_url.split(":", 1)[1] if media_url and ":" in media_url else media_url or ""
            audio_tag = f'<audio controls><source src="{stripped}" type="audio/mpeg"></audio>'
            wp_cli.run("post", "update", post_id, f"--post_content={audio_tag}")
            wp_cli.run("post", "term", "set", post_id, "post_format", "post-format-audio", "--by=slug")

            data["post_type"] = "audio"
            data["media_id"] = media_id
        except Exception as exc:
            logger.exception("Audio import failed: %s", exc)
            data["post_type"] = "Error processing audio."

    # ── DOCUMENT ──────────────────────────────────────────────────────────────
    else:
        try:
            # Generic document thumbnail (WP media ID 307 — must exist in WP)
            wp_cli.run("post", "meta", "set", post_id, "_thumbnail_id", "307")

            media_id = wp_cli.run(
                "media", "import", local_full_path,
                f"--title={title}",
                f"--caption={title}",
                f"--user={wp_user}",
                f"--post_id={post_id}",
                "--porcelain",
            )
            data["post_type"] = "document"
            data["media_id"] = media_id
        except Exception as exc:
            logger.exception("Document import failed: %s", exc)
            data["post_type"] = "Error importing document."

    data["file"] = file_relative_path
    data["post_category"] = category

    return await _finish(update, context)


async def _finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Clean cache, build summary message, end conversation."""
    data = _get_data(context)
    post_id = data.get("post_id", "")

    # Clean WP Rocket cache
    try:
        wp_cli.run(
            "rocket", "clean",
            "--confirm",
            "--path=/var/www/html/public/",
        )
    except Exception as exc:
        logger.warning("WP Rocket cache clean failed (non-fatal): %s", exc)

    # Get post URL
    try:
        post_url = wp_cli.run("post", "get", post_id, "--field=guid")
    except Exception:
        post_url = "(URL no disponible)"

    lines = ["✅ <b>Entrada publicada con éxito</b>"]
    if post_url:
        lines.append(f"🔗 <a href='{post_url}'>Ver entrada</a>\n")

    lines.append(f"📌 <b>Post ID:</b> {post_id}")
    if data.get("title"):
        lines.append(f"📝 <b>Título:</b> {data['title']}")
    if data.get("content_tg"):
        lines.append(f"💬 <b>Extracto:</b> {data['content_tg']}")
    elif data.get("content"):
        lines.append(f"💬 <b>Extracto:</b> {data['content']}")
    if data.get("post_category"):
        lines.append(f"📂 <b>Categoría:</b> {data['post_category']}")
    if data.get("post_type"):
        lines.append(f"📎 <b>Medio:</b> {data['post_type']}")
    if data.get("media_id"):
        lines.append(f"🆔 <b>Media ID:</b> {data['media_id']}")

    msg_text = "\n".join(lines)

    # Clean up the temporary status message
    if "status_msg_id" in data:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=data["status_msg_id"])
        except Exception:
            pass

    if data.get("thumb_local_path") and os.path.exists(data["thumb_local_path"]):
        try:
            with open(data["thumb_local_path"], "rb") as photo_file:
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=msg_text,
                    parse_mode="HTML",
                    reply_markup=REMOVE_KEYBOARD
                )
        except Exception as exc:
            logger.warning("No se pudo enviar la foto con reply_photo, cayendo fallback a reply_text: %s", exc)
            await update.message.reply_text(
                msg_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=REMOVE_KEYBOARD
            )
    else:
        await update.message.reply_text(
            msg_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=REMOVE_KEYBOARD
        )

    # Guardar en last_published para el comando /deshacer
    context.user_data["last_published"] = {
        "post_id": post_id,
        "media_id": data.get("media_id", "").split()[0] if data.get("media_id") else None, # Puede traer texto extra en videos
        "thumbnail_id": data.get("raw_thumbnail_id")
    }

    _clear_data(context)
    return ConversationHandler.END


# ── Standalone Commands ───────────────────────────────────────────────────────

async def ayuda_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía un mensaje de ayuda explicando las funcionalidades."""
    help_text = (
        "🤖 <b>Menú de Ayuda del Bot</b>\n\n"
        "Comandos disponibles:\n"
        "• /blog - Inicia el asistente paso a paso para publicar una nueva entrada.\n"
        "• /fecha - Cambia la fecha de publicación de la última entrada publicada.\n"
        "• /borrar - Elimina por completo (de WordPress y tu servidor) la última entrada que acabas de publicar, incluyendo sus fotos o vídeos.\n"
        "• /ayuda - Muestra este mensaje.\n\n"
        "📝 <b>Cómo publicar:</b>\n"
        "1. Escribe el <b>Título</b> (obligatorio)\n"
        "2. Escribe el <b>Texto/Extracto</b> (o pulsa SALTAR)\n"
        "3. Envía una <b>Ubicación (GPS)</b> (o pulsa SALTAR)\n"
        "4. Envía un <b>Medio</b> (obligatorio): Puede ser una Foto, Vídeo, Nota de voz o Archivo.\n\n"
        "<i>Nota: Los vídeos pesados pueden tardar unos segundos en procesarse para generar su formato óptimo web y carátula.</i>"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def borrar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina permanentemente el último post creado por este bot y sus medios asociados."""
    user_id = update.effective_user.id
    if not _allowed(user_id):
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return

    last_pub = context.user_data.get("last_published")
    if not last_pub or not last_pub.get("post_id"):
        await update.message.reply_text("❌ No se ha encontrado ninguna publicación reciente para deshacer.")
        return

    status_msg = await update.message.reply_text("🗑️ Eliminando contenido de WordPress...")
    
    deleted_items = []
    
    # Borrar thumbnail auxiliar de vídeo (si existe)
    if last_pub.get("thumbnail_id"):
        try:
            wp_cli.run("post", "delete", last_pub["thumbnail_id"], "--force")
            deleted_items.append("miniatura")
        except Exception as exc:
            logger.warning("Fallo al borrar thumbnail_id %s: %s", last_pub["thumbnail_id"], exc)

    # Borrar medio adjunto (foto, vídeo, audio)
    if last_pub.get("media_id") and last_pub["media_id"].isdigit():
        try:
            wp_cli.run("post", "delete", last_pub["media_id"], "--force")
            deleted_items.append("medio")
        except Exception as exc:
            logger.warning("Fallo al borrar media_id %s: %s", last_pub["media_id"], exc)

    # Borrar el post principal
    try:
        wp_cli.run("post", "delete", last_pub["post_id"], "--force")
        deleted_items.append("entrada principal")
    except Exception as exc:
        logger.exception("Fallo al borrar post_id %s: %s", last_pub["post_id"], exc)
        await status_msg.edit_text("❌ Ocurrió un error al intentar eliminar la entrada.")
        return

    # Limpiar caché WP Rocket
    try:
        wp_cli.run("rocket", "clean", "--confirm", "--path=/var/www/html/public/")
    except Exception:
        pass

    # Limpiar estado para evitar doble borrado
    context.user_data.pop("last_published", None)

    items_str = ", ".join(deleted_items)
    await status_msg.edit_text(f"✅ <b>Deshecho con éxito.</b>\nSe ha eliminado: {items_str}.", parse_mode="HTML")

# ── Build the ConversationHandler ─────────────────────────────────────────────

MEDIA_FILTER = (
    filters.PHOTO
    | filters.VIDEO
    | filters.AUDIO
    | filters.VOICE
    | filters.Document.ALL
    | filters.TEXT
)

def build_blog_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("blog", blog_start)],
        states={
            TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title),
            ],
            CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_content),
            ],
            LOCATION_STATE: [
                MessageHandler((filters.LOCATION | filters.TEXT) & ~filters.COMMAND, handle_location),
            ],
            MEDIA: [
                MessageHandler(MEDIA_FILTER & ~filters.COMMAND, handle_media),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
        ],
        # Allow user to restart the command mid-conversation
        allow_reentry=True,
        # Persist per-user data across restarts is handled by user_data (in-memory)
        per_message=False,
    )
