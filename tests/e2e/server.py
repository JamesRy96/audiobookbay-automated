# File: tests/e2e/server.py
"""Serve real application flows, replacing only catalog transport and the qBittorrent SDK."""

import json
import os
import signal
import sys
from contextlib import ExitStack
from pathlib import Path
from threading import RLock
from types import FrameType, SimpleNamespace
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flask import Response, jsonify, request
from flask_wtf.csrf import CSRFError

from audiobook_automated import create_app
from audiobook_automated.config import Config
from audiobook_automated.extensions import csrf
from audiobook_automated.scraper import core, network


class BrowserConfig(Config):
    """Use normal controllers/security with isolated external integration boundaries."""

    TESTING = False
    DL_CLIENT = "qbittorrent"
    DL_HOST = "127.0.0.1"
    DL_API_KEY = "isolated-browser-fixture"
    DL_CATEGORY = "abb-automated"
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


CATALOG = Path(__file__).parent / "catalog"
CAPTURED = json.loads((CATALOG / "captured/manifest.json").read_text())
lock = RLock()
jobs: dict[str, Any] = {}
events: list[dict[str, Any]] = []
controls = {"fail_add": False}
csrf_failures: list[str] = []


def reset_state() -> None:
    """Isolate each browser test without hiding application transport or parsing behavior."""
    with lock:
        jobs.clear()
        jobs["fixture-1"] = SimpleNamespace(
            hash="fixture-1",
            name="The Clockmaker's Voyage - Mira Sol",
            state="downloading",
            total_size=440401920,
            progress=0.42,
            category="abb-automated",
            save_path="/downloads/audiobooks/existing",
        )
        events.clear()
        csrf_failures.clear()
        controls["fail_add"] = False
    with network.CACHE_LOCK:
        network.search_cache.clear()
    with core.CACHE_LOCK:
        network.details_cache.clear()


class CatalogTransport:
    """Return catalog-shaped HTML at the HTTP boundary; fail closed on unknown paths."""

    def get(self, url: str, **kwargs: Any) -> Any:
        """Let the real core and parsers consume catalog responses."""
        parsed = urlparse(url)
        if parsed.netloc not in {"catalog.example", "audiobookbay.lu"}:
            raise AssertionError(f"Unexpected external request: {url}")
        query = parse_qs(parsed.query).get("s", [""])[0]
        path = parsed.path
        status = 200
        if path.startswith("/page/") or path.startswith("/audio-books/"):
            page_number = int(path.strip("/").split("/")[-1]) if path.startswith("/page/") else 1
            if query == "unavailable":
                status, name = 503, "empty.html"
            elif query == "recorded-encoded":
                name = "captured/search-encoded.html" if page_number == 1 else "empty.html"
            elif query == "recorded-hobbit":
                name = "captured/search-hobbit.html" if page_number == 1 else "empty.html"
            elif query == "empty" or page_number > 2:
                name = "empty.html"
            elif query == "missing-hash":
                name = "missing-search.html"
            else:
                name = f"search-{page_number}.html"
        elif path.startswith("/abss/"):
            captured = next((book for book in CAPTURED["details"] if book["path"] == path), None)
            name = "captured/" + captured["file"] if captured else path.strip("/").split("/")[-1] + ".html"
        else:
            raise AssertionError(f"Unexpected catalog route: {url}")
        fixture = CATALOG / name
        response = network.requests.Response()
        response.url = url
        response.status_code = status if fixture.is_file() else 404
        response.encoding = "utf-8"
        text = fixture.read_text() if fixture.is_file() else "Unknown fixture book"
        local = f"http://127.0.0.1:{os.environ.get('E2E_PORT', '5090')}"
        response._content = text.replace("{{COVER_BASE}}", local).encode()  # pyright: ignore[reportPrivateUsage]
        return response


class IsolatedQbitSDK:
    """Stateful qBittorrent SDK boundary used by the actual manager and client adapter."""

    def __init__(self, **kwargs: Any) -> None:
        """Create a request-local handle onto shared isolated client state."""
        self.app = SimpleNamespace(version="v5.3.0")
        self._http_session: Any = None

    def torrents_add(self, urls: str, save_path: str, category: str) -> str:
        """Record the actual extracted magnet and destination, or reject dispatch."""
        with lock:
            if controls["fail_add"]:
                raise ConnectionError("Isolated Download Client rejected the request")
            parameters = parse_qs(urlparse(urls).query)
            hash_id = parameters["xt"][0].removeprefix("urn:btih:")
            if len(hash_id) != 40 or any(c not in "0123456789abcdef" for c in hash_id):
                raise ValueError("Invalid fixture magnet")
            name = parameters["dn"][0]
            jobs[hash_id] = SimpleNamespace(
                hash=hash_id,
                name=name,
                state="metaDL",
                total_size=-1,
                progress=0,
                category=category,
                save_path=save_path,
            )
            events.append(
                {
                    "action": "add",
                    "hash": hash_id,
                    "name": name,
                    "magnet": urls,
                    "save_path": save_path,
                    "category": category,
                }
            )
            return "Ok."

    def torrents_info(self, category: str) -> list[Any]:
        """Return the client's real current test state through the adapter."""
        with lock:
            return [job for job in jobs.values() if job.category == category]

    def torrents_delete(self, torrent_hashes: str, delete_files: bool) -> None:
        """Require a known task and record whether removal preserves its files."""
        with lock:
            del jobs[torrent_hashes]
            events.append({"action": "remove", "hash": torrent_hashes, "delete_files": delete_files})


reset_state()
stack = ExitStack()
stack.enter_context(
    patch("audiobook_automated.scraper.network.find_best_mirror", return_value="https://catalog.example")
)
stack.enter_context(
    patch("audiobook_automated.scraper.network.get_mirrors", return_value=["catalog.example", "audiobookbay.lu"])
)
stack.enter_context(patch("audiobook_automated.scraper.network.get_session", return_value=CatalogTransport()))
stack.enter_context(patch("audiobook_automated.scraper.core.time.sleep"))
stack.enter_context(patch("audiobook_automated.clients.qbittorrent.QbClient", side_effect=IsolatedQbitSDK))
app = create_app(BrowserConfig)
original_csrf_handler = app.error_handler_spec[None][400][CSRFError]


@app.errorhandler(CSRFError)
def observe_csrf_failure(error: CSRFError) -> Any:
    """Retain the actual security failure reason without exposing cookies or tokens."""
    with lock:
        csrf_failures.append(error.description or "CSRF validation failed")
    return original_csrf_handler(error)


@app.route("/e2e/client", methods=["GET", "POST"])
@csrf.exempt  # type: ignore[untyped-decorator]
def fixture_client() -> Response:
    """Expose isolated effects to tests; this route exists only in the test server."""
    if request.method == "POST":
        data = request.get_json() or {}
        if data.get("reset"):
            reset_state()
        with lock:
            if "fail_add" in data:
                controls["fail_add"] = bool(data["fail_add"])
    with lock:
        return jsonify(events=events, torrents=[vars(job) for job in jobs.values()], csrf_failures=csrf_failures)


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
