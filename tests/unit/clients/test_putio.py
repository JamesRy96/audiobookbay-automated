# File: tests/unit/clients/test_putio.py
"""Unit tests for Put.io download client plugin."""

import pytest
import requests_mock
from flask import Flask

from audiobook_automated.clients.manager import TorrentManager
from audiobook_automated.clients.putio import PutioClient


def test_putio_init_defaults() -> None:
    """Test Put.io client initialization with default parameters."""
    client = PutioClient("localhost", 443, None, None, token="sample-token")
    assert client.token == "sample-token"
    assert client.folder_id == "0"
    assert client.base_url == "https://api.put.io/v2"


def test_putio_init_custom_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Put.io client initialization with custom host, port, and env variables."""
    monkeypatch.setenv("PUTIO_TOKEN", "env-token")
    monkeypatch.setenv("PUTIO_FOLDER_ID", "42")

    client = PutioClient("custom.putio.internal", 8443, None, None, scheme="https")
    assert client.token == "env-token"
    assert client.folder_id == "42"
    assert client.base_url == "https://custom.putio.internal:8443/v2"


def test_putio_connect_success() -> None:
    """Test successful Put.io session connection."""
    client = PutioClient("localhost", 443, None, "pw-token")
    client.connect()
    assert client.session is not None
    assert client.session.headers.get("Authorization") == "Bearer pw-token"
    client.close()
    assert client.session is None


def test_putio_connect_missing_token() -> None:
    """Test that connect raises ConnectionError when no token is configured."""
    client = PutioClient("localhost", 443, None, None)
    client.token = None
    with pytest.raises(ConnectionError, match="not configured"):
        client.connect()


def test_putio_verify_credentials() -> None:
    """Test Put.io verify_credentials method across success, failure, and exceptions."""
    client = PutioClient("localhost", 443, None, "valid-token")

    with requests_mock.Mocker() as m:
        # Success case
        m.get("https://api.put.io/v2/account/info", json={"status": "OK", "info": {"username": "user"}})
        assert client.verify_credentials() is True

        # Non-OK status in JSON
        m.get("https://api.put.io/v2/account/info", json={"status": "ERROR"})
        assert client.verify_credentials() is False

        # HTTP error status
        m.get("https://api.put.io/v2/account/info", status_code=401)
        assert client.verify_credentials() is False

        # Network/connection error
        m.get("https://api.put.io/v2/account/info", exc=ConnectionError("DNS failure"))
        assert client.verify_credentials() is False

    # Failure when token is completely missing
    client_no_token = PutioClient("localhost", 443, None, None)
    client_no_token.token = None
    assert client_no_token.verify_credentials() is False


def test_putio_add_magnet() -> None:
    """Test Put.io add_magnet across success and error conditions."""
    client = PutioClient("localhost", 443, None, "valid-token", folder_id="100")

    with requests_mock.Mocker() as m:
        # Success case
        m.post("https://api.put.io/v2/transfers/add", json={"status": "OK", "transfer": {"id": 12345}})
        client.add_magnet("magnet:?xt=urn:btih:ABC", "/tmp/save", "audiobooks")
        assert "magnet" in m.last_request.text
        assert "100" in m.last_request.text

        # HTTP status failure
        m.post("https://api.put.io/v2/transfers/add", status_code=400, text="Bad Request")
        with pytest.raises(RuntimeError, match="HTTP 400"):
            client.add_magnet("magnet:?xt=urn:btih:ABC", "/tmp/save", "audiobooks")

        # JSON status error
        m.post(
            "https://api.put.io/v2/transfers/add",
            status_code=200,
            json={"status": "ERROR", "error_message": "Invalid magnet URI"},
        )
        with pytest.raises(RuntimeError, match="Invalid magnet URI"):
            client.add_magnet("magnet:?xt=urn:btih:ABC", "/tmp/save", "audiobooks")

    # Client not connected when token is missing
    client_no_token = PutioClient("localhost", 443, None, None)
    client_no_token.token = None
    with pytest.raises(ConnectionError, match="not configured"):
        client_no_token.add_magnet("magnet:...", "/tmp", "audiobooks")


def test_putio_get_status() -> None:
    """Test Put.io get_status with transfers, metadata fetching, and errors."""
    client = PutioClient("localhost", 443, None, "valid-token")

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.put.io/v2/transfers/list",
            json={
                "status": "OK",
                "transfers": [
                    {
                        "id": 101,
                        "name": "Book One",
                        "status": "DOWNLOADING",
                        "percent_done": 67.891,
                        "size": 52428800,
                    },
                    {
                        "id": 102,
                        "name": None,
                        "status": "IN_QUEUE",
                        "percent_done": 0,
                        "size": 0,
                    },
                ],
            },
        )
        torrents = client.get_status("audiobooks")
        assert len(torrents) == 2
        assert torrents[0].id == "101"
        assert torrents[0].name == "Book One"
        assert torrents[0].progress == 67.89
        assert torrents[0].state == "Downloading"
        assert "50.00 MB" in torrents[0].size
        assert torrents[0].category == "audiobooks"

        assert torrents[1].id == "102"
        assert torrents[1].name == "Unknown"
        assert torrents[1].size == "fetching meta.."

        # HTTP error
        m.get("https://api.put.io/v2/transfers/list", status_code=500, text="Internal Error")
        with pytest.raises(RuntimeError, match="HTTP 500"):
            client.get_status("audiobooks")

    # Client not connected when token is missing
    client_no_token = PutioClient("localhost", 443, None, None)
    client_no_token.token = None
    with pytest.raises(ConnectionError, match="not configured"):
        client_no_token.get_status("audiobooks")


def test_putio_remove_torrent() -> None:
    """Test Put.io remove_torrent (cancel transfer) across success and errors."""
    client = PutioClient("localhost", 443, None, "valid-token")

    with requests_mock.Mocker() as m:
        # Success
        m.post("https://api.put.io/v2/transfers/cancel", json={"status": "OK"})
        client.remove_torrent("101")
        assert "101" in m.last_request.text

        # HTTP error
        m.post("https://api.put.io/v2/transfers/cancel", status_code=404, text="Not Found")
        with pytest.raises(RuntimeError, match="HTTP 404"):
            client.remove_torrent("101")

        # JSON status error
        m.post(
            "https://api.put.io/v2/transfers/cancel",
            status_code=200,
            json={"status": "ERROR", "error_message": "Transfer not found"},
        )
        with pytest.raises(RuntimeError, match="Transfer not found"):
            client.remove_torrent("101")

    # Client not connected when token is missing
    client_no_token = PutioClient("localhost", 443, None, None)
    client_no_token.token = None
    with pytest.raises(ConnectionError, match="not configured"):
        client_no_token.remove_torrent("101")


def test_putio_manager_integration(app: Flask) -> None:
    """Test loading and interacting with PutioClient via TorrentManager."""
    manager = TorrentManager()
    app.config["DL_CLIENT"] = "putio"
    app.config["PUTIO_TOKEN"] = "manager-token"
    app.config["PUTIO_FOLDER_ID"] = "99"

    manager.init_app(app)
    assert isinstance(manager.client, PutioClient)
    assert manager.client.token == "manager-token"
    assert manager.client.folder_id == "99"
    assert manager.client_type == "PutioClient"


def test_putio_status_rejects_api_error() -> None:
    """An HTTP 200 API failure must not look like an empty healthy client."""
    client = PutioClient("localhost", 443, None, "test-token")
    with requests_mock.Mocker() as mock:
        mock.get("https://api.put.io/v2/transfers/list", json={"status": "ERROR", "error_message": "Access denied"})
        with pytest.raises(RuntimeError, match="Access denied"):
            client.get_status("books")
    client.close()


def test_putio_http_contract_preserves_files_and_credentials() -> None:
    """Use the vendor's transfer endpoints and form fields without leaking tokens in URLs."""
    from urllib.parse import parse_qs

    client = PutioClient("localhost", 443, None, None, token="isolated-token", folder_id="42", timeout=7)
    magnet = "magnet:?xt=urn:btih:" + "d" * 40
    with requests_mock.Mocker() as mock:
        mock.get("https://api.put.io/v2/account/info", json={"status": "OK"})
        mock.post("https://api.put.io/v2/transfers/add", json={"status": "OK", "transfer": {"id": 7}})
        mock.get(
            "https://api.put.io/v2/transfers/list",
            json={
                "status": "OK",
                "transfers": [
                    {"id": 7, "name": "Public-domain book", "percent_done": 42.5, "status": "DOWNLOADING", "size": 1024}
                ],
            },
        )
        mock.post("https://api.put.io/v2/transfers/cancel", json={"status": "OK"})
        assert client.verify_credentials()
        client.add_magnet(magnet, "/unused-local-path", "unused-category")
        assert mock.last_request is not None
        assert parse_qs(mock.last_request.text) == {"url": [magnet], "save_parent_id": ["42"]}
        assert client.get_status("books")[0].progress == 42.5
        client.remove_torrent("7")
        assert mock.last_request is not None
        assert parse_qs(mock.last_request.text) == {"transfer_ids": ["7"]}
        for request in mock.request_history:
            assert request.headers["Authorization"] == "Bearer isolated-token"
            assert "isolated-token" not in request.url
            assert "/files/" not in request.url
    client.close()
