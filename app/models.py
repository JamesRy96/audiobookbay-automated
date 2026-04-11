from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class BookResult:
    title: str
    author: str | None
    link: str
    cover: str
    language: str
    post_date: str
    format: str
    bitrate: str
    file_size: str


@dataclass(frozen=True)
class TorrentStatus:
    name: str
    progress: float
    state: str
    size: str


class DownloadState(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    IMPORTING = "importing"
    IMPORTED = "imported"
    FAILED = "failed"


@dataclass(frozen=True)
class DownloadRecord:
    title: str
    details_url: str
    author: str | None = None
    magnet_link: str | None = None
    client: str | None = None
    external_id: str | None = None
    state: DownloadState = DownloadState.QUEUED
    progress: float = 0.0
    error: str | None = None
    added_at: str | None = None
    completed_at: str | None = None
    id: int | None = None
