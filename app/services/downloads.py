from __future__ import annotations

import logging

from adapters.torrent.base import UnsupportedDownloadClientError
from adapters.torrent.factory import create_torrent_client
from config import AppSettings
from errors import ExternalServiceError
from models import DownloadState, TorrentStatus
from services.download_records import create_download_record
from services.audiobookbay import extract_details_metadata

logger = logging.getLogger(__name__)

def add_download(book_details: dict[str, str | None], settings: AppSettings) -> str:
    details_url = book_details["link"]
    title = book_details["title"]
    details_metadata = extract_details_metadata(details_url, settings)
    magnet_link = details_metadata["magnet_link"]
    author = book_details.get("author") or details_metadata.get("author") or "unknown"
    if not magnet_link:
        raise ExternalServiceError("Failed to extract magnet link")

    torrent_client = create_torrent_client(settings)

    logger.info(
        "Starting download for title=%s author=%s",
        title,
        author,
    )

    torrent_client.add_magnet(magnet_link, title, author)
    create_download_record(
        settings.database_path,
        title,
        details_url,
        author=author,
        magnet_link=magnet_link,
        client=settings.download_client,
        state=DownloadState.SENT,
    )
    return (
        "Download added successfully! This may take some time, "
        "the download will show in Audiobookshelf when completed."
    )


def fetch_torrent_status(settings: AppSettings) -> list[TorrentStatus]:
    torrent_client = create_torrent_client(settings)
    return torrent_client.list_torrents()


__all__ = ["UnsupportedDownloadClientError", "add_download", "fetch_torrent_status"]
