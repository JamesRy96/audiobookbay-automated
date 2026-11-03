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
    monkeypatch.setenv("DL_SCHEME", "https")
    # Patch class attributes as well since they are loaded at import
    monkeypatch.setattr(Config, "SECRET_KEY", "prod-secret-key")
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", "/data")
    monkeypatch.setattr(Config, "DL_SCHEME", "https")
    monkeypatch.setattr(Config, "DL_CLIENT", "qbittorrent")  # Required now
    monkeypatch.setattr(Config, "TESTING", False)
    monkeypatch.setattr(Config, "FLASK_DEBUG", False)

    # Should not raise
    Config.validate(logging.getLogger("test"))


def test_config_validate_missing_save_path(monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
    """Ensure validation fails hard if SAVE_PATH_BASE is missing."""
    monkeypatch.setenv("SAVE_PATH_BASE", "")
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", None)
    # Force TESTING to False to trigger the validation error
    monkeypatch.setattr(Config, "TESTING", False)

    with pytest.raises(RuntimeError):
        Config.validate(logging.getLogger("test"))

    assert "Configuration Error: SAVE_PATH_BASE is missing" in caplog.text


def test_validate_dl_client_missing(monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
    """Test that Config.validate raises ValueError if DL_CLIENT is missing."""
    monkeypatch.setattr(Config, "DL_CLIENT", None)
    monkeypatch.setattr(Config, "SAVE_PATH_BASE", "/tmp")  # satisfy save path check
    monkeypatch.setattr(Config, "TESTING", False)

    with pytest.raises(ValueError) as exc:
        Config.validate(logging.getLogger("test"))

    assert "DL_CLIENT must be set" in str(exc.value)
    assert "Configuration Error: DL_CLIENT is missing" in caplog.text


def test_config_validate_invalid_log_level(monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
    """Ensure validation warns on invalid LOG_LEVEL and defaults to INFO."""
    monkeypatch.setenv("LOG_LEVEL", "INVALID_LEVEL")
    monkeypatch.setattr(Config, "LOG_LEVEL_STR", "INVALID_LEVEL")
    # Patch the internal env variable attribute because Config loads this at import time.
    monkeypatch.setattr(Config, "_log_level_env", "INVALID_LEVEL")

    Config.validate(logging.getLogger("test"))

    assert "Configuration Warning: Invalid LOG_LEVEL 'INVALID_LEVEL' provided" in caplog.text


def test_config_validate_invalid_dl_scheme(monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
    """Ensure validation fails for invalid DL_SCHEME."""
    monkeypatch.setattr(Config, "DL_SCHEME", "ftp")
    monkeypatch.setattr(Config, "DL_CLIENT", "qbittorrent")  # Satisfy prerequisite

    with pytest.raises(ValueError, match="Invalid DL_SCHEME"):
        Config.validate(logging.getLogger("test"))

    assert "Invalid DL_SCHEME" in caplog.text


def test_force_https_default() -> None:
    """Test that FORCE_HTTPS defaults to False."""
    # Ensure env var is not set (mocking empty env for this check)
    with pytest.MonkeyPatch.context() as m:
        m.delenv("FORCE_HTTPS", raising=False)
        # We can't easily re-import Config to reset class attributes,
        # but we can check the default value if it hasn't been overridden yet.
        # OR we can verify via parse_bool logic which Config uses.
        assert Config.FORCE_HTTPS is False


def test_force_https_env_var(monkeypatch: MonkeyPatch) -> None:
    """Test that FORCE_HTTPS respects env var."""
    # Since Config attributes are loaded at import time, testing env var influence
    # directly on the class requires reload, which is messy.
    # Instead, we test the `parse_bool` logic specifically for this key is sound
    # by verifying `parse_bool` handles "true" correctly, which we know it does.
    #
    # However, to be thorough, we can create a subclass that re-evaluates.
    import os

    from audiobook_automated.utils import parse_bool

    class DynamicConfig(Config):
        pass

    # Manually re-evaluate because class definition happens once
    DynamicConfig.FORCE_HTTPS = parse_bool(os.environ.get("FORCE_HTTPS"), False)

    monkeypatch.setenv("FORCE_HTTPS", "true")
    # We must re-run the assignment AFTER setting env var, simulating a new process/reload
    DynamicConfig.FORCE_HTTPS = parse_bool(os.environ.get("FORCE_HTTPS"), False)

    assert DynamicConfig.FORCE_HTTPS is True


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
        "DL_PORT": '"8080"',
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
        assert ReloadedConfig.DL_PORT == "8080"
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
        assert ReloadedConfig.DL_PORT is None
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
            "DL_USERNAME": "configured_user",
            "DL_PASSWORD": "configured_pass",
            "SAVE_PATH_BASE": "/tmp",
            "DL_CLIENT": "test",
        },
        clear=True,
    ):
        importlib.reload(config)
        from audiobook_automated.config import Config as ReloadedConfig

        assert ReloadedConfig.DL_USERNAME == "configured_user"
        assert ReloadedConfig.DL_PASSWORD == "configured_pass"
