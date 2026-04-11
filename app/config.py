from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import current_app

load_dotenv()

APP_SETTINGS_KEY = "APP_SETTINGS"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppSettings:
    abb_hostname: str
    page_limit: int
    download_client: str | None
    dl_scheme: str
    dl_host: str | None
    dl_port: int | None
    dl_url: str | None
    dl_username: str | None
    dl_password: str | None
    dl_category: str
    save_path_base: str | None
    nav_link_name: str | None
    nav_link_url: str | None
    database_path: str
    flask_port: int


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def resolve_database_path(default_database_path: str) -> str:
    configured_path = os.getenv("APP_DB_PATH")
    if configured_path:
        return os.path.abspath(configured_path)

    docker_config_dir = "/config"
    if os.path.isdir(docker_config_dir):
        return os.path.join(docker_config_dir, "audiobookbay.db")

    return os.path.abspath(default_database_path)


def load_settings(default_database_path: str) -> AppSettings:
    dl_url = os.getenv("DL_URL")

    if dl_url:
        parsed_url = urlparse(dl_url)
        dl_scheme = parsed_url.scheme
        dl_host = parsed_url.hostname
        dl_port = parsed_url.port
    else:
        dl_scheme = os.getenv("DL_SCHEME", "http")
        dl_host = os.getenv("DL_HOST")
        dl_port = _parse_optional_int(os.getenv("DL_PORT"))

        if dl_host and dl_port:
            dl_url = f"{dl_scheme}://{dl_host}:{dl_port}"

    return AppSettings(
        abb_hostname=os.getenv("ABB_HOSTNAME", "audiobookbay.lu"),
        page_limit=int(os.getenv("PAGE_LIMIT", 5)),
        download_client=os.getenv("DOWNLOAD_CLIENT"),
        dl_scheme=dl_scheme,
        dl_host=dl_host,
        dl_port=dl_port,
        dl_url=dl_url,
        dl_username=os.getenv("DL_USERNAME"),
        dl_password=os.getenv("DL_PASSWORD"),
        dl_category=os.getenv("DL_CATEGORY", "Audiobookbay-Audiobooks"),
        save_path_base=os.getenv("SAVE_PATH_BASE"),
        nav_link_name=os.getenv("NAV_LINK_NAME"),
        nav_link_url=os.getenv("NAV_LINK_URL"),
        database_path=resolve_database_path(default_database_path),
        flask_port=int(os.getenv("PORT", os.getenv("FLASK_PORT", 5078))),
    )


def get_settings() -> AppSettings:
    return current_app.config[APP_SETTINGS_KEY]


def log_settings(settings: AppSettings) -> None:
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
