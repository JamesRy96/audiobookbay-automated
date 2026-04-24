from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, send_from_directory

from config import APP_SETTINGS_KEY, load_settings
from db import initialize_database
from errors import AppError
from logging_utils import configure_logging
from routes.api import api_bp
from routes.settings import settings_bp

logger = logging.getLogger(__name__)

SPA_DIR = os.path.join(os.path.dirname(__file__), "dist")


def create_app() -> Flask:
    app = Flask(__name__)
    configure_logging()

    default_database_path = os.path.join(app.instance_path, "audiobookbay.db")
    settings = load_settings(default_database_path)
    app.config[APP_SETTINGS_KEY] = settings

    app.register_blueprint(api_bp)
    app.register_blueprint(settings_bp)

    initialize_database(settings.database_path)
    register_error_handlers(app)
    register_spa(app)
    log_settings(settings)
    return app


def register_spa(app: Flask) -> None:
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path: str):
        if path and os.path.isfile(os.path.join(SPA_DIR, path)):
            return send_from_directory(SPA_DIR, path)
        return send_from_directory(SPA_DIR, "index.html")


def log_settings(settings) -> None:
    logger.info("ABB_HOSTNAME: %s", settings.abb_hostname)
    logger.info("DOWNLOAD_CLIENT: %s", settings.download_client)
    logger.info("DL_HOST: %s", settings.dl_host)
    logger.info("DL_PORT: %s", settings.dl_port)
    logger.info("DL_URL: %s", settings.dl_url)
    logger.info("DL_USERNAME: %s", settings.dl_username)
    logger.info("DL_CATEGORY: %s", settings.dl_category)
    logger.info("SAVE_PATH_BASE: %s", settings.save_path_base)
    logger.info("NAV_LINK_NAME: %s", settings.nav_link_name)
    logger.info("NAV_LINK_URL: %s", settings.nav_link_url)
    logger.info("DB_PATH: %s", settings.database_path)
    logger.info("PAGE_LIMIT: %s", settings.page_limit)
    logger.info("PORT: %s", settings.flask_port)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        logger.log(error.log_level, str(error))
        return jsonify({"message": error.public_message}), error.status_code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        logger.exception("Unhandled exception", exc_info=error)
        return jsonify({"message": "Internal server error"}), 500
