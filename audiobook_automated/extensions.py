# File: audiobook_automated/extensions.py
"""Global Flask extensions."""

import logging
import signal
import types
from typing import TYPE_CHECKING

from flask import Flask
from flask_executor import Executor
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect

from .clients import TorrentManager

if TYPE_CHECKING:  # pragma: no cover
    pass


logger = logging.getLogger(__name__)

# Initialize extensions (unbound to app)
limiter = Limiter(key_func=get_remote_address)
csrf = CSRFProtect()
talisman = Talisman()
executor = Executor()
torrent_manager = TorrentManager()


def register_shutdown_handlers(app: Flask) -> None:
    """Register signal handlers for graceful shutdown."""

    def shutdown_handler(signal_received: int, frame: types.FrameType | None) -> None:  # noqa: ARG001
        """Handle shutdown signals by stopping executors and network components."""
        app.logger.info("Graceful Shutdown: Signal %d received.", signal_received)

        # 1. Stop Scraper Executor
        app.logger.info("Graceful Shutdown: Stopping Scraper Executor...")
        # shutdown(wait=True) ensures tasks complete
        executor.shutdown(wait=True)

        # 2. Close Network Sessions
        # Local import to avoid circular dependency
        from .scraper.network import shutdown_network  # noqa: PLC0415

        app.logger.info("Graceful Shutdown: Closing Network Sessions...")
        shutdown_network()

        # 3. Close Torrent Client Connection
        app.logger.info("Graceful Shutdown: Closing Torrent Client...")
        torrent_manager.close()

        app.logger.info("Graceful Shutdown: Complete. Exiting.")
        # Removed explicit sys.exit(0) to comply with AGENTS.md

    # Register for SIGTERM (Docker stop) and SIGINT (Ctrl+C)
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
