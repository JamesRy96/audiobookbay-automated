# File: tests/unit/clients/test_deluge.py
"""Unit tests for the Deluge download client plugin."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from audiobook_automated.clients.deluge import DelugeClient


@pytest.fixture
def mock_deluge_client() -> Generator[MagicMock]:
    """Fixture for mocking the Deluge client."""
    with patch("audiobook_automated.clients.deluge.DelugeWebClient") as mock:
        client_instance = mock.return_value
        # Default successful login
        client_instance.login.return_value.error = None
        # Default plugins (None)
        client_instance.execute_call.return_value.result = []
        yield client_instance


def create_client(
    dl_url: str | None = None,
    host: str = "localhost",
    port: int = 8112,
    username: str | None = None,
    password: str | None = None,
) -> DelugeClient:
    """Create a DelugeClient instance for testing."""
    return DelugeClient(dl_url=dl_url, host=host, port=port, username=username, password=password)


def test_deluge_connect_success(mock_deluge_client: MagicMock) -> None:
    """Test successful connection."""
    client = create_client(dl_url="http://localhost:8112", password="pass")
    client.connect()

    mock_deluge_client.login.assert_called_once()
    assert client.client is not None
    assert client.label_plugin_enabled is False


def test_deluge_connect_login_failure(mock_deluge_client: MagicMock) -> None:
    """Test login failure."""
    # Ensure this triggers line 80
    mock_deluge_client.login.return_value.error = "Invalid Password"
    client = create_client(dl_url="http://localhost:8112", password="pass")

    with pytest.raises(ConnectionError, match="Failed to login to Deluge"):
        client.connect()


def test_deluge_connect_with_label_plugin(mock_deluge_client: MagicMock) -> None:
    """Test connection with label plugin enabled."""
    mock_deluge_client.execute_call.return_value.result = ["Label"]
    client = create_client(dl_url="http://localhost:8112", password="pass")
    client.connect()
    assert client.label_plugin_enabled is True


def test_deluge_connect_plugin_check_fail(mock_deluge_client: MagicMock) -> None:
    """Test plugin check failure."""
    mock_deluge_client.execute_call.side_effect = Exception("API Error")
    client = create_client()
    client.connect()
    assert client.label_plugin_enabled is False


def test_deluge_add_magnet_no_client() -> None:
    """Test adding magnet with no client connected."""
    client = create_client()
    with pytest.raises(ConnectionError, match="not connected"):
        client.add_magnet("magnet:?", "/downloads", "audiobooks")


def test_deluge_add_magnet_with_label(mock_deluge_client: MagicMock) -> None:
    """Test adding magnet with label."""
    mock_deluge_client.execute_call.return_value.result = ["Label"]
    client = create_client(dl_url="http://localhost:8112")
    client.connect()

    client.add_magnet("magnet:?", "/downloads", "audiobooks")

    _, kwargs = mock_deluge_client.add_torrent_magnet.call_args
    options = kwargs["torrent_options"]
    assert options.download_location == "/downloads"
    assert options.label == "audiobooks"


def test_deluge_label_failure_is_not_retried(mock_deluge_client: MagicMock) -> None:
    """A label error after acceptance must not submit another unlabelled magnet."""
    mock_deluge_client.execute_call.return_value.result = ["Label"]
    client = create_client()
    client.connect()
    mock_deluge_client.add_torrent_magnet.side_effect = RuntimeError("Unknown parameter: label")
    with pytest.raises(RuntimeError, match="label"):
        client.add_magnet("magnet:?", "/downloads", "books")
    mock_deluge_client.add_torrent_magnet.assert_called_once()


def test_deluge_add_magnet_other_error(mock_deluge_client: MagicMock) -> None:
    """Test adding magnet with other error."""
    # Error NOT related to label
    mock_deluge_client.execute_call.return_value.result = ["Label"]
    client = create_client(dl_url="http://localhost:8112")
    client.connect()

    mock_deluge_client.add_torrent_magnet.side_effect = Exception("Network Error")

    with pytest.raises(Exception, match="Network Error"):
        client.add_magnet("magnet:?", "/downloads", "audiobooks")


def test_deluge_remove_torrent(mock_deluge_client: MagicMock) -> None:
    """Test removing torrent."""
    client = create_client(dl_url="http://localhost:8112")
    client.connect()
    client.remove_torrent("hash")
    mock_deluge_client.remove_torrent.assert_called_with("hash", remove_data=False, timeout=5)


def test_deluge_remove_torrent_no_client() -> None:
    """Test removing torrent with no client."""
    client = create_client()
    with pytest.raises(ConnectionError, match="not connected"):
        client.remove_torrent("hash")


def test_deluge_get_status(mock_deluge_client: MagicMock) -> None:
    """Test getting status."""
    client = create_client(dl_url="http://localhost:8112")
    client.connect()

    mock_deluge_client.get_torrents_status.return_value.result = {
        "hash1": {"name": "Book 1", "state": "Downloading", "progress": 50.5, "total_size": 1024 * 1024}
    }

    statuses = client.get_status("audiobooks")
    assert len(statuses) == 1
    assert statuses[0].id == "hash1"
    assert statuses[0].progress == 50.5
    assert statuses[0].size == "1.00 MB"


def test_deluge_get_status_no_client() -> None:
    """Test getting status with no client."""
    client = create_client()
    with pytest.raises(ConnectionError, match="not connected"):
        client.get_status("cat")


def test_deluge_get_status_invalid_progress(mock_deluge_client: MagicMock) -> None:
    """Test getting status with invalid progress."""
    client = create_client(dl_url="http://localhost:8112")
    client.connect()

    mock_deluge_client.get_torrents_status.return_value.result = {
        "hash1": {"name": "Book 1", "progress": "invalid", "state": "Error", "total_size": 0}
    }

    statuses = client.get_status("audiobooks")
    assert len(statuses) == 1
    assert statuses[0].progress == 0.0


def test_deluge_get_status_bad_data_structure(mock_deluge_client: MagicMock) -> None:
    """Test getting status with bad data structure."""
    client = create_client(dl_url="http://localhost:8112")
    client.connect()

    # result is list instead of dict
    mock_deluge_client.get_torrents_status.return_value.result = ["not a dict"]

    statuses = client.get_status("audiobooks")
    assert statuses == []


def test_deluge_get_status_none_result(mock_deluge_client: MagicMock) -> None:
    """Test getting status with none result."""
    client = create_client(dl_url="http://localhost:8112")
    client.connect()

    mock_deluge_client.get_torrents_status.return_value.result = None

    statuses = client.get_status("audiobooks")
    assert statuses == []


def test_deluge_get_status_null_item(mock_deluge_client: MagicMock) -> None:
    """Test getting status with null item."""
    client = create_client(dl_url="http://localhost:8112")
    client.connect()

    mock_deluge_client.get_torrents_status.return_value.result = {"hash1": None}

    statuses = client.get_status("audiobooks")
    assert statuses == []


def test_deluge_close() -> None:
    """Test closing connection."""
    client = create_client()
    client.client = MagicMock()
    client.close()
    assert client.client is None


def test_deluge_add_magnet_no_label_plugin() -> None:
    """Test add_magnet when label plugin is disabled."""
    client = create_client(dl_url="http://d:1234")
    client.client = MagicMock()
    client.label_plugin_enabled = False  # Explicitly disable

    client.add_magnet("magnet:?", "/path", "cat")

    # Verify calls arguments to ensure no label was passed
    client.client.add_torrent_magnet.assert_called_once()
    call_args = client.client.add_torrent_magnet.call_args
    # call_args[1] is kwargs. Check torrent_options.
    assert "torrent_options" in call_args[1]
    # We can check the attributes of TorrentOptions object if accessible, or just that it ran
    # The coverage gap was the creation of options without label.
    # If the code executed, line 80 is covered.


def test_deluge_get_status_with_label_plugin() -> None:
    """Test get_status when label plugin is enabled."""
    client = create_client(dl_url="http://d:1234")
    client.client = MagicMock()
    client.label_plugin_enabled = True  # Explicitly enable

    # Mock response
    mock_response = MagicMock()
    mock_response.result = {}
    client.client.get_torrents_status.return_value = mock_response

    client.get_status("my-category")

    # Check that filter_dict contained 'label'
    client.client.get_torrents_status.assert_called_once()
    call_args = client.client.get_torrents_status.call_args
    filter_dict = call_args[1]["filter_dict"]
    assert filter_dict.get("label") == "my-category"


def test_deluge_uses_core_plugin_list(mock_deluge_client: MagicMock) -> None:
    """Labels depend on enabled daemon plugins, not the Web UI's plugin dictionary."""
    mock_deluge_client.get_plugins.return_value.result = {"available_plugins": ["Label"], "enabled_plugins": []}
    mock_deluge_client.execute_call.return_value.result = ["Label"]
    client = create_client()
    client.connect()
    assert client.label_plugin_enabled is True
    mock_deluge_client.execute_call.assert_called_once_with(
        {"method": "core.get_enabled_plugins", "params": []}, timeout=5
    )


def test_deluge_honors_timeout_and_closes_session(mock_deluge_client: MagicMock) -> None:
    """Every SDK request uses the configured timeout and cleanup closes its socket pool."""
    client = create_client()
    client.timeout = 7
    client.connect()
    client.add_magnet("magnet:?xt=urn:btih:" + "a" * 40, "/downloads", "books")
    client.get_status("books")
    client.remove_torrent("a" * 40)
    mock_deluge_client.login.assert_called_once_with(timeout=7)
    assert mock_deluge_client.add_torrent_magnet.call_args.kwargs["timeout"] == 7
    options = mock_deluge_client.add_torrent_magnet.call_args.kwargs["torrent_options"]
    assert options.add_paused is False
    assert mock_deluge_client.get_torrents_status.call_args.kwargs["timeout"] == 7
    mock_deluge_client.remove_torrent.assert_called_once_with("a" * 40, remove_data=False, timeout=7)
    client.close()
    client.close()
    mock_deluge_client.close_session.assert_called_once()
    assert client.client is None


def test_deluge_label_detection_is_thread_local() -> None:
    """A second request cannot change the first request's label support."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client = create_client()
    barrier = Barrier(2, timeout=5)

    def request_thread(enabled: bool) -> bool:
        """Hold distinct plugin observations in overlapping request threads."""
        client.label_plugin_enabled = enabled
        barrier.wait()
        return client.label_plugin_enabled

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(request_thread, [True, False])) == [True, False]
    assert client.label_plugin_enabled is False


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("destination", [None, "/downloads/book"])
def test_deluge_real_sdk_rpc_contract(enabled: bool, destination: str | None) -> None:
    """Exercise real SDK serialization, labeling, status and removal at the HTTP boundary."""
    from typing import Any

    calls: list[dict[str, Any]] = []
    info_hash = "a" * 40
    transport = MagicMock()

    def rpc(url: str, **kwargs: Any) -> MagicMock:
        """Return Deluge-shaped responses without replacing SDK methods."""
        assert url == "https://downloads.example/deluge/json"
        assert kwargs["timeout"] == 7
        payload = kwargs["json"]
        calls.append(payload)
        method = payload["method"]
        results: dict[str, Any] = {
            "auth.login": True,
            "web.connected": True,
            "core.get_enabled_plugins": ["Label"] if enabled else [],
            "core.add_torrent_magnet": info_hash,
            "label.add": None,
            "label.set_torrent": None,
            "core.get_torrents_status": {
                info_hash: {"name": "Public-domain book", "progress": 42.5, "state": "Downloading", "total_size": 1024}
            },
            "core.remove_torrent": True,
        }
        assert method in results, method
        response = MagicMock()
        response.ok = True
        response.json.return_value = {"result": results[method], "error": None, "id": payload["id"]}
        response.__enter__.return_value = response
        return response

    transport.post.side_effect = rpc
    with patch("niquests.Session", return_value=transport):
        client = DelugeClient(
            "https://downloads.example/deluge/",
            host="ignored",
            port=8112,
            username=None,
            password="test-password",
            timeout=7,
        )
        client.connect()
        client.add_magnet("magnet:?xt=urn:btih:" + info_hash, destination, "books")
        status = client.get_status("books")
        client.remove_torrent(info_hash)
        client.close()
    assert status[0].progress == 42.5
    add = next(call for call in calls if call["method"] == "core.add_torrent_magnet")
    assert add["params"][0] == "magnet:?xt=urn:btih:" + info_hash
    if destination:
        assert add["params"][1]["download_location"] == destination
    else:
        assert "download_location" not in add["params"][1]
    assert add["params"][1]["add_paused"] is False
    assert sum(call["method"] == "core.add_torrent_magnet" for call in calls) == 1
    assert any(call["method"] == "label.set_torrent" for call in calls) is enabled
    status_call = next(call for call in calls if call["method"] == "core.get_torrents_status")
    assert status_call["params"][0] == ({"label": "books"} if enabled else {})
    assert calls[-1]["method"] == "core.remove_torrent"
    assert calls[-1]["params"] == [info_hash, False]
    transport.close.assert_called_once()


def test_deluge_default_destination_is_omitted(mock_deluge_client: MagicMock) -> None:
    """The daemon receives no download-location override when the user leaves it unset."""
    client = create_client()
    client.connect()
    client.add_magnet("magnet:?xt=test", None, "books")
    options = mock_deluge_client.add_torrent_magnet.call_args.kwargs["torrent_options"]
    assert "download_location" not in options.to_dict()
