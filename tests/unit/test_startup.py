# File: tests/unit/test_startup.py
"""Unit tests for startup configuration and verification logic."""

import importlib
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import audiobook_automated
import audiobook_automated.config


class MockConfig(dict[str, Any]):
    """A dictionary that behaves like a Flask config object (supporting from_object)."""

    def from_object(self, obj: Any) -> None:
        """Emulate Flask config.from_object by reading uppercase attributes."""
        for key in dir(obj):
            if key.isupper():
                self[key] = getattr(obj, key)


@pytest.fixture
def mock_flask_factory() -> Generator[tuple[Any, Any]]:
    """Patch Flask class to return a mock app with a traceable logger and working config."""
    with patch("flask.Flask") as mock_class:
        mock_app = MagicMock()
        mock_logger = MagicMock()
        mock_app.logger = mock_logger

        # Use a real dict-like object so it passes isinstance(config, dict)
        mock_config = MockConfig()
        mock_app.config = mock_config

        mock_class.return_value = mock_app
        yield mock_class, mock_logger

    # --- TEARDOWN ---
    # Restore the app module to a clean state to prevent pollution between tests.
    safe_env = {
        "TESTING": "1",
        "SAVE_PATH_BASE": "/tmp/startup_test_safe_restore",
        "SECRET_KEY": "startup_test_safe_key",
        "FLASK_DEBUG": "0",
        "LOG_LEVEL": "INFO",
    }

    # Reload modules to restore original state
    with patch.dict(os.environ, safe_env):
        # Do not use sys.modules.pop(), it causes ImportError on reload.
        importlib.reload(audiobook_automated.config)
        importlib.reload(audiobook_automated)

        if "audiobook_automated.app" in sys.modules:
            importlib.reload(sys.modules["audiobook_automated.app"])
        else:
            importlib.import_module("audiobook_automated.app")


def test_startup_missing_save_path(monkeypatch: Any, mock_flask_factory: Any) -> None:
    """Ensure startup fails with critical error if SAVE_PATH_BASE is missing."""
    _, mock_logger = mock_flask_factory

    # Updated: Expect RuntimeError instead of SystemExit (Gunicorn safety improvement)
    monkeypatch.delenv("SAVE_PATH_BASE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)

    # Patch torrent_manager inside this test scope because reloading modules
    # resets module-level patches.
    with patch("audiobook_automated.extensions.torrent_manager") as mock_tm:
        mock_tm.verify_credentials.return_value = True

        with pytest.raises(RuntimeError) as excinfo:
            importlib.reload(audiobook_automated.config)
            importlib.reload(audiobook_automated)
            if "audiobook_automated.app" in sys.modules:
                importlib.reload(sys.modules["audiobook_automated.app"])
            else:
                importlib.import_module("audiobook_automated.app")

    assert "Configuration Error: SAVE_PATH_BASE is missing" in str(excinfo.value)
    args, _ = mock_logger.critical.call_args
    assert "Configuration Error: SAVE_PATH_BASE is missing" in args[0]


def test_startup_invalid_log_level(monkeypatch: Any, mock_flask_factory: Any) -> None:
    """Ensure startup warns on invalid LOG_LEVEL."""
    _, mock_logger = mock_flask_factory
    monkeypatch.setenv("SAVE_PATH_BASE", "/tmp")
    monkeypatch.setenv("LOG_LEVEL", "INVALID_LEVEL")

    importlib.reload(audiobook_automated.config)
    audiobook_automated.config.Config.validate(mock_logger)

    args, _ = mock_logger.warning.call_args
    assert "Configuration Warning: Invalid LOG_LEVEL" in args[0]


def test_create_app_calculates_runtime_static_version(monkeypatch: Any, mock_flask_factory: Any) -> None:
    """Test that create_app computes STATIC_VERSION at runtime via calculate_static_hash."""
    mock_class, _ = mock_flask_factory

    # Reload app module so it imports the patched Flask class from the fixture.
    # Without this, app.create_app() uses the real Flask class, causing the mock assertions to fail.
    importlib.reload(audiobook_automated)

    mock_app = mock_class.return_value
    mock_app.root_path = "/mock/root"

    # Ensure environment is valid for create_app
    monkeypatch.setenv("SAVE_PATH_BASE", "/tmp/test")

    expected_hash = "runtime-hash-123"

    with (
        patch("audiobook_automated.utils.calculate_static_hash", return_value=expected_hash) as mock_calc,
        # Patch torrent_manager to prevent a real connection attempt during startup
        patch("audiobook_automated.extensions.torrent_manager") as mock_torrent_manager,
    ):
        # Mock the verify_credentials return to avoid warnings
        mock_torrent_manager.verify_credentials.return_value = True

        # Call create_app directly
        audiobook_automated.create_app()

        assert mock_app.config["STATIC_VERSION"] == expected_hash
        mock_calc.assert_called_once()


def test_app_entry_point() -> None:
    """Ensures the app module can be imported and the global app instance is created.

    Reloading ensures coverage captures the top-level code execution.
    """
    # Use sys.modules to get the already-loaded module object so importlib.reload() works correctly
    # Check if loaded, if not import it
    if "audiobook_automated.app" not in sys.modules:
        importlib.import_module("audiobook_automated.app")

    # Patch here as well to prevent real connection on reload
    with patch("audiobook_automated.extensions.torrent_manager") as mock_tm:
        mock_tm.verify_credentials.return_value = True
        reloaded_module = importlib.reload(sys.modules["audiobook_automated.app"])

    # Verify that the module contains the 'app' variable (the Flask instance)
    assert reloaded_module.app is not None


# --- New Tests added for Coverage Cleanup ---


class StartupConfig(audiobook_automated.config.Config):
    """Configuration for startup tests."""

    TESTING = True
    DL_CLIENT = "qbittorrent"


def test_startup_connection_warning(caplog: Any) -> None:
    """Test that a warning is logged if the torrent client is unreachable at startup.

    This covers the `if not torrent_manager.verify_credentials():` block in __init__.py.
    """
    # We patch verify_credentials directly on the global instance
    # because create_app uses the global instance.
    from audiobook_automated.extensions import torrent_manager

    with patch.object(torrent_manager, "verify_credentials", return_value=False):
        # We also need to patch init_app to prevent it from trying to load plugins if we don't want to test that here
        # But we do want init_app to run to set up the client_type, so we assume it works or mock it?
        # If we use StartupConfig with DL_CLIENT, init_app will try to load plugin.
        # We should probably mock init_app to do nothing, but verify_credentials depends on it?
        # verify_credentials calls get_client.
        # It's simpler to just force verify_credentials to False.

        audiobook_automated.create_app(StartupConfig)

        # Assert the warning was logged
        assert "Startup Check: Torrent client is NOT connected" in caplog.text


def test_startup_connection_success(caplog: Any) -> None:
    """Test that no warning is logged if the torrent client connects."""
    from audiobook_automated.extensions import torrent_manager

    with patch.object(torrent_manager, "verify_credentials", return_value=True):
        audiobook_automated.create_app(StartupConfig)

        # Assert the warning was NOT logged
        assert "Startup Check: Torrent client is NOT connected" not in caplog.text


def test_entrypoint_environment_compatibility() -> None:
    """Test that environment variables exported in entrypoint.sh allow Python to initialize cleanly.

    Catches unsupported runtime flags (such as PYTHON_GIL on standard CPython builds).
    """
    entrypoint_path = Path(__file__).resolve().parents[2] / "entrypoint.sh"
    assert entrypoint_path.is_file(), f"entrypoint.sh not found at {entrypoint_path}"

    content = entrypoint_path.read_text(encoding="utf-8")
    env = os.environ.copy()

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("export ") and "=" in line:
            var_part = line[len("export ") :].strip()
            key, val = var_part.split("=", 1)
            val = val.strip("'\"")
            if ":-" in val:
                val = val.split(":-")[-1].rstrip("}")
            env[key] = val

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Python failed to initialize with entrypoint env: {result.stderr}"
