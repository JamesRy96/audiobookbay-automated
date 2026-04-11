from __future__ import annotations

from qbittorrentapi import Client as QbittorrentClient

from adapters.torrent.base import TorrentClientAdapter
from models import TorrentStatus


class QbittorrentAdapter(TorrentClientAdapter):
    def _client(self) -> QbittorrentClient:
        client = QbittorrentClient(
            host=self.settings.dl_host,
            port=self.settings.dl_port,
            username=self.settings.dl_username,
            password=self.settings.dl_password,
        )
        client.auth_log_in()
        return client

    def add_magnet(self, magnet_link: str, title: str) -> None:
        client = self._client()
        client.torrents_add(
            urls=magnet_link,
            save_path=self.build_save_path(title),
            category=self.settings.dl_category,
        )

    def list_torrents(self) -> list[TorrentStatus]:
        client = self._client()
        torrents = client.torrents_info(category=self.settings.dl_category)
        return [
            TorrentStatus(
                name=torrent.name,
                progress=round(torrent.progress * 100, 2),
                state=torrent.state,
                size=self.format_size_mb(torrent.total_size),
            )
            for torrent in torrents
        ]
