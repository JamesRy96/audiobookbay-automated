from __future__ import annotations

from deluge_web_client import DelugeWebClient
from deluge_web_client import TorrentOptions as DelugeTorrentOptions

from adapters.torrent.base import TorrentClientAdapter
from models import TorrentStatus


class DelugeAdapter(TorrentClientAdapter):
    def _client(self) -> DelugeWebClient:
        client = DelugeWebClient(
            url=self.settings.dl_url,
            password=self.settings.dl_password,
        )
        client.login()
        return client

    def add_magnet(
        self,
        magnet_link: str,
        title: str,
        author: str | None = None,
    ) -> None:
        client = self._client()
        torrent_options = DelugeTorrentOptions(
            download_location=self.build_save_path(title, author),
            label=self.settings.dl_category,
        )
        client.add_torrent_magnet(magnet_link, torrent_options=torrent_options)

    def list_torrents(self) -> list[TorrentStatus]:
        client = self._client()
        torrents = client.get_torrents_status(
            filter_dict={"label": self.settings.dl_category},
            keys=["name", "state", "progress", "total_size"],
        )
        return [
            TorrentStatus(
                name=torrent["name"],
                progress=round(torrent["progress"], 2),
                state=torrent["state"],
                size=self.format_size_mb(torrent["total_size"]),
            )
            for torrent in torrents.result.values()
        ]
