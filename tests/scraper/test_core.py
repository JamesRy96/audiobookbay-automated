# File: tests/scraper/test_core.py
"""Unit tests for the scraper core module."""

import concurrent.futures
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from flask import Flask

from audiobook_automated.scraper.core import fetch_page_results, get_search_url, search_audiobookbay


def test_fetch_page_results_unexpected_exception() -> None:
    """Test that unexpected exceptions are handled."""
    mock_session = MagicMock()
    mock_session.get.side_effect = ValueError("Something unexpected")

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        with patch("audiobook_automated.scraper.core.network.get_semaphore"):
            # Patch logging.getLogger to capture the logger instance
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                results = fetch_page_results("http://example.com")
                assert results == []


def test_fetch_page_missing_href() -> None:
    """Test fetch_page_results handles post title missing href attribute gracefully."""
    html_content = """
    <html>
        <body>
            <div class="post">
                <div class="postTitle">
                    <h2><a>Title Without Href</a></h2>
                </div>
                <div class="postContent">
                    <img src="/cover.jpg" />
                    Some content
                </div>
                <div class="postInfo">Info</div>
            </div>
        </body>
    </html>
    """

    mock_response = MagicMock()
    mock_response.text = html_content
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        with patch("audiobook_automated.scraper.core.network.get_semaphore"):
            results = fetch_page_results("http://audiobookbay.lu/page/1/?s=query")
            assert results == []


def test_search_partial_failure() -> None:
    """Test that search continues and clears cache if one page fails but others succeed."""
    success_result = [
        {
            "title": "Book 1",
            "link": "http://link1",
            "cover": None,
            "language": "En",
            "category": ["Audio"],
            "post_date": "2024",
            "format": "MP3",
            "bitrate": "128",
            "file_size": "100MB",
        }
    ]

    future_success: concurrent.futures.Future[list[dict[str, Any]]] = concurrent.futures.Future()
    future_success.set_result(success_result)

    future_failure: concurrent.futures.Future[list[dict[str, Any]]] = concurrent.futures.Future()
    # The search loop logic re-raises HTTPError inside fetch_page_results,
    # but the loop calling future.result() catches it.
    future_failure.set_exception(requests.HTTPError("500 Server Error"))

    def check_active_mirror(key: Any) -> bool:
        """Check if active mirror is being cleared."""
        return str(key) == "active_mirror"

    with patch("audiobook_automated.scraper.core.executor") as mock_executor:
        # submit is called once per page. We request 2 pages.
        mock_executor.submit.side_effect = [future_success, future_failure]

        with patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="audiobookbay.lu"):
            with patch("audiobook_automated.scraper.core.network.mirror_cache") as mock_mirror_cache:
                # We need to mock __contains__ to return True for "active_mirror"
                mock_mirror_cache.__contains__.side_effect = check_active_mirror

                results = search_audiobookbay("test_query", max_pages=2)

                assert len(results) == 1
                assert results[0]["title"] == "Book 1"
                mock_mirror_cache.__delitem__.assert_called_with("active_mirror")


def test_search_total_failure() -> None:
    """Test that search raises ConnectionError when no mirrors found."""
    import pytest

    with (
        patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value=None),
        pytest.raises(ConnectionError, match="No working AudiobookBay mirrors found"),
    ):
        search_audiobookbay("query")


def test_search_pagination_cancellation(app: Flask) -> None:
    """Test that pagination stops and futures are cancelled when a page returns no results."""
    mock_future1 = MagicMock()
    mock_future1.result.return_value = [{"title": "Book 1", "link": "http://link1"}]

    mock_future2 = MagicMock()
    mock_future2.result.return_value = []

    mock_future3 = MagicMock()
    mock_future3.result.return_value = []

    with (
        app.app_context(),
        patch("audiobook_automated.scraper.core.executor.submit") as mock_submit,
        patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="mirror.com"),
        patch("audiobook_automated.scraper.core.network.get_session"),
    ):
        mock_submit.side_effect = [mock_future1, mock_future2, mock_future3]

        results = search_audiobookbay("test", max_pages=3)

        assert len(results) == 1
        assert results[0]["title"] == "Book 1"


def test_search_http_error_invalidation() -> None:
    """Test that search invalidates mirror and raises ConnectionError on HTTPError."""
    future_failure: concurrent.futures.Future[Any] = concurrent.futures.Future()
    future_failure.set_exception(requests.HTTPError("502 Bad Gateway"))

    def check_active_mirror(key: Any) -> bool:
        """Check if active mirror is being cleared."""
        return str(key) == "active_mirror"

    with patch("audiobook_automated.scraper.core.executor") as mock_executor:
        # Only one page requested, so only one submit call
        mock_executor.submit.return_value = future_failure
        with patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="mirror.com"):
            with patch("audiobook_automated.scraper.core.network.mirror_cache") as mock_mirror_cache:
                # We need to mock __contains__ to return True so the del item logic is triggered
                mock_mirror_cache.__contains__.side_effect = check_active_mirror

                with pytest.raises(ConnectionError, match="AudiobookBay mirror is currently unreachable"):
                    search_audiobookbay("test_query", max_pages=1)
                mock_mirror_cache.__delitem__.assert_called_with("active_mirror")


def test_fetch_page_results_reraises_http_error() -> None:
    """Test that fetch_page_results re-raises HTTPError."""
    mock_session = MagicMock()
    error = requests.HTTPError("404 Not Found")
    mock_session.get.side_effect = error

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        with patch("audiobook_automated.scraper.core.network.get_semaphore"):
            try:
                fetch_page_results("http://example.com")
            except requests.HTTPError as e:
                assert e is error
            else:
                pytest.fail("Should have raised HTTPError")


def test_core_get_search_url_no_query() -> None:
    """Test get_search_url without a query string."""
    # Code logic: if starts with http, keep it.
    url = get_search_url("http://base.com", None, page=1)
    assert url == "http://base.com/page/1/"


def test_core_get_search_url_taxonomy_and_queries() -> None:
    """Test get_search_url with categories, tags, authors, narrators, and direct paths."""
    # Direct path
    assert (
        get_search_url("base.com", "/audio-books/type/action/", page=1) == "https://base.com/audio-books/type/action/"
    )
    assert (
        get_search_url("base.com", "/audio-books/type/action/", page=2)
        == "https://base.com/audio-books/type/action/page/2/"
    )

    # Taxonomy prefixes: category, language, author, narrator
    assert get_search_url("base.com", "category:Sci-Fi", page=1) == "https://base.com/audio-books/type/sci-fi/"
    assert get_search_url("base.com", "category:Sci-Fi", page=3) == "https://base.com/audio-books/type/sci-fi/page/3/"

    assert get_search_url("base.com", "language:English", page=1) == "https://base.com/audio-books/tag/english/"
    assert (
        get_search_url("base.com", "author:Brandon Sanderson", page=1)
        == "https://base.com/page/1/?s=Brandon%20Sanderson"
    )
    assert get_search_url("base.com", "narrator:Ray Porter", page=2) == "https://base.com/page/2/?s=Ray%20Porter"

    # Standard keyword query
    assert (
        get_search_url("base.com", "Dungeon Crawler Carl", page=1)
        == "https://base.com/page/1/?s=Dungeon%20Crawler%20Carl"
    )

    # HTTP scheme preserved when stat indicates http protocol
    with patch("audiobook_automated.scraper.network.get_mirror_stat") as mock_stat:
        mock_stat.return_value.protocol = "http"
        assert get_search_url("http-only.com", "Dungeon", page=1) == "http://http-only.com/page/1/?s=Dungeon"


@pytest.mark.parametrize(
    ("query", "path"),
    [
        ("category:Fantasy", "type/fantasy"),
        ("CATEGORY:Science Fiction", "type/science-fiction"),
        ("language:German", "tag/german"),
        ("Language: Français", "tag/français"),
    ],
)
def test_user_facing_taxonomy_prefixes(query: str, path: str) -> None:
    """User-facing prefixes reach the correct paginated native feeds."""
    assert get_search_url("https://example.com", query) == f"https://example.com/audio-books/{path}/"
    assert get_search_url("https://example.com", query, page=2) == f"https://example.com/audio-books/{path}/page/2/"


@pytest.mark.parametrize(
    ("query", "encoded"),
    [
        ("author:J.R.R. Tolkien", "Tolkien"),
        ("author:J. R. R. Tolkien", "Tolkien"),
        ("AUTHOR: George R. R. Martin", "George%20Martin"),
        ("narrator:Andy Serkis", "Andy%20Serkis"),
        ("narrator:Gert Heidenreich", "Gert%20Heidenreich"),
        ("author:Simon & Schuster Audio", "Simon%20%26%20Schuster%20Audio"),
        ("author:J. R.", "J.%20R."),
        ("author:Émile Zola", "%C3%89mile%20Zola"),
    ],
)
def test_contributor_search_uses_supported_catalog_keywords(query: str, encoded: str) -> None:
    """Use the real catalog search, not nonexistent contributor archive routes."""
    assert get_search_url("https://catalog.example", query) == f"https://catalog.example/page/1/?s={encoded}"
    assert get_search_url("https://catalog.example", query, 2) == f"https://catalog.example/page/2/?s={encoded}"


def test_missing_catalog_page_does_not_penalize_mirror() -> None:
    """A 404 page ends pagination without marking the entire catalog unavailable."""
    response = requests.Response()
    response.status_code = 404
    error = requests.HTTPError("Not found", response=response)
    session = MagicMock()
    session.get.return_value.raise_for_status.side_effect = error
    with (
        patch("audiobook_automated.scraper.core.network.get_session", return_value=session),
        patch("audiobook_automated.scraper.core.network.record_request_outcome") as record,
    ):
        assert fetch_page_results("https://catalog.example/page/30/?s=books") == []
    record.assert_not_called()


@pytest.mark.parametrize("error", [requests.ConnectionError("DNS failed"), requests.Timeout("timed out")])
def test_catalog_transport_failure_is_not_empty_results(error: Exception) -> None:
    """A healthy mirror probe does not turn a subsequent page failure into catalog absence."""
    session = MagicMock()
    session.get.side_effect = error
    with (
        patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="https://catalog.example"),
        patch("audiobook_automated.scraper.core.network.get_session", return_value=session),
        patch("audiobook_automated.scraper.core.network.search_cache", {}),
        pytest.raises(ConnectionError),
    ):
        search_audiobookbay("isolated-transport-failure")
