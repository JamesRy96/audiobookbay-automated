# File: audiobook_automated/clients/base.py
"""Base classes and types for torrent clients."""

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar


class TorrentState(StrEnum):
    """Canonical torrent lifecycle states recognized across all client plugins."""

    DOWNLOADING = "Downloading"
    SEEDING = "Seeding"
    PAUSED = "Paused"
    STALLED = "Stalled"
    QUEUED = "Queued"
    CHECKING = "Checking"
    COMPLETED = "Completed"
    ERROR = "Error"
    UNKNOWN = "Unknown"


_EXACT_STATE_MAP: dict[str, TorrentState] = {
    "downloading": TorrentState.DOWNLOADING,
    "download": TorrentState.DOWNLOADING,
    "dl": TorrentState.DOWNLOADING,
    "forceddl": TorrentState.DOWNLOADING,
    "seeding": TorrentState.SEEDING,
    "seed": TorrentState.SEEDING,
    "up": TorrentState.SEEDING,
    "uploading": TorrentState.SEEDING,
    "stalledup": TorrentState.SEEDING,
    "forcedup": TorrentState.SEEDING,
    "paused": TorrentState.PAUSED,
    "pause": TorrentState.PAUSED,
    "pauseddl": TorrentState.PAUSED,
    "pausedup": TorrentState.PAUSED,
    "stoppeddl": TorrentState.PAUSED,
    "stoppedup": TorrentState.PAUSED,
    "stopped": TorrentState.PAUSED,
    "stop": TorrentState.PAUSED,
    "stalled": TorrentState.STALLED,
    "stalleddl": TorrentState.STALLED,
    "waiting": TorrentState.STALLED,
    "queued": TorrentState.QUEUED,
    "queueddl": TorrentState.QUEUED,
    "queuedup": TorrentState.QUEUED,
    "queue": TorrentState.QUEUED,
    "in_queue": TorrentState.QUEUED,
    "pending": TorrentState.QUEUED,
    "check_pending": TorrentState.QUEUED,
    "checking": TorrentState.CHECKING,
    "checkingdl": TorrentState.CHECKING,
    "checkingup": TorrentState.CHECKING,
    "check": TorrentState.CHECKING,
    "verifying": TorrentState.CHECKING,
    "completed": TorrentState.COMPLETED,
    "complete": TorrentState.COMPLETED,
    "finished": TorrentState.COMPLETED,
    "finish": TorrentState.COMPLETED,
    "done": TorrentState.COMPLETED,
    "error": TorrentState.ERROR,
    "failed": TorrentState.ERROR,
    "fail": TorrentState.ERROR,
}

_HEURISTIC_STATE_PATTERNS: tuple[tuple[tuple[str, ...], TorrentState], ...] = (
    (("download", "dl"), TorrentState.DOWNLOADING),
    (("seed", "up"), TorrentState.SEEDING),
    (("pause", "stop"), TorrentState.PAUSED),
    (("stall",), TorrentState.STALLED),
    (("queue",), TorrentState.QUEUED),
    (("check", "verify"), TorrentState.CHECKING),
    (("error", "fail"), TorrentState.ERROR),
)


def normalize_torrent_state(raw_state: str | None) -> TorrentState:
    """Normalize any client-specific raw state string into a canonical TorrentState."""
    if not raw_state:
        return TorrentState.UNKNOWN

    s = raw_state.strip().lower()
    if s in _EXACT_STATE_MAP:
        return _EXACT_STATE_MAP[s]

    for keywords, state in _HEURISTIC_STATE_PATTERNS:
        if any(kw in s for kw in keywords):
            return state

    return TorrentState.UNKNOWN


@dataclass
class TorrentStatus:
    """Dataclass representing a standardized torrent status object."""

    id: str | int
    name: str
    progress: float
    state: str
    size: str
    # Category allows validating that a torrent belongs to our label before deletion
    category: str | None = None
    # Client identifier for multi-client support (e.g., 'qbittorrent', 'putio')
    client: str | None = None

    def __post_init__(self) -> None:
        """Ensure state is normalized to a canonical TorrentState value."""
        if not isinstance(self.state, TorrentState):
            self.state = str(normalize_torrent_state(self.state).value)


class _ClientConnections(threading.local):
    """Initialize connection handles independently in each request thread."""

    def __init__(self) -> None:
        """Keep local SDK clients and HTTP sessions out of other request threads."""
        self.client: Any = None
        self.session: Any = None


class TorrentClientPlugin(ABC):
    """Abstract base class for download client plugins."""

    # Plugin Configuration Contracts
    # Subclasses should override this to define their default port.
    DEFAULT_PORT: ClassVar[int] = 8080

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        scheme: str = "http",
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        """Initialize the client plugin configuration.

        Accepts **kwargs to allow subclasses to accept extra parameters
        without breaking the common interface.
        """
        self._connections = _ClientConnections()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.scheme = scheme
        self.timeout = timeout

    @property
    def client(self) -> Any:
        """Return this thread's SDK connection handle."""
        return self._connections.client

    @client.setter
    def client(self, value: Any) -> None:
        self._connections.client = value

    @property
    def session(self) -> Any:
        """Return this thread's HTTP connection handle."""
        return self._connections.session

    @session.setter
    def session(self, value: Any) -> None:
        self._connections.session = value

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the torrent client."""
        pass  # pragma: no cover

    @abstractmethod
    def close(self) -> None:
        """Close the connection to the torrent client and release resources."""
        pass  # pragma: no cover

    @abstractmethod
    def add_magnet(self, magnet_link: str, save_path: str, category: str) -> None:
        """Add a magnet link to the client."""
        pass  # pragma: no cover

    @abstractmethod
    def remove_torrent(self, torrent_id: str) -> None:
        """Remove a torrent by ID."""
        pass  # pragma: no cover

    @abstractmethod
    def get_status(self, category: str) -> list[TorrentStatus]:
        """Retrieve status of torrents in the given category."""
        pass  # pragma: no cover

    def verify_credentials(self) -> bool:
        """Verify that the provided credentials work.

        The default implementation simply attempts to connect.
        Subclasses may override this if a lighter-weight check is available.
        """
        try:
            self.connect()
            return True
        except Exception:
            return False  # pragma: no cover

    def teardown(self) -> None:
        """Perform request-scoped cleanup.

        This method is called by the TorrentManager at the end of each request.
        The default implementation calls close() to ensure resources are released.
        Plugins that maintain persistent connections may override this to do nothing
        or perform lighter cleanup.
        """
        self.close()

    def __del__(self) -> None:
        """Ensure resources are released when the plugin instance is garbage collected.

        This acts as a safety net for thread-local instances that might not be explicitly closed.
        """
        try:
            self.close()
        except Exception:  # noqa: S110
            # Swallow errors during GC to prevent noisy stderr output
            pass  # pragma: no cover
