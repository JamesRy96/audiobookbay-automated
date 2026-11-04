# File: audiobook_automated/constants.py
"""Application constants and configuration defaults."""

from typing import Final

# --- Application Constants ---
FALLBACK_TITLE: Final[str] = "Unknown_Title_Fallback"
DEFAULT_COVER_FILENAME: Final[str] = "default_cover.jpg"
SAFE_SUFFIX: Final[str] = "_Safe"
DEFAULT_SITE_TITLE: Final[str] = "AudiobookBay Automated"
DEFAULT_SITE_LOGO: Final[str] = "/static/images/audiobookbay-header.jpg"
DEFAULT_THEME: Final[str] = "purple"
DEFAULT_SPLASH_VIDEO: Final[str] = "/static/images/audiobookbay-splash.mp4"
DEFAULT_SPLASH_VIDEO_WEBM: Final[str | None] = None
DEFAULT_SPLASH_MESSAGE: Final[str] = (
    "Welcome to AudiobookBay Automated.<br>Search, manage, and automate your audiobook library."
)

# --- Error Constants ---
ERROR_HASH_NOT_FOUND: Final[str] = "Info Hash could not be found on the page."

# --- Search Configuration ---
MIN_SEARCH_QUERY_LENGTH: Final[int] = 2


# --- Filesystem Constants ---
# Windows reserved filenames to sanitize against, ensuring SMB/Cross-platform compatibility.
WINDOWS_RESERVED_NAMES: Final[set[str]] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

# Calculated from Windows MAX_PATH (260) - 10 (Safety/UUID Buffer) - 1 (Path Separator)
WINDOWS_PATH_SAFE_LIMIT: Final[int] = 249
# Threshold of remaining characters to trigger a warning about deep paths
DEEP_PATH_WARNING_THRESHOLD: Final[int] = 10
# Absolute minimum filename length to allow (prevents empty/unusable names)
MIN_FILENAME_LENGTH: Final[int] = 5
# Maximum filename length to enforce (safe default cap)
MAX_FILENAME_LENGTH: Final[int] = 240

# --- Network Constants ---
# Timeout for Audiobookshelf API integration calls (Seconds)
ABS_TIMEOUT_SECONDS: Final[int] = 10

SCRAPER_REQUEST_TIMEOUT_SECONDS: Final[int] = 10
MIRROR_PROBE_TIMEOUT_SECONDS: Final[float] = 2.5
MIRROR_LIST_TIMEOUT_SECONDS: Final[float] = 3.0
MAX_CATALOG_REDIRECTS: Final[int] = 3
MAX_CATALOG_REQUEST_ATTEMPTS: Final[int] = 2

# A curated list of diverse, modern User-Agents to rotate through to avoid bot detection.
USER_AGENTS: Final[list[str]] = [
    # Desktop Chrome (Windows, Mac, Linux)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Desktop Firefox (Windows, Mac, Linux)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux i686; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Desktop Edge, Opera, Safari
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.2420.81",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Mobile/Tablet (iOS, Android)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A536U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    # Older/Diverse Agents (for wider coverage)
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko",
]

# Default top mirrors to use if primary fails or no environment overrides are set.
# Provides default host (audiobookbay.lu) + 2 best mirrors (audiobookbay.ch, audiobookbay.fi),
# with tested community lists fetched dynamically from remote mirrors.json.
DEFAULT_MIRRORS: Final[list[str]] = [
    "audiobookbay.lu",
    "audiobookbay.ch",
    "audiobookbay.fi",
]

# Remote repository URL for dynamically synchronizing latest community mirrors
DEFAULT_MIRRORS_REMOTE_URL: Final[str] = (
    "https://raw.githubusercontent.com/meek2100/audiobookbay-automated/main/examples/mirrors.json"
)

# Concurrency setting for mirror availability checks
MIRROR_CHECK_THREADS: Final[int] = 5

# Default public trackers to ensure magnet links have connectivity.
DEFAULT_TRACKERS: Final[list[str]] = [
    "udp://tracker.openbittorrent.com:80",
    "udp://opentor.org:2710",
    "udp://tracker.ccc.de:80",
    "udp://tracker.blackunicorn.xyz:6969",
    "udp://tracker.coppersurfer.tk:6969",
    "udp://tracker.leechers-paradise.org:6969",
]

# Fallback port if client is unknown or unlisted (safe default)
DEFAULT_PORT: Final[int] = 8080
