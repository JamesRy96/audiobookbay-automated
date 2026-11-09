# File: audiobook_automated/clients/__init__.py
"""Torrent clients package."""

from .base import TorrentClientPlugin, TorrentStatus
from .manager import TorrentManager

__all__ = ["TorrentClientPlugin", "TorrentManager", "TorrentStatus"]
