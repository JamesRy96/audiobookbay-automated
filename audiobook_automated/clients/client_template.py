# File: audiobook_automated/clients/client_template.py
"""Template for creating custom Torrent Client plugins.

Instructions for Developers:
1. Copy this file and rename it to your client's name (e.g., `rtorrent.py`).
2. Implement every API method, including safe, idempotent close().
   See docs/agents/torrent-clients.md for the complete contract and tests.
3. Update `DEFAULT_PORT` to the standard port for your client.
4. Place the file in the `audiobook_automated/clients/` directory.
5. Set `DL_CLIENT=your_filename_without_extension` (e.g., `rtorrent`) in your .env file.
"""

import logging
from typing import Any, override

from .base import TorrentClientPlugin, TorrentStatus

logger = logging.getLogger(__name__)


class CustomClient(TorrentClientPlugin):
    """Starting scaffold for a new Download Client API adapter."""

    # MANDATORY: Define the default WebUI/RPC port for this client.
    # This allows the app to configure itself automatically if DL_PORT is missing.
    DEFAULT_PORT = 0000

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the client plugin.

        Args:
            *args: Standard arguments passed by TorrentManager (host, port, etc).
            **kwargs: Extra arguments. Use this to capture any custom config if needed.
        """
        super().__init__(*args, **kwargs)
        self.client: Any = None  # Replace 'Any' with your actual client library type

    @override
    def connect(self) -> None:
        """Establish connection to the torrent client.

        Raises:
            ConnectionError: If connection or authentication fails.
        """
        # Example Implementation:
        # url = f"{self.scheme}://{self.host}:{self.port}"
        # try:
        #     self.client = MyClientLib(url, self.username, self.password)
        #     self.client.login()
        # except Exception as e:
        #     raise ConnectionError(f"Failed to connect: {e}")
        raise NotImplementedError("Implement the connect method.")

    @override
    def close(self) -> None:
        """Close the connection and release resources."""
        # if self.client:
        #     self.client.close()
        # self.client = None
        pass

    @override
    def add_magnet(self, magnet_link: str, save_path: str, category: str) -> None:
        """Add a magnet link to the client.

        Args:
            magnet_link: The full magnet URI.
            save_path: The absolute path where files should be downloaded.
            category: The category/label to assign (e.g., 'audiobooks').

        Raises:
            ConnectionError: If the client is not connected.
            Exception: If adding the torrent fails.
        """
        if not self.client:
            raise ConnectionError("Client not connected")

        # Implement logic to add torrent.
        # Ensure you handle 'category' if the client supports it.
        # If the client does NOT support categories, you may ignore that argument.
        raise NotImplementedError("Implement add_magnet.")

    @override
    def remove_torrent(self, torrent_id: str) -> None:
        """Remove a torrent by ID.

        Args:
            torrent_id: The unique identifier (usually info_hash) of the torrent.

        Raises:
            ConnectionError: If the client is not connected.
        """
        if not self.client:
            raise ConnectionError("Client not connected")

        # Implement logic to remove torrent.
        # IMPORTANT: Ensure you set delete_data=False (remove only the .torrent task).
        raise NotImplementedError("Implement remove_torrent.")

    @override
    def get_status(self, category: str) -> list[TorrentStatus]:
        """Retrieve status of torrents in the given category.

        Args:
            category: Filter results to this category/label only.

        Returns:
            list[TorrentStatus]: Standardized status objects.
        """
        if not self.client:
            raise ConnectionError("Client not connected")

        results: list[TorrentStatus] = []

        # Fetch torrents from client.
        # Filter by 'category' manually here if the client API doesn't support server-side filtering.

        # Example Loop:
        # for t in torrents:
        #     results.append(TorrentStatus(
        #         id=t.hash,
        #         name=t.name,
        #         progress=t.progress_percent,  # Must be 0.0 - 100.0
        #         state=t.state,                # e.g., 'Downloading', 'Seeding'
        #         size=format_size(t.size_bytes)
        #     ))

        return results
