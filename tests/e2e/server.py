# File: tests/e2e/server.py
"""Serve actual application pages with isolated integrations for browser tests."""

import os
import signal
import sys
from contextlib import ExitStack
from html import escape
from pathlib import Path
from types import FrameType
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flask import Response, jsonify, request

from audiobook_automated import create_app
from audiobook_automated.clients.base import TorrentStatus
from audiobook_automated.config import Config
from audiobook_automated.extensions import torrent_manager
from audiobook_automated.scraper.parser import parse_book_details, parse_html


class BrowserConfig(Config):
    """Use normal templates and security without any external connections."""

    TESTING = False
    DL_CLIENT = "qbittorrent"
    DL_HOST = "127.0.0.1"
    SAVE_PATH_BASE = "/downloads/audiobooks"
    FORCE_HTTPS = False
    RATELIMIT_ENABLED = False
    ENABLE_DIAGNOSTICS = True
    SPLASH_ENABLED = False
    STATIC_VERSION = "browser-fixture"
    SITE_TITLE = "AudiobookBay Automated"
    SITE_LOGO = "/static/images/audiobookbay-header.jpg"
    DEFAULT_THEME = "purple"
    ABS_URL = None
    ABS_KEY = None
    ABS_LIB = None


TITLES = [
    "The Clockmaker's Voyage - Mira Sol",
    "A Long Journey: The Last Map, Book 2 - Owen Vale",
    "The Last Map",
    "The Lantern Keeper - Mira Sol",
    "Across the Silver Sea - Ada Moon",
    "A Quiet Harbor - Owen Vale",
]
BOOKS: list[dict[str, Any]] = [
    {
        "title": title,
        "link": f"https://catalog.example/book-{index}",
        "cover": f"/e2e/cover/{index}.svg" if index != 2 else None,
        "category": ["Fantasy", "Adventure"] if index % 2 == 0 else ["Mystery"],
        "language": "English",
        "format": "M4B",
        "bitrate": "128 Kbps",
        "file_size": "420 MB",
        "post_date": "14 Oct 2026",
    }
    for index, title in enumerate(TITLES)
]


def search_books(query: str, **kwargs: Any) -> list[dict[str, Any]]:
    """Provide two pages and empty/error states without a catalog request."""
    if query == "unavailable":
        raise ConnectionError("Fixture catalog unavailable")
    if query == "empty" or kwargs.get("start_page", 1) > 2:
        return []
    return (
        BOOKS
        if kwargs.get("start_page", 1) == 1
        else [{**BOOKS[0], "title": "The Winter Clock - Ada Moon", "language": "French"}]
    )


def details(link: str) -> dict[str, Any]:
    """Exercise the real parser with a metadata header and rich synopsis."""
    book = next((book for book in BOOKS if book["link"] == link), BOOKS[0])
    html = f"""<div class="postTitle"><h1>{escape(book["title"])}</h1></div>
    <div class="desc"><p>Written by <span class="author" itemprop="author">Mira Sol</span><br>
    Read by <span class="narrator" itemprop="author">Jane Doe</span>, <span class="narrator" itemprop="author">John Smith</span><br>
    Format: <span>M4B</span><br>Bitrate: <span>128 Kbps</span></p>
    <p>A journey through a world of lost clocks and hidden harbors.</p></div>"""
    parsed = parse_book_details(parse_html(html), link)
    return {
        **parsed,
        **book,
        "description": parsed["description"],
        "info_hash": "a" * 40,
        "trackers": ["udp://tracker.example:80/announce"],
    }


stack = ExitStack()
client_mocks: list[tuple[str, dict[str, Any]]] = [
    ("init_app", {"return_value": None}),
    ("verify_credentials", {"return_value": True}),
    ("list_clients", {"return_value": ["qbittorrent"]}),
    (
        "get_status",
        {"return_value": [TorrentStatus("fixture-1", TITLES[0], 42, "Downloading", "420 MB", client="qbittorrent")]},
    ),
    ("add_magnet", {"return_value": None}),
    ("remove_torrent", {"return_value": True}),
]
for target, options in client_mocks:
    stack.enter_context(patch.object(torrent_manager, target, **options))
stack.enter_context(patch("audiobook_automated.routes.search_audiobookbay", side_effect=search_books))
stack.enter_context(patch("audiobook_automated.routes.get_book_details", side_effect=details))
stack.enter_context(
    patch("audiobook_automated.routes.extract_magnet_link", return_value=("magnet:?xt=urn:btih:" + "a" * 40, None))
)
stack.enter_context(
    patch(
        "audiobook_automated.scraper.network.get_session",
        side_effect=AssertionError("External network disabled in browser tests"),
    )
)
app = create_app(BrowserConfig)


@app.before_request
def diagnostics_fixture() -> Response | None:
    """Return observations without probing real mirrors or reading host logs."""
    if request.path == "/api/diagnostics/health":
        return jsonify(
            status="healthy",
            system={"memory_rss_mb": 80},
            cache={},
            mirrors={
                "active_mirror": "catalog.example",
                "mirrors": [
                    {
                        "hostname": "catalog.example",
                        "tested": True,
                        "reachable": True,
                        "latency_ms": 180,
                        "ema_latency_ms": 190,
                        "success_rate": 100,
                        "success_count": 2,
                        "failure_count": 0,
                        "score": 981,
                        "protocol": "https",
                    }
                ],
            },
            clients=[],
        )
    if request.path == "/api/diagnostics/logs":
        return jsonify(logs=["[INFO] Browser fixture ready."])
    if request.path == "/api/diagnostics/inspect":
        return jsonify(book=details(BOOKS[0]["link"]))
    return None


@app.get("/e2e/cover/<int:index>.svg")
def cover(index: int) -> Response:
    """Serve deterministic local artwork in several source aspect ratios."""
    width, height = [(300, 450), (400, 400), (600, 300)][index % 3]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="#211039"/><stop offset="1" stop-color="#5b2aad"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/><rect x="20" y="20" width="{width - 40}" height="{height - 40}" rx="8" fill="none" stroke="#cbb6ed"/><circle cx="{width / 2}" cy="{height / 2}" r="65" fill="none" stroke="#cbb6ed" stroke-width="2"/><path d="M{width / 2 - 35} {height / 2}h70m-35-35v70" stroke="#cbb6ed" stroke-width="2"/></svg>'
    return Response(svg, mimetype="image/svg+xml")


def stop(_signum: int, _frame: FrameType | None) -> None:
    """Exit when the browser runner stops its owned fixture process."""
    stack.close()
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    app.run(host="127.0.0.1", port=int(os.environ.get("E2E_PORT", "5090")), use_reloader=False, threaded=True)
