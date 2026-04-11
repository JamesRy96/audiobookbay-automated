from __future__ import annotations

from adapters.torrent.base import UnsupportedDownloadClientError
from adapters.torrent.deluge import DelugeAdapter
from adapters.torrent.qbittorrent import QbittorrentAdapter
from adapters.torrent.transmission import TransmissionAdapter
from config import AppSettings


def create_torrent_client(settings: AppSettings):
    adapter_map = {
        "qbittorrent": QbittorrentAdapter,
        "transmission": TransmissionAdapter,
        "delugeweb": DelugeAdapter,
    }

    adapter_class = adapter_map.get(settings.download_client)
    if not adapter_class:
        raise UnsupportedDownloadClientError("Unsupported download client")

    return adapter_class(settings)
