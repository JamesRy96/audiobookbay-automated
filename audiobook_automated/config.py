# File: audiobook_automated/config.py
"""Configuration module."""

import logging
import re

from .constants import (
    DEFAULT_SITE_LOGO,
    DEFAULT_SITE_TITLE,
    DEFAULT_SPLASH_MESSAGE,
    DEFAULT_SPLASH_VIDEO,
    DEFAULT_SPLASH_VIDEO_WEBM,
    DEFAULT_THEME,
)
from .environment import get_env
from .utils import parse_bool
from .web_security import parse_public_url, parse_trusted_proxies


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
    raw = get_env(key)
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


def parse_client_connections(configured: str | None) -> dict[str, dict[str, str]]:
    """Read independent connection settings for configured client plugins."""
    names = dict.fromkeys((configured or "").split(","))
    fields = (
        "HOST",
        "PORT",
        "USERNAME",
        "PASSWORD",
        "SCHEME",
        "API_KEY",
        "URL",
        "TIMEOUT",
        "TOKEN",
        "FOLDER_ID",
        "SAVE_PATH_BASE",
    )
    connections: dict[str, dict[str, str]] = {}
    for raw_name in names:
        name = raw_name.strip().lower()
        if not name:
            continue
        values = {}
        for field in fields:
            value = get_env(f"{name.upper()}_{field}")
            if value is not None:
                values[field] = value.strip(" \"'")
        connections[name] = values
    return connections


def validate_client_connections(connections: dict[str, dict[str, str]]) -> None:
    """Reject unusable ports, timeouts and URL schemes with actionable setting names."""
    max_port = 65535
    for name, values in connections.items():
        for field in ("PORT", "TIMEOUT"):
            raw = values.get(field)
            if raw:
                try:
                    number = int(raw)
                except ValueError:
                    raise ValueError(f"{name.upper()}_{field} must be a positive whole number.") from None
                if number <= 0 or (field == "PORT" and number > max_port):
                    raise ValueError(f"{name.upper()}_{field} is outside the allowed range.")
        if values.get("SCHEME", "http") not in ("http", "https"):
            raise ValueError(f"{name.upper()}_SCHEME must be http or https.")


def log_client_setup(connections: dict[str, dict[str, str]], logger: logging.Logger) -> None:
    """Explain incomplete built-in client login settings without contacting clients or logging secrets."""
    for name, values in connections.items():
        if name == "qbittorrent" and not values.get("API_KEY"):
            missing = [f"QBITTORRENT_{field}" for field in ("USERNAME", "PASSWORD") if not values.get(field)]
            if missing:
                logger.warning(
                    "qBittorrent login is incomplete. Set %s, or set QBITTORRENT_API_KEY. "
                    "If qBittorrent allows access without signing in, these can stay empty.",
                    " and ".join(missing),
                )
        elif name == "deluge" and not values.get("PASSWORD"):
            logger.warning("Deluge needs its Web interface password. Set DELUGE_PASSWORD and restart this app.")
        elif name == "putio" and not values.get("TOKEN"):
            logger.warning("Put.io needs an access token. Set PUTIO_TOKEN and restart this app.")
        elif name == "transmission" and bool(values.get("USERNAME")) != bool(values.get("PASSWORD")):
            missing_setting = "TRANSMISSION_PASSWORD" if values.get("USERNAME") else "TRANSMISSION_USERNAME"
            logger.warning(
                "Transmission login is incomplete. Set %s, or leave both login settings empty "
                "if Transmission allows access without signing in.",
                missing_setting,
            )


class Config:
    """Centralized configuration for the Flask application.

    Loads settings from environment variables with safe defaults.
    """

    # Core Flask Config
    # Optional override; create_app generates an in-memory signing key when empty.
    SECRET_KEY: str = get_env("SECRET_KEY", "").strip(" \"'")
    FLASK_DEBUG: bool = parse_bool(get_env("FLASK_DEBUG"), False)
    TESTING: bool = parse_bool(get_env("TESTING"), False)
    ENABLE_DIAGNOSTICS: bool = parse_bool(get_env("ENABLE_DIAGNOSTICS"), False)

    # Static Asset Caching (1 Year)
    SEND_FILE_MAX_AGE_DEFAULT: int = 31536000

    # Static Version Override (Optional)
    # Allows developers to force a version string via .env, overriding the Docker build hash.
    _static_version: str | None = get_env("STATIC_VERSION")
    STATIC_VERSION: str | None = _static_version.strip(" \"'") if _static_version else None

    # File System
    _save_path_base: str | None = get_env("SAVE_PATH_BASE")
    SAVE_PATH_BASE: str | None = _save_path_base.strip(" \"'") if _save_path_base else None

    # Integrations
    _abs_url: str | None = get_env("ABS_URL")
    ABS_URL: str | None = _abs_url.strip(" \"'") if _abs_url else None
    _abs_key: str | None = get_env("ABS_KEY")
    ABS_KEY: str | None = _abs_key.strip(" \"'") if _abs_key else None
    _abs_lib: str | None = get_env("ABS_LIB")
    ABS_LIB: str | None = _abs_lib.strip(" \"'") if _abs_lib else None

    # UI Customization
    _nav_link_name: str | None = get_env("NAV_LINK_NAME")
    NAV_LINK_NAME: str | None = _nav_link_name.strip(" \"'") if _nav_link_name else None
    _nav_link_url: str | None = get_env("NAV_LINK_URL")
    NAV_LINK_URL: str | None = _nav_link_url.strip(" \"'") if _nav_link_url else None

    # Optional public origin; local HTTP needs no web security settings.
    PUBLIC_URL: str | None = parse_public_url(get_env("PUBLIC_URL"))
    TRUSTED_PROXIES = parse_trusted_proxies(get_env("TRUSTED_PROXIES"))

    # Session & CSRF Configuration
    SESSION_COOKIE_NAME: str = "audiobook_session"
    SESSION_COOKIE_SAMESITE: str = "Lax"
    WTF_CSRF_SSL_STRICT: bool = True

    # Listen Host/Port
    # nosec B104: Default to all interfaces for Docker container usage
    LISTEN_HOST: str = get_env("LISTEN_HOST", "0.0.0.0").strip(" \"'")  # noqa: S104
    LISTEN_PORT: int = parse_env_int("LISTEN_PORT", 5078)

    # Torrent Client Configuration
    _dl_client: str | None = get_env("DL_CLIENT")
    DL_CLIENT: str | None = _dl_client.strip(" \"'").lower() if _dl_client else None
    CLIENT_CONNECTIONS: dict[str, dict[str, str]] = parse_client_connections(DL_CLIENT)
    DL_CATEGORY: str = get_env("DL_CATEGORY", "abb-automated").strip(" \"'")

    # Logging
    # We allow LOG_LEVEL to be None if unset to support Gunicorn level inheritance in __init__.py.
    _log_level_raw: str | None = get_env("LOG_LEVEL")
    _log_level_env: str | None = _log_level_raw.strip(" \"'") if _log_level_raw else None
    LOG_LEVEL_STR: str = _log_level_env.upper() if _log_level_env else "INFO"
    # Logic: If Env is set, resolve it (defaulting to INFO if invalid string). If not set, leave as None.
    LOG_LEVEL: int | None = getattr(logging, LOG_LEVEL_STR, logging.INFO) if _log_level_env else None

    # Scraper Configuration
    # Support single host or comma-separated list in ABB_HOSTNAME
    _hostname_raw: str = get_env("ABB_HOSTNAME", "audiobookbay.lu").strip(" \"'")
    _parsed_hostnames: list[str] = [h.strip() for h in _hostname_raw.split(",") if h.strip()]
    ABB_HOSTNAME: str = _parsed_hostnames[0] if _parsed_hostnames else "audiobookbay.lu"
    _extra_hosts: list[str] = _parsed_hostnames[1:] if len(_parsed_hostnames) > 1 else []

    # Parse comma-separated mirrors into a list
    # Strip the whole string first in case the list is quoted: "a.com,b.com"
    _mirrors_str: str = get_env("ABB_MIRRORS", "").strip(" \"'")
    ABB_MIRRORS: list[str] = _extra_hosts + [m.strip() for m in _mirrors_str.split(",") if m.strip()]

    # Remote mirrors sync URL (optional override)
    _mirrors_remote_url: str | None = get_env("ABB_MIRRORS_REMOTE_URL")
    ABB_MIRRORS_REMOTE_URL: str | None = _mirrors_remote_url.strip(" \"'") if _mirrors_remote_url else None

    # Parse comma-separated trackers into a list
    _trackers_str: str = get_env("MAGNET_TRACKERS", "").strip(" \"'")
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
    SITE_TITLE: str = get_env("SITE_TITLE", DEFAULT_SITE_TITLE).strip(" \"'")
    SITE_LOGO: str | None = parse_asset_path(get_env("SITE_LOGO"), DEFAULT_SITE_LOGO)
    DEFAULT_THEME: str = get_env("DEFAULT_THEME", DEFAULT_THEME).strip(" \"'").lower()

    # Splash Screen Configuration
    SPLASH_ENABLED: bool = parse_bool(get_env("SPLASH_ENABLED"), True)
    SPLASH_VIDEO: str | None = parse_asset_path(get_env("SPLASH_VIDEO"), DEFAULT_SPLASH_VIDEO)
    SPLASH_VIDEO_WEBM: str | None = parse_asset_path(get_env("SPLASH_VIDEO_WEBM"), DEFAULT_SPLASH_VIDEO_WEBM)
    # Fallback to SITE_TITLE if SPLASH_TITLE is not explicitly set
    SPLASH_TITLE: str = get_env("SPLASH_TITLE", SITE_TITLE).strip(" \"'")
    SPLASH_MESSAGE: str = get_env("SPLASH_MESSAGE", DEFAULT_SPLASH_MESSAGE).strip(" \"'")
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

        # Validate DL_CLIENT
        # Allow any string identifier to support drop-in client plugins without hardcoded enum restriction.
        # The Manager will fail later if the module doesn't exist.
        if not cls.DL_CLIENT:
            message = "Choose a Download Client. Set DL_CLIENT=qbittorrent, deluge, transmission or putio; use commas for several clients."
            logger.critical(message)
            raise ValueError(message)

        names = [name.strip() for name in cls.DL_CLIENT.split(",")]
        for name in names:
            if not re.fullmatch(r"[a-z0-9_-]+", name):
                raise ValueError("Use client names separated by commas in DL_CLIENT, without trailing punctuation.")
        validate_client_connections(cls.CLIENT_CONNECTIONS)
