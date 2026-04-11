from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from typing import Any, Mapping


class SettingsRepository:
    def __init__(self, database_path: str):
        self.database_path = database_path

    def load_all(self) -> dict[str, Any]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute("SELECT key, value FROM settings").fetchall()

        return {
            key: json.loads(value) if value is not None else None
            for key, value in rows
        }

    def save_all(self, settings: Mapping[str, Any]) -> None:
        if not settings:
            return

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executemany(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """.strip(),
                [
                    (key, json.dumps(value, separators=(",", ":")))
                    for key, value in settings.items()
                ],
            )
            connection.commit()
