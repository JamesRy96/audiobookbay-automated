from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import PurePosixPath

from config import AppSettings
from errors import ConfigurationError, ValidationError
from models import TorrentStatus
from utils import sanitize_title


class UnsupportedDownloadClientError(ValidationError):
    pass


class TorrentClientAdapter(ABC):
    def __init__(self, settings: AppSettings):
        self.settings = settings

    def build_save_path(self, title: str, author: str | None = None) -> str:
        if not self.settings.save_path_base:
            raise ConfigurationError("SAVE_PATH_BASE is not configured")

        path = PurePosixPath(self.settings.save_path_base)
        if author:
            path /= sanitize_title(author)
        path /= sanitize_title(title)
        return str(path)

    def format_size_mb(self, total_size_bytes: int | float) -> str:
        return f"{total_size_bytes / (1024 * 1024):.2f} MB"

    @abstractmethod
    def add_magnet(
        self,
        magnet_link: str,
        title: str,
        author: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_torrents(self) -> list[TorrentStatus]:
        raise NotImplementedError
