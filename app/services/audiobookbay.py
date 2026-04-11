from __future__ import annotations

import logging
import requests

from adapters.abb.client import AudiobookBayClient
from adapters.abb.parser import parse_magnet_link, parse_search_results
from config import AppSettings
from models import BookResult

logger = logging.getLogger(__name__)


def search_audiobookbay(
    query: str, settings: AppSettings, max_pages: int | None = None
) -> list[BookResult]:
    client = AudiobookBayClient(settings)
    results: list[BookResult] = []
    max_pages = max_pages or settings.page_limit

    logger.info("Searching for '%s' on https://%s...", query, settings.abb_hostname)

    for page in range(1, max_pages + 1):
        try:
            html = client.fetch_search_page(query, page)
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to fetch page %s: %s", page, exc)
            break

        page_results = parse_search_results(
            html,
            settings.abb_hostname,
            client.cover_url_is_valid,
        )

        if not page_results:
            logger.info("No more results found on page %s.", page)
            break

        logger.info("Processing %s posts on page %s.", len(page_results), page)
        results.extend(page_results)

    return results


def extract_magnet_link(details_url: str, settings: AppSettings) -> str | None:
    client = AudiobookBayClient(settings)

    try:
        details_html = client.fetch_details_page(details_url)
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to fetch details page: %s", exc)
        return None

    magnet_link = parse_magnet_link(details_html)
    if not magnet_link:
        logger.error("Info Hash not found on the page.")
        return None

    logger.debug("Generated magnet link: %s", magnet_link)
    return magnet_link
