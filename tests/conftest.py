# File: tests/conftest.py
"""Global pytest fixtures and configuration for the test suite.

This module defines the 'World' in which tests run, including the Flask application
instance, test clients, and global configuration overrides.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from flask import Flask
from flask.testing import FlaskClient, FlaskCliRunner

from audiobook_automated import create_app

# Import the class for safer patching if needed, though patching instance usually works
from audiobook_automated.config import Config
from audiobook_automated.extensions import torrent_manager


class TestConfig(Config):
    """Test configuration with overrides.

    Passed to create_app to ensure extensions (like Flask-Limiter)
    pick up settings during their init_app() phase.
    """

    TESTING = True
    # Use system temp directory instead of hardcoded /tmp for cross-platform compatibility
    # (prevents permission issues or creation of C:\tmp on Windows).
    SAVE_PATH_BASE = os.path.join(tempfile.gettempdir(), "test_downloads")
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False

    # Enable Rate Limit headers for assertions
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_ENABLED = True

    # Prevent real connections in config
    CLIENT_CONNECTIONS = {"qbittorrent": {"HOST": "mock_localhost"}}


@pytest.fixture(autouse=True)
def mock_global_dependencies() -> Generator[None]:
    """Isolate the test suite from the real world.

    This fixture runs automatically for every test. It mocks the heavy
    lifters (TorrentManager) to prevent the application from trying to
    connect to a real torrent client during startup (verify_credentials)
    or request handling.
    """
    # Patch the methods on the REAL instance object directly.
    # Patching the module attribute ("audiobook_automated.extensions.torrent_manager")
    # fails because other modules (like __init__.py and routes.py) have already
    # imported the real instance reference before this fixture runs.
    # By modifying the instance in-place, all references see the mocks.

    # We patch the instance methods. create=True is used to ensure that if the
    # method is missing (due to some import weirdness or dynamic loading), it is created,
    # satisfying the test requirements.
    with patch.object(torrent_manager, "verify_credentials", return_value=True):
        with patch.object(torrent_manager, "get_status", return_value=[]):
            with patch.object(torrent_manager, "add_magnet", return_value="OK", create=True):
                with patch.object(torrent_manager, "remove_torrent", return_value="OK"):
                    # Mock init_app to prevent real connection attempts
                    with patch.object(torrent_manager, "init_app"):
                        with patch("audiobook_automated.routes.get_book_details", return_value=None):
                            yield


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[Any]:
    """Globally mock time.sleep for ALL tests to speed up execution.

    Moved here from tests/scraper/conftest.py to ensure Functional and Unit
    tests also benefit from zero-delay sleeps (e.g. when testing search routes).
    """
    with patch("time.sleep") as mock_sleep:
        yield mock_sleep


@pytest.fixture
def app(mock_global_dependencies: None) -> Generator[Flask]:
    """Create the 'World' for the tests: A Flask application instance.

    Uses TestConfig to ensure configuration is present before extension initialization.
    Explicitly depends on mock_global_dependencies to ensure TorrentManager is mocked
    before create_app triggers the startup connection check.
    """
    app = create_app(TestConfig)
    yield app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """The observer within the world: A test client to make requests."""
    return app.test_client()


@pytest.fixture
def runner(app: Flask) -> FlaskCliRunner:
    """A CLI runner for command-line context."""
    return app.test_cli_runner()


@pytest.fixture(autouse=True)
def push_app_context(app: Flask) -> Generator[None]:
    """Automatically push application and request context for all tests."""
    with app.app_context(), app.test_request_context():
        yield
