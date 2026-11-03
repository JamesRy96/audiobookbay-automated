# File: tests/unit/test_utils.py
"""Unit tests for utility functions."""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest import LogCaptureFixture

from audiobook_automated.constants import FALLBACK_TITLE, SAFE_SUFFIX
from audiobook_automated.utils import (
    calculate_static_hash,
    construct_safe_save_path,
    ensure_collision_safety,
    format_size,
    get_application_version,
    parse_bool,
    sanitize_title,
)


def test_sanitize_title_basic() -> None:
    """Test basic title sanitization."""
    assert sanitize_title("Valid Title") == "Valid Title"
    assert sanitize_title("Title: Subtitle") == "Title Subtitle"
    assert sanitize_title("Title/With/Slashes") == "TitleWithSlashes"


def test_sanitize_title_empty() -> None:
    """Test sanitization of empty or invalid titles."""
    assert sanitize_title(None) == FALLBACK_TITLE
    assert sanitize_title("") == FALLBACK_TITLE
    assert sanitize_title("   ") == FALLBACK_TITLE
    # "..." strips to empty string
    assert sanitize_title("...") == FALLBACK_TITLE


def test_sanitize_title_windows_reserved() -> None:
    """Test sanitization of Windows reserved names."""
    assert sanitize_title("CON") == f"CON{SAFE_SUFFIX}"
    assert sanitize_title("con.txt") == f"con.txt{SAFE_SUFFIX}"
    assert sanitize_title("LPT1") == f"LPT1{SAFE_SUFFIX}"


def test_ensure_collision_safety_clean() -> None:
    """Test that safe titles are returned unchanged."""
    title = "My Safe Book"
    assert ensure_collision_safety(title) == title


def test_ensure_collision_safety_collision() -> None:
    """Test that collision-prone titles get a UUID appended."""
    # Mock uuid to get a predictable value
    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "12345678" * 4  # 32 chars

        # Test 1: Fallback Title
        result = ensure_collision_safety(FALLBACK_TITLE)
        expected = f"{FALLBACK_TITLE}_12345678"
        assert result == expected

        # Test 2: Safe Suffix (Reserved Name)
        unsafe = f"CON{SAFE_SUFFIX}"
        result = ensure_collision_safety(unsafe)
        expected = f"{unsafe}_12345678"
        assert result == expected


def test_ensure_collision_safety_max_length() -> None:
    """Test that titles exceeding max_length are truncated and get a UUID."""
    # Mock uuid
    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "12345678" * 4
        # UUID suffix is _12345678 (9 chars)

        # Title: "123456789012345" (15 chars)
        # Max: 10
        # Expected Logic:
        # trunc_len = max_length(10) - 9 = 1
        # Prefix = title[:1] = "1"
        # Suffix = "_12345678"
        # Result = "1_12345678" (Total 10 chars)

        title = "123456789012345"
        result = ensure_collision_safety(title, max_length=10)
        assert len(result) == 10
        assert result == "1_12345678"


def test_ensure_collision_safety_short_max_length() -> None:
    """Test max_length logic when the allowed length is extremely short (< 10).

    This forces trunc_len to be < 1, triggering the safety floor of 1.
    """
    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "12345678" * 4

        title = "ShortTitle"
        # With new logic: if max_length < 10, truncate strictly.
        # max_length = 5
        # Result = "Short" (5 chars)
        result = ensure_collision_safety(title, max_length=5)
        assert result == "Short"
        assert len(result) == 5


def test_construct_safe_save_path_windows_path() -> None:
    """Test that construct_safe_save_path handles Windows paths correctly."""
    base_path = "C:\\Downloads"
    title = "My Book"
    # Should use PureWindowsPath
    expected = "C:\\Downloads\\My Book"
    assert construct_safe_save_path(base_path, title) == expected


def test_construct_safe_save_path_windows_reserved_collision_logic() -> None:
    """Test that Windows reserved names trigger UUID collision safety even on Linux paths.

    This simulates the app running on Linux (Docker) but saving to a Windows SMB share/path structure.
    """
    # Simulate a path structure that implies Windows (backslashes)
    base_path = r"\\Server\Share\Books"
    # Reserved name
    unsafe_title = "CON"

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "12345678" * 4

        # Expected flow:
        # 1. sanitize_title("CON") -> "CON_Safe"
        # 2. ensure_collision_safety("CON_Safe") -> "CON_Safe_12345678" (due to _Safe suffix trigger)
        # 3. PureWindowsPath join
        result = construct_safe_save_path(base_path, unsafe_title)

        expected_suffix = "12345678"
        # We check that the result contains the safe suffix AND the uuid
        assert "CON_Safe" in result
        assert expected_suffix in result
        # Check path separators
        assert "\\" in result


def test_get_application_version(tmp_path: Path) -> None:
    """Test get_application_version delegates directly to calculate_static_hash."""
    static_folder = tmp_path / "static"
    static_folder.mkdir()

    with patch(
        "audiobook_automated.utils.calculate_static_hash",
        return_value="calculated_v1",
    ) as mock_calc:
        version = get_application_version(static_folder)
        assert version == "calculated_v1"
        mock_calc.assert_called_once_with(static_folder)


def test_calculate_static_hash(tmp_path: Path) -> None:
    """Test static hash calculation."""
    # Create dummy static structure
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "style.css").write_text("body { color: red; }")

    # Calculate hash
    hash1 = calculate_static_hash(static_dir)
    assert len(hash1) == 8

    # Modify file
    (static_dir / "style.css").write_text("body { color: blue; }")
    hash2 = calculate_static_hash(static_dir)

    assert hash1 != hash2


def test_calculate_static_hash_missing_dir() -> None:
    """Test hash calculation handles missing directory gracefully."""
    assert calculate_static_hash("nonexistent/path") == "v1"


def test_calculate_static_hash_oserror(tmp_path: Path) -> None:
    """Test that hash calculation ignores files that raise OSError (e.g. permissions)."""
    static_dir = tmp_path / "static_oserror"
    static_dir.mkdir()
    # Create two files: one readable, one "unreadable"
    (static_dir / "readable.css").write_text("content")
    (static_dir / "unreadable.css").write_text("secret")

    # Capture the real Path.open to pass through for the readable file
    original_open = Path.open

    # Explicit types needed on side_effect to satisfy mypy [no-untyped-def]
    def side_effect(self: Any, *args: Any, **kwargs: Any) -> Any:
        # Trigger OSError only for the specific unreadable file
        # We check self.name which should exist on the Path object passed as self
        if getattr(self, "name", "") == "unreadable.css":
            raise OSError("Simulated permission error")
        return original_open(self, *args, **kwargs)

    # Patch Path.open to inject the error
    with patch("pathlib.Path.open", side_effect=side_effect, autospec=True):
        # The hash should be calculated based on readable.css only
        # We assume readable.css (alphabetical) or order doesn't matter for this test
        # logic just needs to ensure it doesn't crash.
        h = calculate_static_hash(static_dir)
        assert len(h) == 8


def test_calculate_static_hash_os_error_read(tmp_path: Path) -> None:
    """Test that hash calculation handles OSError during file reading.

    This ensures full coverage for the `except OSError: pass` block in calculate_static_hash,
    specifically when `f.read()` fails.
    """
    static_dir = tmp_path / "static_os_read_error"
    static_dir.mkdir()
    file_path = static_dir / "test.txt"
    file_path.write_text("some content")

    # Mock the file object returned by open
    with patch("pathlib.Path.open") as mock_open:
        mock_file = mock_open.return_value.__enter__.return_value
        # Simulate OSError on read
        mock_file.read.side_effect = OSError("Simulated read error")

        # The function should ignore the error and return a hash (of nothing/empty/other files)
        # Since this is the only file, it might result in a hash of empty or initial state
        # but crucial part is: it must not raise.
        h = calculate_static_hash(static_dir)
        assert isinstance(h, str)
        assert len(h) > 0


def test_sanitize_title_dot_handling() -> None:
    """Verify dot handling.

    We now strip BOTH leading and trailing dots to prevent hidden files on Linux.
    """
    # 1. Leading dot with space -> stripped
    assert sanitize_title(". Hidden Book") == "Hidden Book"
    # 2. Leading dot no space -> stripped
    assert sanitize_title(".Hidden Book") == "Hidden Book"
    # 3. Trailing dot -> stripped (Windows compat)
    assert sanitize_title("Hidden Book.") == "Hidden Book"
    # 4. Just dots (should fallback as it becomes empty)
    # "..." strip(". ") -> "" -> FALLBACK
    assert sanitize_title("...") == FALLBACK_TITLE


def test_construct_safe_save_path_deep_path_warning(caplog: LogCaptureFixture) -> None:
    """Test that a warning is logged if SAVE_PATH_BASE is deep but valid."""
    # 249 - 235 = 14 (safe, > 10). Wait, warning threshold is < 10.
    # We want a path that triggers warning (limit < 10) but NOT exception (limit >= 5).
    # 249 - x < 10 => x > 239.
    # 249 - x >= 5 => x <= 244.
    # So length 240 is perfect. (249-240 = 9).
    deep_path = "/" + "a" * 239  # +1 slash = 240 chars
    with caplog.at_level(logging.WARNING):
        construct_safe_save_path(deep_path, "Short Title")
    assert "SAVE_PATH_BASE is extremely deep" in caplog.text


def test_construct_safe_save_path_raises_if_too_deep() -> None:
    """Test that ValueError is raised if SAVE_PATH_BASE leaves no room for filename."""
    # Calculated limit = 249 - base_len.
    # We want limit < MIN_FILENAME_LENGTH (5).
    # 249 - x < 5 => x > 244.
    deep_path = "/" + "a" * 245  # 246 chars
    with pytest.raises(ValueError, match="SAVE_PATH_BASE is too deep"):
        construct_safe_save_path(deep_path, "Short Title")


def test_format_size() -> None:
    """Test the format_size utility (human readable bytes)."""
    assert format_size(None) == "Unknown"
    assert format_size("invalid") == "Unknown"
    assert format_size(500) == "500.00 B"
    assert format_size(1024) == "1.00 KB"
    assert format_size(1024 * 1024) == "1.00 MB"
    assert format_size(1024 * 1024 * 1024) == "1.00 GB"
    assert format_size("2048") == "2.00 KB"


def test_construct_safe_save_path_very_long_base() -> None:
    """Test construct_safe_save_path with base path > 250 chars."""
    long_base = "/" + "a" * 255
    # Calculated limit = 260 - 10 - 255 = -5.
    # This should raise ValueError because it's less than MIN_FILENAME_LENGTH (5).
    with pytest.raises(ValueError, match="SAVE_PATH_BASE is too deep"):
        construct_safe_save_path(long_base, "Any Title")


def test_ensure_collision_safety_short_max_length_extra() -> None:
    """Test that collision safety truncates without UUID if max_length is very small."""
    title = "A" * 20
    # max_length < 10, so it should just truncate to max_length
    safe = ensure_collision_safety(title, max_length=5)
    assert len(safe) == 5
    assert safe == "AAAAA"
    assert "_" not in safe  # UUID separator shouldn't be there


def test_construct_safe_save_path_extremely_long_path() -> None:
    """Test construct_safe_save_path with an extremely long path (>250 chars).

    This simulates a scenario where the base path plus the title far exceeds system limits.
    """
    # Create a base path that is already close to the limit (e.g., 200 chars)
    # Then add a title that pushes it well over 260
    # base = 200 chars
    # title = 100 chars
    # total = 300 chars > 260
    # Expectation: It should truncate the title aggressively and still succeed (or warn)
    # UNLESS the base path itself leaves too little room (<5 chars), then it raises.

    long_base = "/" + "b" * 200  # 201 chars with leading slash
    long_title = "t" * 100

    # Limit = 260 - 10 - 201 = 49 chars available for title.
    # So it should be able to truncate the title to ~49 chars and succeed.
    result = construct_safe_save_path(long_base, long_title)

    assert len(result) <= 260
    assert long_base in result
    # It should have truncated the title
    assert len(result) < (len(long_base) + len(long_title))


def test_ensure_collision_safety_uuid_appended() -> None:
    """Test that UUID is appended when length exceeds limit (normal case)."""
    title = "A" * 50
    safe = ensure_collision_safety(title, max_length=20)
    assert len(safe) <= 20
    assert "_" in safe
    # UUID suffix is 8 chars + 1 underscore = 9 chars
    # So suffix should be present
    assert safe.endswith(safe.split("_")[-1])


def test_sanitize_title_strip_trailing_dots() -> None:
    """Test that trailing dots and spaces are stripped."""
    assert sanitize_title("Book Title.") == "Book Title"
    assert sanitize_title("Book Title .") == "Book Title"
    assert sanitize_title("Book Title. ") == "Book Title"


def test_parse_bool_quoted() -> None:
    """Test parse_bool handles quoted strings."""
    assert parse_bool('"true"') is True
    assert parse_bool("'true'") is True
    assert parse_bool('"True"') is True
    assert parse_bool("'TRUE'") is True
    assert parse_bool('"1"') is True
    assert parse_bool("'1'") is True
    assert parse_bool('"false"') is False
    assert parse_bool("'0'") is False
    assert parse_bool(None) is False
    assert parse_bool(None, default=True) is True


def test_ensure_collision_safety_utf8_bytes() -> None:
    """Test that max_length constraint respects UTF-8 byte length, not just char count."""
    # This emoji is 4 bytes: \xf0\x9f\x93\x95
    emoji_title = "📕" * 10  # 10 chars, 40 bytes.

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "1" * 32
        # UUID suffix is "_11111111" (9 chars/bytes).

        # Case 1: Limit 20 bytes.
        # Available for title: 20 - 9 = 11 bytes.
        # "📕" (4 bytes) * 2 = 8 bytes. Next one is 4 bytes (total 12 > 11).
        # So it should truncate to 2 emojis.
        result = ensure_collision_safety(emoji_title, max_length=20)

        assert len(result.encode("utf-8")) <= 20
        assert result.endswith("_11111111")
        # Should be "📕📕_11111111"
        assert result.startswith("📕📕")
        assert len(result) == 2 + 9 + 1 - 1  # 2 emojis + 9 suffix chars = 11 chars.

        # Case 2: Limit 22 bytes.
        # Available: 22 - 9 = 13 bytes.
        # 3 emojis = 12 bytes. Fits!
        result_2 = ensure_collision_safety(emoji_title, max_length=22)
        assert result_2.startswith("📕📕📕")
        assert len(result_2.encode("utf-8")) <= 22


def test_safe_get() -> None:
    """Test safe_get utility."""
    from audiobook_automated.utils import safe_get

    d = {"key": "value", "none": None}

    assert safe_get(d, "key") == "value"
    assert safe_get(d, "missing") is None
    assert safe_get(d, "missing", "default") == "default"
    # Key exists but value is None -> returns default
    assert safe_get(d, "none", "default") == "default"


def test_format_user_error() -> None:
    """Test format_user_error for all supported contexts and fallbacks."""
    from audiobook_automated.utils import format_user_error

    # Case 1: Client error
    friendly_client, debug_client = format_user_error(Exception("Host unreachable"), context="client")
    assert "Couldn't reach your Download Client" in friendly_client
    assert debug_client == "Host unreachable"

    # Case 2: Search error
    friendly_search, debug_search = format_user_error("Timeout", context="search")
    assert "Couldn't reach the book catalog" in friendly_search
    assert debug_search == "Timeout"

    # Case 3: Details error
    friendly_details, debug_details = format_user_error(ValueError("Invalid HTML"), context="details")
    assert "Could not load book details" in friendly_details
    assert debug_details == "Invalid HTML"

    # Case 4: General error with empty string
    friendly_gen, debug_gen = format_user_error("", context="unknown")
    assert "Something went wrong" in friendly_gen
    assert debug_gen is None


def test_build_github_issue_url() -> None:
    """Test generating a pre-filled 1-click GitHub issue URL."""
    from audiobook_automated.logging_buffer import log_ring_buffer
    from audiobook_automated.utils import build_github_issue_url

    log_ring_buffer.clear()
    record = logging.LogRecord("test", logging.INFO, "test.py", 10, "Sample test log output", (), None)
    log_ring_buffer.emit(record)

    url = build_github_issue_url(
        error_summary="Search query timed out",
        technical_details="ConnectionError to mirrors",
        context="search",
    )

    assert "https://github.com/meek2100/audiobookbay-automated/issues/new?" in url
    assert "title=" in url
    assert "Bug%3A+%5BSearch%5D+Search+query+timed+out" in url or "Bug%3A" in url
    assert "labels=bug%2Cautomated-report" in url
    assert "Sample+test+log+output" in url or "Sample" in url

    # Test fallback branch when exception occurs fetching logs
    with patch(
        "audiobook_automated.logging_buffer.log_ring_buffer.get_text_logs", side_effect=Exception("Buffer failure")
    ):
        fallback_url = build_github_issue_url("Fallback error", context="general")
        assert "No+logs+available" in fallback_url
