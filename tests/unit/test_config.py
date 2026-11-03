# File: tests/unit/test_config.py
"""Unit tests for configuration validation."""

import importlib
import logging
import os
from unittest.mock import patch

import pytest
from pytest import LogCaptureFixture, MonkeyPatch

from audiobook_automated import config
from audiobook_automated.config import Config
from audiobook_automated.constants import (
    DEFAULT_SITE_LOGO,
    DEFAULT_SITE_TITLE,
    DEFAULT_SPLASH_MESSAGE,
    DEFAULT_SPLASH_VIDEO,
    DEFAULT_SPLASH_VIDEO_WEBM,
    DEFAULT_THEME,
)


def test_config_validate_success(monkeypatch: MonkeyPatch) -> None:
    """Ensure validation passes with valid configuration."""
    monkeypatch.setenv("SECRET_KEY", "prod-secret-key")
    monkeypatch.setenv("SAVE_PATH_BASE", "/data")
    monkeypatch.setenv("QBITTORRENT_SCHEME", "https")
    # Patch class attributes as well since they are loaded at import
    monkeypatch.setattr(Config, "SECRET_KEY", "prod-secret-key")
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", "/data")
    monkeypatch.setattr(Config, "CLIENT_CONNECTIONS", {"qbittorrent": {"SCHEME": "https"}})
    monkeypatch.setattr(Config, "DL_CLIENT", "qbittorrent")  # Required now
    monkeypatch.setattr(Config, "TESTING", False)
    monkeypatch.setattr(Config, "FLASK_DEBUG", False)

    # Should not raise
    Config.validate(logging.getLogger("test"))


def test_config_allows_client_default_destination(monkeypatch: MonkeyPatch) -> None:
    """Normal setup uses the Download Client's own folder without a path override."""
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", None)
    monkeypatch.setattr(Config, "TESTING", False)
    Config.validate(logging.getLogger("test"))


def test_validate_dl_client_missing(monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
    """Test that Config.validate raises ValueError if DL_CLIENT is missing."""
    monkeypatch.setattr(Config, "DL_CLIENT", None)
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", "/tmp")  # satisfy save path check
    monkeypatch.setattr(Config, "TESTING", False)

    with pytest.raises(ValueError) as exc:
        Config.validate(logging.getLogger("test"))

    assert "Set DL_CLIENT=qbittorrent" in str(exc.value)
    assert "Choose a Download Client" in caplog.text


def test_config_validate_invalid_log_level(monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
    """Ensure validation warns on invalid LOG_LEVEL and defaults to INFO."""
    monkeypatch.setenv("LOG_LEVEL", "INVALID_LEVEL")
    monkeypatch.setattr(Config, "LOG_LEVEL_STR", "INVALID_LEVEL")
    # Patch the internal env variable attribute because Config loads this at import time.
    monkeypatch.setattr(Config, "_log_level_env", "INVALID_LEVEL")

    Config.validate(logging.getLogger("test"))

    assert "Configuration Warning: Invalid LOG_LEVEL 'INVALID_LEVEL' provided" in caplog.text


def test_config_validate_invalid_client_scheme(monkeypatch: MonkeyPatch) -> None:
    """Validate the client-specific scheme with a useful setting name."""
    monkeypatch.setattr(Config, "CLIENT_CONNECTIONS", {"qbittorrent": {"SCHEME": "ftp"}})
    monkeypatch.setattr(Config, "DL_CLIENT", "qbittorrent")
    with pytest.raises(ValueError, match="QBITTORRENT_SCHEME"):
        Config.validate(logging.getLogger("test"))


def test_library_reload_enabled(monkeypatch: MonkeyPatch) -> None:
    """Test that LIBRARY_RELOAD_ENABLED property works correctly."""
    # Case 1: All required vars present
    monkeypatch.setattr(Config, "ABS_URL", "http://abs")
    monkeypatch.setattr(Config, "ABS_KEY", "token")
    monkeypatch.setattr(Config, "ABS_LIB", "lib")

    # Property must be accessed on an instance
    assert Config().LIBRARY_RELOAD_ENABLED is True

    # Case 2: Missing one variable (ABS_URL)
    monkeypatch.setattr(Config, "ABS_URL", None)
    assert Config().LIBRARY_RELOAD_ENABLED is False

    # Case 3: Missing another variable (ABS_KEY)
    monkeypatch.setattr(Config, "ABS_URL", "http://abs")
    monkeypatch.setattr(Config, "ABS_KEY", None)
    assert Config().LIBRARY_RELOAD_ENABLED is False


def test_parse_env_int_success(monkeypatch: MonkeyPatch) -> None:
    """Test parsing a valid integer string."""
    monkeypatch.setenv("TEST_INT", "42")
    # Updated: Use public function name
    assert config.parse_env_int("TEST_INT", 10) == 42


def test_parse_env_int_float_string(monkeypatch: MonkeyPatch) -> None:
    """Test parsing a float string as an integer (Docker/K8s common case)."""
    monkeypatch.setenv("TEST_INT", "42.0")
    # Updated: Use public function name
    assert config.parse_env_int("TEST_INT", 10) == 42


def test_parse_env_int_missing(monkeypatch: MonkeyPatch) -> None:
    """Test fallback to default when env var is missing."""
    monkeypatch.delenv("TEST_INT", raising=False)
    # Updated: Use public function name
    assert config.parse_env_int("TEST_INT", 10) == 10


def test_parse_env_int_invalid(monkeypatch: MonkeyPatch) -> None:
    """Test fallback to default when env var is invalid garbage."""
    monkeypatch.setenv("TEST_INT", "not-a-number")
    # Updated: Use public function name
    assert config.parse_env_int("TEST_INT", 10) == 10


def test_parse_env_int_overflow() -> None:
    """Test parse_env_int handles OverflowError (infinity)."""
    # Mock float() to raise OverflowError
    with patch("builtins.float", side_effect=OverflowError("Inf")):
        val = config.parse_env_int("ANY_KEY", 100)
        assert val == 100


def test_parse_env_int_quoted() -> None:
    """Test parse_env_int handles quoted strings."""
    with patch.dict(os.environ, {"TEST_INT": '"123"', "TEST_FLOAT": '"12.3"'}, clear=True):
        assert config.parse_env_int("TEST_INT", 0) == 123
        assert config.parse_env_int("TEST_FLOAT", 0) == 12
        assert config.parse_env_int("MISSING", 5) == 5


def test_config_parsing_quoted() -> None:
    """Test that Config strips quotes from all string variables."""
    # Since Config attributes are loaded at import time, testing env var influence
    # requires reload.
    env_vars = {
        "SECRET_KEY": '"secret"',
        "STATIC_VERSION": '"v123"',
        "SAVE_PATH_BASE": '"/tmp/data"',
        "ABS_URL": '"http://abs.local"',
        "NAV_LINK_NAME": '"My Link"',
        "DL_CLIENT": '"deluge"',
        "DELUGE_PORT": '"8080"',
        "LOG_LEVEL": '"DEBUG"',
        "ABB_MIRRORS": '"mirror1, mirror2"',
        "MAGNET_TRACKERS": '"tracker1, tracker2"',
        "SITE_TITLE": '"Quoted Title"',
        "SPLASH_MESSAGE": "'Quoted Message'",
        "SITE_LOGO": '"/path/to/logo.png"',
        "SPLASH_VIDEO": '"/path/to/splash.mp4"',
        "SPLASH_VIDEO_WEBM": '"/path/to/splash.webm"',
        "SPLASH_TITLE": "'Quoted Splash Title'",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        importlib.reload(config)
        from audiobook_automated.config import Config as ReloadedConfig

        assert ReloadedConfig.SECRET_KEY == "secret"
        assert ReloadedConfig.STATIC_VERSION == "v123"
        assert ReloadedConfig.SAVE_PATH_BASE == "/tmp/data"
        assert ReloadedConfig.ABS_URL == "http://abs.local"
        assert ReloadedConfig.NAV_LINK_NAME == "My Link"
        assert ReloadedConfig.DL_CLIENT == "deluge"
        assert ReloadedConfig.CLIENT_CONNECTIONS["deluge"]["PORT"] == "8080"
        assert ReloadedConfig.LOG_LEVEL_STR == "DEBUG"
        assert ReloadedConfig.ABB_MIRRORS == ["mirror1", "mirror2"]
        assert ReloadedConfig.MAGNET_TRACKERS == ["tracker1", "tracker2"]
        assert ReloadedConfig.SITE_TITLE == "Quoted Title"
        assert ReloadedConfig.SPLASH_MESSAGE == "Quoted Message"
        assert ReloadedConfig.SITE_LOGO == "/path/to/logo.png"
        assert ReloadedConfig.SPLASH_VIDEO == "/path/to/splash.mp4"
        assert ReloadedConfig.SPLASH_VIDEO_WEBM == "/path/to/splash.webm"
        assert ReloadedConfig.SPLASH_TITLE == "Quoted Splash Title"


def test_config_parsing_defaults() -> None:
    """Test defaults when env vars are missing."""
    with patch.dict(os.environ, {"SAVE_PATH_BASE": "/tmp", "DL_CLIENT": "test"}, clear=True):
        importlib.reload(config)
        from audiobook_automated.config import Config as ReloadedConfig

        assert ReloadedConfig.SECRET_KEY == ""
        assert ReloadedConfig.ABS_URL is None
        assert ReloadedConfig.NAV_LINK_NAME is None
        assert ReloadedConfig.CLIENT_CONNECTIONS == {"test": {}}
        assert ReloadedConfig.SITE_TITLE == DEFAULT_SITE_TITLE
        assert ReloadedConfig.SPLASH_MESSAGE == DEFAULT_SPLASH_MESSAGE
        assert ReloadedConfig.SITE_LOGO == DEFAULT_SITE_LOGO
        assert ReloadedConfig.SPLASH_VIDEO == DEFAULT_SPLASH_VIDEO
        assert ReloadedConfig.SPLASH_VIDEO_WEBM == DEFAULT_SPLASH_VIDEO_WEBM
        assert ReloadedConfig.DEFAULT_THEME == DEFAULT_THEME


def test_parse_asset_path() -> None:
    """Test parse_asset_path normalizes bare filenames while preserving paths and URLs."""
    from audiobook_automated.config import parse_asset_path

    # Defaults and empty cases
    assert parse_asset_path(None, "/default.png") == "/default.png"
    assert parse_asset_path("", "/default.png") == "/default.png"
    assert parse_asset_path("   ", "/default.png") == "/default.png"

    # Bare filenames are prefixed with /static/images/
    assert parse_asset_path("custom-logo.jpg", "/default.png") == "/static/images/custom-logo.jpg"
    assert parse_asset_path('"logo.png"', "/default.png") == "/static/images/logo.png"

    # Existing paths and URLs are preserved
    assert parse_asset_path("/static/images/logo.png", "/default.png") == "/static/images/logo.png"
    assert parse_asset_path("https://example.com/logo.png", "/default.png") == "https://example.com/logo.png"
    assert parse_asset_path("data:image/png;base64,...", "/default.png") == "data:image/png;base64,..."


def test_config_credentials_from_environment() -> None:
    """Load the documented credential settings from the environment."""
    with patch.dict(
        os.environ,
        {
            "TEST_USERNAME": "configured_user",
            "TEST_PASSWORD": "configured_pass",
            "SAVE_PATH_BASE": "/tmp",
            "DL_CLIENT": "test",
        },
        clear=True,
    ):
        importlib.reload(config)
        from audiobook_automated.config import Config as ReloadedConfig

        assert ReloadedConfig.CLIENT_CONNECTIONS["test"]["USERNAME"] == "configured_user"
        assert ReloadedConfig.CLIENT_CONNECTIONS["test"]["PASSWORD"] == "configured_pass"


def test_config_loads_independent_client_connections() -> None:
    """Load the actual Compose environment names without leaking another client's credentials."""
    with patch.dict(
        os.environ,
        {
            "DL_CLIENT": "qbittorrent,deluge,transmission",
            "QBITTORRENT_HOST": "qbit",
            "QBITTORRENT_API_KEY": "test-key",
            "DELUGE_HOST": "deluge",
            "DELUGE_PASSWORD": "deluge-only",
            "DELUGE_PORT": "8112",
            "TRANSMISSION_USERNAME": "tx-user",
            "TRANSMISSION_PASSWORD": "tx-only",
        },
        clear=True,
    ):
        importlib.reload(config)
        loaded = config.Config
        assert loaded.DL_CLIENT == "qbittorrent,deluge,transmission"
        assert loaded.CLIENT_CONNECTIONS == {
            "qbittorrent": {"HOST": "qbit", "API_KEY": "test-key"},
            "deluge": {"HOST": "deluge", "PASSWORD": "deluge-only", "PORT": "8112"},
            "transmission": {"USERNAME": "tx-user", "PASSWORD": "tx-only"},
        }


@pytest.mark.parametrize(
    "values", [{"PORT": "bad"}, {"PORT": "0"}, {"PORT": "65536"}, {"TIMEOUT": "0"}, {"SCHEME": "ftp"}]
)
def test_client_connection_validation(values: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """Reject unusable overrides with the setting name and without credential values."""
    monkeypatch.setattr(Config, "CLIENT_CONNECTIONS", {"deluge": values})
    monkeypatch.setattr(Config, "DL_CLIENT", "deluge")
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", "/downloads")
    with pytest.raises(ValueError, match="DELUGE_"):
        Config.validate(logging.getLogger("test"))


def test_client_names_and_empty_connection_list(monkeypatch: MonkeyPatch) -> None:
    """Explain comma-separated primary values rather than selecting another client."""
    assert config.parse_client_connections(None) == {}
    monkeypatch.setattr(Config, "DL_CLIENT", "qbittorrent,deluge,transmission.")
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", "/downloads")
    with pytest.raises(ValueError, match="DL_CLIENT"):
        Config.validate(logging.getLogger("test"))


def test_putio_only_setup_needs_no_local_folder(monkeypatch: MonkeyPatch) -> None:
    """Cloud-only setup does not require an unused local destination."""
    monkeypatch.setattr(Config, "DL_CLIENT", "putio")
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", None)
    monkeypatch.setattr(Config, "TESTING", False)
    monkeypatch.setattr(Config, "CLIENT_CONNECTIONS", {"putio": {"TOKEN": "isolated-token"}})
    Config.validate(logging.getLogger("test"))


@pytest.mark.parametrize("spelling", ["upper", "lower", "mixed"])
def test_configuration_names_ignore_case(spelling: str) -> None:
    """Case variations work for client settings and ordinary application options."""
    values = {
        "DL_CLIENT": "qbittorrent,deluge,transmission,customcloud",
        "QBITTORRENT_USERNAME": "QbitUser",
        "QBITTORRENT_PASSWORD": "QbitSecretCase",
        "DELUGE_PASSWORD": "DelugeSecretCase",
        "TRANSMISSION_USERNAME": "TransmissionUser",
        "TRANSMISSION_PASSWORD": "TransmissionSecretCase",
        "CUSTOMCLOUD_TOKEN": "CustomTokenCase",
        "CUSTOMCLOUD_SAVE_PATH_BASE": "/CaseSensitive/Books",
        "SITE_TITLE": "Mixed Case Title",
        "SPLASH_ENABLED": "false",
        "CLIENT_TIMEOUT": "17",
    }

    def rename(key: str) -> str:
        if spelling == "upper":
            return key
        if spelling == "lower":
            return key.lower()
        supplied_names = {
            "QBITTORRENT_USERNAME": "qbittorrent_UserNAmE",
            "QBITTORRENT_PASSWORD": "qbittorrent_PASSWORD",
            "DELUGE_PASSWORD": "deluge_PASSWORD",
            "TRANSMISSION_USERNAME": "transmission_USERNAME",
            "TRANSMISSION_PASSWORD": "transmission_PassWoRD",
        }
        return supplied_names.get(
            key, "".join(char.lower() if index % 2 else char.upper() for index, char in enumerate(key))
        )

    with patch.dict(os.environ, {rename(key): value for key, value in values.items()}, clear=True):
        importlib.reload(config)
        loaded = config.Config
        loaded.validate(logging.getLogger("test"))
        assert loaded.CLIENT_CONNECTIONS["qbittorrent"]["USERNAME"] == "QbitUser"
        assert loaded.CLIENT_CONNECTIONS["qbittorrent"]["PASSWORD"] == "QbitSecretCase"
        assert loaded.CLIENT_CONNECTIONS["deluge"]["PASSWORD"] == "DelugeSecretCase"
        assert loaded.CLIENT_CONNECTIONS["transmission"]["PASSWORD"] == "TransmissionSecretCase"
        assert loaded.CLIENT_CONNECTIONS["customcloud"]["TOKEN"] == "CustomTokenCase"
        assert loaded.CLIENT_CONNECTIONS["customcloud"]["SAVE_PATH_BASE"] == "/CaseSensitive/Books"
        assert loaded.SITE_TITLE == "Mixed Case Title"
        assert loaded.SPLASH_ENABLED is False
        assert loaded.CLIENT_TIMEOUT == 17


def test_duplicate_setting_spellings_are_unambiguous() -> None:
    """Identical duplicates are safe; differing secrets fail without leaking either value."""
    from audiobook_automated.environment import get_env

    with patch.dict(os.environ, {"Client_Password": "SecretOne", "CLIENT_PASSWORD": "SecretOne"}, clear=True):
        assert get_env("client_password") == "SecretOne"
        assert get_env("missing") is None
        assert get_env("missing", "fallback") == "fallback"
    with patch.dict(os.environ, {"Client_Password": "SecretOne", "CLIENT_PASSWORD": "SecretTwo"}, clear=True):
        with pytest.raises(ValueError, match="CLIENT_PASSWORD") as error:
            get_env("CLIENT_PASSWORD")
        assert "Remove the duplicate" in str(error.value)
        assert "SecretOne" not in str(error.value)
        assert "SecretTwo" not in str(error.value)


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("https://Books.Example/", "https://books.example"),
        ("http://books.local:80", "http://books.local"),
        ("https://books.example:443", "https://books.example"),
        ("https://books.example:8443", "https://books.example:8443"),
        ("http://[::1]:5078/", "http://[::1]:5078"),
    ],
)
def test_public_url_normalization(value: str | None, expected: str | None) -> None:
    """Accept a single public origin with sensible default port normalization."""
    from audiobook_automated.web_security import parse_public_url

    assert parse_public_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "books.example",
        "ftp://books.example",
        "https://",
        "https://user:secret@books.example",
        "https://books.example/books",
        "https://books.example/?query=1",
        "https://books.example/#fragment",
        "https://books.example:bad",
        "https://books.example:0",
        "https://books.example:65536",
        "http://[bad",
        "https://book s.example",
        "https://books.example\nforged",
        "https://books%65.example",
        "https://books|example",
        "https://books\\example",
    ],
)
def test_public_url_rejects_invalid_or_ambiguous_origins(value: str) -> None:
    """Invalid site addresses fail clearly without exposing credentials in the error."""
    from audiobook_automated.web_security import parse_public_url

    with pytest.raises(ValueError, match="PUBLIC_URL") as error:
        parse_public_url(value)
    assert "secret" not in str(error.value)


def test_proxy_allowlist_validation() -> None:
    """No proxies are trusted by default; explicit IPs and networks are accepted."""
    from audiobook_automated.web_security import parse_trusted_proxies

    assert parse_trusted_proxies(None) == ()
    assert [str(item) for item in parse_trusted_proxies("10.0.0.5, 2001:db8::/64")] == ["10.0.0.5/32", "2001:db8::/64"]
    with pytest.raises(ValueError, match="TRUSTED_PROXIES"):
        parse_trusted_proxies("*")


@pytest.mark.parametrize(
    ("name", "values", "expected"),
    [
        ("qbittorrent", {}, "QBITTORRENT_USERNAME and QBITTORRENT_PASSWORD"),
        ("qbittorrent", {"USERNAME": "private-user"}, "Set QBITTORRENT_PASSWORD"),
        ("qbittorrent", {"PASSWORD": "private-secret"}, "Set QBITTORRENT_USERNAME"),
        ("qbittorrent", {"USERNAME": "private-user", "PASSWORD": "private-secret"}, ""),
        ("qbittorrent", {"API_KEY": "private-secret"}, ""),
        ("deluge", {}, "Set DELUGE_PASSWORD"),
        ("deluge", {"PASSWORD": "private-secret"}, ""),
        ("putio", {}, "Set PUTIO_TOKEN"),
        ("putio", {"TOKEN": "private-secret"}, ""),
        ("transmission", {"USERNAME": "private-user"}, "Set TRANSMISSION_PASSWORD"),
        ("transmission", {"PASSWORD": "private-secret"}, "Set TRANSMISSION_USERNAME"),
        ("transmission", {}, ""),
        ("transmission", {"USERNAME": "private-user", "PASSWORD": "private-secret"}, ""),
        ("custom_plugin", {}, ""),
    ],
)
def test_client_setup_messages(name: str, values: dict[str, str], expected: str, caplog: LogCaptureFixture) -> None:
    """Incomplete credentials name the correction without leaking secrets or blocking startup."""
    from audiobook_automated.config import log_client_setup

    log_client_setup({name: values}, logging.getLogger("test"))
    if expected:
        assert expected in caplog.text
    else:
        assert not caplog.text
    assert "private-user" not in caplog.text
    assert "private-secret" not in caplog.text
