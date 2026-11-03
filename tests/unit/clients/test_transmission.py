# File: tests/unit/clients/test_transmission.py
"""Unit tests for TransmissionClient."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from audiobook_automated.clients.transmission import TransmissionClient


def test_transmission_add_magnet(app: Flask) -> None:
    """Test TransmissionClient add_magnet."""
    with (
        patch("audiobook_automated.clients.transmission.TxClient") as MockTxClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30
        mock_instance = MockTxClient.return_value

        client = TransmissionClient("localhost", 9091, "admin", "admin")
        client.connect()
        client.add_magnet("magnet:?xt=urn:btih:DEF", "/downloads/Book", "audiobooks")

        mock_instance.add_torrent.assert_called_with(
            "magnet:?xt=urn:btih:DEF", download_dir="/downloads/Book", labels=["audiobooks"], paused=False
        )


def test_transmission_label_rejection_does_not_dispatch_an_untracked_task() -> None:
    """Do not retry without labels after a server rejects the requested options."""
    with patch("audiobook_automated.clients.transmission.TxClient") as sdk:
        sdk.return_value.add_torrent.side_effect = RuntimeError("Invalid argument: labels")
        client = TransmissionClient("localhost", 9091, None, None)
        client.connect()
        with pytest.raises(RuntimeError, match="labels"):
            client.add_magnet("magnet:?xt=urn:btih:" + "a" * 40, "/downloads/book", "books")
        sdk.return_value.add_torrent.assert_called_once()


def test_transmission_add_magnet_generic_error(app: Flask) -> None:
    """Test Transmission re-raises generic errors."""
    with (
        patch("audiobook_automated.clients.transmission.TxClient") as MockTxClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30
        mock_instance = MockTxClient.return_value
        mock_instance.add_torrent.side_effect = Exception("Disk Full")

        client = TransmissionClient("localhost", 9091, "admin", "admin")
        client.connect()

        with pytest.raises(Exception) as exc:
            client.add_magnet("magnet:...", "/path", "cat")
        assert "Disk Full" in str(exc.value)


def test_remove_torrent_transmission_int_id(app: Flask) -> None:
    """Test removing torrent with integer ID."""
    with (
        patch("audiobook_automated.clients.transmission.TxClient") as MockTxClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30
        mock_instance = MockTxClient.return_value

        client = TransmissionClient("localhost", 9091, "admin", "admin")
        client.connect()
        client.remove_torrent("123")

        mock_instance.remove_torrent.assert_called_with(ids=[123], delete_data=False)


def test_remove_torrent_transmission_hash_id(app: Flask) -> None:
    """Test removing torrent with hash ID."""
    with (
        patch("audiobook_automated.clients.transmission.TxClient") as MockTxClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30
        mock_instance = MockTxClient.return_value

        client = TransmissionClient("localhost", 9091, "admin", "admin")
        client.connect()
        client.remove_torrent("hash123")

        mock_instance.remove_torrent.assert_called_with(ids=["hash123"], delete_data=False)


def test_get_status_transmission(app: Flask) -> None:
    """Test fetching status from Transmission."""
    with (
        patch("audiobook_automated.clients.transmission.TxClient") as MockTxClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30
        mock_instance = MockTxClient.return_value

        mock_torrent = MagicMock()
        mock_torrent.id = 1
        mock_torrent.name = "Test Book"
        mock_torrent.progress = 75.0
        mock_status = MagicMock()
        mock_status.name = "downloading"
        mock_torrent.status = mock_status
        mock_torrent.total_size = 1024
        mock_torrent.labels = ["cat"]

        mock_instance.get_torrents.return_value = [mock_torrent]

        client = TransmissionClient("localhost", 9091, "admin", "admin")
        client.connect()
        results = client.get_status("cat")

        mock_instance.get_torrents.assert_called_with(
            arguments=["id", "name", "percentDone", "status", "totalSize", "labels"]
        )

        assert len(results) == 1
        assert results[0].progress == 75.0
        assert results[0].size == "1.00 KB"


def test_get_status_transmission_robustness(app: Flask) -> None:
    """Test fetching status from Transmission handles None values gracefully."""
    with (
        patch("audiobook_automated.clients.transmission.TxClient") as MockTxClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30
        mock_instance = MockTxClient.return_value

        mock_torrent_bad = MagicMock()
        mock_torrent_bad.id = 2
        mock_torrent_bad.name = "Bad Torrent"
        mock_torrent_bad.progress = None
        mock_torrent_bad.total_size = None
        mock_status_bad = MagicMock()
        mock_status_bad.name = "error"
        mock_torrent_bad.status = mock_status_bad
        mock_torrent_bad.labels = ["cat"]

        mock_instance.get_torrents.return_value = [mock_torrent_bad]

        client = TransmissionClient("localhost", 9091, "admin", "admin")
        client.connect()
        results = client.get_status("cat")

        assert len(results) == 1
        assert results[0].name == "Bad Torrent"
        assert results[0].progress == 0.0
        assert results[0].size == "Unknown"


def test_get_status_transmission_filtering(app: Flask) -> None:
    """Test client-side filtering by label."""
    with (
        patch("audiobook_automated.clients.transmission.TxClient") as MockTxClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30
        mock_instance = MockTxClient.return_value

        t1 = MagicMock(id=1, labels=["cat1"])
        t1.name = "T1"
        t2 = MagicMock(id=2, labels=["cat2"])
        t2.name = "T2"

        # Mock status/progress for robustness
        t1.status.name = "dl"
        t1.progress = 10
        t1.total_size = 100
        t2.status.name = "dl"
        t2.progress = 20
        t2.total_size = 200

        mock_instance.get_torrents.return_value = [t1, t2]

        client = TransmissionClient("localhost", 9091, "admin", "admin")
        client.connect()
        results = client.get_status("cat1")

        assert len(results) == 1
        assert results[0].name == "T1"


def test_transmission_close(app: Flask) -> None:
    """Test closing Transmission client."""
    with (
        patch("audiobook_automated.clients.transmission.TxClient") as MockTxClient,
        app.app_context(),
    ):
        from flask import current_app

        current_app.config["CLIENT_TIMEOUT"] = 30
        # Mock successful connection
        MockTxClient.return_value = MagicMock()

        client = TransmissionClient("localhost", 9091, "admin", "admin")
        client.connect()
        assert client.client is not None
        client.close()
        assert client.client is None


def test_transmission_not_connected() -> None:
    """Test errors when client is not connected."""
    client = TransmissionClient("localhost", 9091, "admin", "admin")
    # Do NOT connect

    with pytest.raises(ConnectionError, match="Transmission client not connected"):
        client.add_magnet("magnet:...", "/path", "cat")

    with pytest.raises(ConnectionError, match="Transmission client not connected"):
        client.remove_torrent("123")

    with pytest.raises(ConnectionError, match="Transmission client not connected"):
        client.get_status("cat")


def test_transmission_closes_http_session() -> None:
    """Releasing a request must close the SDK's connection pool."""
    client = TransmissionClient("localhost", 9091, None, None)
    sdk = MagicMock()
    client.client = sdk
    client.close()
    client.close()
    sdk._http_session.close.assert_called_once()
    assert client.client is None


def test_transmission_real_sdk_rpc_contract() -> None:
    """Validate SDK session negotiation, dispatch, labels and file-preserving removal."""
    from typing import Any

    import requests_mock

    calls: list[dict[str, Any]] = []
    info_hash = "b" * 40

    def rpc(request: Any, context: Any) -> dict[str, Any]:
        """Emulate only the remote RPC transport using official response shapes."""
        payload = request.json()
        calls.append(payload)
        context.headers["X-Transmission-Session-Id"] = "isolated-session"
        if len(calls) == 1:
            context.status_code = 409
            return {}
        assert request.headers["X-Transmission-Session-Id"] == "isolated-session"
        method = payload["method"]
        results = {
            "session-get": {"version": "4.0.6", "rpc-version": 17, "rpc-version-minimum": 1},
            "torrent-add": {"torrent-added": {"id": 7, "hashString": info_hash, "name": "Public-domain book"}},
            "torrent-get": {
                "torrents": [
                    {
                        "id": 7,
                        "name": "Public-domain book",
                        "percentDone": 0.425,
                        "status": 4,
                        "totalSize": 1024,
                        "labels": ["books"],
                    }
                ]
            },
            "torrent-remove": {},
        }
        assert method in results
        return {"result": "success", "arguments": results[method]}

    with requests_mock.Mocker() as mock:
        mock.post("http://localhost:9091/transmission/rpc", json=rpc)
        client = TransmissionClient("localhost", 9091, None, None, timeout=7)
        client.connect()
        client.add_magnet("magnet:?xt=urn:btih:" + info_hash, "/downloads/book", "books")
        status = client.get_status("books")
        client.remove_torrent("7")
        client.close()
    assert status[0].progress == 42.5
    assert status[0].state == "Downloading"
    add = next(call for call in calls if call["method"] == "torrent-add")
    assert add["arguments"]["filename"] == "magnet:?xt=urn:btih:" + info_hash
    assert add["arguments"]["download-dir"] == "/downloads/book"
    assert add["arguments"]["labels"] == ["books"]
    assert add["arguments"]["paused"] is False
    assert calls[-1]["arguments"] == {"ids": [7], "delete-local-data": False}
