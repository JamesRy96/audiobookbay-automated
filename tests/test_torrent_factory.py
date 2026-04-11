from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "app")

from adapters.torrent.base import UnsupportedDownloadClientError
from adapters.torrent.deluge import DelugeAdapter
from adapters.torrent.factory import create_torrent_client
from adapters.torrent.qbittorrent import QbittorrentAdapter
from adapters.torrent.transmission import TransmissionAdapter
from config import AppSettings


def make_settings(download_client: str | None) -> AppSettings:
    return AppSettings(
        abb_hostname="audiobookbay.lu",
        page_limit=5,
        download_client=download_client,
        dl_scheme="http",
        dl_host="localhost",
        dl_port=8080,
        dl_url="http://localhost:8112",
        dl_username="user",
        dl_password="pass",
        dl_category="abb",
        save_path_base="/audiobooks",
        nav_link_name=None,
        nav_link_url=None,
        database_path="/tmp/test.db",
        flask_port=5078,
    )


class TorrentFactoryTests(unittest.TestCase):
    def test_create_qbittorrent_client(self):
        client = create_torrent_client(make_settings("qbittorrent"))
        self.assertIsInstance(client, QbittorrentAdapter)

    def test_create_transmission_client(self):
        client = create_torrent_client(make_settings("transmission"))
        self.assertIsInstance(client, TransmissionAdapter)

    def test_create_deluge_client(self):
        client = create_torrent_client(make_settings("delugeweb"))
        self.assertIsInstance(client, DelugeAdapter)

    def test_unknown_client_raises(self):
        with self.assertRaises(UnsupportedDownloadClientError):
            create_torrent_client(make_settings("unknown"))


if __name__ == "__main__":
    unittest.main()
