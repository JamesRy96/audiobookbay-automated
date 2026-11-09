# File: tests/security/test_core.py
"""Tests for core security features like CSRF, SSRF, and input sanitization."""

from typing import Any

import pytest

from audiobook_automated.constants import FALLBACK_TITLE
from audiobook_automated.scraper import get_book_details
from audiobook_automated.utils import sanitize_title


def test_csrf_protection_enabled(app: Any) -> None:
    """Verify that POST requests are rejected without a CSRF token.

    Checks when protection is actually enabled.
    """
    # Temporarily enable CSRF for this specific test
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()

    # Attempt a POST request without the token (simulating an attack)
    response = client.post("/send", json={"link": "http://test.com", "title": "Test Book"})

    # Should fail with 400 Bad Request (CSRF Error)
    assert response.status_code == 400
    assert b"The CSRF token is missing" in response.data or response.status_code == 400


def test_ssrf_protection_on_details_scrape() -> None:
    """Test that get_book_details rejects non-ABB domains.

    This prevents Server-Side Request Forgery (SSRF) attacks.
    """
    with pytest.raises(ValueError) as exc:
        get_book_details("https://google.com/admin")
    assert "Invalid domain" in str(exc.value)


def test_sanitize_simple_title() -> None:
    """Test basic title sanitization."""
    assert sanitize_title("Harry Potter") == "Harry Potter"


def test_sanitize_special_chars() -> None:
    """Test removal of filesystem-unsafe characters."""
    # Colons and slashes should be removed
    assert sanitize_title("Book: The Movie / Part 1") == "Book The Movie  Part 1"


def test_sanitize_windows_reserved() -> None:
    """Test handling of Windows reserved filenames."""
    assert sanitize_title("CON") == "CON_Safe"
    assert sanitize_title("nul") == "nul_Safe"
    assert sanitize_title("LPT1") == "LPT1_Safe"
    # Partial match should remain untouched
    assert sanitize_title("CONFERENCE") == "CONFERENCE"


def test_sanitize_strips_to_empty() -> None:
    """Test that a title composed only of illegal chars falls back safely."""
    # Ensure we test against the Single Source of Truth
    assert sanitize_title("...") == FALLBACK_TITLE
    assert sanitize_title("???") == FALLBACK_TITLE


def make_transport_app(public_url: str | None = None, trusted_proxies: str = "") -> Any:
    """Build real request security with isolated Download Client boundaries from conftest."""
    from flask import jsonify, request, session, url_for
    from flask_wtf.csrf import generate_csrf

    from audiobook_automated import create_app
    from audiobook_automated.config import Config
    from audiobook_automated.web_security import parse_trusted_proxies

    class TransportConfig(Config):
        TESTING = True
        FLASK_DEBUG = False
        DL_CLIENT = "qbittorrent"
        SECRET_KEY = "isolated-transport-test"
        PUBLIC_URL = public_url
        TRUSTED_PROXIES = parse_trusted_proxies(trusted_proxies)
        WTF_CSRF_ENABLED = True
        RATELIMIT_ENABLED = False

    app = create_app(TransportConfig)

    @app.route("/_transport", methods=["GET", "POST"])
    def transport_review() -> Any:
        session["visited"] = True
        return jsonify(
            scheme=request.scheme,
            host=request.host,
            client=request.remote_addr,
            prefix=request.script_root,
            link=url_for("transport_review", _external=True),
            csrf=generate_csrf(),
        )

    return app


@pytest.mark.parametrize("scheme,secure", [("http", False), ("https", True)])
def test_direct_transport_controls_cookie_without_shared_state(scheme: str, secure: bool) -> None:
    """Alternating direct transports chooses cookie flags per request without changing app settings."""
    app = make_transport_app()
    with app.test_client() as client:
        response = client.get("/_transport", base_url=scheme + "://books.example")
        assert response.status_code == 200
        assert ("; Secure" in response.headers["Set-Cookie"]) is secure
        assert app.config["SESSION_COOKIE_SECURE"] is False
        other = client.get("/_transport", base_url=("http" if secure else "https") + "://books.example")
        assert ("; Secure" in other.headers["Set-Cookie"]) is not secure


def test_forwarded_headers_from_untrusted_senders_are_ignored() -> None:
    """An arbitrary sender cannot forge its identity, origin or routing prefix."""
    app = make_transport_app(trusted_proxies="10.0.0.5")
    response = app.test_client().get(
        "/_transport",
        base_url="http://books.example",
        environ_base={"REMOTE_ADDR": "198.51.100.23"},
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "forged.example",
            "X-Forwarded-For": "203.0.113.7",
            "X-Forwarded-Prefix": "/forged",
            "X-Forwarded-Port": "443",
            "Forwarded": "proto=https;host=forged.example",
        },
    )
    assert response.json["scheme"] == "http"
    assert response.json["host"] == "books.example"
    assert response.json["client"] == "198.51.100.23"
    assert response.json["prefix"] == ""
    assert "; Secure" not in response.headers["Set-Cookie"]


@pytest.mark.parametrize("peer", ["10.0.0.5", "::ffff:10.0.0.5"])
def test_only_allowlisted_proxy_can_supply_forwarded_values(peer: str) -> None:
    """Trust one explicit proxy hop, including IPv4 peers on an IPv6 listener."""
    app = make_transport_app(trusted_proxies="10.0.0.0/24")
    response = app.test_client().get(
        "/_transport",
        environ_base={"REMOTE_ADDR": peer},
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "books.example",
            "X-Forwarded-Port": "443",
            "X-Forwarded-For": "198.51.100.9, 203.0.113.7",
            "X-Forwarded-Prefix": "/books",
        },
    )
    assert response.json["scheme"] == "https"
    assert response.json["client"] == "203.0.113.7"
    assert response.json["prefix"] == "/books"
    assert "; Secure" in response.headers["Set-Cookie"]


@pytest.mark.parametrize("peer", ["", "not-an-ip", "2001:db8::1"])
def test_invalid_or_unlisted_peer_never_becomes_trusted(peer: str) -> None:
    """Malformed addresses and other networks cannot opt into proxy handling."""
    app = make_transport_app(trusted_proxies="10.0.0.5")
    response = app.test_client().get(
        "/_transport", environ_base={"REMOTE_ADDR": peer}, headers={"X-Forwarded-Proto": "https"}
    )
    assert response.json["scheme"] == "http"


@pytest.mark.parametrize("trusted", ["", "10.0.0.5"])
def test_public_origin_handles_tls_termination_without_redirect_loops(trusted: str) -> None:
    """One declared origin supplies secure cookies and URLs despite an HTTP backend connection."""
    app = make_transport_app("https://books.example:8443", trusted)
    response = app.test_client().get(
        "/_transport",
        base_url="http://books.example:8443",
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
        headers={"X-Forwarded-Proto": "http", "X-Forwarded-Host": "books.example:8443"},
    )
    assert response.status_code == 200
    assert response.json["scheme"] == "https"
    assert response.json["host"] == "books.example:8443"
    assert response.json["link"] == "https://books.example:8443/_transport"
    assert "; Secure" in response.headers["Set-Cookie"]
    assert "Strict-Transport-Security" not in response.headers
    assert app.test_client().get("/health", base_url="http://127.0.0.1:5078").status_code == 200


def test_public_https_csrf_requires_the_declared_browser_origin() -> None:
    """Valid HTTPS browser actions work; cross-site and missing referrers are rejected."""
    app = make_transport_app("https://books.example")
    with app.test_client() as client:
        token = client.get(
            "/_transport", base_url="https://books.example", environ_overrides={"wsgi.url_scheme": "http"}
        ).json["csrf"]
        for referrer, expected in [("https://books.example/", 200), ("https://attacker.example/", 400), (None, 400)]:
            headers = {"X-CSRFToken": token}
            if referrer:
                headers["Referer"] = referrer
            response = client.post(
                "/_transport",
                base_url="https://books.example",
                environ_overrides={"wsgi.url_scheme": "http"},
                headers=headers,
            )
            assert response.status_code == expected


@pytest.mark.parametrize("local_origin", ["http://10.25.25.246:5078", "http://localhost:5078", "http://[::1]:5078"])
def test_public_url_preserves_independent_local_http_session(local_origin: str) -> None:
    """Local browsers retain their actual HTTP origin, usable cookies and valid action tokens."""
    app = make_transport_app("https://books.example")
    with app.test_client() as client:
        response = client.get("/_transport", base_url=local_origin)
        assert response.status_code == 200
        assert response.json["scheme"] == "http"
        assert response.json["link"] == local_origin + "/_transport"
        assert "; Secure" not in response.headers["Set-Cookie"]
        token = response.json["csrf"]
        valid = client.post(
            "/_transport", base_url=local_origin, headers={"X-CSRFToken": token, "Referer": local_origin + "/"}
        )
        assert valid.status_code == 200
        invalid = client.post("/_transport", base_url=local_origin)
        assert invalid.status_code == 400


@pytest.mark.parametrize("host", ["books.example", "BOOKS.EXAMPLE", "books.example:443"])
def test_public_domain_selects_https_even_over_http_backend(host: str) -> None:
    """Domain recognition includes case and explicit default ports without trusting forwarded headers."""
    app = make_transport_app("https://books.example")
    response = app.test_client().get("/_transport", base_url="http://" + host)
    assert response.json["scheme"] == "https"
    assert response.json["host"] == "books.example"
    assert "; Secure" in response.headers["Set-Cookie"]


def test_local_and_public_sessions_cannot_exchange_action_tokens() -> None:
    """Independent HTTP and HTTPS sessions remain separate and reject the other session's tokens."""
    app = make_transport_app("https://books.example")
    local_origin = "http://10.25.25.246:5078"
    with app.test_client() as client:
        local_token = client.get("/_transport", base_url=local_origin).json["csrf"]
        public_token = client.get("/_transport", base_url="http://books.example").json["csrf"]
        for origin, token, expected in [
            (local_origin, local_token, 200),
            (local_origin, public_token, 400),
            ("https://books.example", public_token, 200),
            ("https://books.example", local_token, 400),
        ]:
            response = client.post(
                "/_transport",
                base_url=origin,
                environ_overrides={"wsgi.url_scheme": "http"},
                headers={"X-CSRFToken": token, "Referer": origin + "/"},
            )
            assert response.status_code == expected


def test_untrusted_forwarding_cannot_change_local_session_with_public_url() -> None:
    """Declaring a public domain does not let arbitrary forwarding headers mark LAN HTTP as HTTPS."""
    app = make_transport_app("https://books.example")
    response = app.test_client().get(
        "/_transport",
        base_url="http://10.25.25.246:5078",
        headers={"X-Forwarded-Host": "books.example", "X-Forwarded-Proto": "https"},
    )
    assert response.json["scheme"] == "http"
    assert response.json["host"] == "10.25.25.246:5078"
    assert "; Secure" not in response.headers["Set-Cookie"]
