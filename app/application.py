from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, render_template, request

from config import APP_SETTINGS_KEY, load_settings, log_settings
from db import initialize_database
from errors import AppError
from logging_utils import configure_logging
from routes.downloads import downloads_bp
from routes.pages import pages_bp
from routes.settings import settings_bp

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    configure_logging()

    default_database_path = os.path.join(app.instance_path, "audiobookbay.db")
    settings = load_settings(default_database_path)
    app.config[APP_SETTINGS_KEY] = settings

    @app.context_processor
    def inject_nav_link() -> dict[str, str | None]:
        return {
            "nav_link_name": settings.nav_link_name,
            "nav_link_url": settings.nav_link_url,
        }

    app.register_blueprint(pages_bp)
    app.register_blueprint(downloads_bp)
    app.register_blueprint(settings_bp)

    initialize_database(settings.database_path)
    register_error_handlers(app)
    log_settings(settings)
    return app


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        logger.log(error.log_level, str(error))
        if request.endpoint == "pages.search":
            query = request.form.get("query", "")
            return (
                render_template(
                    "search.html",
                    books=[],
                    query=query,
                    error=error.public_message,
                ),
                error.status_code,
            )
        return jsonify({"message": error.public_message}), error.status_code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        logger.exception("Unhandled exception", exc_info=error)
        if request.endpoint == "pages.search":
            query = request.form.get("query", "")
            return (
                render_template(
                    "search.html",
                    books=[],
                    query=query,
                    error="Unexpected error while processing the request.",
                ),
                500,
            )
        return jsonify({"message": "Internal server error"}), 500
