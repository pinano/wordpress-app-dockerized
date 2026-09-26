"""
wp_cli.py — Thin wrapper that runs WP-CLI commands natively inside the bot container.

Requires PHP-CLI, WP-CLI, and the docroot volume mounted at /var/www/html.
All commands run as the bot user so that file ownership in shared volumes
matches the host UID/GID.
"""
import logging
import os
import shlex
import subprocess
from typing import Optional

import config

logger = logging.getLogger(__name__)


def run(
    *wp_args: str,
    capture: bool = True,
    timeout: int = 120,
) -> Optional[str]:
    """
    Execute: wp <wp_args...>
    Returns the stripped stdout string when capture=True, else None.
    Raises subprocess.CalledProcessError on non-zero exit.
    """
    # Ensure PHP-CLI uses the same timezone as the container to prevent
    # WordPress from creating posts with a future date (which triggers
    # the 'future' / 'missed schedule' status).
    tz = os.environ.get("TZ", "UTC")
    cmd = [
        "php",
        "-d", f"date.timezone={tz}",
        config.WP_CLI_PATH,
        *wp_args,
        "--skip-themes",  # speeds up WP-CLI boots significantly
        "--path=/var/www/html/public",
    ]

    logger.debug("wp-cli: %s", shlex.join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        logger.warning(
            "wp-cli failed (exit %d): %s\nstderr: %s",
            result.returncode,
            shlex.join(cmd),
            result.stderr.strip() if result.stderr else "",
        )
        result.check_returncode()  # raises CalledProcessError

    output = result.stdout.strip() if capture and result.stdout else None
    logger.debug("wp-cli output: %r", output)
    return output
