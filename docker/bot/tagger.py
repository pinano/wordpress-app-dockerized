"""
tagger.py — Standalone script and module to analyze post media using Gemini API
and automatically assign tags to WordPress posts via WP-CLI.

Uses the new google-genai SDK (google.genai).
"""
import argparse
import json
import logging
import os
import subprocess
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
_genai_client_v1beta = None


def _get_client():
    """Return an initialized Gemini client (v1 stable), or None on failure."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured in environment.")
        return None

    try:
        from google import genai
        from google.genai import types
        # Use stable v1 API
        _genai_client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version="v1"),
        )
        return _genai_client
    except ImportError:
        logger.error("google-genai package is not installed. Please run 'make rebuild bot'.")
        return None


def _get_client_v1beta():
    """Return an initialized Gemini client (v1beta), or None on failure."""
    global _genai_client_v1beta
    if _genai_client_v1beta is not None:
        return _genai_client_v1beta

    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured in environment.")
        return None

    try:
        from google import genai
        from google.genai import types
        # Use v1beta API (required for Files API operations)
        _genai_client_v1beta = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version="v1beta"),
        )
        return _genai_client_v1beta
    except ImportError:
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


def get_post_media_info(post_id: int) -> list[dict]:
    """
    Get all media attachments and the featured image for a post using a single wp eval call.
    Returns a list of dicts: [{'id': int, 'mime': str, 'file': str, 'is_thumbnail': bool}]
    """
    php_code = (
        f"$res = array();"
        f"$thumb_id = get_post_meta({post_id}, '_thumbnail_id', true);"
        f"if ($thumb_id) {{"
        f"  $t = get_post($thumb_id);"
        f"  if ($t) {{"
        f"    $res[] = array("
        f"      'id' => (int)$t->ID,"
        f"      'mime' => $t->post_mime_type,"
        f"      'file' => get_post_meta($t->ID, '_wp_attached_file', true),"
        f"      'is_thumbnail' => true"
        f"    );"
        f"  }}"
        f"}}"
        f"$attachments = get_posts(array("
        f"  'post_parent' => {post_id},"
        f"  'post_type' => 'attachment',"
        f"  'posts_per_page' => -1"
        f"));"
        f"foreach ($attachments as $a) {{"
        f"  $found = false;"
        f"  foreach ($res as $r) {{"
        f"    if ($r['id'] == $a->ID) {{ $found = true; break; }}"
        f"  }}"
        f"  if (!$found) {{"
        f"    $res[] = array("
        f"      'id' => (int)$a->ID,"
        f"      'mime' => $a->post_mime_type,"
        f"      'file' => get_post_meta($a->ID, '_wp_attached_file', true),"
        f"      'is_thumbnail' => false"
        f"    );"
        f"  }}"
        f"}}"
        f"echo json_encode($res);"
    )
    try:
        raw = wp_cli.run("eval", php_code)
        if not raw or not raw.strip():
            return []
        return json.loads(raw.strip())
    except Exception as exc:
        logger.error("Failed to get post media info: %s", exc)
        return []


def get_post_text_info(post_id: int) -> tuple[str, str]:
    """Get the post title and excerpt/content to fall back on or enrich tagging."""
    try:
        title = wp_cli.run("post", "get", str(post_id), "--field=post_title").strip()
        excerpt = wp_cli.run("post", "get", str(post_id), "--field=post_excerpt").strip()
        if not excerpt:
            excerpt = wp_cli.run("post", "get", str(post_id), "--field=post_content").strip()
            # strip html tags if any
            import re
            excerpt = re.sub('<[^<]+?>', '', excerpt).strip()
        return title, excerpt
    except Exception as exc:
        logger.warning("Failed to get post text info: %s", exc)
        return "", ""


def download_media_to_temp(relative_path: str, post_id: int, item_id: Optional[int] = None) -> Optional[str]:
    """
    Download a media file from WordPress uploads to a local temp path.
    Returns the absolute temp file path, or None on failure.
    """
    try:
        # Build internal HTTP URL (bot → app container, port 8080)
        url = f"http://{config.WP_CONTAINER}:8080/wp-content/uploads/{relative_path}"
        ext = Path(relative_path).suffix
        suffix = f"_{item_id}" if item_id else ""
        temp_path = os.path.join(config.DOWNLOAD_PATH, f"tagger_temp_{post_id}{suffix}{ext}")
        os.makedirs(config.DOWNLOAD_PATH, exist_ok=True)
        logger.info("Downloading media for post %s: %s", post_id, url)
        urllib.request.urlretrieve(url, temp_path)
        return temp_path
    except Exception as exc:
        logger.error("Failed to download media for post %s: %s", post_id, exc)
        return None


def optimize_image_resolution(local_path: str) -> str:
    """
    Resize image to a maximum dimension of 800px and compress it
    using ffmpeg to reduce size and minimize safety false positives.
    Modifies the file in-place.
    """
    temp_out = None
    try:
        temp_out = local_path + ".opt.jpg"
        cmd = [
            config.FFMPEG_PATH or "ffmpeg",
            "-y",
            "-i", local_path,
            "-vf", "scale='min(800,iw)':'min(800,ih)':force_original_aspect_ratio=decrease",
            "-q:v", "5",
            temp_out
        ]
        logger.info("Optimizing image resolution/quality: %s", local_path)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.isfile(temp_out) and os.path.getsize(temp_out) > 0:
            os.replace(temp_out, local_path)
            logger.info("Successfully optimized image: %s", local_path)
    except Exception as exc:
        logger.warning("Failed to optimize image resolution/quality for %s: %s", local_path, exc)
    finally:
        if temp_out and os.path.isfile(temp_out):
            try:
                os.remove(temp_out)
            except Exception:
                pass
    return local_path


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
_AUDIO_MIME_TYPES = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg", "audio/mp4", "audio/x-m4a"}

def _detect_mime_type(local_file_path: str) -> str:
    """Detect MIME type from file extension."""
    ext = Path(local_file_path).suffix.lower()
    mapping = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif",
        ".mp4": "video/mp4", ".mov": "video/quicktime",
        ".mpeg": "video/mpeg", ".webm": "video/webm",
        ".mp3": "audio/mpeg", ".wav": "audio/wav",
        ".ogg": "audio/ogg", ".m4a": "audio/mp4",
    }
    return mapping.get(ext, "application/octet-stream")


def get_tags_from_gemini(local_file_paths: list[str], post_title: str = "", post_excerpt: str = "") -> list[str]:
    """
    Analyze media files and/or text with Gemini and return suggested tags.
    """
    from google import genai
    from google.genai import types

    # Dynamically select v1beta for video posts (required by Files API)
    has_video = any(_detect_mime_type(path) in _VIDEO_MIME_TYPES for path in local_file_paths)
    client = _get_client_v1beta() if has_video else _get_client()
    if not client:
        return []

    model_name = config.GEMINI_MODEL or "gemini-2.5-flash"
    parts = []
    uploaded_files = []

    try:
        for path in local_file_paths:
            mime_type = _detect_mime_type(path)
            is_image = mime_type in _IMAGE_MIME_TYPES
            is_audio = mime_type in _AUDIO_MIME_TYPES
            is_video = mime_type in _VIDEO_MIME_TYPES

            if is_image:
                logger.info("Adding image %s (%s) to Gemini request...", path, mime_type)
                with open(path, "rb") as f:
                    image_bytes = f.read()
                parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
            elif is_audio:
                logger.info("Adding audio %s (%s) to Gemini request...", path, mime_type)
                with open(path, "rb") as f:
                    audio_bytes = f.read()
                parts.append(types.Part.from_bytes(data=audio_bytes, mime_type=mime_type))
            elif is_video:
                logger.info("Uploading video %s (%s) to Gemini Files API...", path, mime_type)
                uploaded_file = client.files.upload(file=path)
                uploaded_files.append(uploaded_file)

                # Wait for processing
                while uploaded_file.state.name == "PROCESSING":
                    time.sleep(2)
                    uploaded_file = client.files.get(name=uploaded_file.name)
                if uploaded_file.state.name == "FAILED":
                    logger.error("Gemini failed to process video.")
                    continue

                parts.append(types.Part.from_uri(
                    file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type
                ))

        # Build prompt
        prompt = _build_prompt()
        if not local_file_paths and (post_title or post_excerpt):
            prompt = (
                f"Analiza el siguiente título y descripción de un post de blog y sugiere etiquetas descriptivas.\n"
                f"Título: {post_title}\n"
                f"Descripción: {post_excerpt}\n\n"
                f"{prompt}"
            )
            logger.info("No supported media files found. Falling back to text-based tagging...")

        contents = parts + [prompt]

        # Configure safety settings to avoid false positives on family photos (e.g. at the beach or kids playing)
        safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]
        config_obj = types.GenerateContentConfig(safety_settings=safety_settings)

        # Retry with backoff on 429 (rate limit) and 503 (overload)
        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config_obj
                )
                if not response.text:
                    try:
                        resp_dump = response.model_dump_json(exclude_none=True)
                    except Exception:
                        resp_dump = str(response)
                    logger.warning(
                        "Gemini response text is empty or blocked. Full response structure: %s",
                        resp_dump
                    )
                    return []
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
                    match = re.search(r"retryDelay['\"]:\s*['\"](\d+)", exc_str)
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
        for f in uploaded_files:
            try:
                client.files.delete(name=f.name)
                logger.info("Deleted remote video file %s from Gemini.", f.name)
            except Exception as exc:
                logger.warning("Failed to delete remote file %s: %s", f.name, exc)


# ── Core logic ────────────────────────────────────────────────────────────────

def tag_single_post(post_id: int, dry_run: bool = False) -> list[str]:
    """
    Analyze the media (images, audio, video thumbnails) or text content for a post,
    get AI tags from Gemini, and assign them.
    Returns the list of tags (whether or not dry_run is active).
    """
    logger.info("=== Processing Post ID %s ===", post_id)

    # 1. Fetch text info for fallback or additional context
    post_title, post_excerpt = get_post_text_info(post_id)

    # 2. Fetch all media attachments for the post
    media_items = get_post_media_info(post_id)

    # 3. Filter generic placeholder thumbnails (306/307)
    valid_items = [item for item in media_items if item['id'] not in (306, 307)]

    selected_items = []

    # Check for audio files first
    audio_items = [item for item in valid_items if item['mime'] and item['mime'].startswith('audio/')]
    video_items = [item for item in valid_items if item['mime'] and item['mime'].startswith('video/')]
    image_items = [item for item in valid_items if item['mime'] and item['mime'].startswith('image/')]

    is_video_post = False
    if audio_items:
        # Audio post: process the audio file
        logger.info("Detected audio post. Selecting audio file for analysis.")
        selected_items = [audio_items[0]]
    elif video_items:
        # Video post: download the video file for full analysis via Gemini Files API
        logger.info("Detected video post. Selecting video file for complete analysis.")
        selected_items = [video_items[0]]
        is_video_post = True
    elif image_items:
        if len(image_items) > 1:
            # Gallery post: process multiple images (cap at 8)
            logger.info("Detected gallery post with %d images. Selecting up to 8 images.", len(image_items))
            selected_items = image_items[:8]
        else:
            # Single photo post
            logger.info("Detected image post. Selecting photo for analysis.")
            selected_items = [image_items[0]]
    else:
        logger.info("No supported media attachments found. Will use text-only analysis.")

    # 4. Download and process selected items
    temp_files = []
    try:
        for item in selected_items:
            if not item.get('file'):
                continue
            temp_path = download_media_to_temp(item['file'], post_id, item['id'])
            if temp_path:
                mime_type = _detect_mime_type(temp_path)
                if mime_type in _IMAGE_MIME_TYPES:
                    temp_path = optimize_image_resolution(temp_path)
                temp_files.append(temp_path)

        # Fallback to thumbnail image if video download failed
        if not temp_files and is_video_post and image_items:
            logger.info("Video download failed. Trying thumbnail image as fallback...")
            fallback_item = image_items[0]
            if fallback_item.get('file'):
                temp_path = download_media_to_temp(fallback_item['file'], post_id, fallback_item['id'])
                if temp_path:
                    mime_type = _detect_mime_type(temp_path)
                    if mime_type in _IMAGE_MIME_TYPES:
                        temp_path = optimize_image_resolution(temp_path)
                    temp_files.append(temp_path)

        # 5. Call Gemini API
        tags = get_tags_from_gemini(temp_files, post_title=post_title, post_excerpt=post_excerpt)

        # Fallback to text-only if media-based tagging returned no results (e.g. due to safety block on images)
        if not tags and temp_files:
            logger.info("Media-based tagging returned no results (possibly blocked by safety filters). Falling back to text-only analysis...")
            tags = get_tags_from_gemini([], post_title=post_title, post_excerpt=post_excerpt)

        # 6. Assign tags
        if tags:
            if dry_run:
                logger.info("[Dry Run] Would assign tags to post %s: %s", post_id, tags)
            else:
                wp_cli.run("post", "term", "set", str(post_id), "post_tag", *tags)
                logger.info("Tags assigned to post %s: %s", post_id, tags)
        else:
            logger.warning("No tags generated for post %s.", post_id)

    finally:
        # Clean up all temp files
        for temp_file in temp_files:
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


def repair_comma_tags():
    """
    Find all post tags that contain a comma in their name, split them into
    individual tags, re-assign them to the posts, and delete the broken tags.
    """
    logger.info("Starting repair of comma-separated tags...")
    try:
        # 1. Fetch all tags as JSON
        import json
        raw_terms = wp_cli.run("term", "list", "post_tag", "--fields=term_id,name,slug", "--format=json")
        if not raw_terms:
            logger.info("No tags found.")
            return
        terms = json.loads(raw_terms)
    except Exception as exc:
        logger.error("Failed to fetch tags: %s", exc)
        return

    broken_terms_processed = 0
    for term in terms:
        term_id = term.get("term_id")
        name = term.get("name", "")
        slug = term.get("slug", "")
        
        if "," in name:
            logger.info("Found broken tag ID %s: '%s'", term_id, name)
            new_tags = [t.strip() for t in name.split(",") if t.strip()]
            if not new_tags:
                continue
            
            # 2. Find all posts having this tag
            try:
                raw_posts = wp_cli.run("post", "list", f"--tag={slug}", "--field=ID")
                if raw_posts:
                    post_ids = [int(pid) for pid in raw_posts.strip().split("\n") if pid.strip().isdigit()]
                else:
                    post_ids = []
            except Exception as exc:
                logger.error("Failed to query posts for tag %s: %s", slug, exc)
                continue
            
            logger.info("Found %d posts associated with broken tag '%s'", len(post_ids), name)
            for post_id in post_ids:
                try:
                    # Get all tags for this post to avoid losing other valid tags
                    raw_post_tags = wp_cli.run("post", "term", "list", str(post_id), "post_tag", "--field=name")
                    if raw_post_tags:
                        post_tags = [t.strip() for t in raw_post_tags.strip().split("\n") if t.strip()]
                    else:
                        post_tags = []
                    
                    # Remove the broken tag and merge the new ones
                    filtered_tags = [t for t in post_tags if t != name]
                    for nt in new_tags:
                        if nt not in filtered_tags:
                            filtered_tags.append(nt)
                    
                    # Re-assign tags
                    wp_cli.run("post", "term", "set", str(post_id), "post_tag", *filtered_tags)
                    logger.info("Repaired post %s: replaced '%s' with %s", post_id, name, filtered_tags)
                except Exception as exc:
                    logger.error("Failed to repair tags for post %s: %s", post_id, exc)
            
            # 3. Delete the broken term from WordPress database
            try:
                wp_cli.run("term", "delete", "post_tag", str(term_id))
                logger.info("Deleted broken tag term ID %s", term_id)
                broken_terms_processed += 1
            except Exception as exc:
                logger.error("Failed to delete broken tag term %s: %s", term_id, exc)
                
    logger.info("Done. Repaired %d broken tag terms.", broken_terms_processed)


def show_tagging_stats():
    """
    Query the WordPress database to show how many posts are tagged vs untagged.
    """
    logger.info("Querying tagging statistics via WP-CLI...")
    try:
        # We fetch all counts in a single round-trip
        raw = wp_cli.run(
            "eval",
            (
                "global $wpdb; "
                "$total = $wpdb->get_var(\"SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type='post' AND post_status='publish'\"); "
                "$untagged = $wpdb->get_var(\"SELECT COUNT(*) FROM {$wpdb->posts} p "
                "  WHERE p.post_type='post' AND p.post_status='publish' "
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM {$wpdb->term_relationships} tr "
                "    JOIN {$wpdb->term_taxonomy} tt ON tt.term_taxonomy_id = tr.term_taxonomy_id "
                "    WHERE tr.object_id = p.ID AND tt.taxonomy = 'post_tag'"
                "  )\"); "
                "echo \"$total,$untagged\";"
            )
        )
        if not raw or "," not in raw:
            logger.error("Failed to parse statistics output.")
            return

        total_str, untagged_str = raw.strip().split(",")
        total = int(total_str)
        untagged = int(untagged_str)
        tagged = total - untagged

        tagged_pct = (tagged / total * 100) if total > 0 else 0
        untagged_pct = (untagged / total * 100) if total > 0 else 0

        print("\n=== AI Tagging Statistics ===")
        print(f"Total published posts:  {total}")
        print(f"Tagged posts:           {tagged} ({tagged_pct:.1f}%)")
        print(f"Untagged posts:         {untagged} ({untagged_pct:.1f}%)")
        print("=============================\n")

    except Exception as exc:
        logger.error("Failed to fetch tagging statistics: %s", exc)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Auto-tag WordPress posts using Gemini API.")
        parser.add_argument("--post-id", type=int, help="Tag a single post by ID.")
        parser.add_argument("--limit", type=int, help="Limit number of posts in batch mode.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Suggest tags without modifying the WordPress database.",
        )
        parser.add_argument(
            "--repair",
            action="store_true",
            help="Split comma-separated tags into separate tags without re-calling Gemini.",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show the number of tagged and untagged posts in the database.",
        )
        args = parser.parse_args()

        if args.repair:
            repair_comma_tags()
        elif args.stats:
            show_tagging_stats()
        elif args.post_id:
            if not _get_client():
                sys.exit(1)
            tag_single_post(args.post_id, dry_run=args.dry_run)
        else:
            if not _get_client():
                sys.exit(1)
            tag_all_posts(limit=args.limit, dry_run=args.dry_run)
    except KeyboardInterrupt:
        logger.info("\nExecution interrupted by user (Ctrl+C). Exiting...")
        sys.exit(130)
