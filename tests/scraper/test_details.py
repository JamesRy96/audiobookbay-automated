# File: tests/scraper/test_details.py
"""Tests for get_book_details."""

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import requests
from flask import Flask

from audiobook_automated.scraper import get_book_details
from audiobook_automated.scraper.parser import BookDetails


def test_get_book_details_sanitization(mock_sleep: Any) -> None:
    """Test sanitization of book details."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Sanitized Book</h1></div>
        <div class="desc">
            <p style="color: red;">Allowed P tag.</p>
            <script>alert('XSS');</script>
            <b>Bold Text</b>
            <a href="http://bad.com">Malicious Link</a>
        </div>
    </div>
    """

    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/book")

        assert details is not None
        description = str(details.get("description", ""))

        assert "<p>Allowed P tag.</p>" in description
        assert "style" not in description
        assert "<b>Bold Text</b>" in description
        assert "Malicious Link" in description
        assert "<a href" not in description
        assert "<script>" not in description


def test_get_book_details_caching(mock_sleep: Any) -> None:
    """Test caching of book details."""
    url = "https://audiobookbay.lu/cached_details"
    expected = cast(BookDetails, {"title": "Cached Details"})
    from audiobook_automated.scraper.network import details_cache

    details_cache[url] = expected

    with patch("audiobook_automated.scraper.core.network.get_session") as mock_session_getter:
        result = get_book_details(url)
        assert result == expected
        mock_session_getter.assert_not_called()


def test_get_book_details_success(details_html: str, mock_sleep: Any) -> None:
    """Test successful retrieval of book details."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = details_html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/valid-book")

        assert details is not None
        assert details["title"] == "A Game of Thrones"
        assert details["info_hash"] == "eb154ac7886539c4d01eae14908586e336cdb550"
        assert details["file_size"] == "1.37 GBs"


def test_get_book_details_default_cover_skip(mock_sleep: Any) -> None:
    """Test skipping of default cover image."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Book Default Cover</h1></div>
        <div class="postContent">
            <img itemprop="image" src="/images/default_cover.jpg">
        </div>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/def-cover")
        assert details is not None
        assert details["cover"] is None


def test_get_book_details_failure(mock_sleep: Any) -> None:
    """Test handling of network failure."""
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.exceptions.RequestException("Net Down")

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        with patch("audiobook_automated.scraper.core.logger.error") as mock_log:
            result = get_book_details("https://audiobookbay.lu/fail-book")
            assert result is None
            mock_log.assert_called()


@pytest.mark.parametrize(
    "url", ["https://audiobookbay.lu.unrelated.example/book", "http://audiobookbay.lu@127.0.0.1/private"]
)
def test_get_book_details_ssrf_protection(url: str) -> None:
    """Lookalike hosts and credential-prefixed private targets are rejected before network access."""
    with (
        patch("audiobook_automated.scraper.core.network.get_mirrors", return_value=["audiobookbay.lu"]),
        patch("audiobook_automated.scraper.core.network.get_thread_session") as session,
    ):
        with pytest.raises(ValueError, match="Invalid domain"):
            get_book_details(url)
    session.assert_not_called()


def test_get_book_details_empty(mock_sleep: Any) -> None:
    """Test handling of empty URL."""
    with patch("audiobook_automated.scraper.core.network.get_session"):
        with pytest.raises(ValueError, match="Invalid domain"):
            get_book_details("")


def test_get_book_details_url_parse_error(mock_sleep: Any) -> None:
    """Test handling of invalid URL protocol."""
    with patch("audiobook_automated.scraper.core.network.get_session"):
        with pytest.raises(ValueError, match="Invalid domain"):
            get_book_details("http://anything")


def test_get_book_details_missing_metadata(mock_sleep: Any) -> None:
    """Test handling of missing metadata."""
    html = """<div class="post"><div class="postTitle"><h1>Empty Book</h1></div></div>"""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/empty")
        assert details is not None
        assert details["language"] == "Unknown"
        assert details["format"] == "Unknown"


def test_get_book_details_unknown_bitrate_normalization(mock_sleep: Any) -> None:
    """Test normalization of unknown bitrate."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Unknown Bitrate</h1></div>
        <div class="postContent"><p>Bitrate: ?</p></div>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/unknown")
        assert details is not None
        assert details["bitrate"] == "Unknown"


def test_get_book_details_partial_bitrate(mock_sleep: Any) -> None:
    """Test handling of partial bitrate info."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Partial Info</h1></div>
        <div class="postContent"><p>Bitrate: 128 Kbps</p></div>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/partial_bitrate")
        assert details is not None
        assert details["format"] == "Unknown"
        assert details["bitrate"] == "128 Kbps"


def test_get_book_details_partial_format(mock_sleep: Any) -> None:
    """Test handling of partial format info."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Partial Info</h1></div>
        <div class="postContent"><p>Format: MP3</p></div>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/partial")
        assert details is not None
        assert details["format"] == "MP3"
        assert details["bitrate"] == "Unknown"


def test_get_book_details_content_without_metadata_labels(mock_sleep: Any) -> None:
    """Test handling of content without metadata labels."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>No Metadata</h1></div>
        <div class="postContent"><p>Just text.</p></div>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/no_meta")
        assert details is not None
        assert details["format"] == "Unknown"


def test_get_book_details_consistency_checks(mock_sleep: Any) -> None:
    """Test consistency checks for book details."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Mystery Details</h1></div>
        <div class="postInfo">Category: ? Language: ?</div>
        <div class="postContent">
            <p>Posted: ?</p>
            <p>Format: ?</p>
            <span class="author" itemprop="author">?</span>
            <span class="narrator" itemprop="author">?</span>
        </div>
        <table class="torrent_info">
            <tr><td>File Size:</td><td>?</td></tr>
        </table>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/mystery")

        assert details is not None
        assert details["language"] == "Unknown"
        assert details["category"] == ["Unknown"]
        assert details["post_date"] == "Unknown"
        assert details["format"] == "Unknown"
        assert details["author"] == "Unknown"
        assert details["narrator"] == "Unknown"
        assert details["file_size"] == "Unknown"


def test_get_book_details_info_hash_method_2(mock_sleep: Any) -> None:
    """Test info hash extraction method 2 (table row lookup)."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Method 2 Book</h1></div>
        <table>
            <tr>
                <td>Info Hash:</td>
                <td>1111111111222222222233333333334444444444</td>
            </tr>
        </table>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/method2")
        assert details is not None
        assert details["info_hash"] == "1111111111222222222233333333334444444444"


def test_get_book_details_info_hash_method_3(mock_sleep: Any) -> None:
    """Test info hash extraction method 3 (body text regex)."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Method 3 Book</h1></div>
        <div class="postContent">
            Some text containing the hash 5555555555666666666677777777778888888888 in the body.
        </div>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        details = get_book_details("https://audiobookbay.lu/method3")
        assert details is not None
        assert details["info_hash"] == "5555555555666666666677777777778888888888"


def test_get_book_details_relative_url(mock_sleep: Any) -> None:
    """Test get_book_details handles relative URLs from search results correctly."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Relative URL Book</h1></div>
        <div class="postContent">Content</div>
    </div>
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_session.get.return_value = mock_response

    with patch("audiobook_automated.scraper.core.network.get_session", return_value=mock_session):
        with patch("audiobook_automated.scraper.core.network.find_best_mirror", return_value="audiobookbay.lu"):
            details = get_book_details("/abss/relative-book/")
            assert details is not None
            assert details["title"] == "Relative URL Book"


def test_get_book_details_network_failure_records_outcome(app: Flask) -> None:
    """A connection failure while fetching details is fed back into mirror ranking."""
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("down")
    with (
        app.app_context(),
        patch("audiobook_automated.scraper.core.network.get_session", return_value=session),
        patch("audiobook_automated.scraper.core.network.get_mirrors", return_value=["audiobookbay.lu"]),
        patch("audiobook_automated.scraper.core.network.record_request_outcome") as record,
    ):
        assert get_book_details("https://audiobookbay.lu/abss/x/", refresh=True) is None
        record.assert_called_once()
        assert record.call_args.args[:2] == ("https://audiobookbay.lu/abss/x/", False)


def test_uncached_details_obeys_request_jitter_and_semaphore() -> None:
    """A real Details fetch uses the same bounded request policy as search."""
    entered = False

    class Gate:
        """Observe the exact external request scope without a real semaphore."""

        def __enter__(self) -> None:
            nonlocal entered
            entered = True

        def __exit__(self, *_: Any) -> None:
            nonlocal entered
            entered = False

    session = MagicMock()
    response = MagicMock()
    response.text = '<div class="postTitle"><h1>Test book</h1></div>'

    def request(*_: Any, **__: Any) -> Any:
        """Only permit the external request after the configured jitter and gate."""
        assert entered
        sleep.assert_called_once_with(1.0)
        return response

    session.get.side_effect = request
    with (
        patch("audiobook_automated.scraper.core.network.get_mirrors", return_value=["catalog.example"]),
        patch("audiobook_automated.scraper.core.network.get_session", return_value=session),
        patch("audiobook_automated.scraper.core.network.get_semaphore", return_value=Gate()),
        patch("audiobook_automated.scraper.network.random.uniform", return_value=1.0),
        patch("audiobook_automated.scraper.network.time.sleep") as sleep,
    ):
        assert get_book_details("https://catalog.example/book", refresh=True) is not None
    assert not entered
