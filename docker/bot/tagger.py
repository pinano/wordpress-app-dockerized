"""
tagger.py — Standalone script and module to analyze post media using Gemini API
and automatically assign tags to WordPress posts via WP-CLI.

Uses the new google-genai SDK (google.genai).
"""
import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

import config
import wp_cli

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("tagger")

# Lazy-load google.genai to avoid crashing if not installed yet
_genai_client = None


def _get_client():
    """Return an initialized Gemini client, or None on failure."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured in environment.")
        return None

    try:
        from google import genai
        from google.genai import types
        # Use stable v1 API (v1beta has free-tier quota = 0 on many accounts)
        _genai_client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version="v1"),
        )
        return _genai_client
    except ImportError:
        logger.error("google-genai package is not installed. Please run 'make rebuild bot'.")
        return None



# ── WP-CLI helpers ────────────────────────────────────────────────────────────

def get_untagged_post_ids() -> list[int]:
    """Return a list of post IDs that have no tags using a single WP-CLI call."""
    logger.info("Querying posts with no tags via wp-cli...")
    try:
        # We get all post IDs, then filter client-side based on tag absence.
        # Using wp post list with --tag__not_in requires a term ID; simpler to
        # use a raw SQL query via wp eval, which is a single round-trip.
        raw = wp_cli.run(
            "eval",
            (
                "global $wpdb; "
                "$ids = $wpdb->get_col("
                "  \"SELECT p.ID FROM {$wpdb->posts} p "
                "  WHERE p.post_type='post' AND p.post_status='publish' "
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM {$wpdb->term_relationships} tr "
                "    JOIN {$wpdb->term_taxonomy} tt ON tt.term_taxonomy_id = tr.term_taxonomy_id "
                "    WHERE tr.object_id = p.ID AND tt.taxonomy = 'post_tag'"
                "  ) ORDER BY p.post_date DESC\""
                "); "
                "echo implode(',', $ids);"
            ),
        )
        if not raw or not raw.strip():
            return []
        return [int(x) for x in raw.strip().split(",") if x.strip().isdigit()]
    except Exception as exc:
        logger.error("Failed to query untagged posts: %s", exc)
        return []


def get_post_media_path(post_id: int) -> Optional[str]:
    """
    Find the primary media attachment for a post and return its relative uploads path.
    Checks featured image first, then the first attached file.
    """
    # 1. Try featured image
    try:
        thumb_id_str = wp_cli.run("post", "meta", "get", str(post_id), "_thumbnail_id")
        if thumb_id_str and thumb_id_str.strip().isdigit():
            media_id = int(thumb_id_str.strip())
            attached = wp_cli.run("post", "meta", "get", str(media_id), "_wp_attached_file")
            if attached and attached.strip():
                return attached.strip()
    except Exception:
        pass

    # 2. Try first attachment
    try:
        attachments_json = wp_cli.run(
            "post", "list",
            f"--post_parent={post_id}",
            "--post_type=attachment",
            "--format=json",
            "--fields=ID",
            "--posts_per_page=1",
        )
        if attachments_json:
            attachments = json.loads(attachments_json)
            if attachments:
                media_id = int(attachments[0]["ID"])
                attached = wp_cli.run("post", "meta", "get", str(media_id), "_wp_attached_file")
                if attached and attached.strip():
                    return attached.strip()
    except Exception as exc:
        logger.warning("Failed to find attachment for post %s: %s", post_id, exc)

    return None


def download_media_to_temp(relative_path: str, post_id: int) -> Optional[str]:
    """
    Download a media file from WordPress uploads to a local temp path.
    Returns the absolute temp file path, or None on failure.
    """
    try:
        # Build internal HTTP URL (bot → app container, port 8080)
        url = f"http://{config.WP_CONTAINER}:8080/wp-content/uploads/{relative_path}"
        ext = Path(relative_path).suffix
        temp_path = os.path.join(config.DOWNLOAD_PATH, f"tagger_temp_{post_id}{ext}")
        os.makedirs(config.DOWNLOAD_PATH, exist_ok=True)
        logger.info("Downloading media for post %s: %s", post_id, url)
        urllib.request.urlretrieve(url, temp_path)
        return temp_path
    except Exception as exc:
        logger.error("Failed to download media for post %s: %s", post_id, exc)
        return None


# ── Gemini AI ─────────────────────────────────────────────────────────────────

def _build_prompt() -> str:
    """Build the tagging prompt by reading gemini_instructions.txt or using a fallback prompt."""
    instructions_file = Path(__file__).parent / "gemini_instructions.txt"
    if instructions_file.is_file():
        try:
            return instructions_file.read_text(encoding="utf-8").strip()
        except Exception as exc:
            logger.warning("Failed to read gemini_instructions.txt, using fallback: %s", exc)

    # Fallback prompt in case the file doesn't exist
    return (
        "Analiza esta imagen o vídeo y devuelve únicamente una lista de entre 3 y 6 "
        "etiquetas (tags) en español que describan mejor su contenido principal "
        "(por ejemplo: playa, niños, fiesta, naturaleza, familia, comida, etc.). "
        "Las etiquetas deben ser palabras sencillas, en minúsculas y estar separadas únicamente por comas. "
        "No incluyas explicaciones, introducción, puntos finales ni formato de lista; solo las etiquetas."
    )


_IMAGE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
_VIDEO_MIME_TYPES = {"video/mp4", "video/mov", "video/mpeg", "video/webm", "video/quicktime"}

def _detect_mime_type(local_file_path: str) -> str:
    """Detect MIME type from file extension."""
    ext = Path(local_file_path).suffix.lower()
    mapping = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif",
        ".mp4": "video/mp4", ".mov": "video/quicktime",
        ".mpeg": "video/mpeg", ".webm": "video/webm",
    }
    return mapping.get(ext, "application/octet-stream")


def get_tags_from_gemini(local_file_path: str) -> list[str]:
    """
    Analyze a local media file with Gemini and return suggested tags.

    For images: sends inline bytes (uses stable v1 API, no Files API needed).
    For videos: uses the Files API (required for large files).
    """
    from google import genai
    from google.genai import types

    client = _get_client()
    if not client:
        return []

    model_name = config.GEMINI_MODEL or "gemini-2.0-flash"
    mime_type = _detect_mime_type(local_file_path)

    logger.info("Analyzing %s (%s) with model %s...", local_file_path, mime_type, model_name)

    is_image = mime_type in _IMAGE_MIME_TYPES
    is_video = mime_type in _VIDEO_MIME_TYPES

    if not is_image and not is_video:
        logger.warning("Unsupported MIME type %s, skipping.", mime_type)
        return []

    uploaded_file = None

    try:
        if is_image:
            # ── Images: send inline as bytes (no Files API, uses v1 stable) ──
            with open(local_file_path, "rb") as f:
                image_bytes = f.read()
            media_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        else:
            # ── Videos: upload via Files API (required for large files) ──
            logger.info("Uploading video to Gemini Files API...")
            uploaded_file = client.files.upload(file=local_file_path)
            logger.info("Upload complete. Name: %s", uploaded_file.name)

            # Wait for processing
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = client.files.get(name=uploaded_file.name)
            if uploaded_file.state.name == "FAILED":
                logger.error("Gemini failed to process video.")
                return []

            media_part = types.Part.from_uri(
                file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type
            )

        contents = [media_part, _build_prompt()]

        # Retry with backoff on 429 (rate limit) and 503 (overload)
        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(model=model_name, contents=contents)
                raw = response.text.strip()
                logger.info("Gemini response: %s", raw)
                return [t.strip().lower() for t in raw.split(",") if t.strip()]
            except Exception as exc:
                exc_str = str(exc)
                is_rate_limit = "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str
                is_overload = "503" in exc_str or "UNAVAILABLE" in exc_str
                if is_rate_limit or is_overload:
                    retry_delay = 15 if is_overload else 60
                    import re
                    match = re.search(r"retryDelay['\"]:\s*['\"](\\d+)", exc_str)
                    if match:
                        retry_delay = int(match.group(1)) + 2
                    if attempt < max_retries - 1:
                        logger.warning(
                            "%s (attempt %d/%d). Waiting %ds...",
                            "Overload" if is_overload else "Rate limit",
                            attempt + 1, max_retries, retry_delay,
                        )
                        time.sleep(retry_delay)
                    else:
                        logger.error("API unavailable after %d retries.", max_retries)
                        return []
                else:
                    raise
        return []

    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        return []
    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
                logger.info("Deleted remote video file from Gemini.")
            except Exception as exc:
                logger.warning("Failed to delete remote file: %s", exc)


# ── Core logic ────────────────────────────────────────────────────────────────

def tag_single_post(post_id: int, dry_run: bool = False) -> list[str]:
    """
    Analyze the primary media for a post, get AI tags, and assign them.
    Returns the list of tags (whether or not dry_run is active).
    """
    logger.info("=== Processing Post ID %s ===", post_id)

    media_path = get_post_media_path(post_id)
    if not media_path:
        logger.warning("No media found for post %s. Skipping.", post_id)
        return []

    temp_file = download_media_to_temp(media_path, post_id)
    if not temp_file:
        return []

    tags = []
    try:
        tags = get_tags_from_gemini(temp_file)
        if tags:
            if dry_run:
                logger.info("[Dry Run] Would assign tags to post %s: %s", post_id, tags)
            else:
                wp_cli.run("post", "term", "set", str(post_id), "post_tag", ",".join(tags))
                logger.info("Tags assigned to post %s: %s", post_id, tags)
        else:
            logger.warning("No tags generated for post %s.", post_id)
    finally:
        try:
            os.remove(temp_file)
        except Exception:
            pass

    return tags


def tag_all_posts(limit: Optional[int] = None, dry_run: bool = False):
    """
    Find all published posts without tags, then process them up to `limit`.
    Respects the Gemini Free Tier rate limit with a delay between calls.
    """
    post_ids = get_untagged_post_ids()
    logger.info("Found %s posts with no tags.", len(post_ids))

    if not post_ids:
        logger.info("Nothing to do.")
        return

    if limit:
        post_ids = post_ids[:limit]
        logger.info("Processing the first %s posts.", len(post_ids))

    processed = 0
    for i, post_id in enumerate(post_ids):
        # Rate-limit: max 15 requests/min on the free tier → 1 request per 4.5s
        if i > 0:
            logger.info("Waiting 5 seconds to respect API rate limits...")
            time.sleep(5)

        try:
            tags = tag_single_post(post_id, dry_run=dry_run)
            if tags:
                processed += 1
        except Exception as exc:
            logger.error("Error processing post %s: %s", post_id, exc)

    logger.info("Done. %s/%s posts tagged successfully.", processed, len(post_ids))


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-tag WordPress posts using Gemini API.")
    parser.add_argument("--post-id", type=int, help="Tag a single post by ID.")
    parser.add_argument("--limit", type=int, help="Limit number of posts in batch mode.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Suggest tags without modifying the WordPress database.",
    )
    args = parser.parse_args()

    if not _get_client():
        logger.error("Cannot proceed: Gemini client could not be initialized.")
        sys.exit(1)

    if args.post_id:
        tag_single_post(args.post_id, dry_run=args.dry_run)
    else:
        tag_all_posts(limit=args.limit, dry_run=args.dry_run)
