from __future__ import annotations

from abc import ABC, abstractmethod

from config import AppSettings
from models import TorrentStatus
from utils import sanitize_title


class UnsupportedDownloadClientError(ValueError):
    pass


class TorrentClientAdapter(ABC):
    def __init__(self, settings: AppSettings):
        self.settings = settings

    def build_save_path(self, title: str) -> str:
        if not self.settings.save_path_base:
            raise ValueError("SAVE_PATH_BASE is not configured")
        return f"{self.settings.save_path_base}/{sanitize_title(title)}"

    def format_size_mb(self, total_size_bytes: int | float) -> str:
        return f"{total_size_bytes / (1024 * 1024):.2f} MB"

    @abstractmethod
    def add_magnet(self, magnet_link: str, title: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_torrents(self) -> list[TorrentStatus]:
        raise NotImplementedError
