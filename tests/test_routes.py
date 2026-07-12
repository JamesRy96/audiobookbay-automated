from types import SimpleNamespace
from unittest.mock import Mock

import requests


def test_search_route_renders_and_processes_queries(monkeypatch, client, app_module):
    monkeypatch.setattr(
        app_module, "search_audiobookbay", Mock(return_value=[{"title": "Book"}])
    )

    search_page = client.get("/")
    assert search_page.status_code == 200
    assert b'<form method="post" action="/"' in search_page.data
    response = client.post("/", data={"query": "Book"})
    assert response.status_code == 200
    app_module.search_audiobookbay.assert_called_once_with("Book")


def test_search_route_handles_search_error(monkeypatch, client, app_module):
    monkeypatch.setattr(
        app_module, "search_audiobookbay", Mock(side_effect=RuntimeError("offline"))
    )

    response = client.post("/", data={"query": "Book"})

    assert response.status_code == 200
    assert b"Failed to search. offline" in response.data


def test_details_returns_parsed_book_details(monkeypatch, client, app_module):
    details = {"title": "Meditations", "source_url": "https://abb.example/book"}
    monkeypatch.setattr(app_module, "ABB_HOSTNAME", "abb.example")
    monkeypatch.setattr(app_module, "extract_book_details", Mock(return_value=details))

    response = client.post("/details", json={"link": "https://abb.example/book"})

    assert response.status_code == 200
    assert response.get_json() == details
    app_module.extract_book_details.assert_called_once_with("https://abb.example/book")


def test_details_rejects_other_hosts_and_reports_fetch_errors(
    monkeypatch, client, app_module
):
    monkeypatch.setattr(app_module, "ABB_HOSTNAME", "abb.example")
    assert (
        client.post("/details", json={"link": "https://other.example/book"}).status_code
        == 400
    )

    monkeypatch.setattr(
        app_module,
        "extract_book_details",
        Mock(side_effect=requests.exceptions.RequestException("offline")),
    )
    response = client.post("/details", json={"link": "https://abb.example/book"})
    assert response.status_code == 502
    assert response.get_json()["message"] == "Unable to load details from AudiobookBay"


def test_send_rejects_invalid_or_unavailable_magnet(monkeypatch, client, app_module):
    assert client.post("/send", json={}).status_code == 400

    monkeypatch.setattr(app_module, "extract_magnet_link", Mock(return_value=None))
    response = client.post(
        "/send", json={"link": "https://abb.example/book", "title": "Book"}
    )
    assert response.status_code == 500
    assert response.get_json()["message"] == "Failed to extract magnet link"


def test_send_uses_qbittorrent_and_surfaces_errors(monkeypatch, client, app_module):
    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "qbittorrent")
    monkeypatch.setattr(app_module, "SAVE_PATH_BASE", "/audiobooks")
    monkeypatch.setattr(
        app_module, "extract_magnet_link", Mock(return_value="magnet:?xt=abc")
    )
    add_torrent = Mock()
    monkeypatch.setattr(app_module, "qbittorrent_add_torrent", add_torrent)

    response = client.post(
        "/send", json={"link": "https://abb.example/book", "title": "A / Book"}
    )
    assert response.status_code == 200
    add_torrent.assert_called_once_with("magnet:?xt=abc", "/audiobooks/A  Book")

    monkeypatch.setattr(
        app_module, "qbittorrent_add_torrent", Mock(side_effect=RuntimeError("denied"))
    )
    response = client.post(
        "/send", json={"link": "https://abb.example/book", "title": "Book"}
    )
    assert response.status_code == 500
    assert response.get_json()["message"] == "denied"


def test_send_supports_transmission_and_deluge(monkeypatch, client, app_module):
    monkeypatch.setattr(app_module, "SAVE_PATH_BASE", "/audiobooks")
    monkeypatch.setattr(
        app_module, "extract_magnet_link", Mock(return_value="magnet:?xt=abc")
    )

    transmission = Mock()
    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "transmission")
    monkeypatch.setattr(app_module, "transmissionrpc", Mock(return_value=transmission))
    assert (
        client.post(
            "/send", json={"link": "https://abb.example/book", "title": "Book"}
        ).status_code
        == 200
    )
    transmission.add_torrent.assert_called_once()

    deluge = Mock()
    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "delugeweb")
    monkeypatch.setattr(app_module, "delugewebclient", Mock(return_value=deluge))
    monkeypatch.setattr(
        app_module, "delugetorrentoptions", Mock(return_value="options")
    )
    assert (
        client.post(
            "/send", json={"link": "https://abb.example/book", "title": "Book"}
        ).status_code
        == 200
    )
    deluge.login.assert_called_once_with()
    deluge.add_torrent_magnet.assert_called_once_with(
        "magnet:?xt=abc", torrent_options="options"
    )


def test_send_rejects_unsupported_client(monkeypatch, client, app_module):
    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "unsupported")
    monkeypatch.setattr(
        app_module, "extract_magnet_link", Mock(return_value="magnet:?xt=abc")
    )

    response = client.post(
        "/send", json={"link": "https://abb.example/book", "title": "Book"}
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Unsupported download client"


def test_status_supports_qbittorrent(monkeypatch, client, app_module):
    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "qbittorrent")
    monkeypatch.setattr(
        app_module,
        "qbittorrent_torrents",
        Mock(
            return_value=[
                SimpleNamespace(
                    name="Book",
                    progress=0.5,
                    state="downloading",
                    total_size=2 * 1024 * 1024,
                )
            ]
        ),
    )

    response = client.get("/status")

    assert response.status_code == 200
    assert b"Book" in response.data
    assert b"50.0%" in response.data


def test_status_supports_transmission_and_deluge(monkeypatch, client, app_module):
    transmission = Mock()
    transmission.get_torrents.return_value = [
        SimpleNamespace(
            name="Transmission book",
            progress=15.5,
            status="downloading",
            total_size=1024 * 1024,
        )
    ]
    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "transmission")
    monkeypatch.setattr(app_module, "transmissionrpc", Mock(return_value=transmission))
    assert b"Transmission book" in client.get("/status").data

    deluge = Mock()
    deluge.get_torrents_status.return_value = SimpleNamespace(
        result={
            "hash": {
                "name": "Deluge book",
                "progress": 33.3,
                "state": "Downloading",
                "total_size": 1024 * 1024,
            }
        }
    )
    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "delugeweb")
    monkeypatch.setattr(app_module, "delugewebclient", Mock(return_value=deluge))
    assert b"Deluge book" in client.get("/status").data


def test_status_handles_unsupported_clients_and_errors(monkeypatch, client, app_module):
    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "unsupported")
    assert client.get("/status").status_code == 400

    monkeypatch.setattr(app_module, "DOWNLOAD_CLIENT", "qbittorrent")
    monkeypatch.setattr(
        app_module, "qbittorrent_torrents", Mock(side_effect=RuntimeError("offline"))
    )
    response = client.get("/status")
    assert response.status_code == 500
    assert response.get_json()["message"] == "Failed to fetch torrent status: offline"
