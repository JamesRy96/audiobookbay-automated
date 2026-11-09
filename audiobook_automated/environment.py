# File: audiobook_automated/environment.py
"""Read app settings consistently in Python, container startup and health checks."""

import logging
import os
import sys
from typing import overload

logger = logging.getLogger(__name__)

STARTUP_SETTINGS = (
    "LISTEN_HOST",
    "LISTEN_PORT",
    "THREADS",
    "TIMEOUT",
    "LOG_LEVEL",
    "FLASK_DEBUG",
    "PUID",
    "PGID",
    "TZ",
)


@overload
def get_env(key: str, default: str) -> str: ...


@overload
def get_env(key: str, default: None = None) -> str | None: ...


def get_env(key: str, default: str | None = None) -> str | None:
    """Resolve case-insensitive names without changing values or choosing conflicting duplicates."""
    canonical = key.upper()
    values = {value for name, value in os.environ.items() if name.upper() == canonical}
    if len(values) > 1:
        raise ValueError(f"{canonical} is set more than once with different values. Remove the duplicate setting.")
    return next(iter(values), default)


def startup_exports() -> str:
    """Emit safe unset/export records for the POSIX entrypoint, without shell evaluation."""
    records: list[str] = []
    for key in STARTUP_SETTINGS:
        value = get_env(key)
        if value is not None:
            if "\n" in value or "\r" in value:
                raise ValueError(f"{key} must be a single line.")
            records.extend(name for name in os.environ if name.upper() == key and name != key)
            records.append(f"{key}={value}")
    return "".join(record + "\n" for record in records)


def main() -> None:
    """Resolve startup names for the entrypoint or report a concise configuration error."""
    logging.basicConfig(level=logging.ERROR)
    try:
        sys.stdout.write(startup_exports())
    except ValueError as error:
        logger.error("%s", error)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
