# File: tests/unit/clients/test_manager.py
"""Unit tests for the TorrentManager."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, get_ident
from typing import Any
from unittest.mock import MagicMock, patch

from flask import Flask
from pytest import LogCaptureFixture, raises

from audiobook_automated.clients.base import TorrentClientPlugin, TorrentStatus
from audiobook_automated.clients.manager import TorrentManager


class MockClient(TorrentClientPlugin):
    """Mock client plugin for testing."""

    def connect(self) -> None:
        """Mock connect."""
        pass

    def close(self) -> None:
        """Mock close."""
        pass

    def add_magnet(self, magnet_link: str, save_path: str | None, category: str) -> None:
        """Mock add_magnet."""
        pass

    def remove_torrent(self, torrent_id: str) -> None:
        """Mock remove_torrent."""
        pass

    def get_status(self, category: str) -> list[TorrentStatus]:
        """Mock get_status."""
        return []

    def verify_credentials(self) -> bool:
        """Mock verify_credentials."""
        return True

    DEFAULT_PORT = 1234


def test_manager_load_client_success(app: Flask, caplog: LogCaptureFixture) -> None:
    """Test successful client plugin loading."""
    import logging

    caplog.set_level(logging.INFO)
    manager = TorrentManager()

    mock_module = MagicMock()
    mock_module.MockClient = MockClient

    with patch("importlib.import_module", return_value=mock_module):
        app.config["DL_CLIENT"] = "mock_client"
        app.config.setdefault("CLIENT_CONNECTIONS", {}).setdefault(app.config["DL_CLIENT"].split(",")[0], {})[
            "HOST"
        ] = "1.2.3.4"
        app.config.setdefault("CLIENT_CONNECTIONS", {}).setdefault(app.config["DL_CLIENT"].split(",")[0], {})[
            "PORT"
        ] = "9999"
        app.config.setdefault("CLIENT_CONNECTIONS", {}).setdefault(app.config["DL_CLIENT"].split(",")[0], {})[
            "USERNAME"
        ] = "testuser"
        app.config.setdefault("CLIENT_CONNECTIONS", {}).setdefault(app.config["DL_CLIENT"].split(",")[0], {})[
            "PASSWORD"
        ] = "testpass"

        manager.init_app(app)

        assert isinstance(manager.client, MockClient)
        assert manager.client.host == "1.2.3.4"
        assert manager.client.port == 9999
        assert manager.client.username == "testuser"
        assert manager.client.password == "testpass"

        assert "Successfully loaded 'mock_client'" in caplog.text


def test_manager_load_client_default_port(app: Flask, caplog: LogCaptureFixture) -> None:
    """Use documented defaults when host and port are unset."""
    manager = TorrentManager()

    mock_module = MagicMock()
    mock_module.MockClient = MockClient

    with patch("importlib.import_module", return_value=mock_module):
        app.config["DL_CLIENT"] = "mock_client"
        app.config.setdefault("CLIENT_CONNECTIONS", {}).setdefault(app.config["DL_CLIENT"].split(",")[0], {})[
            "HOST"
        ] = None
        # Client PORT missing or None to trigger default logic
        app.config.setdefault("CLIENT_CONNECTIONS", {}).setdefault(app.config["DL_CLIENT"].split(",")[0], {})[
            "PORT"
        ] = None

        manager.init_app(app)

        assert isinstance(manager.client, MockClient)
        assert manager.client.host == "localhost"
        assert manager.client.port == 1234  # MockClient.DEFAULT_PORT


def test_manager_invalid_port_does_not_select_another_port(app: Flask) -> None:
    """Reject invalid internal configuration rather than dispatching to an unexpected service."""
    app.config.update(DL_CLIENT="qbittorrent", CLIENT_CONNECTIONS={"qbittorrent": {"PORT": "invalid"}})
    with raises(ValueError):
        TorrentManager().init_app(app)


def test_manager_load_client_invalid_name(app: Flask, caplog: LogCaptureFixture) -> None:
    """Test invalid client name."""
    manager = TorrentManager()
    app.config["DL_CLIENT"] = "invalid$name"

    with patch("importlib.import_module") as mock_import:
        mock_import.side_effect = ImportError("Stop here")

        manager.init_app(app)

        assert "Security: Invalid DL_CLIENT name" in caplog.text
        assert "No client loaded" in caplog.text
        mock_import.assert_not_called()


def test_manager_load_client_import_error(app: Flask, caplog: LogCaptureFixture) -> None:
    """Test client plugin import error."""
    manager = TorrentManager()
    app.config["DL_CLIENT"] = "missing_client"

    with patch("importlib.import_module", side_effect=ImportError("No module")):
        manager.init_app(app)

        assert manager.client is None
        assert "Failed to load client 'missing_client'" in caplog.text


def test_manager_load_client_no_class(app: Flask, caplog: LogCaptureFixture) -> None:
    """Test with no valid plugin class."""
    manager = TorrentManager()
    app.config["DL_CLIENT"] = "empty_client"

    mock_module = MagicMock(spec=[])

    with patch("importlib.import_module", return_value=mock_module):
        manager.init_app(app)

    assert manager.client is None
    assert "Failed to load client 'empty_client'" in caplog.text


def test_manager_proxy_methods_no_client() -> None:
    """Test proxy methods with no client."""
    manager = TorrentManager()
    manager.client = None

    assert manager.verify_credentials() is False
    with raises(ConnectionError, match="No Download Client"):
        manager.add_magnet("link", "path")
    assert manager.get_status() == []
    assert manager.remove_torrent("id") is False
    manager.close()


def test_manager_proxy_methods_with_client(app: Flask) -> None:
    """Test proxy methods with client."""
    manager = TorrentManager()
    app.config["DL_CATEGORY"] = "abb-automated"
    # Access private member via public method or fixture?
    # Or just ignore lint for test
    manager._app = app  # pyright: ignore[reportPrivateUsage]

    client = MagicMock()
    manager.client = client

    client.verify_credentials.return_value = True
    assert manager.verify_credentials() is True

    manager.add_magnet("link", "path")
    # Verify add_magnet called. It returns None so we check assertion side effect only.
    client.add_magnet.assert_called_with("link", "path", "abb-automated")

    status = TorrentStatus("test-id", "Test audiobook", 42, "Downloading", "1 MB")
    client.get_status.return_value = [status]
    assert manager.get_status() == [status]
    assert status.client == "magicmock"
    client.get_status.assert_called_with("abb-automated")

    client.remove_torrent.return_value = True
    assert manager.remove_torrent("id") is True

    # Exception handling
    client.remove_torrent.side_effect = Exception("Fail")
    assert manager.remove_torrent("id") is False

    manager.close()
    client.close.assert_called_once()


def test_manager_teardown_request() -> None:
    """Test teardown request."""
    manager = TorrentManager()
    client = MagicMock()
    manager.client = client

    manager.teardown_request()

    client.teardown = MagicMock()
    manager.teardown_request()
    client.teardown.assert_called_once()


def test_manager_client_type() -> None:
    """Test client type."""
    manager = TorrentManager()
    assert manager.client_type == "None"

    manager.client = MockClient("h", 1, None, None)
    assert manager.client_type == "MockClient"


def test_manager_multi_client_loading(app: Flask, caplog: LogCaptureFixture) -> None:
    """Test loading multiple clients via comma-separated DL_CLIENT."""
    manager = TorrentManager()

    mock_module = MagicMock()
    mock_module.MockClient = MockClient

    with patch("importlib.import_module", return_value=mock_module):
        app.config["DL_CLIENT"] = "client_a"
        app.config["DL_CLIENT"] = "client_a,client_b"

        manager.init_app(app)

        assert len(manager.clients) == 2
        assert "client_a" in manager.clients
        assert "client_b" in manager.clients
        assert manager.list_clients() == ["client_a", "client_b"]
        assert manager.get_client("client_a") is not None
        assert manager.get_client("client_b") is not None
        assert manager.get_client("nonexistent") is None


def test_manager_multi_client_add_and_status(app: Flask) -> None:
    """Test adding magnet and querying status across multiple clients."""
    manager = TorrentManager()
    app.config["DL_CATEGORY"] = "abb-automated"
    manager._app = app  # pyright: ignore[reportPrivateUsage]

    client_a = MagicMock()
    client_b = MagicMock()
    client_a.get_status.return_value = [
        TorrentStatus(id="1", name="Book A", progress=50.0, state="downloading", size="500MB")
    ]
    client_b.get_status.return_value = [
        TorrentStatus(id="2", name="Book B", progress=100.0, state="seeding", size="1GB")
    ]
    client_a.verify_credentials.return_value = True
    client_b.verify_credentials.return_value = False

    manager.clients = {"client_a": client_a, "client_b": client_b}
    manager.client = client_a

    # Verify credentials targeted
    assert manager.verify_credentials("client_a") is True
    assert manager.verify_credentials("client_b") is False

    # Targeted add_magnet
    manager.add_magnet("magnet:?xt=test", "/save/path", client_name="client_b")
    client_b.add_magnet.assert_called_with("magnet:?xt=test", "/save/path", "abb-automated")
    client_a.add_magnet.assert_not_called()

    # Aggregated status (no filter)
    all_statuses = manager.get_status()
    assert len(all_statuses) == 2
    assert all_statuses[0].client == "client_a"
    assert all_statuses[1].client == "client_b"

    # Filtered status
    status_a = manager.get_status(client_name="client_a")
    assert len(status_a) == 1
    assert status_a[0].name == "Book A"

    # Multi-client removal across clients
    client_b.remove_torrent.side_effect = Exception("Not here")
    client_a.remove_torrent.return_value = True
    assert manager.remove_torrent("1") is True

    # Multi-client teardown and close
    manager.close()
    client_a.close.assert_called_once()
    client_b.close.assert_called_once()
    manager.teardown_request()
    client_a.teardown.assert_called_once()
    client_b.teardown.assert_called_once()


def test_manager_multi_client_aggregation_error(app: Flask) -> None:
    """Test get_status logs warning when one client errors during aggregation."""
    manager = TorrentManager()
    manager._app = app  # pyright: ignore[reportPrivateUsage]

    good_client = MagicMock()
    good_client.get_status.return_value = [
        TorrentStatus(id="1", name="Good Book", progress=10.0, state="downloading", size="10MB")
    ]
    bad_client = MagicMock()
    bad_client.get_status.side_effect = RuntimeError("Client unreachable")

    manager.clients = {"good": good_client, "bad": bad_client}
    manager.client = good_client

    statuses = manager.get_status()
    assert len(statuses) == 1
    assert statuses[0].name == "Good Book"
    assert statuses[0].client == "good"


def test_manager_primary_fallback(app: Flask) -> None:
    """Test manager selects first available client if DL_CLIENT not in clients."""
    manager = TorrentManager()

    mock_module = MagicMock()
    mock_module.MockClient = MockClient

    def mock_import(name: str) -> Any:
        if "client_a" in name:
            return mock_module
        raise ImportError(f"No module {name}")

    with patch("importlib.import_module", side_effect=mock_import):
        app.config["DL_CLIENT"] = "unsupported_client"
        app.config["DL_CLIENT"] = "unsupported_client,client_a"

        manager.init_app(app)
        assert manager.client is not None
        assert "client_a" in manager.clients
        assert manager.client == manager.clients["client_a"]


def test_manager_status_single_client_tagging(app: Flask) -> None:
    """Test get_status populates client attribute when only one client configured."""
    manager = TorrentManager()
    manager._app = app  # pyright: ignore[reportPrivateUsage]
    client_instance = MagicMock()
    client_instance.get_status.return_value = [
        TorrentStatus(id="1", name="Single Book", progress=100.0, state="seeding", size="1GB")
    ]
    manager.client = client_instance
    manager.clients = {"qbittorrent": client_instance}

    statuses = manager.get_status()
    assert len(statuses) == 1
    assert statuses[0].client is not None


def test_manager_remove_torrent_fallback_loop(app: Flask) -> None:
    """Test remove_torrent iterates across clients when client_name is None and client has no target."""
    manager = TorrentManager()
    client_a = MagicMock()
    client_b = MagicMock()
    client_a.remove_torrent.side_effect = RuntimeError("Not found")
    client_b.remove_torrent.return_value = True

    manager.clients = {"a": client_a, "b": client_b}
    manager.client = None

    assert manager.remove_torrent("hash123") is True
    client_a.remove_torrent.assert_called_once_with("hash123")
    client_b.remove_torrent.assert_called_once_with("hash123")

    client_b.remove_torrent.side_effect = RuntimeError("Failed too")
    assert manager.remove_torrent("hash456") is False


def test_manager_connects_transport_in_each_request_thread() -> None:
    """A startup connection must not mask missing handles on fresh request threads."""
    connected: list[int] = []

    class RequestClient(MockClient):
        """Require a request-local handle just like the real SDK plugins."""

        def connect(self) -> None:
            """Open the current thread's handle."""
            connected.append(get_ident())
            self.client = object()

        def get_status(self, category: str) -> list[TorrentStatus]:
            """Reject operations that did not establish a handle."""
            assert self.client is not None
            return []

        def close(self) -> None:
            """Release only this thread's connection."""
            self.client = None

    plugin = RequestClient("localhost", 8080, None, None)
    manager = TorrentManager()
    manager.clients = {"test": plugin}
    manager.client = plugin
    barrier = Barrier(2, timeout=5)

    def request_thread(_: int) -> int:
        """Perform repeated reads and request cleanup without any shared handle."""
        assert plugin.client is None
        assert manager.get_status() == []
        handle = plugin.client
        assert manager.get_status("test") == []
        assert plugin.client is handle
        barrier.wait()
        identity = id(handle)
        manager.teardown_request()
        assert plugin.client is None
        return identity

    with ThreadPoolExecutor(max_workers=2) as pool:
        identities = list(pool.map(request_thread, [0, 1]))
    assert len(set(identities)) == 2
    assert len(connected) == 2
    assert plugin.client is None


def test_manager_registers_request_cleanup() -> None:
    """The real Flask lifecycle must call connection cleanup after an app context ends."""
    isolated = Flask("client-cleanup")
    manager = TorrentManager()
    plugin = MagicMock()
    manager.clients = {"test": plugin}
    with patch.object(manager, "_load_clients"):
        manager.init_app(isolated)
    with isolated.app_context():
        pass
    plugin.teardown.assert_called_once()


def test_manager_passes_deluge_url(app: Flask) -> None:
    """A documented reverse-proxy URL must reach the Deluge adapter."""
    from audiobook_automated.clients.deluge import DelugeClient

    app.config.update(DL_CLIENT="deluge", CLIENT_CONNECTIONS={"deluge": {"URL": "https://downloads.example/deluge/"}})
    manager = TorrentManager()
    manager.init_app(app)
    assert isinstance(manager.client, DelugeClient)
    assert manager.client.dl_url == "https://downloads.example/deluge/"


def test_manager_isolates_per_client_connections(app: Flask) -> None:
    """Instantiate all real adapters with independent credentials and default ports."""
    app.config.update(
        DL_CLIENT="qbittorrent,deluge,transmission",
        CLIENT_CONNECTIONS={
            "qbittorrent": {"HOST": "qbit-host", "API_KEY": "qbit-key", "PASSWORD": ""},
            "deluge": {"HOST": "deluge-host", "PASSWORD": "deluge-only", "URL": "https://deluge.example/"},
            "transmission": {"HOST": "tx-host", "USERNAME": "tx-user", "PASSWORD": "tx-only", "TIMEOUT": "7"},
        },
    )
    manager = TorrentManager()
    manager.init_app(app)
    qbit = manager.get_client("qbittorrent")
    deluge = manager.get_client("deluge")
    tx = manager.get_client("transmission")
    assert qbit is not None and deluge is not None and tx is not None
    assert (qbit.host, qbit.port, qbit.password) == ("qbit-host", 8080, "")
    assert (deluge.host, deluge.port, deluge.password) == ("deluge-host", 8112, "deluge-only")
    assert (tx.host, tx.port, tx.username, tx.password, tx.timeout) == ("tx-host", 9091, "tx-user", "tx-only", 7)
    assert manager.get_client("missing") is None
    with raises(ConnectionError):
        manager.get_status("missing")
    with raises(ConnectionError):
        manager.add_magnet("magnet:?", "/downloads", client_name="missing")
    assert manager.remove_torrent("absent", client_name="missing") is False
