from __future__ import annotations

import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, "app")

from config import AppSettings
from models import DownloadState
from services.downloads import add_download, fetch_torrent_status


def make_settings() -> AppSettings:
    return AppSettings(
        abb_hostname="audiobookbay.lu",
        page_limit=5,
        download_client="qbittorrent",
        dl_scheme="http",
        dl_host="localhost",
        dl_port=8080,
        dl_url="http://localhost:8080",
        dl_username="user",
        dl_password="pass",
        dl_category="abb",
        save_path_base="/audiobooks",
        nav_link_name=None,
        nav_link_url=None,
        database_path="/tmp/downloads.db",
        flask_port=5078,
    )


class DownloadServiceTests(unittest.TestCase):
    def test_add_download_persists_tracked_record(self):
        settings = make_settings()
        book_details = {
            "link": "https://example.com/book",
            "title": "Example Book",
            "author": None,
        }

        with (
            patch(
                "services.downloads.extract_details_metadata",
                return_value={
                    "magnet_link": "magnet:?xt=urn:btih:abc123",
                    "author": "Example Author",
                },
            ) as extract_details_metadata,
            patch("services.downloads.create_torrent_client") as create_torrent_client,
            patch("services.downloads.create_download_record") as create_download_record,
        ):
            torrent_client = Mock()
            create_torrent_client.return_value = torrent_client

            message = add_download(book_details, settings)

        self.assertIn("Download added successfully", message)
        extract_details_metadata.assert_called_once_with("https://example.com/book", settings)
        create_torrent_client.assert_called_once_with(settings)
        torrent_client.add_magnet.assert_called_once_with(
            "magnet:?xt=urn:btih:abc123",
            "Example Book",
            "Example Author",
        )
        create_download_record.assert_called_once_with(
            settings.database_path,
            "Example Book",
            "https://example.com/book",
            author="Example Author",
            magnet_link="magnet:?xt=urn:btih:abc123",
            client="qbittorrent",
            state=DownloadState.SENT,
        )

    def test_fetch_torrent_status_delegates_to_client(self):
        settings = make_settings()

        with patch("services.downloads.create_torrent_client") as create_torrent_client:
            torrent_client = Mock()
            torrent_client.list_torrents.return_value = []
            create_torrent_client.return_value = torrent_client

            status = fetch_torrent_status(settings)

        self.assertEqual(status, [])
        create_torrent_client.assert_called_once_with(settings)
        torrent_client.list_torrents.assert_called_once()


if __name__ == "__main__":
    unittest.main()
