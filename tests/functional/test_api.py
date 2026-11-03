# File: tests/functional/test_api.py
"""Functional tests for API endpoints."""

import os
import re
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from audiobook_automated import create_app
from audiobook_automated.config import Config
from audiobook_automated.scraper.parser import BookDetails


def test_health_check(client: FlaskClient) -> None:
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "app": "healthy"}


def test_health_check_client_disconnected_app_still_healthy(client: FlaskClient) -> None:
    """Test health check remains 200 OK even when download client is disconnected."""
    from unittest.mock import patch

    from audiobook_automated.extensions import torrent_manager

    # We patch the instance that is already imported
    with patch.object(
        torrent_manager, "verify_credentials", side_effect=AssertionError("Health attempted a connection")
    ) as verify:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json == {"status": "ok", "app": "healthy"}
        verify.assert_not_called()


def test_search_endpoint_valid(client: FlaskClient) -> None:
    """Test a valid search request."""
    mock_results = [{"title": "Test Book", "link": "http://test", "file_size": "100MB"}]

    with patch("audiobook_automated.routes.search_audiobookbay", return_value=mock_results):
        response = client.get("/?query=testbook")
        assert response.status_code == 200
        assert b"Test Book" in response.data


def test_search_endpoint_short_query(client: FlaskClient) -> None:
    """Test search with a query that is too short."""
    response = client.get("/?query=a")
    assert response.status_code == 200
    assert b"Enter at least" in response.data


def test_search_endpoint_connection_error(client: FlaskClient) -> None:
    """Test search endpoint handles connection errors to mirrors."""
    with patch("audiobook_automated.routes.search_audiobookbay", side_effect=ConnectionError("Mirror down")):
        response = client.get("/?query=testbook")
        assert response.status_code == 200
        # Verify the user friendly error message is displayed
        assert b"Could not connect to AudiobookBay mirrors" in response.data


def test_details_endpoint(client: FlaskClient) -> None:
    """Test the details endpoint rendering."""
    mock_details: BookDetails = {
        "title": "Detailed Book",
        "cover": "http://cover.jpg",
        "description": "<p>Desc</p>",
        "trackers": ["udp://tracker"],
        "file_size": "200MB",
        "info_hash": "12345",
        "link": "http://test/details",
        "language": "English",
        "category": ["Audiobook"],
        "post_date": "2025-01-01",
        "format": "MP3",
        "bitrate": "128kbps",
        "author": "Author",
        "narrator": "Narrator",
    }

    with patch("audiobook_automated.routes.get_book_details", return_value=mock_details):
        response = client.get("/details?link=http://test/details")
        assert response.status_code == 200
        assert b"Detailed Book" in response.data
        assert b"128kbps" in response.data


def test_details_missing_link(client: FlaskClient) -> None:
    """Test details endpoint redirects when link is missing."""
    response = client.get("/details")
    assert response.status_code == 302
    assert response.location == "/" or response.location == "http://localhost/"


def test_details_fetch_error(client: FlaskClient) -> None:
    """Test details endpoint error handling."""
    with patch(
        "audiobook_automated.routes.get_book_details",
        side_effect=Exception("Fetch failed"),
    ):
        response = client.get("/details?link=http://test")
        assert response.status_code == 200
        assert b"Could not load book details" in response.data


def test_send_success(client: FlaskClient) -> None:
    """Test successful download request and verify path spoofing prevention."""
    mock_details = {"title": "Real Scraped Title", "info_hash": "123", "trackers": []}

    with patch(
        "audiobook_automated.routes.extract_magnet_link",
        return_value=("magnet:?xt=urn:btih:123", None),
    ):
        # Patch get_book_details to return a trusted title
        with patch("audiobook_automated.routes.get_book_details", return_value=mock_details):
            with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
                response = client.post(
                    "/send",
                    # User sends "Spoofed Title"
                    json={"link": "https://audiobookbay.lu/book", "title": "Spoofed Title"},
                )

                assert response.status_code == 200
                assert response.json is not None
                assert "Sent to your Download Client" in response.json["message"]
                mock_tm.add_magnet.assert_called_once()

                # The save path must use the Scraped Title, not the user provided one
                args, _ = mock_tm.add_magnet.call_args
                save_path = args[1]
                assert "Real Scraped Title" in save_path
                assert "Spoofed Title" not in save_path


def test_send_invalid_json(client: FlaskClient) -> None:
    """Test send endpoint with non-JSON body."""
    response = client.post("/send", data="not json", content_type="application/json")
    # Flask raises 400 Bad Request on parsing failure (HTML response by default)
    assert response.status_code == 400


def test_send_missing_fields(client: FlaskClient) -> None:
    """Test send endpoint with missing fields."""
    response = client.post("/send", json={"title": "No Link"})
    assert response.status_code == 400
    assert response.json is not None
    assert "Invalid request" in response.json["message"]


def test_send_empty_payload(client: FlaskClient) -> None:
    """Test send endpoint with an empty JSON payload."""
    response = client.post("/send", json={})
    assert response.status_code == 400
    assert response.json is not None
    assert "Invalid request: Title or Link missing" in response.json["message"]


def test_send_extraction_failure(client: FlaskClient) -> None:
    """Test handling of magnet extraction failures."""
    with patch("audiobook_automated.routes.extract_magnet_link") as mock_extract:
        mock_extract.return_value = (None, "Page Not Found")
        response = client.post(
            "/send",
            json={"link": "https://audiobookbay.lu/bad-page", "title": "Bad Book"},
        )
        # Updated to 400 because "Page Not Found" does not contain lowercase "found"
        assert response.status_code == 400
        assert response.json is not None
        assert "Download failed" in response.json["message"]


def test_send_connection_error(client: FlaskClient) -> None:
    """Test handling of connection errors during send."""
    with patch(
        "audiobook_automated.routes.extract_magnet_link",
        side_effect=ConnectionError("Down"),
    ):
        response = client.post(
            "/send",
            json={"link": "https://audiobookbay.lu/book", "title": "Book"},
        )
        # Without specific handler, it falls through to generic 500 handler
        assert response.status_code == 500
        assert response.json is not None
        assert "Down" in response.json["message"]


def test_delete_success(client: FlaskClient) -> None:
    """Test successful torrent deletion."""
    from audiobook_automated.clients.base import TorrentStatus

    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        # Mock get_status to return the torrent we want to delete
        mock_tm.get_status.return_value = [
            TorrentStatus(
                id="hash123", name="Book", progress=100.0, state="Seeding", size="1GB", category="abb-automated"
            )
        ]
        response = client.post("/delete", json={"id": "hash123"})
        assert response.status_code == 200
        mock_tm.remove_torrent.assert_called_with("hash123")


def test_delete_missing_id(client: FlaskClient) -> None:
    """Test delete endpoint without ID."""
    response = client.post("/delete", json={})
    assert response.status_code == 400


def test_reload_library_success(client: FlaskClient) -> None:
    """Test successful library scan trigger."""
    # Ensure config is set
    client.application.config["ABS_URL"] = "http://abs"
    client.application.config["ABS_KEY"] = "key"
    client.application.config["ABS_LIB"] = "lib"

    with patch("audiobook_automated.routes.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        response = client.post("/reload_library")
        assert response.status_code == 200
        assert response.json is not None
        assert "scan initiated" in response.json["message"]


def test_status_json(client: FlaskClient) -> None:
    """Test status endpoint returning JSON."""
    from audiobook_automated.clients.base import TorrentStatus

    mock_status = [
        TorrentStatus(
            id="1",
            name="Book",
            progress=50.0,
            state="Downloading",
            size="100 MB",
            category="audiobooks",
            client="qbittorrent",
        )
    ]
    expected_json = [
        {
            "id": "1",
            "name": "Book",
            "progress": 50.0,
            "state": "Downloading",
            "size": "100 MB",
            "category": "audiobooks",
            "client": "qbittorrent",
        }
    ]

    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.return_value = mock_status
        response = client.get("/status?json=1")
        assert response.status_code == 200
        assert response.json == expected_json


def test_status_json_failure_banned(client: FlaskClient) -> None:
    """Test /status?json=1 error response when client IP is banned."""
    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.side_effect = RuntimeError("Your IP address has been banned")
        response = client.get("/status?json=1")
        assert response.status_code == 500
        json_data = response.get_json()
        assert isinstance(json_data, dict)
        assert json_data.get("client_status") == "banned"


def test_status_json_failure_auth(client: FlaskClient) -> None:
    """Test /status?json=1 error response when client auth fails."""
    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.side_effect = RuntimeError("Invalid password or auth cooldown")
        response = client.get("/status?json=1")
        assert response.status_code == 500
        json_data = response.get_json()
        assert isinstance(json_data, dict)
        assert json_data.get("client_status") == "auth_failed"


def test_status_html_failure_banned(client: FlaskClient) -> None:
    """Test /status HTML rendering with banned status pill."""
    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.side_effect = RuntimeError("Your IP address has been banned")
        mock_tm.list_clients.return_value = ["qbittorrent"]
        response = client.get("/status")
        assert response.status_code == 200
        assert b"IP Banned" in response.data


def test_status_html_failure_auth(client: FlaskClient) -> None:
    """Test /status HTML rendering with auth warning status pill."""
    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.side_effect = RuntimeError("Incorrect password")
        mock_tm.list_clients.return_value = ["qbittorrent"]
        response = client.get("/status")
        assert response.status_code == 200
        assert b"Auth Failed" in response.data


def test_api_clients_endpoint(client: FlaskClient) -> None:
    """Test /api/clients endpoint returning available clients."""

    def mock_verify(name: str | None = None) -> bool:
        return name == "qbittorrent"

    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.list_clients.return_value = ["qbittorrent", "putio"]
        mock_tm.verify_credentials.side_effect = mock_verify
        mock_tm.client_type = "QbittorrentClient"

        response = client.get("/api/clients")
        assert response.status_code == 200
        assert response.json == {
            "clients": [
                {"name": "qbittorrent", "connected": True, "message": ""},
                {
                    "name": "putio",
                    "connected": False,
                    "message": "Cannot connect to Put.io. Check your internet connection and PUTIO_TOKEN in the app settings.",
                },
            ],
            "primary": "qbittorrent",
        }


def test_send_with_client_selection(client: FlaskClient) -> None:
    """Test send endpoint when target client is explicitly specified."""
    mock_details = {"title": "Test Book", "info_hash": "123", "trackers": []}

    with patch(
        "audiobook_automated.routes.extract_magnet_link",
        return_value=("magnet:?xt=urn:btih:123", None),
    ):
        with patch("audiobook_automated.routes.get_book_details", return_value=mock_details):
            with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
                response = client.post(
                    "/send",
                    json={"link": "https://audiobookbay.lu/book", "title": "Test Book", "client": "putio"},
                )
                assert response.status_code == 200
                assert response.json is not None
                assert "Sent to your Download Client" in response.json["message"]
                mock_tm.add_magnet.assert_called_once()
                _, kwargs = mock_tm.add_magnet.call_args
                assert kwargs.get("client_name") == "putio"


def test_send_sanitization_warning(client: FlaskClient, caplog: Any) -> None:
    """Test logging warning for titles requiring sanitization fallback."""
    # We must patch get_book_details to return the unsafe title or fail, so it falls back to user title
    # Here we mock it to return the same unsafe title to trigger the warning logic on that title
    mock_details = {"title": "...", "info_hash": "123", "trackers": []}

    with patch(
        "audiobook_automated.routes.extract_magnet_link",
        return_value=("magnet:?xt=urn:btih:123", None),
    ):
        with patch("audiobook_automated.routes.get_book_details", return_value=mock_details):
            with patch("audiobook_automated.routes.torrent_manager"):
                client.post("/send", json={"link": "http://example.com", "title": "..."})
                # Updated expectation to match the new log message format in routes.py
                assert "required fallback/truncate handling" in caplog.text
                assert "Using collision-safe directory name" in caplog.text


@pytest.fixture
def csrf_app() -> Generator[Flask]:
    """Fixture creating an app with CSRF protection explicitly ENABLED.

    Overrides the default test config which disables CSRF.
    """
    app = create_app()
    app.config.update(
        {
            "TESTING": True,
            "SAVE_PATH_BASE": "/tmp/test_security",
            "SECRET_KEY": "test-security-secret",
            "WTF_CSRF_ENABLED": True,  # CRITICAL: Enable CSRF for this suite
        }
    )
    yield app


def test_search_page_renders_csrf_token(csrf_app: Flask) -> None:
    """Ensure the search page template actually includes the CSRF meta tag.

    This confirms that the frontend has the necessary token to perform actions.
    """
    client = csrf_app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    # Check for the meta tag that actions.js reads
    assert b'name="csrf-token"' in response.data


def test_send_endpoint_requires_csrf(csrf_app: Flask) -> None:
    """Ensure the API rejects POST requests that lack the CSRF token.

    Simulates a CSRF attack or a broken frontend client.
    """
    client = csrf_app.test_client()
    # Attempt a POST request without headers/token
    response = client.post("/send", json={"link": "http://example.com", "title": "Test"})

    # Should fail with 400 Bad Request (The CSRF token is missing)
    assert response.status_code == 400
    assert response.json == {"message": "Page expired. Refresh and try again.", "code": "page_expired"}


def test_delete_endpoint_requires_csrf(csrf_app: Flask) -> None:
    """Ensure the Delete endpoint is protected against CSRF."""
    client = csrf_app.test_client()
    response = client.post("/delete", json={"id": "123"})
    assert response.status_code == 400


def test_reload_library_endpoint_requires_csrf(csrf_app: Flask) -> None:
    """Ensure the Library Reload endpoint is protected."""
    client = csrf_app.test_client()
    response = client.post("/reload_library")
    assert response.status_code == 400


def test_send_json_list(client: FlaskClient) -> None:
    """Test send endpoint with JSON list (not dict)."""
    response = client.post("/send", json=["not", "a", "dict"])
    assert response.status_code == 400
    assert response.json is not None
    assert "Invalid JSON format" in response.json["message"]


def test_send_invalid_title_type(client: FlaskClient) -> None:
    """Test send endpoint with a non-string title to ensure type safety."""
    # This prevents the 500 error where .strip() would be called on an int
    response = client.post("/send", json={"title": 12345, "link": "http://example.com/book"})
    assert response.status_code == 400
    assert response.json is not None
    assert "Invalid request" in response.json["message"]


def test_send_deep_path_truncation(client: FlaskClient) -> None:
    """Test that extremely long paths are safely truncated."""
    # Simulate a user with a very deep SAVE_PATH_BASE (240 chars)
    # 249 limit - 240 base - 1 sep = 8 chars left.
    # 8 > MIN_FILENAME_LENGTH (5), so this should SUCCEED with truncation logic.
    deep_path = "/" + "a" * 240
    client.application.config["SAVE_PATH_BASE"] = deep_path

    long_title = "A" * 100  # Should be heavily truncated
    mock_details = {"title": long_title, "info_hash": "123", "trackers": []}

    with patch(
        "audiobook_automated.routes.extract_magnet_link",
        return_value=("magnet:?xt=urn:btih:123", None),
    ):
        with patch("audiobook_automated.routes.get_book_details", return_value=mock_details):
            with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
                response = client.post("/send", json={"link": "http://link", "title": long_title})
                assert response.status_code == 200

                # Verify add_magnet was called with a path that respects the limit.
                # We expect the save_path to be joined with a truncated title.
                args, _ = mock_tm.add_magnet.call_args
                save_path = args[1]

                # The title component (basename) should be very short (~5-8 chars)
                base_name = os.path.basename(save_path)
                assert len(base_name) >= 5  # Minimum floor check
                assert len(save_path) < 270  # Ensure we didn't explode the path length


def test_delete_json_list(client: FlaskClient) -> None:
    """Test delete endpoint with JSON list (not dict)."""
    response = client.post("/delete", json=["not", "a", "dict"])
    assert response.status_code == 400
    assert response.json is not None
    assert "Invalid JSON format" in response.json["message"]


def test_delete_exception(client: FlaskClient) -> None:
    """Test delete endpoint handling exceptions."""
    from audiobook_automated.clients.base import TorrentStatus

    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        # Mock get_status so it passes the check
        mock_tm.get_status.return_value = [
            TorrentStatus(id="123", name="Book", progress=100.0, state="Seeding", size="1GB", category="abb-automated")
        ]
        mock_tm.remove_torrent.side_effect = Exception("Delete failed")
        response = client.post("/delete", json={"id": "123"})
        assert response.status_code == 500
        assert response.json is not None
        assert "Delete failed" in response.json["message"]


def test_reload_library_missing_config(client: FlaskClient) -> None:
    """Test reload_library with missing configuration."""
    # Ensure config is missing
    client.application.config["ABS_URL"] = None

    response = client.post("/reload_library")
    assert response.status_code == 400
    assert response.json is not None
    assert "not configured" in response.json["message"]


def test_reload_library_request_exception(client: FlaskClient) -> None:
    """Test reload_library handling request exceptions."""
    # Setup valid config so we reach the request part
    client.application.config["ABS_URL"] = "http://abs"
    client.application.config["ABS_KEY"] = "key"
    client.application.config["ABS_LIB"] = "lib"

    # Patch requests to raise exception
    import requests

    with patch(
        "audiobook_automated.routes.requests.post",
        side_effect=requests.exceptions.RequestException("ABS Down"),
    ):
        response = client.post("/reload_library")
        assert response.status_code == 500
        assert response.json is not None
        assert "ABS Down" in response.json["message"]


def test_reload_library_request_exception_with_response(client: FlaskClient) -> None:
    """Test reload_library handling request exceptions with response detail."""
    client.application.config["ABS_URL"] = "http://abs"
    client.application.config["ABS_KEY"] = "key"
    client.application.config["ABS_LIB"] = "lib"

    from unittest.mock import Mock

    import requests

    mock_resp = Mock()
    mock_resp.status_code = 503
    mock_resp.reason = "Service Unavailable"
    mock_resp.text = "Maintenance"

    err = requests.exceptions.RequestException("ABS Down")
    err.response = mock_resp

    with patch("audiobook_automated.routes.requests.post", side_effect=err):
        response = client.post("/reload_library")
        assert response.status_code == 500
        assert response.json is not None
        assert "503 Service Unavailable: Maintenance" in response.json["message"]


def test_reload_library_http_error(client: FlaskClient) -> None:
    """Test reload_library handling HTTPError (upstream status forwarding)."""
    client.application.config["ABS_URL"] = "http://abs"
    client.application.config["ABS_KEY"] = "key"
    client.application.config["ABS_LIB"] = "lib"

    from unittest.mock import Mock

    import requests

    mock_resp = Mock()
    mock_resp.status_code = 404
    mock_resp.reason = "Not Found"
    mock_resp.text = "Library ID invalid"

    # Raise HTTPError specifically to hit the new except block
    err = requests.exceptions.HTTPError("404 Client Error")
    err.response = mock_resp

    with patch("audiobook_automated.routes.requests.post", side_effect=err):
        response = client.post("/reload_library")
        # Should return upstream status code (404) not 500
        assert response.status_code == 404
        assert response.json is not None
        assert "Library scan failed" in response.json["message"]
        assert "404 Not Found: Library ID invalid" in response.json["message"]


def test_send_no_save_path_base(client: FlaskClient) -> None:
    """Test send endpoint when SAVE_PATH_BASE is not configured."""
    client.application.config["SAVE_PATH_BASE"] = None

    with patch(
        "audiobook_automated.routes.extract_magnet_link",
        return_value=("magnet:?xt=urn:btih:123", None),
    ):
        with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
            response = client.post("/send", json={"link": "http://link", "title": "Book"})
            assert response.status_code == 200
            # Omit the destination so the client chooses its configured folder.
            mock_tm.add_magnet.assert_called_with("magnet:?xt=urn:btih:123", None)


def test_send_hash_not_found(client: FlaskClient) -> None:
    """Test POST /send when extract_magnet_link fails with ERROR_HASH_NOT_FOUND (404)."""
    from audiobook_automated.constants import ERROR_HASH_NOT_FOUND

    with patch("audiobook_automated.routes.extract_magnet_link") as mock_extract:
        mock_extract.return_value = (None, ERROR_HASH_NOT_FOUND)
        response = client.post(
            "/send",
            json={"link": "https://audiobookbay.lu/missing-hash", "title": "No Hash Book"},
        )
        assert response.status_code == 404
        assert response.json is not None
        assert "Download failed" in response.json["message"]


def test_search_audiobookbay_exception_handling(client: FlaskClient) -> None:
    """Test search endpoint handling generic exceptions from scraper."""
    with patch("audiobook_automated.routes.search_audiobookbay", side_effect=Exception("Unexpected Error")):
        response = client.get("/?query=test")
        assert response.status_code == 200
        assert b"Search Failed: Unexpected Error" in response.data


def test_send_invalid_link_type(client: FlaskClient) -> None:
    """Test send endpoint with a non-string link to ensure type safety."""
    # Sending an integer as link should trigger the type check error
    response = client.post("/send", json={"link": 12345, "title": "Some Book"})
    assert response.status_code == 400
    assert response.json is not None
    assert "Invalid request: Link must be a string" in response.json["message"]


def test_send_invalid_client_type(client: FlaskClient) -> None:
    """Test send endpoint with non-string client parameter to ensure type safety."""
    response = client.post(
        "/send",
        json={"link": "https://audiobookbay.lu/book", "title": "Some Book", "client": 12345},
    )
    assert response.status_code == 400
    assert response.json is not None
    assert "Client must be a string" in response.json["message"]


def test_send_get_book_details_exception(client: FlaskClient) -> None:
    """Test send proceeds when get_book_details raises an unexpected exception."""
    with patch("audiobook_automated.routes.get_book_details", side_effect=RuntimeError("Details timeout")):
        with patch("audiobook_automated.routes.extract_magnet_link", return_value=("magnet:?xt=urn:btih:123", None)):
            with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
                response = client.post(
                    "/send",
                    json={"link": "https://audiobookbay.lu/book", "title": "Fallback Book"},
                )
                assert response.status_code == 200
                assert response.json is not None
                assert "Sent to your Download Client" in response.json["message"]
                mock_tm.add_magnet.assert_called_once()


@pytest.mark.parametrize(
    "link", ["ftp://example.com/book", "javascript:alert(1)", "//example.com/book", "/\\example.com/book", "book-title"]
)
def test_send_invalid_protocol(client: FlaskClient, link: str) -> None:
    """Reject unsupported schemes and external network-path links before dispatch."""
    response = client.post("/send", json={"link": link, "title": "Some Book"})
    assert response.status_code == 400
    assert response.json is not None
    assert "Invalid book link" in response.json["message"]


def test_delete_wrong_category(client: FlaskClient) -> None:
    """Test that deletion is aborted if the category/label does not match the app's configuration."""
    from audiobook_automated.clients.base import TorrentStatus

    # Mock status with wrong category
    mock_status = TorrentStatus(
        id="123",
        name="Movie",
        progress=100.0,
        state="Seeding",
        size="1 GB",
        category="movies",  # Wrong category
    )

    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.return_value = [mock_status]

        response = client.post("/delete", json={"id": "123"})

        assert response.status_code == 403
        assert response.json is not None
        assert "does not match current app category" in response.json["message"]
        mock_tm.remove_torrent.assert_not_called()


def test_rate_limit_loop(client: FlaskClient) -> None:
    """Test that excessive requests (over limit) return 429."""
    # Hit the /search endpoint 32 times (limit is 30 per minute)
    # We patch search_audiobookbay to avoid actual network calls and ensure speed
    with patch("audiobook_automated.routes.search_audiobookbay", return_value=[]):
        # Consume the 30 allowed requests
        for _ in range(30):
            response = client.get("/?query=test")
            assert response.status_code == 200

        # The 31st request should fail
        response = client.get("/?query=test")
        assert response.status_code == 429


def test_delete_torrent_not_found(client: FlaskClient, app: Flask) -> None:
    """Test that deleting a non-existent torrent returns 404."""
    with patch("audiobook_automated.routes.torrent_manager.get_status", return_value=[]):
        # We need to simulate the torrent check failure
        response = client.post("/delete", json={"id": "nonexistent"})
        assert response.status_code == 404
        json_data = response.json
        assert json_data is not None
        assert json_data["message"] == "Torrent not found"


def test_api_search_endpoint_success(client: FlaskClient) -> None:
    """Test /api/search returns JSON with book summaries and pagination."""
    mock_books = [
        {
            "title": "Async Book",
            "link": "/async-book",
            "cover": "cover.jpg",
            "language": "English",
            "category": ["Sci-Fi"],
            "post_date": "2024",
            "format": "MP3",
            "bitrate": "128",
            "file_size": "200MB",
        }
    ]
    with patch("audiobook_automated.routes.search_audiobookbay", return_value=mock_books) as mock_search:
        response = client.get("/api/search?query=async&page=2")
        assert response.status_code == 200
        data = response.json
        assert data is not None
        assert data["page"] == 2
        assert data["has_more"] is True
        assert len(data["books"]) == 1
        assert data["books"][0]["title"] == "Async Book"
        mock_search.assert_called_once_with("async", max_pages=1, start_page=2)


def test_api_search_endpoint_short_or_empty_query(client: FlaskClient) -> None:
    """Test /api/search returns empty list gracefully on invalid/short queries."""
    with patch("audiobook_automated.routes.search_audiobookbay") as mock_search:
        response = client.get("/api/search?query=a&page=1")
        assert response.status_code == 200
        assert response.json == {"books": [], "has_more": False, "page": 1}
        mock_search.assert_not_called()

        response_empty = client.get("/api/search?query=")
        assert response_empty.status_code == 200
        assert response_empty.json == {"books": [], "has_more": False, "page": 1}
        mock_search.assert_not_called()


def test_api_search_endpoint_invalid_page(client: FlaskClient) -> None:
    """Test /api/search handles invalid page parameter by defaulting to page 1."""
    with patch("audiobook_automated.routes.search_audiobookbay", return_value=[]) as mock_search:
        response = client.get("/api/search?query=dune&page=invalid")
        assert response.status_code == 200
        assert response.json == {"books": [], "has_more": False, "page": 1}
        mock_search.assert_called_once_with("dune", max_pages=1, start_page=1)


def test_api_search_endpoint_negative_page(client: FlaskClient) -> None:
    """Test /api/search handles negative page parameter by clamping to 1."""
    with patch("audiobook_automated.routes.search_audiobookbay", return_value=[]) as mock_search:
        response = client.get("/api/search?query=dune&page=-5")
        assert response.status_code == 200
        assert response.json == {"books": [], "has_more": False, "page": 1}
        mock_search.assert_called_once_with("dune", max_pages=1, start_page=1)


def test_api_search_endpoint_exception(client: FlaskClient) -> None:
    """Test /api/search handles scraping exceptions gracefully with 500 JSON error."""
    with patch("audiobook_automated.routes.search_audiobookbay", side_effect=Exception("Timeout")):
        response = client.get("/api/search?query=dune&page=1")
        assert response.status_code == 500
        data = response.json
        assert data is not None
        assert "Timeout" in data["error"]
        assert data["books"] == []
        assert data["has_more"] is False


def test_delete_routes_to_selected_client_and_rejects_ambiguous_ids(client: FlaskClient) -> None:
    """Do not remove a same-ID download from a different Download Client."""
    from audiobook_automated.clients.base import TorrentStatus

    with patch("audiobook_automated.routes.torrent_manager") as manager:
        manager.get_status.return_value = [
            TorrentStatus("same", "Book", 10, "Downloading", "1 GB", client="qbittorrent"),
            TorrentStatus("same", "Book", 20, "Downloading", "1 GB", client="transmission"),
        ]
        manager.remove_torrent.return_value = True
        assert client.post("/delete", json={"id": "same"}).status_code == 409
        manager.remove_torrent.assert_not_called()
        assert client.post("/delete", json={"id": "same", "client": "transmission"}).status_code == 200
        manager.remove_torrent.assert_called_once_with("same", client_name="transmission")
        manager.remove_torrent.return_value = False
        assert client.post("/delete", json={"id": "same", "client": "transmission"}).status_code == 502


def test_delete_rejects_invalid_client_values(client: FlaskClient) -> None:
    """Validate optional Download Client values before accessing integrations."""
    values: tuple[object, ...] = ([], 4, "", " ")
    for value in values:
        assert client.post("/delete", json={"id": "same", "client": value}).status_code == 400


def test_missing_details_shows_recoverable_error(client: FlaskClient) -> None:
    """A failed scraper response must not render a blank Details page."""
    with patch("audiobook_automated.routes.get_book_details", return_value=None):
        response = client.get("/details?link=https://audiobookbay.lu/book")
    assert response.status_code == 200
    assert b"Audiobook details unavailable" in response.data
    assert b"Back to Search" in response.data


def test_catalog_credit_does_not_fetch_details_or_change_raw_title(client: FlaskClient) -> None:
    """Derive credit locally and leave cached search objects unmodified."""
    book = {"title": "A series - A subtitle - Anna Elliott,Charles Veley", "link": "/book"}
    with (
        patch("audiobook_automated.routes.search_audiobookbay", return_value=[book]) as search,
        patch("audiobook_automated.routes.get_book_details") as details,
    ):
        response = client.get("/api/search?query=books&page=2")
        assert response.status_code == 200
        assert response.json is not None
        result = response.json["books"][0]
        assert result["title"] == book["title"]
        assert result["display_title"] == "A series - A subtitle"
        assert result["credited_contributors"] == ["Anna Elliott", "Charles Veley"]
        assert "author_credit" not in book
        search.assert_called_once_with("books", max_pages=1, start_page=2)
        details.assert_not_called()


class SessionConfig(Config):
    """Keep production session and CSRF behavior with isolated integrations."""

    TESTING = False
    SAVE_PATH_BASE = "/tmp/test_session_security"
    DL_CLIENT = "qbittorrent"
    SECRET_KEY = ""
    WTF_CSRF_ENABLED = True
    RATELIMIT_ENABLED = False
    SPLASH_ENABLED = False


def page_token(client: FlaskClient) -> str:
    """Read the token supplied to the real browser action controls."""
    response = client.get("/")
    assert response.status_code == 200
    token = re.search(rb'name="csrf-token" content="([^"]+)"', response.data)
    assert token is not None
    return token.group(1).decode()


@pytest.mark.parametrize("fixed_key", [False, True])
def test_restart_signing_and_page_recovery(fixed_key: bool) -> None:
    """Reject old automatic-key tokens, support explicit keys and recover after refresh."""

    class SigningConfig(SessionConfig):
        SECRET_KEY = "test-explicit-restart-key" if fixed_key else ""

    original: Flask = create_app(SigningConfig)
    restarted: Flask = create_app(SigningConfig)
    if fixed_key:
        assert original.secret_key == restarted.secret_key == SigningConfig.SECRET_KEY
    else:
        assert isinstance(original.secret_key, str)
        assert len(bytes.fromhex(original.secret_key)) == 32
        assert original.secret_key != restarted.secret_key
        assert SigningConfig.SECRET_KEY == ""

    before = original.test_client()
    token = page_token(before)
    # A missing download returns 404 only after the real CSRF gate accepts the request.
    assert before.post("/delete", json={"id": "absent"}, headers={"X-CSRFToken": token}).status_code == 404
    cookie_name = original.config["SESSION_COOKIE_NAME"]
    cookie = before.get_cookie(cookie_name)
    assert cookie is not None
    after = restarted.test_client()
    after.set_cookie(cookie_name, cookie.value)
    response = after.post("/delete", json={"id": "absent"}, headers={"X-CSRFToken": token})
    if fixed_key:
        assert response.status_code == 404
    else:
        assert response.status_code == 400
        assert response.json == {"message": "Page expired. Refresh and try again.", "code": "page_expired"}
    fresh_token = page_token(after)
    assert after.post("/delete", json={"id": "absent"}, headers={"X-CSRFToken": fresh_token}).status_code == 404
    assert after.post("/delete", json={"id": "absent"}, headers={"X-CSRFToken": "forged"}).status_code == 400


@pytest.mark.parametrize(
    "link", ["/abss/will-wpight-cradle-series-full-books-1-12-will-wight/", "/abss/the-fsleeper-awakes-hg-wells/"]
)
def test_send_catalog_relative_search_link(client: FlaskClient, link: str) -> None:
    """Catalog-relative links emitted by initial and appended search cards must reach dispatch."""
    with (
        patch("audiobook_automated.routes.get_book_details", return_value={"title": "Catalog title"}) as details,
        patch(
            "audiobook_automated.routes.extract_magnet_link", return_value=("magnet:?xt=urn:btih:" + "a" * 40, None)
        ) as magnet,
        patch("audiobook_automated.routes.torrent_manager") as manager,
    ):
        response = client.post("/send", json={"link": link, "title": "Search title"})
        assert response.status_code == 200
        details.assert_called_once_with(link)
        magnet.assert_called_once_with(link)
        manager.add_magnet.assert_called_once()


@pytest.mark.parametrize("url", ["/static/css/style.css", "/api/search?query=a", "/api/clients", "/health"])
def test_background_response_does_not_delete_page_session(url: str) -> None:
    """A late cookie-less resource must not erase the page's valid CSRF session."""
    app = create_app(SessionConfig)
    page = app.test_client()
    token = page_token(page)
    background = app.test_client(use_cookies=False)
    response = background.get(url)
    assert response.status_code == 200
    assert "Set-Cookie" not in response.headers
    assert page.post("/delete", json={"id": "absent"}, headers={"X-CSRFToken": token}).status_code == 404


@pytest.mark.parametrize("clock_delta", [-2, 2])
def test_signed_page_rejects_clock_rollback_and_expiry(clock_delta: int) -> None:
    """A future-dated session or expired action token must remain invalid."""
    from itsdangerous import TimestampSigner

    app = create_app(SessionConfig)
    app.config["WTF_CSRF_TIME_LIMIT"] = 1
    browser = app.test_client()
    with patch.object(TimestampSigner, "get_timestamp", return_value=1700000000):
        token = page_token(browser)
    assert browser.get_cookie(app.config["SESSION_COOKIE_NAME"]) is not None
    with patch.object(TimestampSigner, "get_timestamp", return_value=1700000000 + clock_delta):
        response = browser.post("/delete", json={"id": "absent"}, headers={"X-CSRFToken": token})
    assert response.status_code == 400
    assert response.json == {"message": "Page expired. Refresh and try again.", "code": "page_expired"}


def test_api_clients_checks_only_requested_client(client: FlaskClient) -> None:
    """Independent checks do not wait for unrelated offline clients."""
    with patch("audiobook_automated.routes.torrent_manager") as manager:
        manager.list_clients.return_value = ["qbittorrent", "deluge"]
        manager.client_type = "QbittorrentClient"
        manager.verify_credentials.return_value = False
        response = client.get("/api/clients?client=DELUGE")
        assert response.status_code == 200
        assert response.json is not None
        assert response.json["clients"][0]["connected"] is False
        assert "DELUGE_HOST" in response.json["clients"][0]["message"]
        assert "127.0.0.1" in response.json["clients"][0]["message"]
        manager.verify_credentials.assert_called_once_with("deluge")
        manager.verify_credentials.reset_mock()
        response = client.get("/api/clients?client=unknown")
        assert response.status_code == 400
        manager.verify_credentials.assert_not_called()


@pytest.mark.parametrize(
    "shared, per_client, expected",
    [
        (None, None, None),
        ("/shared", None, "/shared/Test Book"),
        ("/shared", "/transmission-books", "/transmission-books/Test Book"),
    ],
)
def test_download_destination_is_optional_and_client_specific(
    client: FlaskClient, app: Flask, shared: str | None, per_client: str | None, expected: str | None
) -> None:
    """Client default wins unless an explicit shared or per-client root is configured."""
    app.config["SAVE_PATH_BASE"] = shared
    app.config["CLIENT_CONNECTIONS"] = {"transmission": {"SAVE_PATH_BASE": per_client}}
    with (
        patch("audiobook_automated.routes.get_book_details", return_value={"title": "Test Book"}),
        patch("audiobook_automated.routes.extract_magnet_link", return_value=("magnet:?xt=test", None)),
        patch("audiobook_automated.routes.torrent_manager.add_magnet") as add,
    ):
        response = client.post("/send", json={"link": "/abss/test/", "title": "Test Book", "client": "transmission"})
    assert response.status_code == 200
    add.assert_called_once_with("magnet:?xt=test", expected, client_name="transmission")
