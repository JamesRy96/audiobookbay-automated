# File: audiobook_automated/clients/qbittorrent.py
"""Download client plugin for qBittorrent."""

import logging
import time
from typing import Any, Protocol, cast, override

from qbittorrentapi import Client as QbClient
from qbittorrentapi.exceptions import Forbidden403Error, LoginFailed, Unauthorized401Error

from audiobook_automated.utils import format_size

from .base import TorrentClientPlugin, TorrentStatus

logger = logging.getLogger(__name__)


class QbTorrentProtocol(Protocol):
    """Protocol defining the expected structure of a qBittorrent torrent object."""

    hash: str
    name: str
    state: str
    total_size: int | None
    progress: float


class QBittorrentClient(TorrentClientPlugin):
    """Download client plugin for qBittorrent."""

    DEFAULT_PORT = 8080
    AUTH_FAIL_LIMIT = 3
    AUTH_BACKOFF_SECONDS = 300.0  # 5 minutes backoff to prevent IP ban

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the qBittorrent client plugin."""
        super().__init__(*args, **kwargs)
        self.api_key: str | None = kwargs.get("api_key")
        # If password looks like an API key (e.g. qbt_ prefix), allow using it as api_key
        if not self.api_key and self.password and self.password.startswith("qbt_"):
            self.api_key = self.password
        self.client: QbClient | None = None
        self.consecutive_auth_failures: int = 0
        self.auth_cooldown_until: float = 0.0
        self.is_ip_banned: bool = False
        self.last_auth_error: str | None = None

    @override
    def connect(self) -> None:
        """Connect to the qBittorrent client.

        Raises:
            ConnectionError: If authentication fails, host is unreachable, or cooldown is active.
        """
        now = time.time()
        if self.is_ip_banned:
            raise ConnectionError(
                "qBittorrent IP address is banned: too many failed authentication attempts. "
                "Check downloader Web UI settings to unban."
            )

        if now < self.auth_cooldown_until:
            remaining = int(self.auth_cooldown_until - now)
            raise ConnectionError(
                f"qBittorrent authentication cooldown active ({remaining}s remaining) "
                "to protect your IP from being banned. Please verify your username, password, or API key."
            )

        try:
            if self.api_key:
                # Direct API key authentication (qBittorrent v5.2+)
                self.client = QbClient(
                    host=self.host,
                    port=self.port,
                    username=self.username or "",
                    api_key=self.api_key,
                    REQUESTS_ARGS={"timeout": self.timeout},
                )
                # Verify key validity with a lightweight call
                _ = self.client.app.version
            else:
                self.client = QbClient(
                    host=self.host,
                    port=self.port,
                    username=self.username or "",
                    password=self.password or "",
                    REQUESTS_ARGS={"timeout": self.timeout},
                )
                self.client.auth_log_in()

            # Connection succeeded, reset failure metrics
            self.consecutive_auth_failures = 0
            self.auth_cooldown_until = 0.0
            self.is_ip_banned = False
            self.last_auth_error = None

        except Forbidden403Error as e:
            err_str = str(e).lower()
            if "banned" in err_str:
                self.is_ip_banned = True
                self.last_auth_error = "IP Banned (Too many failed login attempts)"
                logger.critical(
                    "qBittorrent IP BANNED: Host %s:%s has blocked requests due to repeated failed logins.",
                    self.host,
                    self.port,
                )
                raise ConnectionError(
                    "qBittorrent rejected connection: IP address banned due to failed attempts."
                ) from e

            # Non-ban 403 (e.g. invalid API key or restricted endpoint)
            self._record_auth_failure("Forbidden / Invalid Credentials")
            raise ConnectionError("qBittorrent authentication failed: Invalid API key or credentials.") from e

        except (LoginFailed, Unauthorized401Error) as e:
            self._record_auth_failure("Invalid username or password")
            raise ConnectionError("qBittorrent authentication failed: Incorrect username or password.") from e

    def _record_auth_failure(self, reason: str) -> None:
        """Track consecutive authentication failures and trigger cooldown before an IP ban occurs."""
        self.consecutive_auth_failures += 1
        self.last_auth_error = reason
        logger.warning(
            "qBittorrent auth failure (%d/%d): %s",
            self.consecutive_auth_failures,
            self.AUTH_FAIL_LIMIT,
            reason,
        )
        if self.consecutive_auth_failures >= self.AUTH_FAIL_LIMIT:
            self.auth_cooldown_until = time.time() + self.AUTH_BACKOFF_SECONDS
            logger.error(
                "qBittorrent auth failure limit reached (%d). Backing off for %ds to prevent IP ban.",
                self.AUTH_FAIL_LIMIT,
                int(self.AUTH_BACKOFF_SECONDS),
            )

    @override
    def close(self) -> None:
        """Close the qBittorrent client session."""
        if self.client:
            try:
                # If session-based, attempt log out
                if not self.api_key:
                    self.client.auth_log_out()
                http_session = getattr(self.client, "_http_session", None)
                if http_session is not None and hasattr(http_session, "close"):
                    http_session.close()
                    self.client._http_session = None  # pyright: ignore[reportPrivateUsage]
            except Exception as e:
                logger.debug(f"Error closing qBittorrent connection: {e}")
            self.client = None

    @override
    def add_magnet(self, magnet_link: str, save_path: str, category: str) -> None:
        """Add a magnet link to qBittorrent.

        Args:
            magnet_link: The magnet link URI.
            save_path: The filesystem path where the torrent should be downloaded.
            category: The category label to apply to the torrent.

        Raises:
            ConnectionError: If the client is not connected or returns a failure response.
        """
        if not self.client:
            raise ConnectionError("qBittorrent client not connected")

        # qBittorrent API v2.14+ returns JSON metadata, older versions return 'Ok.' or 'Fails.'
        result = self.client.torrents_add(urls=magnet_link, save_path=save_path, category=category)

        # Check for legacy string failure response
        if isinstance(result, str) and result.lower() == "fails.":
            raise ConnectionError(f"qBittorrent returned failure response: {result}")

    @override
    def remove_torrent(self, torrent_id: str) -> None:
        """Remove a torrent from qBittorrent.

        Args:
            torrent_id: The hash of the torrent to remove.

        Raises:
            ConnectionError: If the client is not connected.
        """
        if not self.client:
            raise ConnectionError("qBittorrent client not connected")
        self.client.torrents_delete(torrent_hashes=torrent_id, delete_files=False)

    @override
    def get_status(self, category: str) -> list[TorrentStatus]:
        """Get torrent status from qBittorrent.

        Args:
            category: The category label to filter by.

        Returns:
            list[TorrentStatus]: A list of torrent status objects.

        Raises:
            ConnectionError: If the client is not connected.
        """
        if not self.client:
            raise ConnectionError("qBittorrent client not connected")
        results: list[TorrentStatus] = []
        # qBittorrent supports server-side filtering by category
        qb_torrents = cast(list[QbTorrentProtocol], self.client.torrents_info(category=category))
        state_map = {
            "error": "Error",
            "pausedUP": "Paused",
            "pausedDL": "Paused",
            "queuedUP": "Queued",
            "queuedDL": "Queued",
            "uploading": "Seeding",
            "stalledUP": "Seeding",
            "checkingUP": "Checking",
            "checkingDL": "Checking",
            "downloading": "Downloading",
            "stalledDL": "Stalled",
            "metaDL": "Downloading Metadata",
            "forcedMetaDL": "Downloading Metadata",
            "forcedDL": "Downloading",
            "forcedUP": "Seeding",
            "allocating": "Allocating",
            "moving": "Moving",
        }
        for qb_torrent in qb_torrents:
            raw_state = qb_torrent.state or "unknown"
            friendly_state = state_map.get(raw_state, raw_state.capitalize())
            results.append(
                TorrentStatus(
                    id=qb_torrent.hash,
                    name=qb_torrent.name,
                    # qB API returns progress as 0.0-1.0 float, normalize to 0.0-100.0
                    progress=round(qb_torrent.progress * 100, 2) if qb_torrent.progress else 0.0,
                    state=friendly_state,
                    size=format_size(
                        qb_torrent.total_size
                        if qb_torrent.total_size is not None and qb_torrent.total_size >= 0
                        else None
                    ),
                )
            )
        return results
