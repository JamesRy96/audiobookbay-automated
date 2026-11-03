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
