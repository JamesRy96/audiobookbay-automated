# File: audiobook_automated/app.py
"""Entry point for the application."""

import logging

from . import create_app

logger = logging.getLogger(__name__)

# Create the application instance using the factory.
# This global 'app' variable is what Gunicorn looks for by default.
app = create_app()


def main() -> None:  # pragma: no cover
    """CLI entry point to launch audiobookbay-automated directly."""
    app.run(host=app.config["LISTEN_HOST"], port=app.config["LISTEN_PORT"])


if __name__ == "__main__":  # pragma: no cover
    main()
