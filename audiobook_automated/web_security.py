# File: audiobook_automated/web_security.py
"""Public-origin handling and explicit reverse-proxy trust for the web appliance."""

from collections.abc import Iterable
from ipaddress import IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network
from typing import override
from urllib.parse import urlsplit
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from flask import Flask, request
from flask.sessions import SecureCookieSessionInterface
from werkzeug.middleware.proxy_fix import ProxyFix

DEFAULT_PORTS = {"http": 80, "https": 443}


def parse_public_url(value: str | None) -> str | None:
    """Accept one HTTP(S) origin without credentials, subpaths, query strings or fragments."""
    if not value or not value.strip():
        return None
    value = value.strip(" \"'")
    try:
        origin = urlsplit(value)
        host = origin.hostname
        port = origin.port
        if (
            origin.scheme not in ("http", "https")
            or not host
            or origin.username is not None
            or origin.password is not None
            or origin.path not in ("", "/")
            or "?" in value
            or "#" in value
            or any(char.isspace() or not char.isprintable() for char in value)
            or port == 0
        ):
            raise ValueError
        host = host.encode("idna").decode("ascii").lower()
        if any(char in host for char in ("\\", "%")) or (
            ":" not in host and not all(char.isalnum() or char in ".-_" for char in host)
        ):
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError(
            "PUBLIC_URL must be an http:// or https:// site address without a login, path, query or fragment."
        ) from None
    if ":" in host:
        host = f"[{host}]"
    default_port = DEFAULT_PORTS[origin.scheme]
    authority = host if port in (None, default_port) else f"{host}:{port}"
    return f"{origin.scheme}://{authority}"


def parse_trusted_proxies(value: str | None) -> tuple[IPv4Network | IPv6Network, ...]:
    """Trust only explicitly listed proxy addresses or networks, never all private networks."""
    try:
        return tuple(ip_network(item.strip(), strict=False) for item in (value or "").split(",") if item.strip())
    except ValueError:
        raise ValueError("TRUSTED_PROXIES must contain proxy IP addresses or networks separated by commas.") from None


class TransportSessionInterface(SecureCookieSessionInterface):
    """Choose Secure cookies for this request without mutating shared app configuration."""

    @override
    def get_cookie_secure(self, app: Flask) -> bool:  # noqa: ARG002
        """Use the verified transport or explicitly configured public HTTPS origin."""
        return request.is_secure


class PublicOriginMiddleware:
    """Apply allowlisted proxy headers and recognize the configured public host."""

    def __init__(
        self, app: WSGIApplication, public_url: str | None, trusted_proxies: tuple[IPv4Network | IPv6Network, ...]
    ) -> None:
        """Capture immutable deployment configuration once for all request threads."""
        self.app = app
        self.origin = urlsplit(public_url) if public_url else None
        self.public_hosts = set()
        if self.origin:
            self.public_hosts.add(self.origin.netloc)
            if self.origin.port is None:
                self.public_hosts.add(f"{self.origin.netloc}:{DEFAULT_PORTS[self.origin.scheme]}")
        self.trusted_proxies = trusted_proxies
        self.proxy_app = ProxyFix(self._serve, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    def _trusted(self, peer: str) -> bool:
        """Check the actual socket peer before forwarded values can replace it."""
        try:
            address = ip_address(peer)
        except ValueError:
            return False
        if isinstance(address, IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return any(address in network for network in self.trusted_proxies)

    def __call__(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        """Ignore untrusted forwarding headers rather than detecting a proxy from their presence."""
        if self.trusted_proxies and self._trusted(environ.get("REMOTE_ADDR", "")):
            return self.proxy_app(environ, start_response)
        for header in (
            "FORWARDED",
            "X_FORWARDED_FOR",
            "X_FORWARDED_PROTO",
            "X_FORWARDED_SCHEME",
            "X_FORWARDED_HOST",
            "X_FORWARDED_PORT",
            "X_FORWARDED_PREFIX",
            "X_REAL_IP",
        ):
            environ.pop("HTTP_" + header, None)
        return self._serve(environ, start_response)

    def _serve(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        """Recognize public HTTPS without changing independent LAN HTTP requests."""
        if self.origin and environ.get("HTTP_HOST", "").lower() in self.public_hosts:
            environ["wsgi.url_scheme"] = self.origin.scheme
            environ["HTTP_HOST"] = self.origin.netloc
            environ["SERVER_NAME"] = self.origin.hostname or ""
            environ["SERVER_PORT"] = str(self.origin.port or DEFAULT_PORTS[self.origin.scheme])
        return self.app(environ, start_response)
