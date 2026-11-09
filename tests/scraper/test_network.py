# File: tests/scraper/test_network.py
# pyright: reportPrivateUsage=false
"""Tests for the network module."""

from typing import cast
from unittest.mock import MagicMock, mock_open, patch

import requests
from flask import Flask
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from audiobook_automated.constants import (
    DEFAULT_SCRAPER_JITTER_MAX,
    DEFAULT_SCRAPER_JITTER_MIN,
    DEFAULT_TRACKERS,
    MAX_CATALOG_REDIRECTS,
    USER_AGENTS,
)
from audiobook_automated.scraper import network
from audiobook_automated.scraper.network import (
    CACHE_LOCK,
    _local,
    find_best_mirror,
    get_ping_session,
    get_trackers,
    mirror_cache,
    shutdown_network,
    tracker_cache,
)


def test_find_best_mirror_failover(app: Flask) -> None:
    """Test that find_best_mirror fails over to the next mirror on error."""
    # Setup
    mirror_cache.clear()
    mirrors = ["mirror1.com", "mirror2.com"]

    # Mocking get_ping_session to control the behavior of head requests
    with patch("audiobook_automated.scraper.network.get_mirrors", return_value=mirrors):
        with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session

            # First mirror fails (Timeout on both HEAD, HTTPS GET, and HTTP GET)
            mock_response_ok = MagicMock()
            mock_response_ok.status_code = 200
            mock_response_ok.text = "<div id='content'><div class='postTitle'>Title</div></div> audiobookbay"
            mock_response_ok.url = "https://mirror2.com/"
            mock_response_ok.elapsed.total_seconds.return_value = 0.5

            def response_for_url(url: str, **_: object) -> MagicMock:
                """Keep every bounded retry of the first host offline while the second remains healthy."""
                if "mirror1.com" in url:
                    raise requests.Timeout("Timeout")
                return mock_response_ok

            mock_session.head.side_effect = response_for_url
            mock_session.get.side_effect = response_for_url
            assert find_best_mirror() == "mirror2.com"
            assert mock_session.head.call_count == 3


def test_find_best_mirror_fast_path(app: Flask) -> None:
    """Test that find_best_mirror returns primary mirror immediately if healthy."""
    mirror_cache.clear()
    mirrors = ["primary.com", "fallback.com"]

    with patch("audiobook_automated.scraper.network.get_mirrors", return_value=mirrors):
        with patch("audiobook_automated.scraper.network.check_mirror") as mock_check:

            def mock_mirror_check(host: str) -> str | None:
                return host if host == "primary.com" else None

            mock_check.side_effect = mock_mirror_check

            best = find_best_mirror()
            assert best == "primary.com"
            mock_check.assert_called_once_with("primary.com")

    mirror_cache.clear()


# --- Merged Coverage Tests from test_network_coverage.py ---


def test_get_trackers_cache_hit(app: Flask) -> None:
    """Test that cached trackers are returned."""
    with CACHE_LOCK:
        tracker_cache.clear()
        tracker_cache["default"] = ["cached_tracker"]

    assert get_trackers() == ["cached_tracker"]

    with CACHE_LOCK:
        tracker_cache.clear()


def test_get_trackers_env_var(app: Flask) -> None:
    """Test loading trackers from environment variable."""
    with CACHE_LOCK:
        tracker_cache.clear()

    app.config["MAGNET_TRACKERS"] = ["env_tracker"]
    with app.app_context():
        assert get_trackers() == ["env_tracker"]


def test_get_trackers_file(app: Flask) -> None:
    """Test loading trackers from trackers.json."""
    with CACHE_LOCK:
        tracker_cache.clear()

    app.config["MAGNET_TRACKERS"] = []

    with patch("pathlib.Path.cwd") as mock_cwd:
        mock_file = MagicMock()
        mock_cwd.return_value = mock_file
        mock_file.__truediv__.return_value = mock_file
        mock_file.exists.return_value = True

        with patch("builtins.open", new_callable=MagicMock) as mock_open_file:
            mock_f = MagicMock()
            mock_open_file.return_value.__enter__.return_value = mock_f

            # Case 1: Valid List
            with patch("json.load", return_value=["file_tracker"]):
                with app.app_context():
                    assert get_trackers() == ["file_tracker"]
                    # Reset cache
                    with CACHE_LOCK:
                        tracker_cache.clear()

            # Case 2: Invalid Data (Dict)
            with patch("json.load", return_value={"key": "value"}):
                with app.app_context():
                    assert get_trackers() == DEFAULT_TRACKERS
                    with CACHE_LOCK:
                        tracker_cache.clear()

            # Case 3: Exception
            with patch("json.load", side_effect=Exception("Read Error")):
                with app.app_context():
                    assert get_trackers() == DEFAULT_TRACKERS


def test_get_ping_session_init(app: Flask) -> None:
    """Test initialization of ping session."""
    _local.ping_session = None
    session = get_ping_session()
    assert session is not None
    assert isinstance(session, requests.Session)
    assert _local.ping_session == session


def test_find_best_mirror_fallback_logic(app: Flask) -> None:
    """Test failover to GET when HEAD fails with 403/405 or exception."""
    network.mirror_cache.clear()
    network.failure_cache.clear()

    with patch("audiobook_automated.scraper.network.get_mirrors", return_value=["mirror1.com"]):
        with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session

            # Case 1: HEAD returns 403, GET succeeds
            mock_head_resp = MagicMock()
            mock_head_resp.status_code = 403
            mock_session.head.return_value = mock_head_resp

            mock_get_resp = MagicMock()
            mock_get_resp.status_code = 200
            mock_get_resp.text = "<div id='content'><div class='postTitle'>Title</div></div> audiobookbay"
            mock_get_resp.url = "https://mirror1.com/"
            # Ensure GET doesn't fail on close()
            mock_get_resp.close = MagicMock()
            mock_session.get.return_value = mock_get_resp

            assert find_best_mirror() == "mirror1.com"

            # Clear cache for next case
            network.mirror_cache.clear()

            # Case 2: HEAD raises RequestException, GET succeeds
            mock_session.head.side_effect = requests.RequestException("Error")
            assert find_best_mirror() == "mirror1.com"
            mock_session.head.side_effect = None  # Reset
            # Restore HEAD return value
            mock_session.head.return_value = mock_head_resp

            # Clear cache for next case
            network.mirror_cache.clear()

            # Case 3: Both Fail
            # HEAD fails (e.g. 500)
            mock_session.head.return_value.status_code = 500
            # GET raises Timeout
            mock_session.get.side_effect = requests.Timeout("Timeout")

            assert find_best_mirror() is None


def test_find_best_mirror_negative_cache(app: Flask) -> None:
    """Test negative caching (failure_cache)."""
    network.mirror_cache.clear()
    network.failure_cache.clear()

    # Force failure to set negative cache
    with patch("audiobook_automated.scraper.network.get_mirrors", return_value=[]):
        find_best_mirror()

    # Now valid mirrors exist but cache should block
    with patch("audiobook_automated.scraper.network.get_mirrors", return_value=["valid.com"]):
        # Negative cache logic uses time.time(), so we can't easily jump ahead without mocking time
        # But we can verify it returns None immediately
        assert find_best_mirror() is None


def test_shutdown_executors() -> None:
    """Test shutdown of executors."""
    # Use the public shutdown function directly
    # Mock the internal executor to ensure it gets called
    with patch("audiobook_automated.scraper.network._mirror_executor.shutdown") as mock_shutdown:
        shutdown_network()
        mock_shutdown.assert_called_with(wait=False, cancel_futures=True)


def test_get_ping_session_configuration() -> None:
    """Test that get_ping_session configures ZERO retries."""
    session = network.get_ping_session()
    adapter = cast(HTTPAdapter, session.adapters["https://"])
    retry = adapter.max_retries

    assert isinstance(retry, Retry)
    assert retry.total == 0
    assert retry.backoff_factor == 0


def test_get_ping_session_singleton() -> None:
    """Test that get_ping_session returns the same singleton instance."""
    # Reset thread-local singleton
    network._local.ping_session = None

    session1 = network.get_ping_session()
    session2 = network.get_ping_session()

    assert session1 is not None
    assert session1 is session2


def test_get_thread_session_initialization() -> None:
    """Test that get_thread_session creates a session and reuses it."""
    # Ensure we start with a clean state for this thread
    network._local.session = None

    # First call: Should create a new session
    session1 = network.get_thread_session()
    assert isinstance(session1, requests.Session)

    # Second call: Should return the EXACT SAME session object (reuse)
    session2 = network.get_thread_session()
    assert session1 is session2


def test_check_mirror_success_head() -> None:
    """Test verifying a mirror via a successful HEAD request."""
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
        mock_session = mock_get_session.return_value
        mock_session.head.return_value.status_code = 200
        mock_session.get.return_value.status_code = 200
        mock_session.get.return_value.text = "<div id='content'><div class='postTitle'>Title</div></div> audiobookbay"
        mock_session.get.return_value.url = "https://good.mirror/"
        result = network.check_mirror("good.mirror")
        assert result == "good.mirror"


def test_check_mirror_success_get_fallback() -> None:
    """Test fallback to GET if HEAD raises an exception."""
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
        mock_session = mock_get_session.return_value
        mock_session.head.side_effect = requests.RequestException("Method Not Allowed")
        mock_session.get.return_value.status_code = 200
        mock_session.get.return_value.text = "<div id='content'><div class='postContent'>Body</div></div> audiobookbay"
        mock_session.get.return_value.url = "https://fallback.mirror/"
        # Ensure GET doesn't fail on close()
        mock_session.get.return_value.close = MagicMock()

        result = network.check_mirror("fallback.mirror")
        assert result == "fallback.mirror"


def test_check_mirror_head_500_fallback() -> None:
    """Test that HEAD 500 does NOT fallback to GET and returns None."""
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
        mock_session = mock_get_session.return_value
        mock_session.head.return_value.status_code = 500
        mock_session.get.return_value.status_code = 200
        mock_session.get.return_value.text = "<div id='content'><div class='postTitle'>Title</div></div> audiobookbay"
        mock_session.get.return_value.url = "https://flaky.mirror/"

        result = network.check_mirror("flaky.mirror")
        assert result is None


def test_check_mirror_head_405_fallback() -> None:
    """Test fallback to GET if HEAD returns 405 Method Not Allowed."""
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
        mock_session = mock_get_session.return_value
        # HEAD returns 405
        mock_session.head.return_value.status_code = 405
        # GET returns 200
        mock_session.get.return_value.status_code = 200
        mock_session.get.return_value.text = "<div id='content'><div class='postTitle'>Title</div></div> audiobookbay"
        mock_session.get.return_value.url = "https://fallback.mirror/"
        # Ensure GET doesn't fail on close()
        mock_session.get.return_value.close = MagicMock()

        result = network.check_mirror("fallback.mirror")
        assert result == "fallback.mirror"
        # Verify both called
        mock_session.head.assert_called()
        mock_session.get.assert_called()


def test_check_mirror_get_exception() -> None:
    """Test check_mirror returns None if both HEAD and GET fail."""
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
        mock_session = mock_get_session.return_value
        mock_session.head.side_effect = requests.RequestException("HEAD Failed")
        mock_session.get.side_effect = requests.RequestException("GET Failed")

        result = network.check_mirror("bad.mirror")
        assert result is None


def test_check_mirror_timeout_fallback() -> None:
    """Test Fallback: check_mirror should try GET if HEAD times out."""
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
        mock_session = mock_get_session.return_value
        # HEAD times out
        mock_session.head.side_effect = requests.Timeout("Connection Timed Out")
        # GET succeeds
        mock_session.get.return_value.status_code = 200
        mock_session.get.return_value.text = "<div id='content'><div class='postTitle'>Title</div></div> audiobookbay"
        mock_session.get.return_value.url = "https://timeout.mirror/"
        # Ensure GET doesn't fail on close()
        mock_session.get.return_value.close = MagicMock()

        result = network.check_mirror("timeout.mirror")

        assert result == "timeout.mirror"
        # Verify GET was called
        mock_session.get.assert_called()


def test_find_best_mirror_cached(app: Flask) -> None:
    """Test that find_best_mirror returns cached value directly."""
    # Clear caches to remove any negative cache
    network.mirror_cache.clear()
    network.failure_cache.clear()

    # Setup cache state manually
    network.mirror_cache["active_mirror"] = "cached-mirror.lu"

    with app.app_context():
        # Execute - should return immediately without calling get_mirrors or checking them
        # We do NOT patch check_mirror here to prove it doesn't get called (would error if called)
        result = network.find_best_mirror()

        assert result == "cached-mirror.lu"
    # Clean up to avoid pollution
    network.mirror_cache.clear()


def test_find_best_mirror_negative_cache_hit(app: Flask) -> None:
    """Test that the function returns None immediately if negative cache is active."""
    # Inject failure into cache
    with network.CACHE_LOCK:
        network.failure_cache["failure"] = True

    with app.app_context():
        # Attempt to find mirror (should skip all network calls)
        with patch("audiobook_automated.scraper.network.get_mirrors") as mock_get:
            result = network.find_best_mirror()
            assert result is None
            mock_get.assert_not_called()


def test_find_best_mirror_all_down(app: Flask) -> None:
    """Test find_best_mirror when all mirrors fail check."""
    network.mirror_cache.clear()
    network.failure_cache.clear()

    with patch("audiobook_automated.scraper.network.get_mirrors", return_value=["down1.com", "down2.com"]):
        with patch("audiobook_automated.scraper.network.check_mirror", return_value=None):
            result = network.find_best_mirror()
            assert result is None
            with network.CACHE_LOCK:
                assert "failure" in network.failure_cache

    network.failure_cache.clear()


def test_get_random_user_agent_returns_string() -> None:
    """Test that the user agent generator returns a string from the known list."""
    ua = network.get_random_user_agent()
    assert isinstance(ua, str)
    assert len(ua) > 10
    assert ua in USER_AGENTS


def test_get_trackers_json_invalid_syntax(app: Flask) -> None:
    """Test when trackers.json exists but contains invalid JSON syntax."""
    network.tracker_cache.clear()
    app.config["MAGNET_TRACKERS"] = []

    with patch("pathlib.Path.exists", return_value=True):
        # Use mock_open but make the read return invalid JSON text
        with patch("builtins.open", mock_open(read_data="{invalid_json")):
            with patch("audiobook_automated.scraper.network.logger") as mock_logger:
                trackers = network.get_trackers()

                # Should fallback to defaults
                assert trackers == DEFAULT_TRACKERS

                # Verify warning was logged
                args, _ = mock_logger.warning.call_args
                # The actual message depends on the implementation, but it usually catches JSONDecodeError
                # checking for "Failed to load" or similar
                assert "Failed to load trackers.json" in args[0]


def test_get_semaphore() -> None:
    """Test retrieving the global semaphore."""
    sem = network.get_semaphore()
    # It should be a BoundedSemaphore
    assert isinstance(sem, network.threading.BoundedSemaphore)


def test_get_headers_with_referer() -> None:
    """Test get_headers with a referer."""
    headers = network.get_headers(referer="http://ref.com")
    assert headers["Referer"] == "http://ref.com"


def test_mirror_stats_tracking() -> None:
    """Test MirrorStat recording success, failure, cooldown, and scoring."""
    stat = network.MirrorStat(hostname="test.mirror")
    assert stat.total_requests == 0
    assert stat.success_rate == 1.0
    assert not stat.is_cooling_down

    # Success records EMA latency
    stat.record_success(100.0)
    assert stat.success_count == 1
    assert stat.ema_latency_ms == 100.0
    assert stat.total_requests == 1
    assert stat.success_rate == 1.0

    stat.record_success(200.0)
    # EMA: 0.7 * 100 + 0.3 * 200 = 130
    assert stat.ema_latency_ms == 130.0

    # Failure applies cooldown
    stat.record_failure("HTTP 500")
    assert stat.failure_count == 1
    assert stat.is_cooling_down
    assert stat.last_error == "HTTP 500"
    assert stat.score < 0


def test_get_all_mirror_stats() -> None:
    """Test get_all_mirror_stats snapshot."""
    stat = network.get_mirror_stat("stat.test")
    stat.record_success(50.0)
    all_stats = network.get_all_mirror_stats()
    assert any(s["hostname"] == "stat.test" for s in all_stats)


def test_fetch_remote_mirrors(app: Flask) -> None:
    """Test remote mirrors fetch and caching."""
    network._remote_mirrors_cache.clear()

    # Success case via remote URL
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_ping:
        mock_sess = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ["remote1.com", "remote2.com"]
        mock_sess.get.return_value = mock_resp
        mock_ping.return_value = mock_sess

        mirrors = network.fetch_remote_mirrors()
        assert mirrors == ["remote1.com", "remote2.com"]

    # Cached
    assert network.fetch_remote_mirrors() == ["remote1.com", "remote2.com"]

    # Fallback to local examples/mirrors.json on network error
    network._remote_mirrors_cache.clear()
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_ping:
        mock_sess = MagicMock()
        mock_sess.get.side_effect = requests.RequestException("Network error")
        mock_ping.return_value = mock_sess

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data='["local1.com", "local2.com"]')):
                mirrors = network.fetch_remote_mirrors()
                assert mirrors == ["local1.com", "local2.com"]


def test_get_mirrors_ranking(app: Flask) -> None:
    """Test adaptive ranking of mirrors in get_mirrors."""
    app.config["ABB_HOSTNAME"] = "primary.com"
    app.config["ABB_MIRRORS"] = ["mirror2.com", "mirror3.com"]

    with patch("audiobook_automated.scraper.network.fetch_remote_mirrors", return_value=["mirror4.com"]):
        # Untried: primary comes first
        mirrors = network.get_mirrors()
        assert mirrors[0] == "primary.com"

        # Record high score for mirror2
        stat_m2 = network.get_mirror_stat("mirror2.com")
        stat_m2.record_success(10.0)

        # Primary cools down
        stat_primary = network.get_mirror_stat("primary.com")
        stat_primary.record_failure("offline")

        ranked = network.get_mirrors()
        assert ranked[0] == "mirror2.com"


def test_fetch_remote_mirrors_fallback_on_invalid_file(app: Flask) -> None:
    """Test fallback when local mirrors.json cannot be read."""
    network._remote_mirrors_cache.clear()
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_ping:
        mock_sess = MagicMock()
        mock_sess.get.side_effect = requests.RequestException("Remote down")
        mock_ping.return_value = mock_sess

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", side_effect=OSError("Read error")):
                mirrors = network.fetch_remote_mirrors()
                assert mirrors == network.DEFAULT_MIRRORS


def test_is_authentic_catalog_edge_cases() -> None:
    """Test semantic verification rules for authentic catalogs."""
    assert not network.is_authentic_catalog("")
    assert not network.is_authentic_catalog("<html>Domain is parked</html>")
    assert not network.is_authentic_catalog("<html>Buy this domain</html>")
    assert not network.is_authentic_catalog("<html>Random unrelated HTML</html>")
    assert not network.is_authentic_catalog(
        "<div id='content'><div class='postTitle'>Title</div></div> audiobookbay",
        final_url="https://expireddomains.net/",
    )
    assert network.is_authentic_catalog(
        "<div id='content'><div class='postTitle'>Title</div></div> audiobookbay", final_url="https://audiobookbay.lu/"
    )


def test_check_mirror_semantic_verification_failure() -> None:
    """Test that check_mirror records failure when HTTP 200 is returned but catalog is inauthentic."""
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
        mock_session = mock_get_session.return_value
        # HEAD returns 200, but GET text is inauthentic
        mock_session.head.return_value.status_code = 200
        mock_session.get.return_value.status_code = 200
        mock_session.get.return_value.text = "<html>Welcome to parked page</html>"
        mock_session.get.return_value.url = "https://fake.mirror/"

        assert network.check_mirror("fake.mirror") is None


def test_check_mirror_https_get_inauthentic_and_http_fallback() -> None:
    """Test check_mirror HTTPS GET inauthentic failure and HTTP GET fallback."""
    with patch("audiobook_automated.scraper.network.get_ping_session") as mock_get_session:
        mock_session = mock_get_session.return_value
        # HEAD fails
        mock_session.head.side_effect = requests.RequestException("HEAD error")
        # HTTPS GET returns 200 but fake
        fake_resp = MagicMock(status_code=200, text="<html>Fake</html>", url="https://fake.mirror/")
        # HTTP GET succeeds with authentic catalog
        ok_resp = MagicMock(
            status_code=200,
            text="<div id='content'><div class='postTitle'>Title</div></div> audiobookbay",
            url="http://fake.mirror/",
        )
        mock_session.get.side_effect = [fake_resp, fake_resp]

        # Inauthentic HTTPS and HTTP GET should return None
        assert network.check_mirror("fake.mirror") is None

        # HTTPS GET non-200 (e.g. 500) then HTTP GET 200
        err_resp = MagicMock(status_code=500)
        mock_session.get.side_effect = [err_resp, ok_resp]
        ok_resp.url = "http://https500.mirror/"
        assert network.check_mirror("https500.mirror") == "https500.mirror"

        # When HTTPS GET throws exception, it falls back to HTTP GET
        mock_session.get.side_effect = [requests.RequestException("HTTPS failed"), ok_resp]
        ok_resp.url = "http://legit.http.mirror/"
        assert network.check_mirror("legit.http.mirror") == "legit.http.mirror"

        # HTTP GET inauthentic returns None
        mock_session.get.side_effect = [requests.RequestException("HTTPS failed"), fake_resp]
        assert network.check_mirror("fake2.mirror") is None

        # HTTP GET 500 returns None
        err_resp = MagicMock(status_code=500)
        mock_session.get.side_effect = [requests.RequestException("HTTPS failed"), err_resp]
        assert network.check_mirror("fake3.mirror") is None


def test_get_mirror_base_url_and_protocol_scoring(app: Flask) -> None:
    """Test get_mirror_base_url and HTTPS vs HTTP score weighting."""
    stat_https = network.get_mirror_stat("https-mirror.com")
    stat_https.record_success(latency_ms=100.0, protocol="https")
    assert network.get_mirror_base_url("https-mirror.com") == "https://https-mirror.com"

    stat_http = network.get_mirror_stat("http-mirror.com")
    stat_http.record_success(latency_ms=100.0, protocol="http")
    assert network.get_mirror_base_url("http-mirror.com") == "http://http-mirror.com"

    # With similar success rate and latency, HTTPS scores higher due to protocol bonus
    assert stat_https.score > stat_http.score

    # Accuracy > Speed > Security:
    # A fast HTTP mirror (80% rate, 580ms latency) MUST rank higher than
    # a slow HTTPS mirror (100% rate, 40,000ms latency).
    stat_fast_http = network.get_mirror_stat("fast-http.com")
    stat_fast_http.record_success(latency_ms=580.0, protocol="http")
    # Simulate 80% success (4 success, 1 failure)
    stat_fast_http.success_count = 4
    stat_fast_http.failure_count = 1
    stat_fast_http.cooldown_until = 0.0  # not in cooldown for test comparison

    stat_slow_https = network.get_mirror_stat("slow-https.com")
    stat_slow_https.record_success(latency_ms=40000.0, protocol="https")
    stat_slow_https.success_count = 10
    stat_slow_https.failure_count = 0

    assert stat_fast_http.score > stat_slow_https.score
    assert stat_fast_http.score > 700.0
    assert stat_slow_https.score < 0.0

    # Parked mirror has 0 success_rate and large negative score
    stat_parked = network.get_mirror_stat("parked-domain.com")
    stat_parked.record_failure("Non-authentic catalog", is_parked=True)
    assert stat_parked.is_parked_or_invalid is True
    assert stat_parked.success_rate == 0.0
    assert stat_parked.score == -9999.0
    assert stat_parked.is_cooling_down is True


def test_get_active_search_mirrors(app: Flask) -> None:
    """Test pruning candidate mirrors to top 3 search mirrors and fallback when all cool down."""
    with patch(
        "audiobook_automated.scraper.network.get_mirrors", return_value=["m1.com", "m2.com", "m3.com", "m4.com"]
    ):
        active = network.get_active_search_mirrors(limit=3)
        assert len(active) == 3
        assert active == ["m1.com", "m2.com", "m3.com"]

        # When all cool down, fallback to top candidates anyway
        for m in ["m1.com", "m2.com", "m3.com", "m4.com"]:
            network.get_mirror_stat(m).record_failure("error")
        fallback_active = network.get_active_search_mirrors(limit=2)
        assert len(fallback_active) == 2


def test_record_request_outcome_success_and_failure(app: Flask) -> None:
    """Real request outcomes update mirror stats; a failure backs off and drops the cached mirror."""
    host = "outcome.example"
    with app.app_context():
        network.record_request_outcome("not-a-url", True)  # no netloc -> ignored
        network.record_request_outcome(f"http://{host}/x", True, 120.0)
        stat = network.get_mirror_stat(host)
        assert stat.protocol == "http"
        assert stat.success_count == 1

        network.mirror_cache["active_mirror"] = host
        network.record_request_outcome(f"https://{host}/x", False, error="boom")
        assert stat.failure_count == 1
        assert stat.is_cooling_down
        assert "active_mirror" not in network.mirror_cache

        # Failure on a different mirror leaves the cached active mirror alone.
        network.mirror_cache["active_mirror"] = "other.example"
        network.record_request_outcome(f"https://{host}/x", False)
        assert network.mirror_cache["active_mirror"] == "other.example"
        network.mirror_cache.clear()


def test_check_mirror_after_delays_then_probes() -> None:
    """The staggered failover probe sleeps its jittered delay before checking."""
    with (
        patch("audiobook_automated.scraper.network.time.sleep") as sleep,
        patch("audiobook_automated.scraper.network.check_mirror", return_value="m.example") as check,
    ):
        assert network._check_mirror_after("m.example", 0.3) == "m.example"  # pyright: ignore[reportPrivateUsage]
        sleep.assert_called_once_with(0.3)
        sleep.reset_mock()
        network._check_mirror_after("m.example", 0.0)  # pyright: ignore[reportPrivateUsage]
        sleep.assert_not_called()
        assert check.call_count == 2


def test_mirror_probes_obey_the_same_request_budget() -> None:
    """HEAD and semantic GET probes must acquire the global semaphore and wait mandatory jitter."""
    response = MagicMock(
        status_code=200,
        text="<div id='content'><div class='postTitle'>Book</div></div> audiobookbay",
        url="https://bounded.example/",
        headers={},
    )
    with (
        patch.object(network, "get_ping_session") as session,
        patch.object(network, "get_semaphore") as semaphore,
        patch("audiobook_automated.scraper.network.time.sleep") as sleep,
    ):
        session.return_value.head.return_value = response
        session.return_value.get.return_value = response
        assert network.check_mirror("bounded.example") == "bounded.example"
        assert semaphore.call_count == 2
        assert sleep.call_count == 2
        assert all(
            DEFAULT_SCRAPER_JITTER_MIN <= call.args[0] <= DEFAULT_SCRAPER_JITTER_MAX for call in sleep.call_args_list
        )


def test_parked_mirror_is_eligible_for_recheck_after_its_cooldown() -> None:
    """A stated 24-hour parked-domain cooldown must not disable a recovered mirror forever."""
    with patch("audiobook_automated.scraper.network.time.time", return_value=1000.0) as clock:
        stat = network.MirrorStat("recover.example")
        stat.record_failure("Parked", is_parked=True)
        assert stat.is_cooling_down
        clock.return_value = 1000.0 + 86401
        assert not stat.is_cooling_down


def test_transient_backoff_resets_after_a_success() -> None:
    """Historical failures remain in accuracy statistics but do not lengthen a new failure streak."""
    with patch("audiobook_automated.scraper.network.time.time", return_value=1000.0):
        stat = network.MirrorStat("streak.example")
        stat.record_failure("First")
        stat.record_failure("Second")
        stat.record_success(20)
        stat.record_failure("New streak")
        assert stat.cooldown_until == 1015.0
        assert stat.failure_count == 3


def test_verified_faster_mirror_can_outrank_a_slow_primary(app: Flask) -> None:
    """Configured primary is an initial preference, not a permanent override of collected performance."""
    app.config.update(ABB_HOSTNAME="slow.example", ABB_MIRRORS=["fast.example"])
    with patch.object(network, "_mirror_stats", {}), patch.object(network, "fetch_remote_mirrors", return_value=[]):
        network.get_mirror_stat("slow.example").record_success(10000)
        network.get_mirror_stat("fast.example").record_success(100)
        assert network.get_mirrors()[0] == "fast.example"


def test_probes_reject_catalog_lookalikes_on_foreign_redirects() -> None:
    """A copied title/brand on an unrelated destination must not qualify a mirror as healthy."""
    with patch.object(network, "get_ping_session") as session:
        session.return_value.head.return_value.status_code = 200
        session.return_value.get.return_value = MagicMock(
            status_code=200,
            text="<div id='content'><div class='postTitle'>Book</div></div> audiobookbay",
            url="https://unrelated.example/",
            headers={},
        )
        assert network.check_mirror("redirect.example") is None


def test_catalog_verification_requires_a_real_content_container() -> None:
    """A brand word and unrelated class substring do not establish catalog structure."""
    assert not network.is_authentic_catalog("<div class='postTitle'>Book</div> audiobookbay")


def test_redirects_keep_the_catalog_host_and_wait_between_hops() -> None:
    """Exercise real Session redirect handling without contacting a redirected third-party destination."""
    import pytest
    import requests_mock

    with requests_mock.Mocker() as boundary, patch("audiobook_automated.scraper.network.time.sleep") as sleep:
        boundary.get("https://catalog.example/start", status_code=302, headers={"Location": "/finish"})
        boundary.get("https://catalog.example/finish", text="Catalog")
        response, latency = network.request_external(network.get_session(), "https://catalog.example/start", timeout=2)
        assert response.text == "Catalog"
        assert latency >= 0
        assert len(boundary.request_history) == 2
        assert sleep.call_count == 2
        boundary.get(
            "https://catalog.example/foreign", status_code=302, headers={"Location": "https://unrelated.example/"}
        )
        with pytest.raises(requests.ConnectionError, match="outside"):
            network.request_external(network.get_session(), "https://catalog.example/foreign", timeout=2)
        assert all(request.hostname == "catalog.example" for request in boundary.request_history)


def test_redirect_loops_and_missing_destinations_are_bounded() -> None:
    """A redirect without Location or a same-host loop must stop within a fixed request budget."""
    import pytest
    import requests_mock

    with requests_mock.Mocker() as boundary:
        boundary.get("https://catalog.example/missing", status_code=302)
        with pytest.raises(requests.ConnectionError, match="redirect"):
            network.request_external(network.get_session(), "https://catalog.example/missing", timeout=2)
        boundary.get("https://catalog.example/loop", status_code=302, headers={"Location": "/loop"})
        with pytest.raises(requests.ConnectionError, match="limit"):
            network.request_external(network.get_session(), "https://catalog.example/loop", timeout=2)
        assert len(boundary.request_history) == 1 + MAX_CATALOG_REDIRECTS + 1


def test_transport_retry_is_bounded_and_reacquires_request_budget() -> None:
    """A transient connection failure retries once with fresh jitter and no hidden adapter retries."""
    import pytest

    session = MagicMock()
    session.get.side_effect = [requests.Timeout("Transient"), MagicMock(status_code=200)]
    with (
        patch("audiobook_automated.scraper.network.time.sleep") as sleep,
        patch("audiobook_automated.scraper.network.time.perf_counter", side_effect=[1.0, 2.0, 3.0, 5.0]),
    ):
        _, latency = network.request_external(session, "https://catalog.example/", timeout=2)
        assert sleep.call_count == 2
        assert latency == 3000.0
    session.get.side_effect = requests.ConnectionError("Offline")
    with pytest.raises(requests.ConnectionError):
        network.request_external(session, "https://catalog.example/", timeout=2)
    assert session.get.call_count == 4
    session.get.reset_mock()
    session.get.side_effect = requests.exceptions.SSLError("Bad certificate")
    with pytest.raises(requests.exceptions.SSLError):
        network.request_external(session, "https://catalog.example/", timeout=2)
    session.get.assert_called_once()


def test_request_session_has_no_automatic_transport_retries() -> None:
    """Only explicitly budgeted attempts may reach the catalog."""
    session = network.get_session()
    assert cast(HTTPAdapter, session.adapters["https://"]).max_retries.total == 0
    session.close()


def test_all_cooling_down_mirrors_are_not_probed(app: Flask) -> None:
    """Backoff remains effective even when every candidate is temporarily unavailable."""
    with (
        patch.object(network, "get_mirrors", return_value=["cool.example"]),
        patch.object(network, "check_mirror") as check,
    ):
        network.get_mirror_stat("cool.example").record_failure("Offline")
        assert network.find_best_mirror() is None
        check.assert_not_called()


def test_failure_backoff_reaches_cap_without_growing_forever() -> None:
    """Repeated failures reach the stated five-minute cap."""
    with patch("audiobook_automated.scraper.network.time.time", return_value=1000.0):
        stat = network.MirrorStat("cap.example")
        for _ in range(10):
            stat.record_failure("Offline")
        assert stat.cooldown_until == 1300.0


def test_request_external_configurable_jitter(app: Flask) -> None:
    """Configured jitter min and max are respected and inverted bounds are swapped."""
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200, headers={})
    app.config["SCRAPER_JITTER_MIN"] = 0.5
    app.config["SCRAPER_JITTER_MAX"] = 0.2

    with (
        patch("audiobook_automated.scraper.network.random.uniform", return_value=0.3) as uniform,
        patch("audiobook_automated.scraper.network.time.sleep") as sleep,
    ):
        network.request_external(session, "https://catalog.example/", timeout=2)
        uniform.assert_called_with(0.2, 0.5)
        sleep.assert_called_once_with(0.3)
