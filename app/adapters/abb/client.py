from __future__ import annotations

from urllib.parse import quote_plus

import requests

from config import AppSettings

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)


def build_search_url(hostname: str, query: str, page: int) -> str:
    return f"https://{hostname}/page/{page}/?s={quote_plus(query.lower())}"


class AudiobookBayClient:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.headers = {"User-Agent": USER_AGENT}

    def fetch_search_page(self, query: str, page: int) -> str:
        response = requests.get(
            build_search_url(self.settings.abb_hostname, query, page),
            headers=self.headers,
            timeout=15,
        )
        response.raise_for_status()
        return response.text

    def fetch_details_page(self, details_url: str) -> str:
        response = requests.get(details_url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.text

    def cover_url_is_valid(self, url: str) -> bool:
        try:
            response = requests.head(
                url,
                timeout=3,
                allow_redirects=True,
                stream=True,
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
