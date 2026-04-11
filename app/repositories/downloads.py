from __future__ import annotations

import sqlite3
from contextlib import closing

from models import DownloadRecord, DownloadState


def _connect(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _row_to_download_record(row: sqlite3.Row) -> DownloadRecord:
    return DownloadRecord(
        id=row["id"],
        title=row["title"],
        author=row["author"],
        details_url=row["details_url"],
        magnet_link=row["magnet_link"],
        client=row["client"],
        external_id=row["external_id"],
        state=DownloadState(row["state"]),
        progress=row["progress"],
        error=row["error"],
        added_at=row["added_at"],
        completed_at=row["completed_at"],
    )


def insert_download_record(database_path: str, record: DownloadRecord) -> DownloadRecord:
    insert_values = {
        "title": record.title,
        "author": record.author,
        "details_url": record.details_url,
        "magnet_link": record.magnet_link,
        "client": record.client,
        "external_id": record.external_id,
        "state": record.state.value,
        "progress": record.progress,
        "error": record.error,
        "completed_at": record.completed_at,
    }
    if record.added_at is not None:
        insert_values["added_at"] = record.added_at

    columns = list(insert_values)
    values = [insert_values[column] for column in columns]
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)

    with closing(_connect(database_path)) as connection:
        cursor = connection.execute(
            f"INSERT INTO downloads ({column_list}) VALUES ({placeholders})",
            values,
        )
        connection.commit()

        inserted_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM downloads WHERE id = ?",
            (inserted_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError("Failed to load inserted download record")

    return _row_to_download_record(row)


def list_download_records(database_path: str) -> list[DownloadRecord]:
    with closing(_connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT * FROM downloads ORDER BY id DESC"
        ).fetchall()

    return [_row_to_download_record(row) for row in rows]


__all__ = ["insert_download_record", "list_download_records"]
