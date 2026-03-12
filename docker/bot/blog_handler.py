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

STRING_SKIP = "SALTAR"
STRING_ENTER_TITLE = "Título de la entrada"
STRING_ENTER_EXCERPT = "Texto de la entrada (o pulsa SALTAR)"
STRING_UPLOAD_MEDIA = "Envía imagen o vídeo (o pulsa SALTAR)"

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
        try:
            wp_cli.run(
                "post", "update", post_id,
                f"--post_content={text}",
                f"--post_excerpt={text}",
            )
        except Exception as exc:
            logger.exception("wp post update content failed: %s", exc)
            # non-fatal — continue

        data["content"] = text

    await update.message.reply_text(STRING_UPLOAD_MEDIA, reply_markup=SKIP_KEYBOARD)
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

    # ── SALTAR ──────────────────────────────────────────────────────────────
    if text == STRING_SKIP or (not msg_type and not text):
        # No media — just finish
        return await _finish(update, context)

    if not msg_type:
        await update.message.reply_text(
            "Tipo de archivo no reconocido. " + STRING_UPLOAD_MEDIA,
            reply_markup=SKIP_KEYBOARD,
        )
        return MEDIA

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
            if thumbnail_id and thumbnail_id.isdigit():
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

            thumb_file_name = wp_cli.run(
                "post", "meta", "pluck", thumbnail_id,
                "_wp_attachment_metadata", "sizes", "medium", "file",
            )
            thumb_url = stripped_dir + (thumb_file_name or "")

            # 6. Update post content with [video] shortcode
            shortcode = f"[video src='{video_url}' poster='{thumb_url}']"
            wp_cli.run("post", "update", post_id, f"--post_content={shortcode}")
            wp_cli.run("post", "term", "set", post_id, "post_format", "post-format-video", "--by=slug")

            data["post_type"] = "video"
            data["media_id"] = f"{media_id} (thumb_id = {thumbnail_id})"
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
            content = f'<audio controls><source src="{stripped}" type="audio/mpeg"></audio>'
            wp_cli.run("post", "update", post_id, f"--post_content={content}")
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

    lines = [post_url or "(sin URL)"]
    for key in ("title", "content", "post_type", "post_category", "media_id", "file"):
        if key in data:
            lines.append(f"\n{key}: {data[key]}")

    await update.message.reply_text("\n".join(lines), reply_markup=REMOVE_KEYBOARD)

    _clear_data(context)
    return ConversationHandler.END


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
