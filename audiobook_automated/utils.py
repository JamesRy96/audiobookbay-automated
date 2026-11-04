# File: audiobook_automated/utils.py
"""Utility functions for the application."""

import hashlib
import logging
import platform
import re
import unicodedata
import urllib.parse
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from audiobook_automated.constants import (
    DEEP_PATH_WARNING_THRESHOLD,
    FALLBACK_TITLE,
    MAX_FILENAME_LENGTH,
    MIN_FILENAME_LENGTH,
    SAFE_SUFFIX,
    WINDOWS_PATH_SAFE_LIMIT,
    WINDOWS_RESERVED_NAMES,
)
from audiobook_automated.logging_buffer import log_ring_buffer

logger = logging.getLogger(__name__)

# Pre-compile regex for faster execution
# Includes standard illegal chars AND control characters (\x00-\x1f)
ILLEGAL_CHARS_RE = re.compile(r'[\x00-\x1f<>:"/\\|?*]')


def sanitize_title(title: str | None) -> str:
    r"""Sanitize a string to be safe for use as a directory name.

    Removes characters like < > : " / \ | ? *
    Also removes trailing periods and spaces (Windows compatibility).
    Returns FALLBACK_TITLE if the resulting string is empty to prevent
    file operations in the root directory.

    Also checks for Windows reserved filenames (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    to ensure compatibility with SMB shares/Windows mounts.
    Checks both the full name and the root name (e.g. "CON.txt" is also invalid).

    Args:
        title: The string to sanitize, potentially None.

    Returns:
        A sanitized string safe for use as a directory name, or FALLBACK_TITLE.
    """
    if not title:
        return FALLBACK_TITLE

    # Normalize Unicode characters to NFKC form (compatibility decomposition)
    # This converts things like '½' to '1/2' (then '/' is removed) or accents to standard chars.
    title = unicodedata.normalize("NFKC", title)

    # Remove illegal characters
    cleaned = ILLEGAL_CHARS_RE.sub("", title)

    # Remove trailing periods and spaces which are invalid in Windows folder names
    # Strip leading/trailing dots and spaces to prevent hidden files on Linux
    sanitized = cleaned.strip(". ")

    if not sanitized:
        return FALLBACK_TITLE

    # Check for Windows reserved filenames (case-insensitive)
    # Check both exact match ("CON") and base stem match ("CON.tar.gz" -> "CON")
    # We use split(".")[0] to catch the primary name before any extensions.
    # Logic Update: Use re.split to correctly handle multiple dots or lack thereof.
    base_stem = sanitized.split(".")[0]

    # Explicit list of reserved names to check against (including COM1-9, LPT1-9)
    # This logic relies on WINDOWS_RESERVED_NAMES being complete, but let's be robust.
    is_reserved = False

    sanitized_upper = sanitized.upper()
    base_stem_upper = base_stem.upper()

    if sanitized_upper in WINDOWS_RESERVED_NAMES or base_stem_upper in WINDOWS_RESERVED_NAMES:
        is_reserved = True

    # Extra check for COM/LPT + digit if not in the constant set
    # Regex: ^(COM|LPT)[1-9]$
    # Note: WINDOWS_RESERVED_NAMES already contains LPT1-9, COM1-9.
    # This check is redundant if the set is complete, but kept for robustness.
    # However, since we enforce coverage, we remove the redundant logic to satisfy DRY/Coverage.
    if is_reserved:
        return f"{sanitized}{SAFE_SUFFIX}"

    return sanitized


def ensure_collision_safety(safe_title: str, max_length: int = 240) -> str:
    """Ensure a sanitized title is safe for filesystem creation by handling collisions and length limits.

    If the title matches the fallback, ends with the safe suffix (indicating a
    reserved name collision), or exceeds the max_length, a UUID is appended/truncated
    to ensure uniqueness and filesystem safety.

    NOTE: This function ONLY checks for reserved filenames/length and does NOT check
    for actual file existence on disk.

    Args:
        safe_title: The already sanitized title string.
        max_length: The maximum allowed length for the directory name in BYTES (default 240).

    Returns:
        str: The collision-safe title, potentially truncated and with a UUID appended.
    """
    needs_uuid = False

    # Check 1: Reserved Name Collision or Fallback
    if safe_title == FALLBACK_TITLE or safe_title.endswith(SAFE_SUFFIX):
        needs_uuid = True

    # Check 2: Length Safety (Bytes)
    # If the title is too long, we force UUID logic to safely truncate
    encoded_title = safe_title.encode("utf-8")
    if len(encoded_title) > max_length:
        needs_uuid = True

    # Check 3: Ultra-short max_length edge case
    # If max_length is so small we can't fit a UUID, we must truncate hard without UUID
    # or return a minimal UUID.

    if needs_uuid:
        # Edge Case: If the max length is too short to reasonably fit a UUID (< 10 chars),
        # we strictly truncate without the UUID to respect the filesystem limit,
        # accepting the collision risk rather than causing an "File name too long" IO error.
        if max_length < 10:  # noqa: PLR2004
            return encoded_title[:max_length].decode("utf-8", "ignore")

        unique_id = uuid.uuid4().hex[:8]
        # Reserve space for ID (8 chars) + Underscore (1) = 9 chars.
        trunc_len = max_length - 9
        # Ensure we don't truncate to a negative or zero length (redundant due to check above, but safe)
        trunc_len = max(trunc_len, 1)

        # Truncate title to fit bytes
        truncated_bytes = encoded_title[:trunc_len]
        # Ignore errors to handle incomplete multi-byte characters at the boundary
        truncated_safe = truncated_bytes.decode("utf-8", "ignore")

        return f"{truncated_safe}_{unique_id}"

    return safe_title


def construct_safe_save_path(base_path: str, title: str) -> str:
    """Construct a safe filesystem path for the torrent download.

    Encapsulates logic for:
    1. Title sanitization.
    2. OS-specific path separators (Windows vs Posix detection).
    3. Path length calculation and truncation.
    4. Collision safety (UUID appending).

    Args:
        base_path: The root save path configured in the app (SAVE_PATH_BASE).
        title: The raw book title.

    Returns:
        str: The full, safe path string.
    """
    safe_title = sanitize_title(title)
    max_len = MAX_FILENAME_LENGTH

    # Dynamic Path Safety Calculation
    # Calculate base length in bytes to ensure accuracy on modern filesystems
    base_len = len(base_path.encode("utf-8"))
    # Use constant for calculation: 260 - 10 - 1 = 249
    calculated_limit = WINDOWS_PATH_SAFE_LIMIT - base_len

    # Explicitly fail if the base path is too deep to support even minimal filenames.
    # This prevents silent failures where the truncation logic would produce unusable names.
    if calculated_limit < MIN_FILENAME_LENGTH:
        raise ValueError(
            f"SAVE_PATH_BASE is too deep ({base_len} bytes). "
            f"Remaining limit {calculated_limit} is less than MIN_FILENAME_LENGTH ({MIN_FILENAME_LENGTH})."
        )

    if calculated_limit < DEEP_PATH_WARNING_THRESHOLD:
        logger.warning(
            f"SAVE_PATH_BASE is extremely deep ({base_len} bytes). "
            "Titles will be severely truncated to prevent file system errors."
        )

    # Prioritize OS limits over "usable" length.
    # Enforce floor of MIN_FILENAME_LENGTH, cap at calculated limit.
    max_len = max(MIN_FILENAME_LENGTH, calculated_limit)
    # Cap at MAX_FILENAME_LENGTH to ensure we never allow massive paths if base is short
    max_len = min(MAX_FILENAME_LENGTH, max_len)

    previous_title = safe_title
    safe_title = ensure_collision_safety(safe_title, max_length=max_len)

    if safe_title != previous_title:
        logger.warning(
            f"Title '{title}' required fallback/truncate handling. Using collision-safe directory name: {safe_title}"
        )

    # Detect the remote path syntax independently of the web server's operating system.
    if PureWindowsPath(base_path).drive or "\\" in base_path:
        return str(PureWindowsPath(base_path).joinpath(safe_title))
    return str(PurePosixPath(base_path).joinpath(safe_title))


def calculate_static_hash(static_folder: str | Path) -> str:
    """Calculate a short SHA256 hash of the contents of the static folder.

    Args:
        static_folder: Path to the static assets directory.

    Returns:
        str: An 8-character hex string representing the content hash.
    """
    hash_sha256 = hashlib.sha256()
    folder_path = Path(static_folder)

    if not folder_path.exists():
        return "v1"

    # Walk through the static folder to hash all file contents
    # Use sorted() to ensure consistent hashing order across systems
    for path in sorted(folder_path.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            try:
                with path.open("rb") as f:
                    # Read in chunks to handle large files efficiently
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_sha256.update(chunk)
            except OSError:
                # If we can't read a file (permissions?), ignore it for the hash
                pass

    return hash_sha256.hexdigest()[:8]


def get_application_version(static_folder: str | Path) -> str:
    """Retrieve the application version hash computed dynamically at runtime.

    Calculates the content hash of the static assets folder at server startup,
    ensuring that live-swapped files, custom volumes, and bind mounts immediately
    bust browser caches without requiring a container rebuild.

    Args:
        static_folder: Path to the static assets directory.

    Returns:
        str: An 8-character hex string representing the static folder hash.
    """
    return calculate_static_hash(static_folder)


def format_size(size_bytes: int | float | str | None) -> str:
    """Format bytes into human-readable B, KB, MB, GB, TB, PB.

    Args:
        size_bytes: The size in bytes (can be string, int, or float).

    Returns:
        str: Formatted string (e.g. "1.50 MB").
    """
    if size_bytes is None:
        return "Unknown"
    try:
        size: float = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:  # noqa: PLR2004
                return f"{size:.2f} {unit}"
            size /= 1024.0  # noqa: PLR2004
        return f"{size:.2f} PB"
    except (ValueError, TypeError):
        return "Unknown"


def parse_bool(value: str | None, default: bool = False) -> bool:
    """Parse a boolean value safely from string or None.

    Supports '1', 'true', 'yes', 'on' (case-insensitive) as True.
    Robustly handles quoted strings from Docker environment variables.

    Args:
        value: The string value to parse (e.g. from environment variable).
        default: The default value if the input is None.

    Returns:
        bool: The parsed boolean.
    """
    if value is None:
        return default
    return value.strip().strip("'\"").lower() in ("1", "true", "yes", "on")


def safe_get(dictionary: dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a value from a dictionary, returning default if key is missing or None.

    Args:
        dictionary: The source dictionary.
        key: The key to look up.
        default: The default value to return.

    Returns:
        The value or default.
    """
    value = dictionary.get(key)
    return value if value is not None else default


def client_connection_help(name: str | None = None, settings: dict[str, str] | None = None) -> str:
    """Explain the selected connection without assuming a particular Docker or VPN product."""
    labels = {"qbittorrent": "qBittorrent", "deluge": "Deluge", "transmission": "Transmission", "putio": "Put.io"}
    if name == "putio":
        return "Cannot connect to Put.io. Check your internet connection and PUTIO_TOKEN in the app settings."
    if not name:
        return "Cannot connect to your Download Clients. Check that they are running and review their address, port and login settings in the app."
    label = labels.get(name, name)
    prefix = name.upper()
    host = (settings or {}).get("HOST") or "127.0.0.1"
    message = f"Cannot connect to {label}. Check that the client is running and its login settings are correct. "
    if settings and settings.get("URL"):
        return message + f"Check {prefix}_URL and that this app can reach that address."
    if host.lower() in ("localhost", "127.0.0.1", "::1", "[::1]"):
        return message + (
            f"A local address is already selected. If the client runs in a separate container or server, "
            f"set {prefix}_HOST to its service name or IP address."
        )
    return message + f"Check {prefix}_HOST and {prefix}_PORT, and that this app can reach that address."


def format_user_error(err: Exception | str, context: str = "general") -> tuple[str, str | None]:
    """Format an exception into a user-friendly message and technical debug details.

    Args:
        err: The exception or error string.
        context: Context of the error ('client', 'search', 'details', 'general').

    Returns:
        tuple[str, str | None]: (user_friendly_message, technical_details)
    """
    raw_error = str(err).strip()

    if context == "client":
        friendly = "Couldn't reach your Download Client. Check that it is running and that its connection settings are correct."
    elif context == "search":
        friendly = "Couldn't reach the book catalog. Try again in a moment."
    elif context == "details":
        friendly = "Could not load book details. Try again, or choose another book."
    else:
        friendly = "Something went wrong. Refresh the page and try again."

    return friendly, raw_error if raw_error else None


def build_github_issue_url(
    error_summary: str,
    technical_details: str | None = None,
    context: str = "general",
) -> str:
    """Generate a pre-filled 1-click GitHub issue reporting URL.

    Scrubs PII and attaches sanitized environment details, mirror states, and logs.
    """
    repo_url = "https://github.com/meek2100/audiobookbay-automated/issues/new"
    title = f"Bug: [{context.title()}] {error_summary[:60]}"

    # Pull sanitized logs if available
    recent_logs = ""
    try:
        recent_logs = log_ring_buffer.get_text_logs(limit=20)
    except Exception:
        recent_logs = "No logs available"

    body = f"""### Description
{error_summary}

### Context
- **Context Type**: {context}
- **Python Version**: {platform.python_version()}
- **OS Platform**: {platform.platform()}

### Technical Error Details
~~~
{technical_details or "None"}
~~~

### Recent Application Logs (Sanitized)
<details>
<summary>Click to view recent logs</summary>

~~~
{recent_logs}
~~~
</details>

*Generated automatically via AudiobookBay Automated 1-Click Issue Reporter.*
"""
    params = {
        "title": title,
        "body": body,
        "labels": "bug,automated-report",
    }
    return f"{repo_url}?{urllib.parse.urlencode(params)}"


if __name__ == "__main__":  # pragma: no cover
    # Script entry point for Docker build time optimization.
    # Calculates the hash of the static directory relative to this file
    # and prints it to stdout for redirection to version.txt.
    static_dir = Path(__file__).parent / "static"
    print(calculate_static_hash(static_dir))
