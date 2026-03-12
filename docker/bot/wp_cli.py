"""
wp_cli.py — Thin wrapper that runs WP-CLI commands via 'docker exec' inside
the WordPress app container.

All commands are run as www-data (uid comes from the container) so that file
ownership matches what WordPress expects.
"""
import logging
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
    Execute: docker exec <WP_CONTAINER> wp <wp_args...>
    Returns the stripped stdout string when capture=True, else None.
    Raises subprocess.CalledProcessError on non-zero exit.
    """
    cmd = [
        "docker", "exec",
        "--user", "www-data",
        config.WP_CONTAINER,
        config.WP_CLI_PATH,
        *wp_args,
        "--allow-root",  # harmless when already www-data, required if root
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
        logger.error(
            "wp-cli failed (exit %d): %s\nstderr: %s",
            result.returncode,
            shlex.join(cmd),
            result.stderr.strip() if result.stderr else "",
        )
        result.check_returncode()  # raises CalledProcessError

    output = result.stdout.strip() if capture and result.stdout else None
    logger.debug("wp-cli output: %r", output)
    return output
