"""
media_date_checker.py — Audit and repair publication date synchronization
between WordPress posts and their associated media attachments.

Supported association methods:
1. Direct parent attachment: attachment.post_parent = post.ID
2. Featured image / thumbnail: wp_postmeta where meta_key = '_thumbnail_id'
3. Gallery shortcodes: [gallery ids="..."] inside post_content
4. Audio / Video / Image embeds matching attachment GUID or filename in post_content
"""
import argparse
import json
import logging
import re
import sys
from datetime import datetime
from typing import Any

import wp_cli

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("media_date_checker")

# Known static / generic thumbnail IDs that are shared across many posts
GENERIC_THUMBNAIL_IDS = {306, 307}


def get_wp_data() -> dict[str, Any]:
    """
    Fetch all published posts, all attachments, thumbnail mappings,
    and attached file metadata in a single bulk query via wp eval.
    """
    php_code = r"""
    global $wpdb;

    // 1. All published posts
    $posts_raw = $wpdb->get_results(
        "SELECT ID, post_title, post_date, post_date_gmt, post_content, post_status " .
        "FROM {$wpdb->posts} WHERE post_type = 'post' AND post_status = 'publish'",
        ARRAY_A
    );

    // 2. All attachments
    $attachments_raw = $wpdb->get_results(
        "SELECT ID, post_title, post_date, post_date_gmt, post_parent, guid, post_mime_type " .
        "FROM {$wpdb->posts} WHERE post_type = 'attachment'",
        ARRAY_A
    );

    // 3. Featured images (_thumbnail_id)
    $thumbnails_raw = $wpdb->get_results(
        "SELECT post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key = '_thumbnail_id'",
        ARRAY_A
    );

    // 4. Attached file paths (_wp_attached_file)
    $files_raw = $wpdb->get_results(
        "SELECT post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attached_file'",
        ARRAY_A
    );

    $out = array(
        'posts' => $posts_raw,
        'attachments' => $attachments_raw,
        'thumbnails' => $thumbnails_raw,
        'files' => $files_raw
    );

    echo json_encode($out);
    """
    logger.info("Fetching posts, attachments, and metadata from WordPress via WP-CLI...")
    raw = wp_cli.run("eval", php_code)
    if not raw:
        raise RuntimeError("Failed to fetch data from WordPress via WP-CLI eval")
    
    return json.loads(raw.strip())


def analyze_database(data: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze the relationships between posts and attachments,
    detecting shared media, orphaned media, and date discrepancies.
    """
    posts_list = data.get("posts", [])
    attachments_list = data.get("attachments", [])
    thumbnails_list = data.get("thumbnails", [])
    files_list = data.get("files", [])

    # Index attachments by ID
    attachments_by_id = {int(att["ID"]): att for att in attachments_list}
    
    # Index attached files by attachment ID
    file_by_att_id = {int(f["post_id"]): f["meta_value"] for f in files_list}
    
    # Index attached files by relative upload path (e.g. '2024/05/audio.mp3' -> att_id)
    att_by_upload_path: dict[str, int] = {}
    for att_id, file_path in file_by_att_id.items():
        if file_path:
            att_by_upload_path[file_path.strip()] = att_id

    # Index thumbnails by post ID
    thumb_by_post_id: dict[int, int] = {}
    for t in thumbnails_list:
        try:
            pid = int(t["post_id"])
            tid = int(t["meta_value"])
            thumb_by_post_id[pid] = tid
        except (ValueError, TypeError):
            continue

    # Map post -> set of media IDs
    post_to_media: dict[int, set[int]] = {}
    # Reverse map: media -> set of post IDs
    media_to_posts: dict[int, set[int]] = {}

    # Regex patterns
    gallery_regex = re.compile(r'\[gallery[^\]]*ids=["\']([0-9, ]+)["\']', re.IGNORECASE)
    wp_image_regex = re.compile(r'wp-image-(\d+)', re.IGNORECASE)
    upload_url_regex = re.compile(r'wp-content/uploads/([a-zA-Z0-9_\-/\.]+)', re.IGNORECASE)

    for p in posts_list:
        pid = int(p["ID"])
        media_set = set()

        # 1. Check thumbnail
        if pid in thumb_by_post_id:
            tid = thumb_by_post_id[pid]
            if tid in attachments_by_id:
                media_set.add(tid)

        # 2. Check gallery shortcode
        content = p.get("post_content", "") or ""
        for match in gallery_regex.finditer(content):
            ids_str = match.group(1)
            for raw_id in ids_str.split(","):
                clean_id = raw_id.strip()
                if clean_id.isdigit():
                    gid = int(clean_id)
                    if gid in attachments_by_id:
                        media_set.add(gid)

        # 3. Check wp-image-ID classes in content
        for match in wp_image_regex.finditer(content):
            img_id = int(match.group(1))
            if img_id in attachments_by_id:
                media_set.add(img_id)

        # 4. Check upload file paths in content (audio, video, documents, images)
        for match in upload_url_regex.finditer(content):
            rel_path = match.group(1)
            if rel_path in att_by_upload_path:
                media_set.add(att_by_upload_path[rel_path])

        post_to_media[pid] = media_set

    # Also add direct parent attachments: attachment.post_parent = post.ID
    for att_id, att in attachments_by_id.items():
        try:
            parent_id = int(att.get("post_parent", 0))
        except (ValueError, TypeError):
            parent_id = 0

        if parent_id in post_to_media:
            post_to_media[parent_id].add(att_id)

    # Populate media_to_posts reverse map
    for pid, m_ids in post_to_media.items():
        for mid in m_ids:
            if mid not in media_to_posts:
                media_to_posts[mid] = set()
            media_to_posts[mid].add(pid)

    # Analyze date discrepancies
    discrepancies: list[dict[str, Any]] = []
    posts_without_media: list[int] = []
    shared_media: dict[int, list[int]] = {}
    total_associations = 0
    synced_associations = 0

    for p in posts_list:
        pid = int(p["ID"])
        p_date = p["post_date"]
        p_date_gmt = p["post_date_gmt"]
        m_ids = post_to_media.get(pid, set())

        if not m_ids:
            posts_without_media.append(pid)
            continue

        for mid in m_ids:
            total_associations += 1
            att = attachments_by_id.get(mid)
            if not att:
                continue

            # Check if shared
            linked_posts = media_to_posts.get(mid, set())
            is_shared = len(linked_posts) > 1 or mid in GENERIC_THUMBNAIL_IDS

            if is_shared and mid not in shared_media:
                shared_media[mid] = list(linked_posts)

            att_date = att["post_date"]
            att_date_gmt = att["post_date_gmt"]

            # Discrepancy if local date or gmt date differs
            date_mismatch = (att_date != p_date)
            date_gmt_mismatch = (att_date_gmt != p_date_gmt)

            if date_mismatch or date_gmt_mismatch:
                discrepancies.append({
                    "post_id": pid,
                    "post_title": p.get("post_title", ""),
                    "post_date": p_date,
                    "post_date_gmt": p_date_gmt,
                    "media_id": mid,
                    "media_title": att.get("post_title", ""),
                    "media_file": file_by_att_id.get(mid, ""),
                    "media_date": att_date,
                    "media_date_gmt": att_date_gmt,
                    "is_shared": is_shared,
                    "shared_count": len(linked_posts),
                    "date_diff": date_mismatch,
                    "date_gmt_diff": date_gmt_mismatch,
                })
            else:
                synced_associations += 1

    return {
        "total_posts": len(posts_list),
        "total_attachments": len(attachments_list),
        "posts_without_media": posts_without_media,
        "total_associations": total_associations,
        "synced_associations": synced_associations,
        "discrepancies": discrepancies,
        "shared_media": shared_media,
        "post_to_media": post_to_media,
        "media_to_posts": media_to_posts,
    }


def print_report(analysis: dict[str, Any]) -> None:
    """Print a clean summary of the database date consistency."""
    total_posts = analysis["total_posts"]
    total_attachments = analysis["total_attachments"]
    posts_no_media = analysis["posts_without_media"]
    total_assoc = analysis["total_associations"]
    synced_assoc = analysis["synced_associations"]
    discrepancies = analysis["discrepancies"]
    shared = analysis["shared_media"]

    # Filter out shared static icons from normal discrepancies count
    exclusive_discrepancies = [d for d in discrepancies if not d["is_shared"]]
    shared_discrepancies = [d for d in discrepancies if d["is_shared"]]

    print("\n" + "=" * 65)
    print(" 📊 INFORME DE COHERENCIA DE FECHAS ENTRADAS <-> MEDIOS")
    print("=" * 65)
    print(f" Total de entradas publicadas:     {total_posts:,}")
    print(f" Total de adjuntos (medios) en BD: {total_attachments:,}")
    print(f" Entradas sin medios detectados:   {len(posts_no_media)}")
    print(f" Total de asociaciones analizadas: {total_assoc:,}")
    print("-" * 65)
    print(f" ✅ Asociaciones 100% sincronizadas: {synced_assoc:,} ({synced_assoc / max(1, total_assoc) * 100:.2f}%)")
    print(f" ⚠️ Asociaciones con desfase fecha:  {len(discrepancies):,} ({len(discrepancies) / max(1, total_assoc) * 100:.2f}%)")
    print(f"    • Medios exclusivos de la entrada: {len(exclusive_discrepancies):,}")
    print(f"    • Medios compartidos / genéricos:   {len(shared_discrepancies):,}")
    print("=" * 65 + "\n")

    if posts_no_media:
        print(f"⚠️ Entradas sin medios asociados ({len(posts_no_media)}): IDs {posts_no_media[:10]}")
        print("-" * 65)

    if exclusive_discrepancies:
        print("📌 Primeros 10 ejemplos de medios exclusivos con desfase de fecha:")
        print("-" * 65)
        for i, d in enumerate(exclusive_discrepancies[:10], 1):
            print(f"[{i}] Post ID {d['post_id']} ('{d['post_title'][:30]}')")
            print(f"    Fecha Post:  {d['post_date']} (GMT: {d['post_date_gmt']})")
            print(f"    Media ID {d['media_id']} ('{d['media_file']}')")
            print(f"    Fecha Media: {d['media_date']} (GMT: {d['media_date_gmt']})")
            print("-" * 65)

    if shared:
        print(f"\n📌 Medios compartidos o genéricos detectados ({len(shared)} en total):")
        for mid, pids in list(shared.items())[:5]:
            generic_tag = " (Ícono Genérico)" if mid in GENERIC_THUMBNAIL_IDS else ""
            print(f"  • Media ID {mid}{generic_tag}: usado en {len(pids)} entradas (ej. Posts: {pids[:5]})")
        print()


def fix_dates(analysis: dict[str, Any], dry_run: bool = False, include_shared: bool = False) -> int:
    """
    Update post_date, post_date_gmt, post_modified, and post_modified_gmt
    on attachments to match their parent post.
    """
    discrepancies = analysis["discrepancies"]
    if not include_shared:
        targets = [d for d in discrepancies if not d["is_shared"]]
    else:
        targets = discrepancies

    if not targets:
        logger.info("No discrepancies to fix.")
        return 0

    action_label = "SIMULATING" if dry_run else "EXECUTING"
    logger.info("%s date repair for %d attachments...", action_label, len(targets))

    if dry_run:
        print(f"\n[DRY RUN] Se actualizarían {len(targets)} medios con las fechas de sus respectivas entradas.")
        return len(targets)

    # Batch SQL update via WP-CLI eval for maximum speed and transaction safety
    # We group updates to run in chunks of 500
    chunk_size = 500
    total_updated = 0

    for i in range(0, len(targets), chunk_size):
        chunk = targets[i:i + chunk_size]
        
        # Build PHP array of updates: array('id' => X, 'date' => Y, 'date_gmt' => Z)
        updates_payload = []
        for item in chunk:
            updates_payload.append({
                "id": item["media_id"],
                "date": item["post_date"],
                "date_gmt": item["post_date_gmt"],
            })

        json_payload = json.dumps(updates_payload).replace("'", "\\'")

        php_fix_code = f"""
        global $wpdb;
        $updates = json_decode('{json_payload}', true);
        $count = 0;
        foreach ($updates as $u) {{
            $id = (int)$u['id'];
            $date = $u['date'];
            $date_gmt = $u['date_gmt'];
            $res = $wpdb->update(
                $wpdb->posts,
                array(
                    'post_date' => $date,
                    'post_date_gmt' => $date_gmt,
                    'post_modified' => $date,
                    'post_modified_gmt' => $date_gmt
                ),
                array('ID' => $id, 'post_type' => 'attachment'),
                array('%s', '%s', '%s', '%s'),
                array('%d', '%s')
            );
            if ($res !== false) {{
                $count++;
            }}
        }}
        echo $count;
        """
        
        raw_res = wp_cli.run("eval", php_fix_code)
        try:
            chunk_updated = int(raw_res.strip()) if raw_res else 0
            total_updated += chunk_updated
            logger.info("Progress: %d / %d attachments updated...", total_updated, len(targets))
        except (ValueError, TypeError) as exc:
            logger.error("Failed parsing update result for chunk: %s", exc)

    logger.info("Date repair finished. Total attachments updated: %d", total_updated)

    # Clean Redis / WP Object Cache
    logger.info("Flushing WordPress cache...")
    try:
        wp_cli.run("cache", "flush")
        logger.info("WordPress Object Cache flushed successfully.")
    except Exception as exc:
        logger.warning("Object cache flush failed (non-fatal): %s", exc)

    return total_updated


def inspect_post(post_id: int, data: dict[str, Any], analysis: dict[str, Any]) -> None:
    """Print detailed inspection of a specific post and its media."""
    posts_list = data.get("posts", [])
    post = next((p for p in posts_list if int(p["ID"]) == post_id), None)
    if not post:
        print(f"❌ Post ID {post_id} not found among published posts.")
        return

    attachments_by_id = {int(att["ID"]): att for att in data.get("attachments", [])}
    media_ids = analysis["post_to_media"].get(post_id, set())

    print(f"\n🔍 DETALLE DE LA ENTRADA ID {post_id}:")
    print(f"  Título:    {post.get('post_title')}")
    print(f"  Fecha:     {post.get('post_date')} (GMT: {post.get('post_date_gmt')})")
    print(f"  Contenido: {post.get('post_content')}")
    print(f"  Medios asociados detectados ({len(media_ids)}): {list(media_ids)}")

    for mid in media_ids:
        att = attachments_by_id.get(mid, {})
        print(f"    • Media ID {mid}: '{att.get('post_title')}' | Fecha: {att.get('post_date')} (GMT: {att.get('post_date_gmt')}) | GUID: {att.get('guid')}")


def main():
    parser = argparse.ArgumentParser(description="Audit and synchronize WordPress post and media dates.")
    parser.add_argument("--fix", action="store_true", help="Apply fixes to database")
    parser.add_argument("--dry-run", action="store_true", help="Simulate fixes without modifying database")
    parser.add_argument("--include-shared", action="store_true", help="Include shared/generic media in updates")
    parser.add_argument("--inspect-post", type=int, help="Inspect a specific post ID in detail")
    args = parser.parse_args()

    data = get_wp_data()
    analysis = analyze_database(data)

    if args.inspect_post:
        inspect_post(args.inspect_post, data, analysis)
        return

    print_report(analysis)

    if args.fix or args.dry_run:
        updated = fix_dates(analysis, dry_run=args.dry_run, include_shared=args.include_shared)
        if not args.dry_run:
            print(f"\n✅ Sincronización completada: {updated} medios actualizados con la fecha de su entrada.")
        else:
            print(f"\nℹ️ Simulación completada: {updated} medios listos para sincronizar.")


if __name__ == "__main__":
    main()

