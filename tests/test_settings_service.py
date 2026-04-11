from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "app")

from config import AppSettings
from db import initialize_database
from errors import ValidationError
from repositories.settings import SettingsRepository
from services.settings_service import SettingsService


def make_base_settings(database_path: str) -> AppSettings:
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


class SettingsServiceTests(unittest.TestCase):
    def test_get_settings_merges_persisted_overrides(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "app.db"
            initialize_database(str(db_path))
            repository = SettingsRepository(str(db_path))
            repository.save_all(
                {
                    "page_limit": 12,
                    "nav_link_name": "Audiobooks",
                    "dl_password": "persisted-secret",
                }
            )

            service = SettingsService(repository)
            settings = service.get_settings(make_base_settings(str(db_path)))

            self.assertEqual(settings["page_limit"], 12)
            self.assertEqual(settings["nav_link_name"], "Audiobooks")
            self.assertEqual(settings["dl_url"], "https://torrent.example.com:9443")
            self.assertTrue(settings["dl_password_configured"])
            self.assertNotIn("dl_password", settings)

    def test_update_settings_normalizes_transport_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "app.db"
            initialize_database(str(db_path))
            service = SettingsService(SettingsRepository(str(db_path)))

            settings = service.update_settings(
                make_base_settings(str(db_path)),
                {
                    "dl_url": "https://example.com:9443",
                    "page_limit": "9",
                },
            )

            self.assertEqual(settings["dl_scheme"], "https")
            self.assertEqual(settings["dl_host"], "example.com")
            self.assertEqual(settings["dl_port"], 9443)
            self.assertEqual(settings["page_limit"], 9)

    def test_update_settings_rejects_unknown_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "app.db"
            initialize_database(str(db_path))
            service = SettingsService(SettingsRepository(str(db_path)))

            with self.assertRaises(ValidationError):
                service.update_settings(
                    make_base_settings(str(db_path)),
                    {"unexpected": "value"},
                )

    def test_update_settings_keeps_password_when_payload_omits_it(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "app.db"
            initialize_database(str(db_path))
            repository = SettingsRepository(str(db_path))
            repository.save_all({"dl_password": "persisted-secret"})
            service = SettingsService(repository)

            settings = service.update_settings(
                make_base_settings(str(db_path)),
                {"page_limit": 9},
            )

            self.assertEqual(settings["page_limit"], 9)
            self.assertTrue(settings["dl_password_configured"])
            self.assertEqual(
                repository.load_all()["dl_password"],
                "persisted-secret",
            )

    def test_update_settings_replaces_password_only_when_provided(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "app.db"
            initialize_database(str(db_path))
            repository = SettingsRepository(str(db_path))
            repository.save_all({"dl_password": "old-secret"})
            service = SettingsService(repository)

            settings = service.update_settings(
                make_base_settings(str(db_path)),
                {"dl_password": "new-secret"},
            )

            self.assertTrue(settings["dl_password_configured"])
            self.assertNotIn("dl_password", settings)
            self.assertEqual(repository.load_all()["dl_password"], "new-secret")


if __name__ == "__main__":
    unittest.main()
