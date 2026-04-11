from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import current_app

load_dotenv()

APP_SETTINGS_KEY = "APP_SETTINGS"


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
    flask_port: int


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def load_settings() -> AppSettings:
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
        flask_port=int(os.getenv("PORT", os.getenv("FLASK_PORT", 5078))),
    )


def get_settings() -> AppSettings:
    return current_app.config[APP_SETTINGS_KEY]


def log_settings(settings: AppSettings) -> None:
    print(f"ABB_HOSTNAME: {settings.abb_hostname}")
    print(f"DOWNLOAD_CLIENT: {settings.download_client}")
    print(f"DL_HOST: {settings.dl_host}")
    print(f"DL_PORT: {settings.dl_port}")
    print(f"DL_URL: {settings.dl_url}")
    print(f"DL_USERNAME: {settings.dl_username}")
    print(f"DL_CATEGORY: {settings.dl_category}")
    print(f"SAVE_PATH_BASE: {settings.save_path_base}")
    print(f"NAV_LINK_NAME: {settings.nav_link_name}")
    print(f"NAV_LINK_URL: {settings.nav_link_url}")
    print(f"PAGE_LIMIT: {settings.page_limit}")
    print(f"PORT: {settings.flask_port}")
