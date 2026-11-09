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


def test_startup_uses_client_default_folder(monkeypatch: Any, mock_flask_factory: Any) -> None:
    """An app without a save-path override starts normally."""
    _, mock_logger = mock_flask_factory
    monkeypatch.delenv("SAVE_PATH_BASE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    with patch("audiobook_automated.extensions.torrent_manager") as manager:
        manager.verify_credentials.return_value = True
        importlib.reload(audiobook_automated.config)
        importlib.reload(audiobook_automated)
        audiobook_automated.create_app()
    mock_logger.critical.assert_not_called()


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


def test_startup_never_connects_to_download_clients() -> None:
    """A blocked or offline Download Client must not prevent the web server starting."""
    from audiobook_automated.extensions import torrent_manager

    with patch.object(
        torrent_manager, "verify_credentials", side_effect=AssertionError("Startup attempted a connection")
    ) as verify:
        app = audiobook_automated.create_app(StartupConfig)

    assert app is not None
    verify.assert_not_called()


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
