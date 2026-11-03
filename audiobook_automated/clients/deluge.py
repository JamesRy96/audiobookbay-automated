# File: audiobook_automated/clients/deluge.py
"""Download client plugin for Deluge."""

import logging
import threading
from typing import Any, override

from deluge_web_client import DelugeWebClient
from deluge_web_client.schema import TorrentOptions

from audiobook_automated.utils import format_size

from .base import TorrentClientPlugin, TorrentStatus

logger = logging.getLogger(__name__)


class _DelugeState(threading.local):
    """Keep daemon plugin observations with the request's connection."""

    def __init__(self) -> None:
        """Start each thread without a daemon plugin observation."""
        self.label_plugin_enabled = False


class DelugeClient(TorrentClientPlugin):
    """Download client plugin for Deluge."""

    DEFAULT_PORT = 8112

    def __init__(self, dl_url: str | None = None, *args: Any, **kwargs: Any) -> None:
        """Initialize the Deluge client plugin.

        Args:
            dl_url: Optional override for the Deluge URL.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.dl_url = dl_url
        self.client: DelugeWebClient | None = None
        self._deluge_state = _DelugeState()

    @property
    def label_plugin_enabled(self) -> bool:
        """Return Label support for this request's daemon connection."""
        return self._deluge_state.label_plugin_enabled

    @label_plugin_enabled.setter
    def label_plugin_enabled(self, enabled: bool) -> None:
        self._deluge_state.label_plugin_enabled = enabled

    @override
    def connect(self) -> None:
        """Connect to the Deluge client."""
        # DelugeWebClient uses the full URL
        url = self.dl_url or f"{self.scheme}://{self.host}:{self.port}"
        self.client = DelugeWebClient(url=url, password=self.password or "")

        # Check login result
        response = self.client.login(timeout=self.timeout)
        # Explicitly check for RPC errors as the client might not raise them automatically
        if response.error:
            # Raise exception so TorrentManager knows connection failed and can retry/log
            raise ConnectionError(f"Failed to login to Deluge: {response.error}")

        # Detect Plugins (Specifically 'Label')
        try:
            plugins_resp = self.client.execute_call(
                {"method": "core.get_enabled_plugins", "params": []}, timeout=self.timeout
            )
            # The daemon list, unlike web.get_plugins, describes actual core Label support.
            if plugins_resp and isinstance(plugins_resp.result, list) and "Label" in plugins_resp.result:
                self.label_plugin_enabled = True
                logger.info("Deluge 'Label' plugin detected.")
            else:
                self.label_plugin_enabled = False
                logger.info("Deluge 'Label' plugin NOT detected. Categorization will be disabled.")
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not verify Deluge plugins: {e}. Defaulting to no labels.")
            self.label_plugin_enabled = False

    @override
    def close(self) -> None:
        """Close the Deluge client session."""
        try:
            if self.client:
                self.client.close_session()
        finally:
            self.client = None
            self.label_plugin_enabled = False

    @override
    def add_magnet(self, magnet_link: str, save_path: str, category: str) -> None:
        """Add a magnet link to Deluge."""
        if not self.client:
            raise ConnectionError("Deluge client not connected")

        options = TorrentOptions(
            download_location=save_path,
            label=category if self.label_plugin_enabled else None,
            add_paused=False,
        )
        # Label errors can occur after acceptance; never blindly submit a second add.
        self.client.add_torrent_magnet(magnet_link, torrent_options=options, timeout=self.timeout)

    @override
    def remove_torrent(self, torrent_id: str) -> None:
        """Remove a torrent from Deluge."""
        if not self.client:  # pragma: no cover
            raise ConnectionError("Deluge client not connected")
        self.client.remove_torrent(torrent_id, remove_data=False, timeout=self.timeout)

    @override
    def get_status(self, category: str) -> list[TorrentStatus]:
        """Get torrent status from Deluge."""
        if not self.client:  # pragma: no cover
            raise ConnectionError("Deluge client not connected")
        results: list[TorrentStatus] = []

        # If Label plugin is enabled, filter by our category.
        # If NOT enabled, we must fetch ALL torrents to ensure the user can see their downloads.
        # (Filtering by label is impossible without the plugin).
        filter_dict: dict[str, Any] = {}
        if self.label_plugin_enabled:
            filter_dict["label"] = category

        # This call handles raising DelugeWebClientError if auth fails (handled by execute_call)
        deluge_torrents = self.client.get_torrents_status(
            filter_dict=filter_dict,
            keys=["name", "state", "progress", "total_size"],
            timeout=self.timeout,
        )

        if deluge_torrents.result is not None:
            if isinstance(deluge_torrents.result, dict):
                results_dict = deluge_torrents.result
                for key, deluge_data in results_dict.items():
                    # Robust check for None or invalid type to please type checkers
                    if deluge_data is None or not isinstance(deluge_data, dict):
                        continue
                    progress_val = deluge_data.get("progress")
                    try:
                        # Deluge returns progress as 0-100 float
                        # Ensure progress_val is convertible to float
                        progress = round(float(progress_val), 2) if progress_val is not None else 0.0
                    except (ValueError, TypeError):
                        # Log if conversion fails but don't crash
                        logger.debug(f"Invalid progress value for {key}: {progress_val}")
                        progress = 0.0

                    results.append(
                        TorrentStatus(
                            id=key,
                            name=deluge_data.get("name", "Unknown"),
                            progress=progress,
                            state=deluge_data.get("state", "Unknown"),
                            size=format_size(deluge_data.get("total_size")),
                        )
                    )
            else:
                logger.warning(f"Deluge returned unexpected data type: {type(deluge_torrents.result)}")
        else:
            logger.warning("Deluge returned empty or invalid result payload.")
        return results
