from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

sys.path.insert(0, "app")

from config import APP_SETTINGS_KEY, AppSettings
from db import initialize_database
from routes.settings import settings_bp


def make_settings(database_path: str) -> AppSettings:
    return AppSettings(
        abb_hostname="audiobookbay.lu",
        page_limit=5,
        download_client="qbittorrent",
        dl_scheme="https",
        dl_host="torrent.example.com",
        dl_port=9443,
        dl_url="https://torrent.example.com:9443",
        dl_username="user",
        dl_password="pass",
        dl_category="Audiobookbay-Audiobooks",
        save_path_base="/audiobooks",
        nav_link_name="Library",
        nav_link_url="/status",
        database_path=database_path,
        flask_port=5078,
    )


class SettingsRouteTests(unittest.TestCase):
    def create_test_client(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "app.db"
        initialize_database(str(db_path))

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config[APP_SETTINGS_KEY] = make_settings(str(db_path))
        app.register_blueprint(settings_bp)
        return app.test_client()

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_get_settings_returns_current_settings(self):
        client = self.create_test_client()

        response = client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["settings"]["page_limit"], 5)
        self.assertEqual(response.get_json()["settings"]["dl_host"], "torrent.example.com")
        self.assertTrue(response.get_json()["settings"]["dl_password_configured"])
        self.assertNotIn("dl_password", response.get_json()["settings"])

    def test_post_settings_persists_updates(self):
        client = self.create_test_client()

        response = client.post(
            "/settings",
            json={"page_limit": 11, "dl_url": "https://example.com:9443"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["settings"]["page_limit"], 11)
        self.assertEqual(response.get_json()["settings"]["dl_host"], "example.com")
        self.assertEqual(response.get_json()["settings"]["dl_port"], 9443)
        self.assertTrue(response.get_json()["settings"]["dl_password_configured"])
        self.assertNotIn("dl_password", response.get_json()["settings"])

    def test_post_settings_does_not_clear_password_when_omitted(self):
        client = self.create_test_client()

        response = client.post("/settings", json={"page_limit": 7})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["settings"]["dl_password_configured"])

        response = client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["settings"]["dl_password_configured"])


if __name__ == "__main__":
    unittest.main()
