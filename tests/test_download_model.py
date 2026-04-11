from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "app")

from models import DownloadRecord, DownloadState


class DownloadModelTests(unittest.TestCase):
    def test_download_state_values_are_stable(self):
        self.assertEqual(DownloadState.QUEUED.value, "queued")
        self.assertEqual(DownloadState.COMPLETED.value, "completed")

    def test_download_record_uses_typed_defaults(self):
        record = DownloadRecord(
            title="Example Book",
            details_url="https://example.com/book",
        )

        self.assertEqual(record.state, DownloadState.QUEUED)
        self.assertEqual(record.progress, 0.0)
        self.assertIsNone(record.id)
        self.assertIsNone(record.added_at)


if __name__ == "__main__":
    unittest.main()

