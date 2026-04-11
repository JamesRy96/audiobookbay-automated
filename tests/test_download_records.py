from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "app")

from db import initialize_database
from models import DownloadState
from services.download_records import create_download_record, fetch_download_records


class DownloadRecordServiceTests(unittest.TestCase):
    def test_create_download_record_persists_typed_record(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "downloads.db"
            initialize_database(str(db_path))

            created = create_download_record(
                str(db_path),
                "Example Book",
                "https://example.com/book",
                author="Example Author",
                client="transmission",
                state="sent",
                progress=12.0,
            )

            self.assertEqual(created.state, DownloadState.SENT)
            self.assertEqual(created.client, "transmission")
            self.assertEqual(created.progress, 12.0)

    def test_fetch_download_records_returns_all_records(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "downloads.db"
            initialize_database(str(db_path))

            create_download_record(
                str(db_path),
                "First",
                "https://example.com/first",
            )
            create_download_record(
                str(db_path),
                "Second",
                "https://example.com/second",
                state=DownloadState.COMPLETED,
            )

            records = fetch_download_records(str(db_path))

            self.assertEqual([record.title for record in records], ["Second", "First"])
            self.assertEqual(records[0].state, DownloadState.COMPLETED)


if __name__ == "__main__":
    unittest.main()
