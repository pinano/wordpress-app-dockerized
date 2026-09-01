## v2026.09.01 (2026-09-01)

- feat: add media date audit and repair tools with Makefile integration (276b076)

## v2026.06.12 (2026-06-12)

- refactor: rename tag-posts to tag-create and add date-based filtering for post tagging (6e5ba1c)
- refactor: fetch post data using JSON format to reduce WP-CLI execution overhead (1ea70c1)

## v2026.06.11 (2026-06-11)

- feat(tagger): avoid infinite loop in video processing and enrich multimodal prompt with title/content context (eb312a8)
- refactor: rename repair-tags make target to tag-repair for consistency (af2c7fd)
- feat(tagger): add show_tagging_stats and tag-stats Makefile command to query tagged vs untagged counts (f4f6a83)
- fix(tagger): catch KeyboardInterrupt and exit cleanly without tracebacks on Ctrl+C (61806f5)
- feat: add repair-comma-tags utility to split and reassign improperly formatted WordPress tags (c5f057b)
- feat(tagger): add repair-tags Makefile target to split broken comma-separated tags (0ed870a)
- fix(tagger): pass tags as separate arguments to wp post term set instead of joined with commas (14f7e45)
- tagger: downscale and compress images using ffmpeg before sending to Gemini to prevent safety blocks (94507be)
- tagger: add robust text fallback and detailed response logging on empty/blocked Gemini response (4b524e5)
- feat: add tag-posts command to Makefile and update documentation for AI-powered retroactive tagging (57ed7fd)
- feat: implement v1beta client for video processing and add permissive safety settings to Gemini tagger (fc7a66f)
- refactor: upgrade media processing to support batch analysis and text-based tagging with audio support (6eb8507)
- feat: integrate Gemini AI tagging functionality to automatically categorize untagged WordPress posts (7f87b9b)

## v2026.06.04 (2026-06-04)

- feat: enhance check-image-updates script to resolve Dockerfile FROM variables and support filtering via Docker Hub API (e8cf763)
- feat: introduce automated virtual environment management and centralized Python interpreter selection in Makefile (f2a2115)

## v2026.06.03.5 (2026-06-03)

- fix: suppress grep errors and handle missing PROJECT_ID in database export filename generation (4273e5a)

## v2026.06.03.4 (2026-06-03)

- chore: update cron configuration, environment injection, volume mounts, and tmp directory initialization permissions (c451051)

## v2026.06.03.3 (2026-06-03)

- chore: upgrade MariaDB to 12.3.2 and Valkey to 9.1-alpine3.23 (a00d674)
- feat: add make check-updates command and python script to scan for Docker image updates (fc7ba1b)

## v2026.06.03.2 (2026-06-03)

- refactor: implement enhanced Apache security, performance tuning, and robust health monitoring systems (5899228)
- docs: update badge image extension to webp in README.md (9928804)
- docs: modernize README.md layout with logo, technology badges, and comprehensive commands list (b70618b)
- chore: handle offline/ssh failures when fetching tags in release scripts (b9e5102)
- chore: align .env.dist with zend-app-dockerized structure (f07f7a1)
- chore: add db-root target to Makefile (48d21f6)

## v2026.06.03.1 (2026-06-03)

- chore: test new commit (c334b7e)

## v2026.06.03 (2026-06-03)

- feat: enhance Makefile and implement release system (ed6ad5b)
- chore: update default MariaDB binding from 127.0.0.1 to 172.17.0.1 for improved container accessibility (d529608)
- refactor: implement regex-based _extract_id helper to robustly parse wp-cli output IDs (00f30d0)
- fix: sanitize wp-cli output by parsing only the first token of raw media import responses (3608582)
- refactor: update secure-wp.sh to use variable-based paths and force chmod operations to prevent errors on restricted filesystems (272f518)
- feat: add WordPress file system hardening script and Makefile commands to manage read-only site states (a77b9ee)
- chore: update SFTP service image to linuxserver/openssh-server in AGENTS.md (beaff13)
- feat: add initialization script to configure SFTP home directory to /config/upload (e99ab3e)
- remap (309d9c6)
- chore: migrate sftp service to linuxserver/openssh-server image and update configuration (4d5c596)
- feat: add gallery category support to blog handler and update help menu command order (dfe5d40)
- feat: add bilingual command aliases and improve date parsing flexibility in bot handlers (410fd76)
- feat: implement gallery mode for multi-photo posts and add /fecha command for publication date updates (a3ddc99)
- feat: Enable direct date input via /fecha command arguments and refactor date processing into a new helper function. (35349ce)
- chore: Remove map emoji and lowercase "Ubicación" in location prompt. (b5e28f9)
- Message format (3266dbd)
- fix: Add `-T` flag to `docker compose exec` for database connection to disable pseudo-TTY allocation. (67290b4)
- feat: update dates of associated media attachments when a post's date is changed (0e44f9e)
- feat: Rename `/deshacer` command to `/borrar` and improve date message formatting and reliability. (0f91eb9)
- feat: implement /fecha command to change the publication date of the last published post. (18cd5c4)
- feat: expand `AGENTS.md` with detailed project stack, bot architecture, management, file structure, and coding style guidelines. (98e1081)
- feat: Add AGENTS.md to provide persistent project context and guidelines for AI models. (a91b2c8)
- Refactor: Directly set post content for video and audio formats, and remove an unnecessary post content update during excerpt setting. (c836409)
- feat: Add optional location input to the `/blog` command, allowing users to embed Google Maps links in WordPress posts, and create comprehensive bot documentation. (6763064)
- docs: Update Valkey version to 9.0.3. (4b32d25)
- feat: Enhance media handling with mandatory uploads, improved processing feedback, and richer post-publication messages. (ebb7d5a)
- feat: add Telegram bot service for WordPress integration with media processing and WP-CLI interaction. (ac9edd6)
- feat: Allow configurable DB_HOST, remove explicit DB service dependency, and integrate cron into Docker Compose profiles. (084d01a)
- feat: Enable SFTP service and configure default Docker Compose profiles for db, sftp, and wpcli. (adf28cc)
- feat: Update app service image name to include ffmpeg and wpcli, and adjust Dockerfile base image accordingly. (ef9a14e)
- feat: Update base PHP image to include ffmpeg and wpcli (a05e21b)
- feat: Remove SFTP support, update PHP versions, add WP-CLI service, and refine documentation for logging, cron, and multi-tenancy. (70fe1b2)
- feat: adapt dockerized application setup from Zend Framework 1 to WordPress, updating documentation, Makefile, and environment configurations. (fd9d593)
- feat: upgrade default PHP version to 8.5 (3b880c8)
- Initial commit (de89cec)

