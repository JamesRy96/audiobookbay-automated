from __future__ import annotations

from repositories.downloads import insert_download_record, list_download_records
from models import DownloadRecord, DownloadState


def create_download_record(
    database_path: str,
    title: str,
    details_url: str,
    *,
    author: str | None = None,
    magnet_link: str | None = None,
    client: str | None = None,
    external_id: str | None = None,
    state: DownloadState | str = DownloadState.QUEUED,
    progress: float = 0.0,
    error: str | None = None,
    completed_at: str | None = None,
    added_at: str | None = None,
) -> DownloadRecord:
    download_state = state if isinstance(state, DownloadState) else DownloadState(state)
    record = DownloadRecord(
        title=title,
        details_url=details_url,
        author=author,
        magnet_link=magnet_link,
        client=client,
        external_id=external_id,
        state=download_state,
        progress=progress,
        error=error,
        added_at=added_at,
        completed_at=completed_at,
    )
    return insert_download_record(database_path, record)


def fetch_download_records(database_path: str) -> list[DownloadRecord]:
    return list_download_records(database_path)


__all__ = ["create_download_record", "fetch_download_records"]
