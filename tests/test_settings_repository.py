from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, "app")

from db import initialize_database
from repositories.settings import SettingsRepository


class SettingsRepositoryTests(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "app.db"
            initialize_database(str(db_path))

            repository = SettingsRepository(str(db_path))
            repository.save_all(
                {
                    "abb_hostname": "example.com",
                    "page_limit": 8,
                    "dl_port": 9443,
                    "dl_url": "https://example.com:9443",
                }
            )

            self.assertEqual(
                repository.load_all(),
                {
                    "abb_hostname": "example.com",
                    "page_limit": 8,
                    "dl_port": 9443,
                    "dl_url": "https://example.com:9443",
                },
            )

            with closing(sqlite3.connect(db_path)) as connection:
                rows = connection.execute("SELECT key FROM settings").fetchall()

            self.assertEqual({row[0] for row in rows}, {"abb_hostname", "page_limit", "dl_port", "dl_url"})


if __name__ == "__main__":
    unittest.main()
