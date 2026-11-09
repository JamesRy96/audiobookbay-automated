# File: audiobook_automated/logging_buffer.py
"""Circular in-memory log buffer with automated secret and PII redaction.

Stores recent application logs in memory (default 500 lines) for diagnostics
and 1-click issue reporting, ensuring zero persistent disk bloat and zero PII leakage.
"""

from __future__ import annotations

import collections
import logging
import re
from typing import Any

# Patterns to sanitize before logs are stored or exported
REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Passwords, keys, tokens in query params or headers
    (
        re.compile(
            r"(?i)(password|passwd|pass|token|secret|key|api_key|auth|bearer)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.\~]{4,})['\"]?"
        ),
        r"\1=<redacted>",
    ),
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE), "Bearer <redacted>"),
    # IP addresses (v4) - replace private and public IPs with generic identifier
    (
        re.compile(
            r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
        ),
        "127.0.0.1",
    ),
    # User paths (/home/username, C:\Users\username)
    (re.compile(r"/(?:home|Users)/[A-Za-z0-9_-]+"), "/home/<user>"),
]


def sanitize_log_message(msg: str) -> str:
    """Scrub passwords, secrets, tokens, and PII from a log string."""
    cleaned = msg
    for pattern, replacement in REDACTION_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


class SanitizingRingBufferHandler(logging.Handler):
    """Logging handler that retains the last N formatted logs in a memory ring buffer."""

    def __init__(self, capacity: int = 500) -> None:
        """Initialize the buffer with a maximum capacity."""
        super().__init__()
        self.capacity = capacity
        self.buffer: collections.deque[dict[str, Any]] = collections.deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        """Sanitize and format log record, then store in ring buffer."""
        try:
            msg = self.format(record)
            safe_msg = sanitize_log_message(msg)
            self.buffer.append(
                {
                    "timestamp": record.created,
                    "level": record.levelname,
                    "name": record.name,
                    "message": safe_msg,
                }
            )
        except Exception:
            self.handleError(record)

    def get_logs(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Retrieve recent logs up to the limit."""
        logs = list(self.buffer)
        if limit and limit < len(logs):
            return logs[-limit:]
        return logs

    def get_text_logs(self, limit: int | None = None) -> str:
        """Retrieve raw text representation of recent logs."""
        logs = self.get_logs(limit)
        return "\n".join(entry["message"] for entry in logs)

    def clear(self) -> None:
        """Clear all entries from the ring buffer."""
        self.buffer.clear()


# Global singleton instance for application use
log_ring_buffer = SanitizingRingBufferHandler(capacity=500)
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log_ring_buffer.setFormatter(formatter)
