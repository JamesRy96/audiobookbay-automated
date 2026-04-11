from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, "app")

from db import initialize_database


class DatabaseTests(unittest.TestCase):
    def test_initialize_database_creates_core_tables(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "app.db"
            initialize_database(str(db_path))

            with closing(sqlite3.connect(db_path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }

        self.assertIn("settings", tables)
        self.assertIn("downloads", tables)
        self.assertIn("import_jobs", tables)


if __name__ == "__main__":
    unittest.main()
