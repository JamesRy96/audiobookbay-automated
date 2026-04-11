from __future__ import annotations

from flask import Flask

from config import APP_SETTINGS_KEY, load_settings, log_settings
from routes.downloads import downloads_bp
from routes.pages import pages_bp


def create_app() -> Flask:
    settings = load_settings()

    app = Flask(__name__)
    app.config[APP_SETTINGS_KEY] = settings

    @app.context_processor
    def inject_nav_link() -> dict[str, str | None]:
        return {
            "nav_link_name": settings.nav_link_name,
            "nav_link_url": settings.nav_link_url,
        }

    app.register_blueprint(pages_bp)
    app.register_blueprint(downloads_bp)

    log_settings(settings)
    return app
