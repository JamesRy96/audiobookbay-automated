from __future__ import annotations

from transmission_rpc import Client as TransmissionClient

from adapters.torrent.base import TorrentClientAdapter
from models import TorrentStatus


class TransmissionAdapter(TorrentClientAdapter):
    def _client(self) -> TransmissionClient:
        return TransmissionClient(
            host=self.settings.dl_host,
            port=self.settings.dl_port,
            protocol=self.settings.dl_scheme,
            username=self.settings.dl_username,
            password=self.settings.dl_password,
        )

    def add_magnet(
        self,
        magnet_link: str,
        title: str,
        author: str | None = None,
    ) -> None:
        client = self._client()
        client.add_torrent(
            magnet_link,
            download_dir=self.build_save_path(title, author),
        )

    def list_torrents(self) -> list[TorrentStatus]:
        client = self._client()
        torrents = client.get_torrents()
        return [
            TorrentStatus(
                name=torrent.name,
                progress=round(torrent.progress, 2),
                state=torrent.status,
                size=self.format_size_mb(torrent.total_size),
            )
            for torrent in torrents
        ]
