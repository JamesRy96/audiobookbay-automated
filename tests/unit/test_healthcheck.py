# File: tests/unit/test_healthcheck.py
"""Unit tests for the healthcheck script."""

from unittest.mock import MagicMock, patch

import pytest

from audiobook_automated.healthcheck import health_check


def test_health_check_success() -> None:
    """Test that health_check exits with 0 on HTTP 200."""
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_open.return_value.__enter__.return_value = mock_resp

        with pytest.raises(SystemExit) as e:
            health_check()
        assert e.value.code == 0


def test_health_check_failure_status(caplog: pytest.LogCaptureFixture) -> None:
    """Test that health_check exits with 1 on non-200 HTTP status and logs to stderr."""
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_open.return_value.__enter__.return_value = mock_resp

        with pytest.raises(SystemExit) as e:
            health_check()
        assert e.value.code == 1

    assert "Health check failed with status: 500" in caplog.text


def test_health_check_exception(caplog: pytest.LogCaptureFixture) -> None:
    """Test that health_check exits with 1 on connection exception and logs to stderr."""
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        with pytest.raises(SystemExit) as e:
            health_check()
        assert e.value.code == 1

    assert "Health check failed: Connection refused" in caplog.text


@pytest.mark.parametrize(
    "env_host, expected_url_host",
    [
        ("0.0.0.0", "127.0.0.1"),
        ("[::]", "[::1]"),
        ("192.168.1.5", "192.168.1.5"),
    ],
)
def test_health_check_host_logic(env_host: str, expected_url_host: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test URL construction based on LISTEN_HOST environment variable.

    Ensures 0.0.0.0 and [::] are converted to localhost for local checks.
    """
    monkeypatch.setenv("LISTEN_HOST", env_host)
    # Set a port to ensure full URL construction verification
    monkeypatch.setenv("LISTEN_PORT", "5000")

    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_open.return_value.__enter__.return_value = mock_resp

        with pytest.raises(SystemExit) as e:
            health_check()

        assert e.value.code == 0

        # Verify that urlopen was called with the correctly formatted URL
        args, _ = mock_open.call_args
        assert args[0] == f"http://{expected_url_host}:5000/health"


def test_container_healthcheck_accepts_mixed_case_listen_settings() -> None:
    """Execute the actual container probe against a local server using its mixed-case port."""
    import os
    import subprocess
    import sys
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from pathlib import Path
    from threading import Thread
    from typing import override

    paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        """Serve only the local app health endpoint for this isolated subprocess check."""

        def do_GET(self) -> None:  # noqa: N802
            """Record the probe and return a successful local response."""
            paths.append(self.path)
            self.send_response(200 if self.path == "/health" else 404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        @override
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            """Keep isolated request details out of test output."""

    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    root = Path(__file__).resolve().parents[2]
    environment = {
        name: value for name, value in os.environ.items() if name.upper() not in {"LISTEN_HOST", "LISTEN_PORT"}
    }
    environment.update(listen_HOST="127.0.0.1", Listen_Port=str(server.server_port), NO_PROXY="127.0.0.1")
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(root / "audiobook_automated/healthcheck.py"),
            ],
            check=False,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert paths == ["/health"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
