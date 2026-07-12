from unittest.mock import Mock

import pytest
import requests


def response(text="", status_code=200, json_data=None):
    result = Mock()
    result.text = text
    result.status_code = status_code
    result.json.return_value = json_data
    return result


def test_inject_nav_link_reads_environment(monkeypatch, app_module):
    monkeypatch.setenv("NAV_LINK_NAME", "Player")
    monkeypatch.setenv("NAV_LINK_URL", "https://player.example")

    assert app_module.inject_nav_link() == {
        "nav_link_name": "Player",
        "nav_link_url": "https://player.example",
    }


def test_is_url_valid_handles_success_and_request_errors(monkeypatch, app_module):
    monkeypatch.setattr(
        app_module.requests, "head", lambda *args, **kwargs: response(status_code=200)
    )
    assert app_module.is_url_valid("https://cover.example") is True

    monkeypatch.setattr(
        app_module.requests,
        "head",
        Mock(side_effect=requests.exceptions.RequestException("offline")),
    )
    assert app_module.is_url_valid("https://cover.example") is False


def test_qbittorrent_api_request_requires_api_key(monkeypatch, app_module):
    monkeypatch.setattr(app_module, "DL_API_KEY", None)

    with pytest.raises(RuntimeError, match="DL_API_KEY"):
        app_module.qbittorrent_api_request("GET", "torrents/info")


def test_qbittorrent_api_request_uses_bearer_key(monkeypatch, app_module):
    request_mock = Mock(return_value=response("Ok."))
    monkeypatch.setattr(app_module, "DL_API_KEY", "qbt_test")
    monkeypatch.setattr(app_module, "DL_URL", "https://qbit.example/")
    monkeypatch.setattr(app_module.requests, "request", request_mock)

    assert (
        app_module.qbittorrent_api_request(
            "GET", "/torrents/info", params={"category": "books"}
        ).text
        == "Ok."
    )
    request_mock.assert_called_once_with(
        "GET",
        "https://qbit.example/api/v2/torrents/info",
        headers={"Authorization": "Bearer qbt_test"},
        timeout=30,
        params={"category": "books"},
    )


def test_qbittorrent_api_request_rejects_failed_response(monkeypatch, app_module):
    monkeypatch.setattr(app_module, "DL_API_KEY", "qbt_test")
    monkeypatch.setattr(app_module, "DL_URL", "http://qbit.example")
    monkeypatch.setattr(
        app_module.requests, "request", Mock(return_value=response("Fails."))
    )

    with pytest.raises(RuntimeError, match="rejected"):
        app_module.qbittorrent_api_request("POST", "torrents/add")


def test_qbittorrent_add_torrent_uses_api_key(monkeypatch, app_module):
    request_mock = Mock()
    monkeypatch.setattr(app_module, "DL_API_KEY", "qbt_test")
    monkeypatch.setattr(app_module, "DL_CATEGORY", "audiobooks")
    monkeypatch.setattr(app_module, "qbittorrent_api_request", request_mock)

    app_module.qbittorrent_add_torrent("magnet:?xt=abc", "/downloads/book")

    request_mock.assert_called_once_with(
        "POST",
        "torrents/add",
        data={
            "urls": "magnet:?xt=abc",
            "savepath": "/downloads/book",
            "category": "audiobooks",
        },
    )


def test_qbittorrent_add_torrent_uses_password_login(monkeypatch, app_module):
    qb = Mock()
    client_factory = Mock(return_value=qb)
    monkeypatch.setattr(app_module, "DL_API_KEY", None)
    monkeypatch.setattr(app_module, "DL_HOST", "qbit.example")
    monkeypatch.setattr(app_module, "DL_PORT", "8080")
    monkeypatch.setattr(app_module, "DL_USERNAME", "user")
    monkeypatch.setattr(app_module, "DL_PASSWORD", "test-password")
    monkeypatch.setattr(app_module, "DL_CATEGORY", "audiobooks")
    monkeypatch.setattr(app_module, "Client", client_factory)

    app_module.qbittorrent_add_torrent("magnet:?xt=abc", "/downloads/book")

    client_factory.assert_called_once_with(
        host="qbit.example",
        port="8080",
        username="user",
        password="test-password",  # pragma: allowlist secret
    )
    qb.auth_log_in.assert_called_once_with()
    qb.torrents_add.assert_called_once_with(
        urls="magnet:?xt=abc", save_path="/downloads/book", category="audiobooks"
    )


def test_qbittorrent_torrents_supports_both_authentication_modes(
    monkeypatch, app_module
):
    api_response = response(json_data=[{"name": "API book"}])
    monkeypatch.setattr(app_module, "DL_API_KEY", "qbt_test")
    monkeypatch.setattr(app_module, "DL_CATEGORY", "audiobooks")
    monkeypatch.setattr(
        app_module, "qbittorrent_api_request", Mock(return_value=api_response)
    )
    assert app_module.qbittorrent_torrents() == [{"name": "API book"}]

    qb = Mock()
    qb.torrents_info.return_value = ["password book"]
    monkeypatch.setattr(app_module, "DL_API_KEY", None)
    monkeypatch.setattr(app_module, "Client", Mock(return_value=qb))
    assert app_module.qbittorrent_torrents() == ["password book"]
    qb.auth_log_in.assert_called_once_with()
    qb.torrents_info.assert_called_once_with(category="audiobooks")


def test_search_audiobookbay_parses_book_and_default_cover(monkeypatch, app_module):
    page = """
    <article class="post">
      <div class="postTitle"><h2><a href="/book">A Book</a></h2></div>
      <img src="https://cover.example/book.jpg">
      <div class="postInfo">Language: English Keywords: mystery</div>
      <div class="postContent"><p style="text-align:center">Posted: Today<br>Format: <span>MP3</span><br>Bitrate: <span>128 kbps</span><br>File Size: <span>123</span> MB</p></div>
    </article>
    <article class="post"><div class="postTitle"><h2><a href="/second">Second</a></h2></div></article>
    """
    monkeypatch.setattr(app_module.requests, "get", Mock(return_value=response(page)))
    monkeypatch.setattr(app_module, "is_url_valid", lambda url: True)
    monkeypatch.setattr(app_module, "ABB_HOSTNAME", "abb.example")

    books = app_module.search_audiobookbay("A Book", max_pages=1)

    assert books[0] == {
        "title": "A Book",
        "link": "https://abb.example/book",
        "cover": "https://cover.example/book.jpg",
        "language": "English",
        "post_date": "Today",
        "format": "MP3",
        "bitrate": "128 kbps",
        "file_size": "123 MB",
    }
    assert books[1]["cover"] == "/static/images/default_cover.jpg"
    assert books[1]["language"] == "N/A"


def test_search_audiobookbay_stops_for_empty_page_or_request_error(
    monkeypatch, app_module
):
    monkeypatch.setattr(
        app_module.requests, "get", Mock(return_value=response("<html></html>"))
    )
    assert app_module.search_audiobookbay("book", max_pages=2) == []

    monkeypatch.setattr(
        app_module.requests,
        "get",
        Mock(side_effect=requests.exceptions.RequestException("offline")),
    )
    assert app_module.search_audiobookbay("book", max_pages=1) == []


def test_extract_magnet_link_uses_page_trackers(monkeypatch, app_module):
    page = """
    <table><tr><td>Info Hash</td><td>abc123</td></tr>
    <tr><td>udp://tracker.example:80</td></tr><tr><td>http://tracker.example/announce</td></tr></table>
    """
    monkeypatch.setattr(app_module.requests, "get", Mock(return_value=response(page)))

    magnet = app_module.extract_magnet_link("https://abb.example/book")

    assert magnet.startswith("magnet:?xt=urn:btih:abc123&")
    assert "tr=udp%3A//tracker.example%3A80" in magnet
    assert "tr=http%3A//tracker.example/announce" in magnet


def test_extract_magnet_link_handles_missing_data_and_errors(monkeypatch, app_module):
    monkeypatch.setattr(
        app_module.requests, "get", Mock(return_value=response("", status_code=404))
    )
    assert app_module.extract_magnet_link("https://abb.example/book") is None

    monkeypatch.setattr(
        app_module.requests, "get", Mock(return_value=response("<td>Nothing</td>"))
    )
    assert app_module.extract_magnet_link("https://abb.example/book") is None

    monkeypatch.setattr(
        app_module.requests,
        "get",
        Mock(side_effect=requests.RequestException("offline")),
    )
    assert app_module.extract_magnet_link("https://abb.example/book") is None


def test_extract_magnet_link_uses_default_trackers(monkeypatch, app_module):
    monkeypatch.setattr(
        app_module.requests,
        "get",
        Mock(
            return_value=response(
                "<table><tr><td>Info Hash</td><td>abc123</td></tr></table>"
            )
        ),
    )

    magnet = app_module.extract_magnet_link("https://abb.example/book")

    assert "tracker.openbittorrent.com" in magnet


@pytest.mark.parametrize(
    ("title", "expected"),
    [(" A / Book: One? ", "A  Book One"), ("Plain title", "Plain title")],
)
def test_sanitize_title(title, expected, app_module):
    assert app_module.sanitize_title(title) == expected
