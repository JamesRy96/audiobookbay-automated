from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "app")

from application import create_app
from errors import ExternalServiceError
from adapters.torrent.base import UnsupportedDownloadClientError


class RouteTests(unittest.TestCase):
    def create_test_client(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.temp_dir.name) / "test.db")
        app = create_app()
        app.config["TESTING"] = True
        return app.test_client()

    def tearDown(self):
        os.environ.pop("APP_DB_PATH", None)
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_send_requires_link_and_title(self):
        client = self.create_test_client()

        response = client.post("/api/send", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["message"], "Invalid request")

    def test_send_uses_central_error_handler(self):
        client = self.create_test_client()

        with patch("routes.api.add_download", side_effect=ExternalServiceError("Failed to extract magnet link")):
            response = client.post(
                "/api/send",
                json={"link": "https://example.com", "title": "Example"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["message"], "Failed to extract magnet link")

    def test_status_unsupported_client_returns_400(self):
        client = self.create_test_client()

        with patch(
            "routes.api.fetch_torrent_status",
            side_effect=UnsupportedDownloadClientError("Unsupported download client"),
        ):
            response = client.get("/api/status")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["message"], "Unsupported download client")

    def test_search_empty_query_returns_empty(self):
        client = self.create_test_client()

        response = client.get("/api/search")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["books"], [])

    def test_config_returns_nav_link(self):
        client = self.create_test_client()

        response = client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("nav_link_name", data)
        self.assertIn("nav_link_url", data)


if __name__ == "__main__":
    unittest.main()
