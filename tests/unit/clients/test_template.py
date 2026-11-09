# File: tests/unit/clients/test_template.py
"""Unit tests for the client template module."""

import pytest

from audiobook_automated.clients.base import TorrentClientPlugin
from audiobook_automated.clients.client_template import CustomClient


def test_template_structure() -> None:
    """Ensure the template plugin follows the required interface."""
    assert issubclass(CustomClient, TorrentClientPlugin)
    assert hasattr(CustomClient, "DEFAULT_PORT")
    assert CustomClient.DEFAULT_PORT == 0000


def test_template_initialization() -> None:
    """Ensure the template can be initialized."""
    client = CustomClient(host="localhost", port=8080, username="user", password="pass")
    assert client.host == "localhost"
    assert client.port == 8080
    assert client.client is None


def test_template_raises_not_implemented() -> None:
    """Ensure all abstract methods raise NotImplementedError in the template."""
    client = CustomClient(host="localhost", port=8080, username="user", password="pass")

    # Mimic a connection for methods that check self.client
    client.client = True

    with pytest.raises(NotImplementedError):
        client.connect()

    with pytest.raises(NotImplementedError):
        client.add_magnet("magnet:?", "/tmp", "audiobooks")

    with pytest.raises(NotImplementedError):
        client.remove_torrent("12345")


def test_template_get_status_returns_empty() -> None:
    """Ensure get_status returns empty list by default (or raises if not implemented)."""
    client = CustomClient(host="localhost", port=8080, username="user", password="pass")
    client.client = True

    # The template implementation in the provided file actually returns []
    assert client.get_status("cat") == []


def test_template_methods_raise_connection_error_when_disconnected() -> None:
    """Ensure methods raise ConnectionError if client is None."""
    client = CustomClient(host="localhost", port=8080, username="user", password="pass")
    client.client = None

    with pytest.raises(ConnectionError, match="Client not connected"):
        client.add_magnet("magnet:?", "/tmp", "cat")

    with pytest.raises(ConnectionError, match="Client not connected"):
        client.remove_torrent("123")

    with pytest.raises(ConnectionError, match="Client not connected"):
        client.get_status("cat")


def test_template_close_is_safe() -> None:
    """Ensure close() does not crash even if client is None."""
    client = CustomClient(host="localhost", port=8080, username="user", password="pass")
    client.close()  # Should not raise
