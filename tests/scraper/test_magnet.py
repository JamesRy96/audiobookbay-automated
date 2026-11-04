# File: tests/scraper/test_magnet.py
"""Tests for magnet link extraction."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from audiobook_automated.scraper.core import extract_magnet_link


def test_extract_magnet_deduplication() -> None:
    """Duplicate trackers and embedded query delimiters survive as distinct valid magnet parameters."""
    tracker = "https://tracker.example/announce?source=archive&token=test"
    details = {"info_hash": "a" * 40, "title": "Public-domain test", "trackers": [tracker, tracker]}
    with (
        patch("audiobook_automated.scraper.core.get_book_details", return_value=details),
        patch(
            "audiobook_automated.scraper.core.network.get_trackers", return_value=[tracker, "udp://other.example:80"]
        ),
    ):
        magnet, error = extract_magnet_link("https://audiobookbay.lu/abss/book/")
    assert error is None and magnet is not None
    values = parse_qs(urlparse(magnet).query)
    assert values["tr"] == [tracker, "udp://other.example:80"]
    assert "token" not in values


def test_extract_magnet_success() -> None:
    """Test successful magnet link extraction."""
    mock_details = {"info_hash": "123", "title": "Book", "trackers": ["t1"]}
    with patch("audiobook_automated.scraper.core.get_book_details", return_value=mock_details):
        with patch("audiobook_automated.scraper.core.network.get_trackers", return_value=["t2"]):
            magnet, error = extract_magnet_link("url")
            assert error is None
            assert magnet is not None
            assert "xt=urn:btih:123" in magnet
            assert "dn=Book" in magnet
            assert "tr=t1" in magnet
            assert "tr=t2" in magnet


def test_extract_magnet_ssrf_inherited() -> None:
    """Magnet extraction retains the real Details domain validation before obtaining a transport."""
    with (
        patch("audiobook_automated.scraper.core.network.get_mirrors", return_value=["audiobookbay.lu"]),
        patch("audiobook_automated.scraper.core.network.get_thread_session") as session,
    ):
        magnet, error = extract_magnet_link("https://unrelated.example/private")
    assert magnet is None
    assert error is not None and "Invalid domain" in error
    session.assert_not_called()


def test_extract_magnet_generic_exception() -> None:
    """Test generic exception handling."""
    with patch("audiobook_automated.scraper.core.get_book_details", side_effect=Exception("Fail")):
        magnet, error = extract_magnet_link("url")
        assert magnet is None
        assert error is not None
        assert "Error" in error


def test_extract_magnet_none_trackers() -> None:
    """Test magnet link generation with no trackers."""
    mock_details = {"info_hash": "123", "title": "Book", "trackers": []}
    with patch("audiobook_automated.scraper.core.get_book_details", return_value=mock_details):
        with patch("audiobook_automated.scraper.core.network.get_trackers", return_value=[]):
            magnet, error = extract_magnet_link("url")
            assert error is None
            assert magnet is not None
            assert "tr=" not in magnet


def test_extract_magnet_missing_hash() -> None:
    """Test handling of missing info hash."""
    mock_details = {"info_hash": "Unknown", "title": "Book", "trackers": []}
    with patch("audiobook_automated.scraper.core.get_book_details", return_value=mock_details):
        magnet, error = extract_magnet_link("url")
        assert magnet is None
        assert error is not None
