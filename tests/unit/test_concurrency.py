# File: tests/unit/test_concurrency.py
"""Unit tests for concurrency and thread safety."""

import concurrent.futures
import time
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from audiobook_automated.scraper.core import get_book_details, search_audiobookbay
from audiobook_automated.scraper.network import (
    CACHE_LOCK,
    details_cache,
    get_trackers,
    mirror_cache,
    search_cache,
    tracker_cache,
)


@pytest.fixture
def clean_caches() -> Generator[None]:
    """Clear all caches before and after each test."""
    with CACHE_LOCK:
        search_cache.clear()
        details_cache.clear()
        tracker_cache.clear()
        mirror_cache.clear()
    yield
    with CACHE_LOCK:
        search_cache.clear()
        details_cache.clear()
        tracker_cache.clear()
        mirror_cache.clear()


def test_concurrent_cache_access(clean_caches: None, app: Flask) -> None:
    """Test concurrent access to shared caches using multiple threads.

    Requires app fixture to ensure worker threads can access current_app.config.
    """
    num_threads = 15
    iterations = 5

    # Mock responses
    mock_search_results: list[dict[str, Any]] = [
        {
            "title": "Book 1",
            "link": "https://audiobookbay.lu/book1",
            "cover": "cover.jpg",
            "language": "English",
            "category": ["Audiobooks"],
            "post_date": "2023-01-01",
            "format": "MP3",
            "bitrate": "128kbps",
            "file_size": "100MB",
        }
    ]

    mock_details = {
        "title": "Book 1",
        "link": "https://audiobookbay.lu/book1",
        "description": "Desc",
        "trackers": [],
        "file_size": "100MB",
        "info_hash": "123",
        "language": "English",
        "category": ["Audiobooks"],
        "post_date": "2023-01-01",
        "format": "MP3",
        "bitrate": "128kbps",
        "cover": "cover.jpg",
    }

    # Mock the underlying network calls
    with patch("audiobook_automated.scraper.core.fetch_page_results", return_value=mock_search_results):
        with patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="audiobookbay.lu"):
            with patch("audiobook_automated.scraper.core.network.get_session") as mock_session:
                # Mock session.get for get_book_details
                mock_response = MagicMock()
                mock_response.text = "<html></html>"
                mock_response.status_code = 200
                mock_session.return_value.get.return_value = mock_response

                # Patch parser.parse_book_details via core's import if possible, or directly in parser module if core uses module reference
                # core.py: book_details = parser.parse_book_details(soup, url)
                # So we patch audiobook_automated.scraper.parser.parse_book_details
                with patch(
                    "audiobook_automated.scraper.parser.parse_book_details",
                    return_value=mock_details,
                ):
                    with patch(
                        "audiobook_automated.scraper.network.Path.exists",
                        return_value=False,
                    ):
                        # Define worker functions
                        def worker_search() -> None:
                            # Use test_request_context to satisfy Flask-Executor/copy_current_request_context
                            with app.test_request_context():
                                for _ in range(iterations):
                                    # Access search_cache
                                    res = search_audiobookbay("query", max_pages=1)
                                    assert res == mock_search_results
                                    time.sleep(0.01)

                        def worker_details() -> None:
                            with app.test_request_context():
                                for _ in range(iterations):
                                    # Access details_cache
                                    res = get_book_details("https://audiobookbay.lu/book1")
                                    assert res == mock_details
                                    time.sleep(0.01)

                        def worker_trackers() -> None:
                            with app.test_request_context():
                                for _ in range(iterations):
                                    # Access tracker_cache
                                    res = get_trackers()
                                    # Should return default trackers if file not found
                                    assert isinstance(res, list)
                                    time.sleep(0.01)

                        # Run threads
                        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                            futures = []
                            for _ in range(5):
                                futures.append(executor.submit(worker_search))
                                futures.append(executor.submit(worker_details))
                                futures.append(executor.submit(worker_trackers))

                            # Wait for all to complete and check for exceptions
                            for future in concurrent.futures.as_completed(futures):
                                try:
                                    future.result()
                                except (RuntimeError, KeyError) as e:
                                    pytest.fail(f"Thread failed with concurrency error: {e}")
                                except Exception as e:
                                    # Other exceptions might be setup issues, but we want to fail explicitly
                                    pytest.fail(f"Thread failed: {e}")

    # Verify caches are populated correctly
    with CACHE_LOCK:
        assert "query::pages_1_1" in search_cache
        assert "https://audiobookbay.lu/book1" in details_cache
        assert "default" in tracker_cache
