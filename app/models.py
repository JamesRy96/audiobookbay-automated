from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TorrentStatus:
    name: str
    progress: float
    state: str
    size: str
