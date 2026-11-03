# File: audiobook_automated/healthcheck.py
"""Healthcheck script for Docker."""

import importlib
import logging
import sys
import urllib.request
from typing import TYPE_CHECKING

# Docker runs this file directly; resolve the sibling helper without loading the Flask package.
if TYPE_CHECKING:
    from . import environment  # pragma: no cover - static typing only
else:
    environment = importlib.import_module(f"{__package__}.environment" if __package__ else "environment")

logger = logging.getLogger(__name__)


def health_check(timeout: int = 3) -> None:
    """Perform a health check against the local Flask application.

    Args:
        timeout: The maximum time in seconds to wait for a response.

    Returns:
        None: This function exits the process directly.
    """
    # Retrieve the port from environment variables, defaulting to 5078
    port = environment.get_env("LISTEN_PORT", "5078")

    # Retrieve the configured listen host
    # If using 0.0.0.0 (all interfaces), we must query localhost (127.0.0.1) for the check to work locally.
    # If using [::] (all IPv6), we query [::1].
    listen_host = environment.get_env("LISTEN_HOST", "127.0.0.1")

    if listen_host == "0.0.0.0":  # nosec B104  # noqa: S104
        host = "127.0.0.1"
    elif listen_host == "[::]":
        host = "[::1]"
    else:
        host = listen_host

    # Use dedicated health endpoint (lighter than hitting the home page)
    url = f"http://{host}:{port}/health"

    try:
        # Explicit timeout prevents the healthcheck from hanging indefinitely
        # nosec B310: URL is constructed from trusted local env vars (localhost/loopback)
        with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec B310  # noqa: S310
            if response.status == 200:  # noqa: PLR2004
                sys.exit(0)  # Success
            else:
                logger.error("Health check failed with status: %s", response.status)
                sys.exit(1)
    except Exception as e:
        # Log the failure so the container health status includes a useful reason
        logger.error("Health check failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.ERROR)
    health_check(timeout=3)
