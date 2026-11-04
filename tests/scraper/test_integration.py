# File: tests/scraper/test_integration.py
"""Integration tests for the scraper pipeline."""

from concurrent.futures import Future
from typing import Any
from unittest.mock import patch

import pytest
from flask import Flask

from audiobook_automated.scraper import network
from audiobook_automated.scraper.core import search_audiobookbay


def test_search_audiobookbay_success(app: Flask) -> None:
    """Test full search pipeline with mocked network calls."""
    mock_results: list[dict[str, Any]] = [
        {
            "title": "Book 1",
            "link": "http://book1",
            "category": ["Audio"],
            "language": "En",
            "format": "MP3",
            "bitrate": "128",
            "file_size": "100MB",
            "cover": None,
            "post_date": "2023",
        }
    ]

    with patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="audiobookbay.lu"):
        with patch("audiobook_automated.scraper.core.fetch_page_results", return_value=mock_results):
            results = search_audiobookbay("query", max_pages=1)
            assert len(results) == 1
            assert results[0]["title"] == "Book 1"


def test_search_caching(app: Flask) -> None:
    """A valid cached search remains available without an external mirror probe."""
    with network.CACHE_LOCK:
        network.search_cache["cached::pages_1_1"] = []
    with patch(
        "audiobook_automated.scraper.core.network.find_best_mirror",
        side_effect=AssertionError("Cached results must not require a mirror"),
    ):
        assert search_audiobookbay("cached") == []


def test_search_audiobookbay_sync_coverage(app: Flask) -> None:
    """Collect pages in their requested order and retain each book once."""
    pages = []
    for books in [
        [{"title": "First", "link": "/a"}],
        [{"title": "Duplicate", "link": "/a"}, {"title": "Second", "link": "/b"}],
    ]:
        future: Future[Any] = Future()
        future.set_result(books)
        pages.append(future)
    with (
        patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="audiobookbay.lu"),
        patch("audiobook_automated.scraper.core.executor.submit", side_effect=pages),
    ):
        assert [book["title"] for book in search_audiobookbay("ordered", max_pages=2)] == ["First", "Second"]


def test_search_no_mirrors_raises_error(app: Flask) -> None:
    """Test behavior when no mirrors are found."""
    import pytest

    with (
        patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value=None),
        pytest.raises(ConnectionError, match="No working AudiobookBay mirrors found"),
    ):
        search_audiobookbay("query")


def test_search_thread_failure(app: Flask) -> None:
    """Successful pages may be returned but a partially failed multi-page result must not be cached."""
    failed: Future[Any] = Future()
    failed.set_exception(ConnectionError("Page unavailable"))
    succeeded: Future[Any] = Future()
    succeeded.set_result([{"title": "Second page", "link": "/second"}])
    with (
        patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="audiobookbay.lu"),
        patch("audiobook_automated.scraper.core.executor.submit", side_effect=[failed, succeeded]),
    ):
        assert len(search_audiobookbay("partial", max_pages=2)) == 1
    assert "partial::pages_1_2" not in network.search_cache


def test_search_audiobookbay_generic_exception_in_thread(app: Flask) -> None:
    """Failed parsing cannot become a cached empty catalog result."""
    failed: Future[Any] = Future()
    failed.set_exception(ValueError("Unexpected catalog markup"))
    with (
        patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="audiobookbay.lu"),
        patch("audiobook_automated.scraper.core.executor.submit", return_value=failed),
    ):
        with pytest.raises(ConnectionError, match="Unexpected catalog markup"):
            search_audiobookbay("parse failure")
    assert "parse failure::pages_1_1" not in network.search_cache


def test_search_pipeline_success(app: Flask) -> None:
    """Test successful search pipeline."""
    mock_results = [{"title": "B1", "link": "L1"}]
    with patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="m"):
        with patch("audiobook_automated.scraper.core.fetch_page_results", return_value=mock_results):
            res = search_audiobookbay("q", 1)
            assert len(res) == 1


def test_search_pipeline_no_results(app: Flask) -> None:
    """Test search pipeline with no results."""
    with patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="m"):
        with patch("audiobook_automated.scraper.core.fetch_page_results", return_value=[]):
            res = search_audiobookbay("q", 1)
            assert res == []


def test_search_pipeline_network_error(app: Flask) -> None:
    """Test search pipeline with network error."""
    with patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="m"):
        with patch("audiobook_automated.scraper.core.fetch_page_results", side_effect=Exception("Net")):
            with pytest.raises(ConnectionError, match="Net"):
                search_audiobookbay("q", 1)
