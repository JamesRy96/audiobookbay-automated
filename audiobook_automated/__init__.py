# File: audiobook_automated/__init__.py
"""Main application package for AudiobookBay Automated."""

import logging
import secrets
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request
from flask_wtf.csrf import CSRFError

from .config import Config, log_client_setup
from .diagnostics import diagnostics_bp
from .extensions import csrf, executor, limiter, register_shutdown_handlers, talisman, torrent_manager
from .logging_buffer import log_ring_buffer
from .routes import main_bp
from .scraper import network
from .utils import get_application_version
from .web_security import PublicOriginMiddleware, TransportSessionInterface


def create_app(config_class: type[Config] = Config) -> Flask:
    """Create and configure a Flask application instance."""
    app = Flask(__name__)
    app.session_interface = TransportSessionInterface()
    app.config.from_object(config_class)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    # Ensure properties on config class instance are resolved into app.config
    app.config["LIBRARY_RELOAD_ENABLED"] = getattr(config_class(), "LIBRARY_RELOAD_ENABLED", False)

    # Validate critical configuration
    config_class.validate(app.logger)

    if app.debug:
        app.logger.warning("Running in DEBUG mode. Security checks may be bypassed.")

    # Configure logging level from application configuration
    configured_level = app.config.get("LOG_LEVEL")
    _configure_logging(app, configured_level)

    # Static asset versioning for cache busting
    # Priority:
    # 1. Config/Env Var (Developer Override)
    # 2. Dynamic Runtime Content Calculation (Busts caches on live swaps/mounts)

    if not app.config.get("STATIC_VERSION"):
        static_folder = Path(app.root_path) / "static"
        app.config["STATIC_VERSION"] = get_application_version(static_folder)

    # Initialize Extensions
    limiter.init_app(app)
    csrf.init_app(app)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(_error: CSRFError) -> tuple[Response, int]:  # pyright: ignore[reportUnusedFunction]
        """Tell users how to recover from an expired page without replaying an action."""
        return jsonify(message="Page expired. Refresh and try again.", code="page_expired"), 400

    # Initialize Security Headers
    # We must allow 'unsafe-inline' for style-src because of the dynamic nature of
    # some UI components, but we restrict scripts strictly.
    # We also allow images from any source (*) because cover images come from random mirrors.
    csp = {
        "default-src": ["'self'"],
        "img-src": ["'self'", "*", "data:"],
        "style-src": ["'self'", "'unsafe-inline'"],
        # Restrict scripts strictly to 'self' without unsafe-eval
        "script-src": ["'self'"],
    }
    talisman.init_app(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=["script-src"],
        # TLS redirects and HSTS belong to the reverse proxy's explicit SSL settings.
        force_https=False,
        strict_transport_security=False,
        # The session interface selects this per request without a global mutation.
        session_cookie_secure=False,
    )

    # Initialize TorrentManager with app configuration
    torrent_manager.init_app(app)
    # Note: Request teardown is handled per-client to prevent connection storms.

    # Gunicorn preloads this factory before binding its HTTP socket. Never connect here.
    log_client_setup(app.config["CLIENT_CONNECTIONS"], app.logger)
    app.logger.info(
        "Download Client setup loaded. Open Status to check connections; "
        "an offline client does not prevent the website from starting."
    )

    # Initialize Scraper Executor
    executor.init_app(app)

    # Register signal handlers for graceful shutdown
    register_shutdown_handlers(app)

    # Initialize Global Request Semaphore
    # This must be done here to avoid circular imports in extensions.py
    max_workers = app.config.get("SCRAPER_THREADS", 3)
    network.init_semaphore(max_workers)

    # Register Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(diagnostics_bp)

    @app.context_processor
    def inject_global_vars() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """Inject global configuration variables into all templates."""
        return {
            "download_clients": torrent_manager.list_clients(),
            "nav_link_name": app.config.get("NAV_LINK_NAME"),
            "nav_link_url": app.config.get("NAV_LINK_URL"),
            "library_reload_enabled": app.config["LIBRARY_RELOAD_ENABLED"],
            "static_version": app.config["STATIC_VERSION"],
            "default_cover_filename": "cover-placeholder.svg",
            "site_title": app.config["SITE_TITLE"],
            "site_logo": app.config.get("SITE_LOGO"),
            "splash_enabled": app.config["SPLASH_ENABLED"],
            "splash_video": app.config.get("SPLASH_VIDEO"),
            "splash_video_webm": app.config.get("SPLASH_VIDEO_WEBM"),
            "splash_title": app.config["SPLASH_TITLE"],
            "splash_message": app.config["SPLASH_MESSAGE"],
            "splash_duration": app.config["SPLASH_DURATION"],
            "default_theme": app.config.get("DEFAULT_THEME", "purple"),
            "abb_host": app.config.get("ABB_HOSTNAME", "audiobookbay.lu"),
            "diagnostics_enabled": bool(
                app.config.get("ENABLE_DIAGNOSTICS", False)
                or app.config.get("FLASK_DEBUG", False)
                or app.config.get("TESTING", False)
            ),
            "flask_debug": bool(app.config.get("FLASK_DEBUG", False) or app.config.get("TESTING", False)),
        }

    # Aggressive caching for static assets
    # Since we use versioning (?v=hash) in templates, we can safely tell
    # the browser to cache static files for a year (31536000 seconds).
    @app.after_request
    def add_header(response: Response) -> Response:  # pyright: ignore[reportUnusedFunction]
        """Add Cache-Control headers to static files."""
        if request.path.startswith("/static"):
            response.headers["Cache-Control"] = "public, max-age=31536000"
        return response

    app.wsgi_app = PublicOriginMiddleware(  # type: ignore[method-assign]
        app.wsgi_app, app.config["PUBLIC_URL"], app.config["TRUSTED_PROXIES"]
    )

    return app


def _configure_logging(app: Flask, configured_level: int | None) -> None:
    """Configure application logging, inheriting from Gunicorn if available.

    Args:
        app: The Flask application instance.
        configured_level: The explicitly configured log level (or None).
    """
    # Priority:
    # 1. Configured LOG_LEVEL (if set in env)
    # 2. Gunicorn Logger Level (if running in Gunicorn)
    # 3. Default (INFO)

    # Attach memory ring buffer for live diagnostics and 1-click issue reporting
    root_logger = logging.getLogger()
    if log_ring_buffer not in root_logger.handlers:
        root_logger.addHandler(log_ring_buffer)
    effective_level = configured_level if configured_level is not None else logging.INFO
    gunicorn_logger = logging.getLogger("gunicorn.error")
    if gunicorn_logger.handlers:
        app.logger.handlers = gunicorn_logger.handlers
        # Sync level to match Gunicorn (unless overridden by config)
        if configured_level is not None:
            effective_level = configured_level
        elif gunicorn_logger.level != logging.NOTSET:
            effective_level = gunicorn_logger.level
    app.logger.setLevel(effective_level)
    root_logger.setLevel(effective_level)
