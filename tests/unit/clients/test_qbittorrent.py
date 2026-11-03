# File: tests/unit/clients/test_qbittorrent.py
"""Unit tests for QBittorrentClient."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from audiobook_automated.clients.qbittorrent import QBittorrentClient


def test_qbittorrent_add_magnet(app: Flask) -> None:
    """Test QBittorrentClient add_magnet."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        # Explicitly set config for test
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30

        mock_instance = MockQbClient.return_value
        # Mock add return (modern API returns JSON/Dict usually)
        mock_instance.torrents_add.return_value = "Ok."

        client = QBittorrentClient("localhost", 8080, "admin", "admin")
        client.connect()
        client.add_magnet("magnet:?xt=urn:btih:ABC", "/downloads/Book", "audiobooks")

        mock_instance.auth_log_in.assert_called_once()
        mock_instance.torrents_add.assert_called_with(
            urls="magnet:?xt=urn:btih:ABC",
            save_path="/downloads/Book",
            category="audiobooks",
        )


def test_qbittorrent_add_magnet_legacy_fail(app: Flask) -> None:
    """Test that qBittorrent legacy 'Fails.' response raises ConnectionError."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30

        mock_instance = MockQbClient.return_value
        mock_instance.torrents_add.return_value = "Fails."

        client = QBittorrentClient("localhost", 8080, "admin", "admin")
        client.connect()

        with pytest.raises(ConnectionError, match="qBittorrent returned failure response: Fails."):
            client.add_magnet("magnet:...", "/path", "cat")


def test_remove_torrent_qbittorrent(app: Flask) -> None:
    """Test removing torrent for qBittorrent."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30

        mock_instance = MockQbClient.return_value

        client = QBittorrentClient("localhost", 8080, "admin", "admin")
        client.connect()
        client.remove_torrent("hash123")

        mock_instance.torrents_delete.assert_called_with(torrent_hashes="hash123", delete_files=False)


def test_get_status_qbittorrent(app: Flask) -> None:
    """Test fetching status from qBittorrent."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30

        mock_instance = MockQbClient.return_value

        mock_torrent = MagicMock()
        mock_torrent.hash = "hash1"
        mock_torrent.name = "Test Book"
        mock_torrent.progress = 0.5
        mock_torrent.state = "downloading"
        mock_torrent.total_size = 1048576  # 1 MB

        mock_instance.torrents_info.return_value = [mock_torrent]

        client = QBittorrentClient("localhost", 8080, "admin", "admin")
        client.connect()
        results = client.get_status("cat")

        assert len(results) == 1
        assert results[0].name == "Test Book"
        assert results[0].progress == 50.0
        assert results[0].state == "Downloading"
        assert results[0].size == "1.00 MB"


def test_qbittorrent_stalledup_maps_to_seeding(app: Flask) -> None:
    """Test that qBittorrent stalledUP status normalizes to Seeding."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        mock_instance = MockQbClient.return_value
        mock_torrent = MagicMock()
        mock_torrent.hash = "hash2"
        mock_torrent.name = "Completed Book"
        mock_torrent.progress = 1.0
        mock_torrent.state = "stalledUP"
        mock_torrent.total_size = 2097152

        mock_instance.torrents_info.return_value = [mock_torrent]

        client = QBittorrentClient("localhost", 8080, "admin", "admin")
        client.connect()
        results = client.get_status("cat")

        assert len(results) == 1
        assert results[0].state == "Seeding"
        assert results[0].progress == 100.0


def test_qbittorrent_close(app: Flask) -> None:
    """Test closing the qBittorrent client."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30

        mock_instance = MockQbClient.return_value

        client = QBittorrentClient("localhost", 8080, "admin", "admin")
        client.connect()
        assert client.client is not None

        client.close()
        mock_instance.auth_log_out.assert_called_once()
        assert client.client is None

        # Also test closing when client has an active _http_session
        client.connect()
        mock_session = MagicMock()
        mock_instance._http_session = mock_session
        client.close()
        mock_session.close.assert_called_once()
        assert client.client is None


def test_qbittorrent_close_exception(app: Flask) -> None:
    """Test closing qBittorrent with exception (should be swallowed/logged)."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30

        mock_instance = MockQbClient.return_value
        mock_instance.auth_log_out.side_effect = Exception("Logout Failed")

        client = QBittorrentClient("localhost", 8080, "admin", "admin")
        client.connect()

        with patch("audiobook_automated.clients.qbittorrent.logger") as mock_logger:
            client.close()
            mock_logger.debug.assert_called()
            assert "Error closing qBittorrent connection" in str(mock_logger.debug.call_args[0])

        assert client.client is None


def test_get_status_qbittorrent_robustness(app: Flask) -> None:
    """Test qBittorrent handling of None progress."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30

        mock_instance = MockQbClient.return_value

        mock_torrent = MagicMock()
        mock_torrent.hash = "hash_bad"
        mock_torrent.name = "Stalled Book"
        mock_torrent.progress = None
        mock_torrent.state = "metaDL"
        mock_torrent.total_size = None

        mock_instance.torrents_info.return_value = [mock_torrent]

        client = QBittorrentClient("localhost", 8080, "admin", "admin")
        client.connect()
        results = client.get_status("cat")

        assert len(results) == 1
        assert results[0].progress == 0.0
        assert results[0].size == "Unknown"


def test_qbittorrent_not_connected() -> None:
    """Test errors when client is not connected."""
    client = QBittorrentClient("localhost", 8080, "admin", "admin")
    # Do NOT connect

    with pytest.raises(ConnectionError, match="qBittorrent client not connected"):
        client.add_magnet("magnet:...", "/path", "cat")

    with pytest.raises(ConnectionError, match="qBittorrent client not connected"):
        client.remove_torrent("123")

    with pytest.raises(ConnectionError, match="qBittorrent client not connected"):
        client.get_status("cat")


def test_qbittorrent_api_key_auth(app: Flask) -> None:
    """Test connecting using api_key parameter."""
    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        mock_instance = MockQbClient.return_value
        mock_instance.app.version = "v5.3.0"

        client = QBittorrentClient("localhost", 8080, "meek2100", "", api_key="test_api_key")
        client.connect()
        assert client.api_key == "test_api_key"
        MockQbClient.assert_called_with(
            host="http://localhost",
            port=8080,
            FORCE_SCHEME_FROM_HOST=True,
            username="meek2100",
            api_key="test_api_key",
            REQUESTS_ARGS={"timeout": 30},
        )
        assert client.client is not None
        client.close()
        assert client.client is None


def test_qbittorrent_password_is_not_guessed_as_an_api_key() -> None:
    """Only the explicit API key setting enables API key authentication."""
    with patch("audiobook_automated.clients.qbittorrent.QbClient") as sdk:
        client = QBittorrentClient("localhost", 8080, "user", "qbt_password")
        client.connect()
        assert client.api_key is None
        sdk.return_value.auth_log_in.assert_called_once()
        assert sdk.call_args.kwargs["password"] == "qbt_password"


def test_qbittorrent_auth_failure_cooldown(app: Flask) -> None:
    """Test repeated auth failures triggering cooldown backoff."""
    from qbittorrentapi.exceptions import LoginFailed

    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        mock_instance = MockQbClient.return_value
        mock_instance.auth_log_in.side_effect = LoginFailed("Auth failed")

        client = QBittorrentClient("localhost", 8080, "admin", "wrong_pass")

        # 1st failure
        with pytest.raises(ConnectionError, match="Incorrect username or password"):
            client.connect()
        assert client.consecutive_auth_failures == 1

        # 2nd failure
        with pytest.raises(ConnectionError, match="Incorrect username or password"):
            client.connect()
        assert client.consecutive_auth_failures == 2

        # 3rd failure triggers backoff
        with pytest.raises(ConnectionError, match="Incorrect username or password"):
            client.connect()
        assert client.consecutive_auth_failures == 3
        assert client.auth_cooldown_until > 0

        # 4th attempt should be blocked by cooldown without hitting server
        with pytest.raises(ConnectionError, match="authentication cooldown active"):
            client.connect()


def test_qbittorrent_ip_banned_detection(app: Flask) -> None:
    """Test handling IP banned Forbidden403Error."""
    from qbittorrentapi.exceptions import Forbidden403Error

    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        mock_instance = MockQbClient.return_value
        mock_instance.auth_log_in.side_effect = Forbidden403Error(
            "Your IP address has been banned after too many failed authentication attempts."
        )

        client = QBittorrentClient("localhost", 8080, "admin", "admin")

        with pytest.raises(ConnectionError, match="IP address banned"):
            client.connect()
        assert client.is_ip_banned is True

        # Subsequent attempts are instantly blocked
        with pytest.raises(ConnectionError, match="IP address is banned"):
            client.connect()


def test_qbittorrent_generic_forbidden(app: Flask) -> None:
    """Test handling generic Forbidden403Error."""
    from qbittorrentapi.exceptions import Forbidden403Error

    with (
        patch("audiobook_automated.clients.qbittorrent.QbClient", autospec=True) as MockQbClient,
        app.app_context(),
    ):
        mock_instance = MockQbClient.return_value
        mock_instance.auth_log_in.side_effect = Forbidden403Error("Access denied")

        client = QBittorrentClient("localhost", 8080, "admin", "admin")

        with pytest.raises(ConnectionError, match="Invalid API key or credentials"):
            client.connect()
        assert client.consecutive_auth_failures == 1


@pytest.mark.parametrize("raw_state", ["stoppedDL", "stoppedUP"])
@pytest.mark.parametrize("raw_size, expected_size", [(-1, "Unknown"), (0, "0.00 B"), (1024, "1.00 KB")])
def test_qbittorrent_stopped_and_pending_metadata(raw_state: str, raw_size: int, expected_size: str) -> None:
    """Real qBittorrent 5 stopped jobs are paused and missing metadata has no negative size."""
    client = QBittorrentClient("localhost", 8080, None, None)
    client.client = MagicMock()
    torrent = MagicMock(hash="test", name="Public-domain audit", state=raw_state, total_size=raw_size, progress=0)
    client.client.torrents_info.return_value = [torrent]
    status = client.get_status("audit")[0]
    assert status.state == "Paused"
    assert status.size == expected_size


@pytest.mark.parametrize("destination", [None, "/downloads/book"])
def test_qbittorrent_real_sdk_https_contract(destination: str | None) -> None:
    """Honor HTTPS and exercise real SDK add/list/delete API parameters."""
    from urllib.parse import parse_qs

    import requests_mock

    info_hash = "c" * 40
    base = "https://client.example:8443/api/v2"
    with requests_mock.Mocker() as mock:
        mock.get(base + "/app/version", text="v5.3.0")
        mock.get(base + "/app/webapiVersion", text="2.14.1")
        mock.post(base + "/torrents/add", text="Ok.")
        mock.post(
            base + "/torrents/info",
            json=[
                {
                    "hash": info_hash,
                    "name": "Public-domain book",
                    "progress": 0.425,
                    "state": "downloading",
                    "total_size": 1024,
                }
            ],
        )
        mock.post(base + "/torrents/delete", text="")
        client = QBittorrentClient(
            "client.example", 8443, None, None, scheme="https", timeout=7, api_key="test-api-key"
        )
        client.connect()
        client.add_magnet("magnet:?xt=urn:btih:" + info_hash, destination, "books")
        add = mock.last_request
        assert add is not None
        expected = {
            "urls": ["magnet:?xt=urn:btih:" + info_hash],
            "category": ["books"],
        }
        if destination:
            expected["savepath"] = [destination]
        assert parse_qs(add.text) == expected
        status = client.get_status("books")
        assert mock.last_request is not None
        assert parse_qs(mock.last_request.text)["category"] == ["books"]
        client.remove_torrent(info_hash)
        assert mock.last_request is not None
        removal = parse_qs(mock.last_request.text)
        assert removal == {"hashes": [info_hash], "deleteFiles": ["False"]}
        client.close()
    assert status[0].progress == 42.5
