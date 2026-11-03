# File: tests/unit/test_container_entrypoint.py
"""Verify container startup boundaries without root access or a Docker daemon."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name == "nt" or shutil.which("sh") is None, reason="The container entrypoint uses a POSIX shell")
def test_entrypoint_keeps_one_worker_and_does_not_change_download_folder(tmp_path: Path) -> None:
    """Preserve the client's directory ownership and the single-worker invariant."""
    commands = tmp_path / "bin"
    commands.mkdir()
    for command in ["groupmod", "usermod"]:
        path = commands / command
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    launcher = commands / "gosu"
    launcher.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$ENTRYPOINT_ARGS"\n')
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
        "LISTEN_HOST": "0.0.0.0",
        "LISTEN_PORT": "5078",
        "THREADS": "8",
        "SAVE_PATH_BASE": str(destination),
        "ENTRYPOINT_ARGS": str(recorded),
        "CHOWN_CALLED": str(changed),
    }
    script = Path(__file__).resolve().parents[2] / "entrypoint.sh"
    subprocess.run(["sh", str(script), "--workers", "3"], env=environment, check=True, capture_output=True)
    arguments = recorded.read_text().splitlines()
    assert arguments.count("--workers") == 1
    assert arguments[arguments.index("--workers") + 1] == "1"
    assert arguments[arguments.index("--threads") + 1] == "8"
    assert arguments[-1] == "audiobook_automated.app:app"
    assert not changed.exists()
