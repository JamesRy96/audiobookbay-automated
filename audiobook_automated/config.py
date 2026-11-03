# File: audiobook_automated/config.py
"""Configuration module."""

import logging
import os

from .constants import (
    DEFAULT_SITE_LOGO,
    DEFAULT_SITE_TITLE,
    DEFAULT_SPLASH_MESSAGE,
    DEFAULT_SPLASH_VIDEO,
    DEFAULT_SPLASH_VIDEO_WEBM,
    DEFAULT_THEME,
)
from .utils import parse_bool


def parse_env_int(key: str, default: int) -> int:
    """Parse an integer environment variable safely.

    Handles cases where values might be passed as float strings (e.g., "3.0")
    by container orchestrators.

    Args:
        key: The environment variable key.
        default: The default value if missing or invalid.

    Returns:
        int: The parsed integer.
    """
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(float(raw.strip().strip("'\"")))
    except (ValueError, TypeError, OverflowError):
        return default


def parse_asset_path(value: str | None, default: str | None) -> str | None:
    """Normalize asset path for web use.

    If a bare filename without path separators is passed (e.g., 'custom-logo.jpg'),
    it is automatically prefixed with '/static/images/'.
    Full paths (e.g., '/static/...', '/custom/...', or URLs) are preserved.

    Args:
        value: The raw environment variable string.
        default: The fallback default path.

    Returns:
        Normalized path or URL string.
    """
    if value is None:
        return default
    val = value.strip(" \"'")
    if not val:
        return default
    if "/" not in val and not val.startswith("data:"):
        return f"/static/images/{val}"
    return val


class Config:
    """Centralized configuration for the Flask application.

    Loads settings from environment variables with safe defaults.
    """

    # Core Flask Config
    # Optional override; create_app generates an in-memory signing key when empty.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "").strip(" \"'")
    FLASK_DEBUG: bool = parse_bool(os.getenv("FLASK_DEBUG"), False)
    TESTING: bool = parse_bool(os.getenv("TESTING"), False)
    ENABLE_DIAGNOSTICS: bool = parse_bool(os.getenv("ENABLE_DIAGNOSTICS"), False)

    # Static Asset Caching (1 Year)
    SEND_FILE_MAX_AGE_DEFAULT: int = 31536000

    # Static Version Override (Optional)
    # Allows developers to force a version string via .env, overriding the Docker build hash.
    _static_version: str | None = os.getenv("STATIC_VERSION")
    STATIC_VERSION: str | None = _static_version.strip(" \"'") if _static_version else None

    # File System
    _save_path_base: str | None = os.getenv("SAVE_PATH_BASE")
    SAVE_PATH_BASE: str | None = _save_path_base.strip(" \"'") if _save_path_base else None

    # Integrations
    _abs_url: str | None = os.getenv("ABS_URL")
    ABS_URL: str | None = _abs_url.strip(" \"'") if _abs_url else None
    _abs_key: str | None = os.getenv("ABS_KEY")
    ABS_KEY: str | None = _abs_key.strip(" \"'") if _abs_key else None
    _abs_lib: str | None = os.getenv("ABS_LIB")
    ABS_LIB: str | None = _abs_lib.strip(" \"'") if _abs_lib else None

    # UI Customization
    _nav_link_name: str | None = os.getenv("NAV_LINK_NAME")
    NAV_LINK_NAME: str | None = _nav_link_name.strip(" \"'") if _nav_link_name else None
    _nav_link_url: str | None = os.getenv("NAV_LINK_URL")
    NAV_LINK_URL: str | None = _nav_link_url.strip(" \"'") if _nav_link_url else None

    # HTTPS Configuration
    # Defaults to False to ensure local deployments work out-of-the-box.
    FORCE_HTTPS: bool = parse_bool(os.getenv("FORCE_HTTPS"), False)

    # Session & CSRF Configuration
    SESSION_COOKIE_NAME: str = "audiobook_session"
    SESSION_COOKIE_SAMESITE: str = "Lax"
    # Force Secure=False to allow cookies over HTTP/IP as requested
    SESSION_COOKIE_SECURE: bool = False
    WTF_CSRF_SSL_STRICT: bool = FORCE_HTTPS

    # Listen Host/Port
    # nosec B104: Default to all interfaces for Docker container usage
    LISTEN_HOST: str = os.getenv("LISTEN_HOST", "0.0.0.0").strip(" \"'")  # noqa: S104
    LISTEN_PORT: int = parse_env_int("LISTEN_PORT", 5078)

    # Torrent Client Configuration
    _dl_client: str | None = os.getenv("DL_CLIENT")
    DL_CLIENT: str | None = _dl_client.strip(" \"'") if _dl_client else None
    _dl_host: str | None = os.getenv("DL_HOST")
    DL_HOST: str | None = _dl_host.strip(" \"'") if _dl_host else None
    _dl_port: str | None = os.getenv("DL_PORT")
    DL_PORT: str | None = _dl_port.strip(" \"'") if _dl_port else None
    _dl_username: str | None = os.getenv("DL_USERNAME")
    DL_USERNAME: str | None = _dl_username.strip(" \"'") if _dl_username else None
    _dl_password: str | None = os.getenv("DL_PASSWORD")
    DL_PASSWORD: str | None = _dl_password.strip(" \"'") if _dl_password else None
    _dl_api_key: str | None = os.getenv("DL_API_KEY")
    DL_API_KEY: str | None = _dl_api_key.strip(" \"'") if _dl_api_key else None
    DL_CATEGORY: str = os.getenv("DL_CATEGORY", "abb-automated").strip(" \"'")
    DL_SCHEME: str = os.getenv("DL_SCHEME", "http").strip(" \"'")
    _dl_url: str | None = os.getenv("DL_URL")
    DL_URL: str | None = _dl_url.strip(" \"'") if _dl_url else None
    DL_CLIENT_OS: str = os.getenv("DL_CLIENT_OS", "posix").strip(" \"'").lower()

    # Put.io Configuration
    _putio_token: str | None = os.getenv("PUTIO_TOKEN")
    PUTIO_TOKEN: str | None = _putio_token.strip(" \"'") if _putio_token else None
    PUTIO_FOLDER_ID: str = os.getenv("PUTIO_FOLDER_ID", "0").strip(" \"'")

    # Logging
    # We allow LOG_LEVEL to be None if unset to support Gunicorn level inheritance in __init__.py.
    _log_level_raw: str | None = os.getenv("LOG_LEVEL")
    _log_level_env: str | None = _log_level_raw.strip(" \"'") if _log_level_raw else None
    LOG_LEVEL_STR: str = _log_level_env.upper() if _log_level_env else "INFO"
    # Logic: If Env is set, resolve it (defaulting to INFO if invalid string). If not set, leave as None.
    LOG_LEVEL: int | None = getattr(logging, LOG_LEVEL_STR, logging.INFO) if _log_level_env else None

    # Scraper Configuration
    # Support single host or comma-separated list in ABB_HOSTNAME
    _hostname_raw: str = os.getenv("ABB_HOSTNAME", "audiobookbay.lu").strip(" \"'")
    _parsed_hostnames: list[str] = [h.strip() for h in _hostname_raw.split(",") if h.strip()]
    ABB_HOSTNAME: str = _parsed_hostnames[0] if _parsed_hostnames else "audiobookbay.lu"
    _extra_hosts: list[str] = _parsed_hostnames[1:] if len(_parsed_hostnames) > 1 else []

    # Parse comma-separated mirrors into a list
    # Strip the whole string first in case the list is quoted: "a.com,b.com"
    _mirrors_str: str = os.getenv("ABB_MIRRORS", "").strip(" \"'")
    ABB_MIRRORS: list[str] = _extra_hosts + [m.strip() for m in _mirrors_str.split(",") if m.strip()]

    # Remote mirrors sync URL (optional override)
    _mirrors_remote_url: str | None = os.getenv("ABB_MIRRORS_REMOTE_URL")
    ABB_MIRRORS_REMOTE_URL: str | None = _mirrors_remote_url.strip(" \"'") if _mirrors_remote_url else None

    # Parse comma-separated trackers into a list
    _trackers_str: str = os.getenv("MAGNET_TRACKERS", "").strip(" \"'")
    MAGNET_TRACKERS: list[str] = [t.strip() for t in _trackers_str.split(",") if t.strip()]

    # Scraper Concurrency
    # Defines the number of worker threads per worker for the scraping executor.
    SCRAPER_THREADS: int = parse_env_int("SCRAPER_THREADS", 3)

    # Scraper Request Timeout (Default 30)
    # Separated from Gunicorn timeout to ensure internal requests fail faster than the worker kill timer.
    SCRAPER_TIMEOUT: int = parse_env_int("SCRAPER_TIMEOUT", 30)

    # Torrent Client Timeout (Default 30)
    CLIENT_TIMEOUT: int = parse_env_int("CLIENT_TIMEOUT", 30)

    # Site Identity
    SITE_TITLE: str = os.getenv("SITE_TITLE", DEFAULT_SITE_TITLE).strip(" \"'")
    SITE_LOGO: str | None = parse_asset_path(os.getenv("SITE_LOGO"), DEFAULT_SITE_LOGO)
    DEFAULT_THEME: str = os.getenv("DEFAULT_THEME", DEFAULT_THEME).strip(" \"'").lower()

    # Splash Screen Configuration
    SPLASH_ENABLED: bool = parse_bool(os.getenv("SPLASH_ENABLED"), True)
    SPLASH_VIDEO: str | None = parse_asset_path(os.getenv("SPLASH_VIDEO"), DEFAULT_SPLASH_VIDEO)
    SPLASH_VIDEO_WEBM: str | None = parse_asset_path(os.getenv("SPLASH_VIDEO_WEBM"), DEFAULT_SPLASH_VIDEO_WEBM)
    # Fallback to SITE_TITLE if SPLASH_TITLE is not explicitly set
    SPLASH_TITLE: str = os.getenv("SPLASH_TITLE", SITE_TITLE).strip(" \"'")
    SPLASH_MESSAGE: str = os.getenv("SPLASH_MESSAGE", DEFAULT_SPLASH_MESSAGE).strip(" \"'")
    SPLASH_DURATION: int = parse_env_int("SPLASH_DURATION", 3500)

    @property
    def LIBRARY_RELOAD_ENABLED(self) -> bool:
        """Check if all required Audiobookshelf configuration is present."""
        return bool(self.ABS_URL and self.ABS_KEY and self.ABS_LIB)

    @classmethod
    def validate(cls, logger: logging.Logger) -> None:
        """Validate critical configuration at startup."""
        # Validate LOG_LEVEL
        # Only validate if the user actually tried to set it
        if cls._log_level_env and not hasattr(logging, cls.LOG_LEVEL_STR):
            logger.warning(
                f"Configuration Warning: Invalid LOG_LEVEL '{cls.LOG_LEVEL_STR}' provided. Defaulting to INFO."
            )

        # Validate SAVE_PATH_BASE
        if not cls.SAVE_PATH_BASE:
            if not cls.TESTING:
                logger.critical("Configuration Error: SAVE_PATH_BASE is missing.")
                # Raise RuntimeError instead of sys.exit(1) to allow WSGI servers to log the error properly
                raise RuntimeError("Configuration Error: SAVE_PATH_BASE is missing.")
        else:
            logger.info(f"SAVE_PATH_BASE configured as: {cls.SAVE_PATH_BASE}")
            logger.info(
                "Reminder: This path must exist inside the TORRENT CLIENT container, "
                "not necessarily this application's container."
            )

        # Validate DL_CLIENT
        # Allow any string identifier to support drop-in client plugins without hardcoded enum restriction.
        # The Manager will fail later if the module doesn't exist.
        if not cls.DL_CLIENT:
            logger.critical("Configuration Error: DL_CLIENT is missing.")
            raise ValueError("DL_CLIENT must be set.")

        # Validate DL_SCHEME
        if cls.DL_SCHEME not in ("http", "https"):
            logger.critical(f"Configuration Error: Invalid DL_SCHEME '{cls.DL_SCHEME}'. Must be 'http' or 'https'.")
            raise ValueError(f"Invalid DL_SCHEME '{cls.DL_SCHEME}'.")
