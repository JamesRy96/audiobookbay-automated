# File: tests/unit/test_container_entrypoint.py
"""Verify container startup boundaries without root access or a Docker daemon."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name == "nt" or shutil.which("sh") is None, reason="The container entrypoint uses a POSIX shell")
@pytest.mark.parametrize("mixed_case", [False, True])
@pytest.mark.parametrize("host,port", [("0.0.0.0", "5078"), ("[::]", "5088"), ("127.0.0.1", "5099")])
def test_entrypoint_keeps_one_worker_and_does_not_change_download_folder(
    tmp_path: Path, host: str, port: str, mixed_case: bool
) -> None:
    """Preserve the client's directory ownership and the single-worker invariant."""
    commands = tmp_path / "bin"
    commands.mkdir()
    for command in ["groupmod", "usermod"]:
        path = commands / command
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    launcher = commands / "gosu"
    launcher.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$ENTRYPOINT_ARGS"\nprintf "%s\\n" "$TZ" > "$ENTRYPOINT_TZ"\n'
    )
    launcher.chmod(0o755)
    chown = commands / "chown"
    chown.write_text('#!/bin/sh\ntouch "$CHOWN_CALLED"\n')
    chown.chmod(0o755)
    destination = tmp_path / "client-downloads"
    destination.mkdir()
    recorded = tmp_path / "arguments"
    changed = tmp_path / "ownership-changed"
    environment = {
        **os.environ,
        "PATH": str(commands) + os.pathsep + os.environ["PATH"],
        "LISTEN_HOST": host,
        "LISTEN_PORT": port,
        "THREADS": "8",
        "SAVE_PATH_BASE": str(destination),
        "ENTRYPOINT_ARGS": str(recorded),
        "CHOWN_CALLED": str(changed),
    }
    evaluated = tmp_path / "evaluated-shell-code"
    timezone = "UTC$(touch " + str(evaluated) + ")"
    environment.update(
        PUID="1234",
        PGID="2345",
        TIMEOUT="45",
        LOG_LEVEL="DEBUG",
        TZ=timezone,
        ENTRYPOINT_TZ=str(tmp_path / "timezone"),
        TMPDIR=str(tmp_path),
    )
    if mixed_case:
        for key in ["LISTEN_HOST", "LISTEN_PORT", "THREADS", "PUID", "PGID", "TIMEOUT", "LOG_LEVEL"]:
            environment[key.swapcase()] = environment.pop(key)
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["sh", str(root / "entrypoint.sh"), "--workers", "3"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "UID=1234, GID=2345" in result.stdout
    assert "log level debug" in result.stdout
    arguments = recorded.read_text().splitlines()
    assert arguments[arguments.index("--bind") + 1] == f"{host}:{port}"
    assert arguments.count("--workers") == 1
    assert arguments[arguments.index("--workers") + 1] == "1"
    assert arguments[arguments.index("--threads") + 1] == "8"
    assert arguments[arguments.index("--timeout") + 1] == "45"
    assert arguments[-1] == "audiobook_automated.app:app"
    assert not changed.exists()
    assert not evaluated.exists()
    assert (tmp_path / "timezone").read_text().strip() == timezone
    assert not list(tmp_path.glob("tmp.*"))


def test_startup_exports_preserve_values_without_changing_process_environment() -> None:
    """Emit literal records only for startup keys and leave unrelated variables alone."""
    from unittest.mock import patch

    from audiobook_automated.environment import startup_exports

    values = {
        "listen_port": "5099",
        "LISTEN_PORT": "5099",
        "Log_Level": "DEBUG",
        "PATH": "/Unchanged/Bin",
        "http_proxy": "http://proxy",
    }
    with patch.dict(os.environ, values, clear=True):
        assert startup_exports().splitlines() == ["listen_port", "LISTEN_PORT=5099", "Log_Level", "LOG_LEVEL=DEBUG"]
        assert dict(os.environ) == values


def test_startup_exports_reject_conflicting_values(caplog: pytest.LogCaptureFixture) -> None:
    """An ambiguous startup setting stops before producing any assignments."""
    from unittest.mock import patch

    from audiobook_automated.environment import main

    with (
        patch.dict(os.environ, {"LISTEN_PORT": "1111", "listen_port": "2222"}, clear=True),
        patch("sys.stdout") as output,
    ):
        with pytest.raises(SystemExit) as error:
            main()
    assert error.value.code == 1
    output.write.assert_not_called()
    assert "LISTEN_PORT" in caplog.text
    assert "1111" not in caplog.text
    assert "2222" not in caplog.text


@pytest.mark.parametrize("newline", ["\n", "\r"])
def test_startup_exports_reject_multiline_values(newline: str) -> None:
    """Keep the literal line protocol unambiguous without echoing invalid values."""
    from unittest.mock import patch

    from audiobook_automated.environment import startup_exports

    with patch.dict(os.environ, {"LISTEN_HOST": "127.0.0.1" + newline + "invalid"}, clear=True):
        with pytest.raises(ValueError, match="LISTEN_HOST must be a single line"):
            startup_exports()


def test_startup_exports_main_emits_assignments(capsys: pytest.CaptureFixture[str]) -> None:
    """The entrypoint reads complete literal records from the helper's standard output."""
    from unittest.mock import patch

    from audiobook_automated.environment import main

    with patch.dict(os.environ, {"listen_port": "5099"}, clear=True):
        main()
    assert capsys.readouterr().out == "listen_port\nLISTEN_PORT=5099\n"
