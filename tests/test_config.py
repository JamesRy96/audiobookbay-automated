from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "app")

from config import load_settings, resolve_database_path


class ConfigTests(unittest.TestCase):
    def test_load_settings_uses_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings("instance/test.db")

        self.assertEqual(settings.abb_hostname, "audiobookbay.lu")
        self.assertEqual(settings.page_limit, 5)
        self.assertEqual(settings.database_path.endswith("instance/test.db"), True)

    def test_load_settings_parses_dl_url(self):
        env = {
            "DL_URL": "https://example.com:9443",
            "DOWNLOAD_CLIENT": "delugeweb",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = load_settings("instance/test.db")

        self.assertEqual(settings.dl_scheme, "https")
        self.assertEqual(settings.dl_host, "example.com")
        self.assertEqual(settings.dl_port, 9443)

    def test_resolve_database_path_prefers_explicit_env(self):
        with patch.dict(os.environ, {"APP_DB_PATH": "/tmp/custom.db"}, clear=True):
            database_path = resolve_database_path("instance/test.db")

        self.assertEqual(database_path, "/tmp/custom.db")

    def test_resolve_database_path_uses_default_when_no_override(self):
        with patch.dict(os.environ, {}, clear=True), patch("config.os.path.isdir", return_value=False):
            database_path = resolve_database_path("instance/test.db")

        self.assertTrue(database_path.endswith("instance/test.db"))


if __name__ == "__main__":
    unittest.main()
