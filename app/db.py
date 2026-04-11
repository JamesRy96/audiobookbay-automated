from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def load_schema() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def initialize_database(database_path: str) -> None:
    os.makedirs(os.path.dirname(database_path), exist_ok=True)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(load_schema())
        connection.commit()
