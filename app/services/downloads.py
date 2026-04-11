from __future__ import annotations

from adapters.torrent.base import UnsupportedDownloadClientError
from adapters.torrent.factory import create_torrent_client
from config import AppSettings
from models import TorrentStatus
from services.audiobookbay import extract_magnet_link


def add_download(details_url: str, title: str, settings: AppSettings) -> str:
    magnet_link = extract_magnet_link(details_url)
    if not magnet_link:
        raise ValueError("Failed to extract magnet link")

    torrent_client = create_torrent_client(settings)
    torrent_client.add_magnet(magnet_link, title)
    return (
        "Download added successfully! This may take some time, "
        "the download will show in Audiobookshelf when completed."
    )


def fetch_torrent_status(settings: AppSettings) -> list[TorrentStatus]:
    torrent_client = create_torrent_client(settings)
    return torrent_client.list_torrents()


__all__ = ["UnsupportedDownloadClientError", "add_download", "fetch_torrent_status"]
