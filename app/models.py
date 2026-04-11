from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BookResult:
    title: str
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
