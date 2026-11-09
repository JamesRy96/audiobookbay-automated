# File: tests/unit/test_logging.py
"""Unit tests for logging configuration."""

# pyright: reportPrivateUsage=false

import logging
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

# Import the private function to be tested
from audiobook_automated import _configure_logging


class TestLoggingConfiguration(unittest.TestCase):
    """Test suite for application logging configuration."""

    def test_configure_logging_inherits_gunicorn(self) -> None:
        """Test that _configure_logging inherits Gunicorn handlers and level."""
        app = Flask(__name__)
        # Default flask logger usually has 1 handler or 0 depending on setup, reset it
        app.logger.handlers = []
        app.logger.setLevel(logging.INFO)

        # Mock Gunicorn logger
        mock_gunicorn = MagicMock()
        mock_handler = MagicMock()
        mock_handler.level = logging.INFO  # Ensure handler has a valid level
        mock_gunicorn.handlers = [mock_handler]
        mock_gunicorn.level = logging.ERROR

        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value = mock_gunicorn

            # Call function under test
            _configure_logging(app, configured_level=None)

            # Assertions
            mock_get_logger.assert_called_with("gunicorn.error")
            self.assertEqual(app.logger.handlers, [mock_handler])
            self.assertEqual(app.logger.level, logging.ERROR)

    def test_configure_logging_override_level(self) -> None:
        """Test that configured_level overrides Gunicorn level."""
        app = Flask(__name__)
        app.logger.handlers = []

        mock_gunicorn = MagicMock()
        mock_handler = MagicMock()
        mock_handler.level = logging.INFO  # Ensure handler has a valid level
        mock_gunicorn.handlers = [mock_handler]
        mock_gunicorn.level = logging.ERROR

        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value = mock_gunicorn

            # Call with explicit debug level
            _configure_logging(app, configured_level=logging.DEBUG)

            self.assertEqual(app.logger.handlers, [mock_handler])
            # Should be DEBUG (10) not ERROR (40)
            self.assertEqual(app.logger.level, logging.DEBUG)

    def test_configure_logging_no_gunicorn(self) -> None:
        """Test fallback when Gunicorn logger has no handlers (local dev)."""
        app = Flask(__name__)
        app.logger.handlers = []

        mock_gunicorn = MagicMock()
        mock_gunicorn.handlers = []  # No handlers

        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value = mock_gunicorn

            _configure_logging(app, configured_level=logging.WARNING)

            # Handlers should remain empty (or default) - technically function doesn't touch handlers if gunicorn has none
            # It just sets level
            self.assertEqual(app.logger.level, logging.WARNING)
