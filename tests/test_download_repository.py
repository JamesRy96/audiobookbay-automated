from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "app")

from db import initialize_database
from models import DownloadRecord, DownloadState
from repositories.downloads import insert_download_record, list_download_records


class DownloadRepositoryTests(unittest.TestCase):
    def test_insert_download_record_round_trips_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "downloads.db"
            initialize_database(str(db_path))

            created = insert_download_record(
                str(db_path),
                DownloadRecord(
                    title="Example Book",
                    details_url="https://example.com/book",
                    author="Example Author",
                    magnet_link="magnet:?xt=urn:btih:abc123",
                    client="qbittorrent",
                    external_id="abc123",
                    state=DownloadState.DOWNLOADING,
                    progress=42.5,
                ),
            )

            self.assertIsNotNone(created.id)
            self.assertEqual(created.title, "Example Book")
            self.assertEqual(created.author, "Example Author")
            self.assertEqual(created.state, DownloadState.DOWNLOADING)
            self.assertEqual(created.progress, 42.5)
            self.assertIsNotNone(created.added_at)

    def test_list_download_records_orders_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "downloads.db"
            initialize_database(str(db_path))

            first = insert_download_record(
                str(db_path),
                DownloadRecord(
                    title="First",
                    details_url="https://example.com/first",
                ),
            )
            second = insert_download_record(
                str(db_path),
                DownloadRecord(
                    title="Second",
                    details_url="https://example.com/second",
                ),
            )

            records = list_download_records(str(db_path))

            self.assertEqual([record.id for record in records], [second.id, first.id])


if __name__ == "__main__":
    unittest.main()

