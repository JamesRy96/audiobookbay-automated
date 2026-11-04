# File: tests/functional/test_system.py
"""Functional tests for system-level routes and static assets."""

from typing import Any
from unittest.mock import MagicMock, patch


def test_health_check_route(client: Any) -> None:
    """Test the /health endpoint returns a 200 OK JSON response."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "app": "healthy"}
    assert response.content_type == "application/json"


def test_home_page_static_versioning(client: Any) -> None:
    """Test that static assets in the home page include version query parameters."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"?v=" in response.data
    assert b"favicon.ico?v=" in response.data


def test_static_assets_cache_control(client: Any) -> None:
    """Test that static assets are served with long-term caching headers."""
    response = client.get("/static/images/favicon.ico")
    if response.status_code == 200:
        cache_control = response.headers.get("Cache-Control", "")
        assert "max-age=31536000" in cache_control
        assert "public" in cache_control


def test_nav_link_injection(client: Any) -> None:
    """Test that injected variables correctly appear in the template."""
    # Update config directly on the app instance — monkeypatching the module would not affect an already-created app
    client.application.config["NAV_LINK_NAME"] = "My Player"
    client.application.config["NAV_LINK_URL"] = "http://player.local"

    response = client.get("/")
    assert b"My Player" in response.data
    assert b"http://player.local" in response.data


def test_library_reload_injection(client: Any) -> None:
    """Test that the Reload Library link appears only when configured."""
    # Case 1: Configured -> Link should be present
    client.application.config["ABS_URL"] = "http://abs"
    client.application.config["ABS_KEY"] = "key"
    client.application.config["ABS_LIB"] = "lib"
    # LIBRARY_RELOAD_ENABLED is derived from env vars at startup; set it directly for the test
    client.application.config["LIBRARY_RELOAD_ENABLED"] = True

    response = client.get("/")
    assert b"Reload Library" in response.data

    # Case 2: Not Configured -> Link should be absent
    client.application.config["ABS_URL"] = None
    client.application.config["LIBRARY_RELOAD_ENABLED"] = False

    response = client.get("/")
    assert b"Reload Library" not in response.data


def test_status_page(client: Any) -> None:
    """Test that the status page renders active downloads correctly."""
    from audiobook_automated.clients.base import TorrentStatus

    # Patch where torrent_manager is imported (routes.py) rather than at its definition site
    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.return_value = [
            TorrentStatus(id="1", name="Book 1", progress=50, state="Downloading", size="100 MB")
        ]
        response = client.get("/status")
        assert response.status_code == 200
        assert b"Book 1" in response.data


def test_status_route_error(client: Any) -> None:
    """Test that the status page displays errors when the torrent manager fails."""
    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.side_effect = Exception("Database Locked")

        response = client.get("/status")
        assert response.status_code == 200
        assert b"Download Client" in response.data
        assert b"address, port and login" in response.data
        assert b"Database Locked" in response.data


def test_status_page_empty(client: Any) -> None:
    """Test status page rendering when there are no active torrents.

    Ensures the empty state message matches the UI expectations.
    """
    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.return_value = []
        response = client.get("/status")
        assert response.status_code == 200
        assert b"No active downloads found" in response.data


def test_status_page_json_response(client: Any) -> None:
    """Test that the status page returns JSON when requested.

    This verifies the frontend polling mechanism works (fixes the hermeneutic gap
    between frontend expectations and backend delivery).
    """
    from audiobook_automated.clients.base import TorrentStatus

    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.return_value = [
            TorrentStatus(id="1", name="JSON Book", progress=99.9, state="Seeding", size="500 MB")
        ]

        response = client.get("/status?json=1")

        assert response.status_code == 200
        assert response.is_json
        data = response.json
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "JSON Book"


def test_status_page_json_error(client: Any) -> None:
    """Test that status page returns JSON error structure on failure when polling."""
    with patch("audiobook_automated.routes.torrent_manager") as mock_tm:
        mock_tm.get_status.side_effect = Exception("Client unreachable")

        response = client.get("/status?json=1")

        assert response.status_code == 500
        assert response.is_json
        # Explicit check for error key as defined in routes.py
        assert "address, port and login" in response.json["error"]
        assert "address, port and login" in response.json["error"]
        assert "Client unreachable" not in response.json["error"]


def test_reload_library_error(client: Any) -> None:
    """Test that the reload_library endpoint handles upstream errors gracefully."""
    # Ensure the feature is enabled
    client.application.config["LIBRARY_RELOAD_ENABLED"] = True
    client.application.config["ABS_URL"] = "http://abs"
    client.application.config["ABS_KEY"] = "key"
    client.application.config["ABS_LIB"] = "lib"

    # Mock requests.post to raise an error or return non-200
    with patch("audiobook_automated.routes.requests.post") as mock_post:
        # Simulate a 500 error from Audiobookshelf
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.reason = "Internal Server Error"
        # Mock raise_for_status to actually raise, simulating Requests behavior
        from requests.exceptions import HTTPError

        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)
        mock_post.return_value = mock_response

        response = client.post("/reload_library")

        # Verify it passes the 500 back to the client
        assert response.status_code == 500
        assert "Library scan failed" in response.json["message"]
        assert "500 Internal Server Error" in response.json["message"]


def test_serve_root_asset(client: Any) -> None:
    """Test serving static assets requested directly at the root (fallback route)."""
    # Valid existing asset
    response = client.get("/audiobookbay-header.jpg")
    assert response.status_code == 200
    assert response.content_type == "image/jpeg"

    # Non-existent asset
    response = client.get("/nonexistent-image.jpg")
    assert response.status_code == 404

    # Non-media or invalid extension
    response = client.get("/something.py")
    assert response.status_code == 404
