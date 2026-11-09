# File: tests/unit/test_logging_buffer.py
"""Unit tests for the sanitizing ring buffer logging handler."""

import logging
from unittest.mock import MagicMock

from audiobook_automated.logging_buffer import SanitizingRingBufferHandler, sanitize_log_message


def test_sanitize_log_message_secrets() -> None:
    """Test scrubbing of passwords, tokens, and authorization headers."""
    raw = "User login password='SuperSecret123' token=abcde12345 api_key=xyz987654321"
    clean = sanitize_log_message(raw)
    assert "SuperSecret123" not in clean
    assert "abcde12345" not in clean
    assert "xyz987654321" not in clean
    assert "password=<redacted>" in clean

    bearer_raw = "Request with Bearer eyJhbGciOiJIUzI1NiJ9.test"
    bearer_clean = sanitize_log_message(bearer_raw)
    assert "eyJhbGci" not in bearer_clean
    assert "Bearer <redacted>" in bearer_clean


def test_sanitize_log_message_ips_and_paths() -> None:
    """Test scrubbing of internal IP addresses and home paths."""
    raw = "Connecting from 192.168.1.100 to /home/runner/work/app and /Users/developer/code"
    clean = sanitize_log_message(raw)
    assert "192.168.1.100" not in clean
    assert "127.0.0.1" in clean
    assert "/home/runner" not in clean
    assert "/Users/developer" not in clean
    assert "/home/<user>" in clean


def test_ring_buffer_capacity() -> None:
    """Test capacity enforcement of the ring buffer."""
    handler = SanitizingRingBufferHandler(capacity=3)
    logger = logging.getLogger("test_buffer")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    for i in range(5):
        logger.info(f"Message {i}")

    logs = handler.get_logs()
    assert len(logs) == 3
    assert logs[0]["message"] == "Message 2"
    assert logs[2]["message"] == "Message 4"

    text = handler.get_text_logs()
    assert "Message 2" in text
    assert "Message 0" not in text

    # Test limit filter
    assert len(handler.get_logs(limit=2)) == 2


def test_ring_buffer_error_handling() -> None:
    """Test that formatting exceptions call handleError without crashing."""
    handler = SanitizingRingBufferHandler(capacity=10)
    mock_record = MagicMock(spec=logging.LogRecord)
    handler.format = MagicMock(side_effect=Exception("Format error"))  # type: ignore[method-assign]
    handler.handleError = MagicMock()  # type: ignore[method-assign]

    handler.emit(mock_record)
    handler.handleError.assert_called_once_with(mock_record)

    # Test clear
    handler.clear()
    assert len(handler.get_logs()) == 0
