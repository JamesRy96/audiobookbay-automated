# File: audiobook_automated/scraper/network.py
"""Network module handling HTTP sessions, proxies, and mirrors."""

import concurrent.futures
import json
import logging
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urljoin, urlparse

import requests
from cachetools import TTLCache
from flask import current_app, has_app_context
from requests.adapters import HTTPAdapter
from requests.sessions import Session
from urllib3.util.retry import Retry

from audiobook_automated.constants import (
    DEFAULT_MIRRORS,
    DEFAULT_MIRRORS_REMOTE_URL,
    DEFAULT_SCRAPER_JITTER_MAX,
    DEFAULT_SCRAPER_JITTER_MIN,
    DEFAULT_TRACKERS,
    MAX_CATALOG_REDIRECTS,
    MAX_CATALOG_REQUEST_ATTEMPTS,
    MIRROR_CHECK_THREADS,
    MIRROR_LIST_TIMEOUT_SECONDS,
    MIRROR_PROBE_TIMEOUT_SECONDS,
    USER_AGENTS,
)
from audiobook_automated.scraper.parser import BookDetails, BookSummary, parse_html

logger = logging.getLogger(__name__)

# --- Concurrency Control ---
DEFAULT_CONCURRENT_REQUESTS = 3
_semaphore: threading.BoundedSemaphore = threading.BoundedSemaphore(DEFAULT_CONCURRENT_REQUESTS)
# Executor for mirror availability checks to prevent thread churn
_mirror_executor: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(
    max_workers=MIRROR_CHECK_THREADS
)
CACHE_LOCK = threading.Lock()
_discovery_lock = threading.Lock()


# --- Mirror Performance & Stats Tracking ---
@dataclass
class MirrorStat:
    """Historical performance and health tracking for a single mirror."""

    hostname: str
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    ema_latency_ms: float = 0.0
    last_latency_ms: float = 0.0
    last_checked_at: float = 0.0
    cooldown_until: float = 0.0
    last_error: str | None = None
    protocol: str = "https"  # "https" or "http"
    is_parked_or_invalid: bool = False

    @property
    def total_requests(self) -> int:
        """Total number of probes/requests made to this mirror."""
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        """Success rate between 0.0 and 1.0 (defaults to 1.0 if untried, 0.0 if parked/invalid)."""
        if self.is_parked_or_invalid:
            return 0.0
        if self.total_requests == 0:
            return 1.0
        return self.success_count / self.total_requests

    @property
    def is_cooling_down(self) -> bool:
        """Whether this mirror is currently on backoff cooldown."""
        return time.time() < self.cooldown_until

    def record_success(self, latency_ms: float, protocol: str = "https") -> None:
        """Record a successful response and update exponential moving average latency."""
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_latency_ms = latency_ms
        self.last_checked_at = time.time()
        self.cooldown_until = 0.0
        self.last_error = None
        self.protocol = protocol
        self.is_parked_or_invalid = False
        if self.ema_latency_ms <= 0.0:
            self.ema_latency_ms = latency_ms
        else:
            # 70% previous EMA, 30% current latency
            self.ema_latency_ms = round((0.7 * self.ema_latency_ms) + (0.3 * latency_ms), 2)

    def record_failure(self, error_msg: str | None = None, is_parked: bool = False) -> None:
        """Record a failure and apply exponential cooldown backoff."""
        self.failure_count += 1
        self.consecutive_failures += 1
        self.last_checked_at = time.time()
        self.last_error = error_msg
        if is_parked:
            self.is_parked_or_invalid = True
            self.cooldown_until = time.time() + 86400.0  # 24hr cooldown for parked/spam
            return
        # Back off consecutive failures exponentially; preserve lifetime counts for accuracy.
        backoff_sec = min(300.0, 15.0 * (2 ** min(self.consecutive_failures - 1, 5)))
        self.cooldown_until = time.time() + backoff_sec

    @property
    def score(self) -> float:
        """Compute performance score (higher is better).

        Penalizes parked/failing/cooling down mirrors heavily.
        Rewards high success rate, low latency, and applies a bonus for HTTPS (+150).
        """
        if self.is_parked_or_invalid and self.is_cooling_down:
            return -9999.0
        if self.is_cooling_down:
            return -1000.0 - (self.cooldown_until - time.time())
        # Base on success rate (0-1000)
        rate_score = self.success_rate * 1000.0
        # Latency penalty:
        # Prioritize Accuracy > Speed > Security.
        # Sub-second latencies (e.g. 580ms) incur modest penalty (~58 points).
        # Multi-second/extreme latencies (e.g. 40,000ms) incur severe penalties (~4000 points),
        # ensuring a fast 80% HTTP mirror (800 - 58 = 742) strongly beats a 40s 100% HTTPS mirror (1000 - 4000 + 150 = -2850).
        effective_lat = self.ema_latency_ms if self.ema_latency_ms > 0 else 100.0
        lat_penalty = effective_lat / 10.0
        # HTTPS protocol bonus: 90% HTTPS (~900 + 150 = 1050) beats 95% HTTP (~950) when latency is close,
        # but 63% HTTP (630) beats 43% HTTPS (430 + 150 = 580).
        protocol_bonus = 150.0 if self.protocol == "https" else 0.0
        return rate_score - lat_penalty + protocol_bonus


_mirror_stats: dict[str, MirrorStat] = {}
_remote_mirrors_cache: TTLCache[str, list[str]] = cast(TTLCache[str, list[str]], TTLCache(maxsize=1, ttl=3600))


# --- Thread-Local Storage ---
class NetworkLocal(threading.local):
    """Thread-local storage for network sessions to ensure thread safety."""

    def __init__(self) -> None:
        """Initialize thread-local attributes."""
        super().__init__()
        self.session: Session | None = None
        self.ping_session: Session | None = None


_local = NetworkLocal()

# --- Caches ---
# mirror_cache: Stores the currently active (working) mirror hostname to avoid repeated checks.
mirror_cache: TTLCache[str, str | None] = cast(TTLCache[str, str | None], TTLCache(maxsize=1, ttl=600))
# failure_cache: Negative cache to prevent rapid retries if all mirrors are known to be down.
failure_cache: TTLCache[str, bool] = cast(TTLCache[str, bool], TTLCache(maxsize=1, ttl=30))
# search_cache: Caches search results by query to reduce load on the mirror and improve speed.
search_cache: TTLCache[str, list[BookSummary]] = cast(TTLCache[str, list[BookSummary]], TTLCache(maxsize=100, ttl=300))
# details_cache: Caches parsed book details by URL to prevent redundant network fetches.
details_cache: TTLCache[str, BookDetails] = cast(TTLCache[str, BookDetails], TTLCache(maxsize=100, ttl=300))
# tracker_cache: Caches the list of magnet trackers to minimize filesystem I/O.
tracker_cache: TTLCache[str, list[str]] = cast(TTLCache[str, list[str]], TTLCache(maxsize=1, ttl=300))


def init_semaphore(max_requests: int) -> None:
    """Initialize the global request semaphore with a specific limit.

    Args:
        max_requests: The maximum number of concurrent external requests allowed.
    """
    global _semaphore
    logger.info(f"Initializing Global Request Semaphore with limit: {max_requests}")
    _semaphore = threading.BoundedSemaphore(max_requests)


def get_semaphore() -> threading.BoundedSemaphore:
    """Retrieve the global request semaphore.

    Returns:
        threading.BoundedSemaphore: The active semaphore.
    """
    return _semaphore


def get_random_user_agent() -> str:
    """Return a random User-Agent string from the constants list."""
    return random.choice(USER_AGENTS)  # nosec B311  # noqa: S311


def get_trackers() -> list[str]:
    """Load trackers from configuration and optional local JSON file.

    Uses TTLCache to avoid repeated I/O while allowing config updates to propagate.
    """
    with CACHE_LOCK:
        if "default" in tracker_cache:
            return tracker_cache["default"]

    env_trackers = current_app.config.get("MAGNET_TRACKERS", [])
    if env_trackers:
        result = cast(list[str], env_trackers)
        with CACHE_LOCK:
            tracker_cache["default"] = result
        return result

    try:
        # Use CWD (Container Workdir /app) to resolve trackers.json reliably in production
        json_path = Path.cwd() / "trackers.json"

        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    logger.info("Loaded custom trackers from trackers.json")
                    with CACHE_LOCK:
                        tracker_cache["default"] = cast(list[str], data)
                    return cast(list[str], data)
                else:
                    logger.warning("trackers.json contains invalid data (expected a list). Using defaults.")
    except Exception as e:
        logger.warning(f"Failed to load trackers.json: {e}", exc_info=True)

    with CACHE_LOCK:
        tracker_cache["default"] = DEFAULT_TRACKERS
    return DEFAULT_TRACKERS


def get_mirror_stat(hostname: str) -> MirrorStat:
    """Get or create the tracking record for a mirror."""
    with CACHE_LOCK:
        if hostname not in _mirror_stats:
            _mirror_stats[hostname] = MirrorStat(hostname=hostname)
        return _mirror_stats[hostname]


def get_all_mirror_stats() -> list[dict[str, Any]]:
    """Return an inspection snapshot of all mirror health and latencies."""
    with CACHE_LOCK:
        stats: list[dict[str, Any]] = []
        for host, stat in _mirror_stats.items():
            stats.append(
                {
                    "hostname": host,
                    "tested": stat.total_requests > 0,
                    "reachable": stat.success_count > 0 and stat.last_error is None and not stat.is_cooling_down,
                    "latency_ms": stat.last_latency_ms,
                    "protocol": stat.protocol,
                    "is_parked": stat.is_parked_or_invalid,
                    "success_count": stat.success_count,
                    "failure_count": stat.failure_count,
                    "total_requests": stat.total_requests,
                    "success_rate": round(stat.success_rate * 100, 1),
                    "ema_latency_ms": stat.ema_latency_ms,
                    "last_latency_ms": stat.last_latency_ms,
                    "cooling_down": stat.is_cooling_down,
                    "score": round(stat.score, 1),
                    "last_error": stat.last_error,
                }
            )
        # Sort by score descending
        stats.sort(key=lambda x: x["score"], reverse=True)
        return stats


def fetch_remote_mirrors() -> list[str]:
    """Fetch remote community mirror list, falling back to local examples/mirrors.json or defaults."""
    with CACHE_LOCK:
        if "mirrors" in _remote_mirrors_cache:
            return _remote_mirrors_cache["mirrors"]

    remote_url = current_app.config.get("ABB_MIRRORS_REMOTE_URL") or DEFAULT_MIRRORS_REMOTE_URL
    session = get_ping_session()

    try:
        resp, _ = request_external(session, remote_url, timeout=MIRROR_LIST_TIMEOUT_SECONDS)
        if resp.status_code == 200:  # noqa: PLR2004
            data = resp.json()
            if isinstance(data, list) and all(isinstance(x, str) for x in data):
                logger.info(f"Loaded {len(data)} remote mirrors from {remote_url}")
                with CACHE_LOCK:
                    _remote_mirrors_cache["mirrors"] = data
                return data
    except Exception as e:
        logger.debug(f"Could not fetch remote mirrors from {remote_url}: {e}")

    # Fallback: local examples/mirrors.json
    local_json = Path.cwd() / "examples" / "mirrors.json"
    if local_json.exists():
        try:
            with open(local_json, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and all(isinstance(x, str) for x in data):
                    logger.info(f"Loaded {len(data)} mirrors from {local_json}")
                    with CACHE_LOCK:
                        _remote_mirrors_cache["mirrors"] = data
                    return data
        except Exception as e:
            logger.debug(f"Could not load local mirrors.json: {e}")

    with CACHE_LOCK:
        _remote_mirrors_cache["mirrors"] = DEFAULT_MIRRORS
    return DEFAULT_MIRRORS


def get_mirrors(*, refresh_remote: bool = True) -> list[str]:
    """Retrieve the list of mirrors to attempt, in adaptive performance-ranked order."""
    primary = current_app.config.get("ABB_HOSTNAME", "audiobookbay.lu")
    extra = current_app.config.get("ABB_MIRRORS", [])
    if refresh_remote:
        remote_mirrors = fetch_remote_mirrors()
    else:
        with CACHE_LOCK:
            remote_mirrors = list(_remote_mirrors_cache.get("mirrors", DEFAULT_MIRRORS))
    candidates = list(dict.fromkeys([primary] + extra + remote_mirrors + DEFAULT_MIRRORS))

    # Rank candidates adaptively by score
    with CACHE_LOCK:

        def rank_key(host: str) -> tuple[int, float, int]:
            """Prefer verified healthy mirrors by score, then untried hosts, then cooling-down hosts."""
            stat = _mirror_stats.get(host)
            primary_tie = int(host == primary)
            if stat is None or (not stat.total_requests):
                return (1, 0.0, primary_tie)
            if stat.is_cooling_down:
                return (0, stat.score, primary_tie)
            return (2 if stat.success_count and stat.last_error is None else 1, stat.score, primary_tie)

        candidates.sort(key=rank_key, reverse=True)
    return candidates


def get_active_search_mirrors(limit: int = 3, *, refresh_remote: bool = True) -> list[str]:
    """Prune candidate mirrors to the top best-performing candidates for fast search execution."""
    mirrors = get_mirrors(refresh_remote=refresh_remote)
    # Filter out mirrors currently on cooldown unless all are on cooldown
    active = [m for m in mirrors if not get_mirror_stat(m).is_cooling_down]
    if not active:
        active = mirrors
    return active[:limit]


def get_session() -> Session:
    """Configure and return a requests Session with retry logic."""
    session = requests.Session()
    session.headers.update({"User-Agent": get_random_user_agent()})
    retry_policy = Retry(
        total=0,
        backoff_factor=0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_policy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_ping_session() -> Session:
    """Retrieve or create a thread-local Session with ZERO retries for checks.

    Uses thread-local storage to avoid race conditions while reusing SSL connections
    within the same worker thread.

    Returns:
        Session: A configured requests Session object with 0 retries.
    """
    if _local.ping_session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": get_random_user_agent()})
        retry_policy = Retry(
            total=0,
            backoff_factor=0,
            status_forcelist=[],
            allowed_methods=["HEAD", "GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_policy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _local.ping_session = session

    return _local.ping_session


def get_thread_session() -> Session:
    """Retrieve a thread-local transport; request_external owns retries and request spacing."""
    if _local.session is None:
        _local.session = get_session()
    return _local.session


def get_headers(user_agent: str | None = None, referer: str | None = None) -> dict[str, str]:
    """Generate standard HTTP headers for scraping requests."""
    if not user_agent:
        user_agent = get_random_user_agent()
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def request_external(
    session: Session,
    url: str,
    *,
    method: Literal["GET", "HEAD"] = "GET",
    timeout: float,
    headers: dict[str, str] | None = None,
) -> tuple[requests.Response, float]:
    """Bound every HTTP attempt, including redirects, and reject changes to the destination host.

    Latency excludes semaphore wait and mandatory jitter, so mirror rankings reflect server response time.
    Automatic adapter retries are disabled: each attempt must pass through this request budget.
    """
    original_host = urlparse(url).hostname
    elapsed_ms = 0.0
    hop = 0
    attempt = 0
    jitter_min = (
        float(current_app.config.get("SCRAPER_JITTER_MIN", DEFAULT_SCRAPER_JITTER_MIN))
        if has_app_context()
        else DEFAULT_SCRAPER_JITTER_MIN
    )
    jitter_max = (
        float(current_app.config.get("SCRAPER_JITTER_MAX", DEFAULT_SCRAPER_JITTER_MAX))
        if has_app_context()
        else DEFAULT_SCRAPER_JITTER_MAX
    )
    if jitter_max < jitter_min:
        jitter_min, jitter_max = jitter_max, jitter_min

    while True:
        with get_semaphore():
            if jitter_max > 0:
                time.sleep(random.uniform(jitter_min, jitter_max))  # noqa: S311
            started = time.perf_counter()
            send = session.get if method == "GET" else session.head
            try:
                response = send(url, headers=headers, timeout=timeout, allow_redirects=False)
            except requests.exceptions.SSLError:
                raise
            except (requests.ConnectionError, requests.Timeout):
                elapsed_ms += (time.perf_counter() - started) * 1000
                attempt += 1
                if attempt >= MAX_CATALOG_REQUEST_ATTEMPTS:
                    raise
                continue
            elapsed_ms += (time.perf_counter() - started) * 1000
        if response.status_code not in (301, 302, 303, 307, 308):
            return response, round(elapsed_ms, 2)
        location = response.headers.get("Location")
        response.close()
        if not location or hop == MAX_CATALOG_REDIRECTS:
            raise requests.ConnectionError("Catalog redirect is missing a destination or exceeds the redirect limit.")
        redirected = urljoin(url, location)
        destination = urlparse(redirected)
        if (
            destination.hostname != original_host
            or destination.scheme not in ("http", "https")
            or destination.username is not None
        ):
            raise requests.ConnectionError("Catalog redirected outside its expected host.")
        url = redirected
        hop += 1
        attempt = 0


def is_authentic_catalog(html_text: str, final_url: str | None = None, expected_host: str | None = None) -> bool:
    """Require authentic catalog structure and reject foreign or parked destinations."""
    if not html_text:
        return False
    text_lower = html_text.lower()
    if any(
        marker in text_lower for marker in ("domain is parked", "buy this domain", "expired domain", "redirecting...")
    ):
        return False
    if final_url:
        host = urlparse(final_url).hostname or ""
        if expected_host and host != expected_host:
            return False
        if any(
            marker in host for marker in ("expireddomains", "parkingcrew", "bodis", "sedo", "dan.com", "hugedomains")
        ):
            return False
    soup = parse_html(html_text)
    return bool(
        soup.select_one("#content")
        and soup.select_one("#content .postTitle, #content .postContent")
        and ("audiobookbay" in text_lower or "audio-books" in text_lower)
    )


@dataclass(frozen=True)
class ProbeResult:
    """Semantic probe outcome with measured network latency and its failure classification."""

    reachable: bool
    latency_ms: float = 0.0
    error: str | None = None
    parked: bool = False
    stop: bool = False


def _probe_catalog_endpoint(session: Session, url: str, headers: dict[str, str]) -> ProbeResult:
    """Fetch a catalog page within the common budget and validate its final destination and structure."""
    try:
        response, latency = request_external(session, url, headers=headers, timeout=MIRROR_PROBE_TIMEOUT_SECONDS)
        if response.status_code == 200:  # noqa: PLR2004
            if is_authentic_catalog(response.text, response.url, urlparse(url).hostname):
                return ProbeResult(True, latency)
            return ProbeResult(False, error="Semantic verification failed (Non-authentic catalog)", parked=True)
        return ProbeResult(False, error=f"HTTP {response.status_code}")
    except requests.RequestException as error:
        return ProbeResult(False, error=str(error))


def _probe_https_mirror(session: Session, hostname: str, headers: dict[str, str]) -> ProbeResult:
    """Probe HTTPS first, validating content rather than accepting a successful HEAD alone."""
    url = f"https://{hostname}/"
    try:
        response, _ = request_external(
            session, url, method="HEAD", headers=headers, timeout=MIRROR_PROBE_TIMEOUT_SECONDS
        )
        if response.status_code >= 500:  # noqa: PLR2004
            return ProbeResult(False, error=f"HTTP {response.status_code}", stop=True)
    except requests.RequestException as error:
        logger.debug("HTTPS HEAD probe for %s: %s", hostname, error)
    return _probe_catalog_endpoint(session, url, headers)


def check_mirror(hostname: str) -> str | None:
    """Check a mirror with semantic validation, common request limits and cooldown-aware HTTPS/HTTP fallback."""
    stat = get_mirror_stat(hostname)
    if stat.is_cooling_down:
        return None
    session = get_ping_session()
    headers = get_headers()
    result = _probe_https_mirror(session, hostname, headers)
    protocol = "https"
    if not result.reachable and not result.parked and not result.stop:
        result = _probe_catalog_endpoint(session, f"http://{hostname}/", headers)
        protocol = "http"
    with CACHE_LOCK:
        if result.reachable:
            stat.record_success(result.latency_ms, protocol=protocol)
        else:
            stat.record_failure(result.error or "Endpoint unreachable", is_parked=result.parked)
    return hostname if result.reachable else None


def get_mirror_base_url(hostname: str) -> str:
    """Return the complete base URL with scheme ('https://' or 'http://') for a mirror."""
    stat = get_mirror_stat(hostname)
    protocol = getattr(stat, "protocol", "https")
    return f"{protocol}://{hostname}"


def _check_mirror_after(hostname: str, delay_seconds: float) -> str | None:
    """Wait a jittered delay, then probe a mirror (skipped entirely if its future was cancelled first)."""
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    return check_mirror(hostname)


def record_request_outcome(url: str, success: bool, latency_ms: float = 0.0, error: str | None = None) -> None:
    """Feed the outcome of a real search/details request back into mirror ranking.

    A failure puts the mirror on backoff and drops it from the active-mirror cache so the next
    request re-ranks instead of repeatedly hitting a mirror that is failing or blocking us.
    """
    parsed = urlparse(url)
    if not parsed.netloc:
        return
    stat = get_mirror_stat(parsed.netloc)
    with CACHE_LOCK:
        if success:
            stat.record_success(latency_ms, protocol="http" if parsed.scheme == "http" else "https")
            return
        stat.record_failure(error)
        if mirror_cache.get("active_mirror") == parsed.netloc:
            del mirror_cache["active_mirror"]


def find_best_mirror() -> str | None:
    """Find the first reachable AudiobookBay mirror using concurrent checks."""
    with _discovery_lock:
        # 1. Check Negative Cache (Backoff)
        with CACHE_LOCK:
            if "failure" in failure_cache:
                logger.debug("Skipping mirror check due to recent failure (Negative Cache hit).")
                return None

        # 2. Check Positive Cache
        cache_key = "active_mirror"
        with CACHE_LOCK:
            if cache_key in mirror_cache:
                return mirror_cache[cache_key]

        mirrors = [host for host in get_mirrors() if not get_mirror_stat(host).is_cooling_down]

        # 3. Fast path: Check the highest-ranked candidate before starting failover workers
        if mirrors:
            primary = mirrors[0]
            logger.debug(f"Fast-path checking preferred mirror: {primary}")
            if check_mirror(primary):
                logger.info(f"Preferred mirror active: {primary}")
                with CACHE_LOCK:
                    mirror_cache[cache_key] = primary
                return primary

        # 4. Failover: Check remaining mirrors concurrently
        failover_mirrors = mirrors[1:] if len(mirrors) > 1 else mirrors
        logger.debug(f"Primary down. Checking failover connectivity for {len(failover_mirrors)} mirrors...")

        # Stagger probes with random delays so failover never fires a simultaneous burst at every mirror.
        futures = []
        delay = 0.0
        for host in failover_mirrors:
            futures.append(_mirror_executor.submit(_check_mirror_after, host, delay))
            delay += random.uniform(0.15, 0.5)  # noqa: S311

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                logger.info(f"Found active mirror: {result}")
                # Best effort cancel other pending tasks
                for f in futures:
                    f.cancel()
                with CACHE_LOCK:
                    mirror_cache[cache_key] = result
                return result

        logger.error("No working AudiobookBay mirrors found! Caching failure for 30s.")
        with CACHE_LOCK:
            failure_cache["failure"] = True
        return None


def shutdown_network() -> None:
    """Shutdown the mirror checking executor gracefully."""
    logger.info("Shutting down network executors...")
    # cancel_futures=True ensures pending checks don't block shutdown (Python 3.9+)
    _mirror_executor.shutdown(wait=False, cancel_futures=True)


# Explicitly export used names to satisfy mypy implicit re-export checks
__all__ = [
    "CACHE_LOCK",
    "DEFAULT_MIRRORS",
    "MirrorStat",
    "check_mirror",
    "details_cache",
    "fetch_remote_mirrors",
    "find_best_mirror",
    "record_request_outcome",
    "request_external",
    "get_active_search_mirrors",
    "get_all_mirror_stats",
    "get_mirror_stat",
    "get_mirrors",
    "get_ping_session",
    "get_random_user_agent",
    "get_semaphore",
    "get_session",
    "get_thread_session",
    "get_trackers",
    "init_semaphore",
    "mirror_cache",
    "requests",
    "search_cache",
    "shutdown_network",
    "threading",
    "tracker_cache",
]
