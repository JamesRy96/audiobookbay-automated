# File: tests/functional/test_diagnostics.py
"""Tests for the diagnostics endpoints and dashboard."""

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from audiobook_automated import diagnostics
from audiobook_automated.extensions import torrent_manager
from audiobook_automated.logging_buffer import log_ring_buffer
from audiobook_automated.scraper import network


@pytest.fixture(autouse=True)
def _reset_probe_cache() -> None:
    """Expire the external probe cache so each test starts with a fresh probe."""
    diagnostics.probe_cache.update({"expires": 0.0, "taken": 0.0, "manual": 0.0, "clients": []})


def _fresh_get(client: FlaskClient) -> Any:
    """GET the health endpoint after expiring the probe cache."""
    diagnostics.probe_cache["expires"] = 0.0
    client.get("/api/diagnostics/health")
    _wait_for_client_check()
    return client.get("/api/diagnostics/health")


def _wait_for_client_check() -> None:
    """Wait only for the test's mocked client work, without relying on a scheduling race."""
    deadline = time.monotonic() + 2
    while diagnostics.probe_state["clients_running"]:
        assert time.monotonic() < deadline, "Client test work did not complete"
        threading.Event().wait(0.001)


def test_diagnostics_disabled_by_default(app: Flask, client: FlaskClient) -> None:
    """Ensure diagnostics routes return 404 when disabled."""
    app.config["ENABLE_DIAGNOSTICS"] = False
    app.config["FLASK_DEBUG"] = False
    app.config["TESTING"] = False

    resp = client.get("/diagnostics")
    assert resp.status_code == 404

    resp_health = client.get("/api/diagnostics/health")
    assert resp_health.status_code == 404

    resp_inspect = client.get("/api/diagnostics/inspect?query=test")
    assert resp_inspect.status_code == 404


def test_diagnostics_dashboard_enabled(app: Flask, client: FlaskClient) -> None:
    """Ensure diagnostics dashboard renders successfully when enabled."""
    app.config["ENABLE_DIAGNOSTICS"] = True
    resp = client.get("/diagnostics")
    assert resp.status_code == 200
    assert b"System Diagnostics" in resp.data
    assert b"Live Parser & Metadata Inspector" in resp.data


def test_diagnostics_health_api(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/health returns correct JSON structure."""
    app.config["ENABLE_DIAGNOSTICS"] = True

    strat_mock = MagicMock()
    strat_mock.verify_credentials.return_value = True
    strat_mock.last_auth_error = None
    strat_mock.is_ip_banned = False
    strat_mock.auth_cooldown_until = 0.0

    strat_fail = MagicMock()
    strat_fail.verify_credentials.side_effect = RuntimeError("Offline client")
    strat_fail.last_auth_error = None
    strat_fail.is_ip_banned = False
    strat_fail.auth_cooldown_until = 0.0

    with patch.object(torrent_manager, "clients", {"client1": strat_mock, "client2": strat_fail}):
        with patch("audiobook_automated.scraper.network.check_mirror", return_value="audiobookbay.lu"):
            resp = _fresh_get(client)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "healthy"
            assert "system" in data
            assert "mirrors" in data
            assert "cache" in data
            assert "clients" in data
            assert len(data["clients"]) == 2
            assert data["clients"][0]["connected"] is True
            assert data["clients"][1]["connected"] is False
            assert "Offline client" in data["clients"][1]["error"]


def test_diagnostics_health_api_single_client_statuses(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/health covers single client status fallback branches."""
    app.config["ENABLE_DIAGNOSTICS"] = True

    client_inst = MagicMock()
    client_inst.verify_credentials.return_value = False
    client_inst.is_ip_banned = True
    client_inst.auth_cooldown_until = 0.0
    client_inst.last_auth_error = "IP banned by host"

    with patch.object(torrent_manager, "clients", {}):
        with patch.object(torrent_manager, "client", client_inst):
            with patch.object(torrent_manager, "verify_credentials", return_value=False):
                with patch("audiobook_automated.scraper.network.check_mirror", return_value="audiobookbay.lu"):
                    resp = _fresh_get(client)
                    assert resp.status_code == 200
                    data = resp.get_json()
                    assert data["clients"][0]["status"] == "IP Banned"

    # Cooldown branch
    client_inst.is_ip_banned = False
    client_inst.auth_cooldown_until = 9999999999.0
    with patch.object(torrent_manager, "clients", {}):
        with patch.object(torrent_manager, "client", client_inst):
            with patch.object(torrent_manager, "verify_credentials", return_value=False):
                with patch("audiobook_automated.scraper.network.check_mirror", return_value="audiobookbay.lu"):
                    resp = _fresh_get(client)
                    assert resp.status_code == 200
                    data = resp.get_json()
                    assert data["clients"][0]["status"] == "Auth Cooldown"

    # Auth error branch
    client_inst.auth_cooldown_until = 0.0
    client_inst.last_auth_error = "Invalid password"
    with patch.object(torrent_manager, "clients", {}):
        with patch.object(torrent_manager, "client", client_inst):
            with patch.object(torrent_manager, "verify_credentials", return_value=False):
                with patch("audiobook_automated.scraper.network.check_mirror", return_value="audiobookbay.lu"):
                    resp = _fresh_get(client)
                    assert resp.status_code == 200
                    data = resp.get_json()
                    assert data["clients"][0]["status"] == "Auth Failed"


def test_diagnostics_health_api_configured_clients_statuses(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/health covers configured_clients status labels."""
    app.config["ENABLE_DIAGNOSTICS"] = True

    client1 = MagicMock()
    client1.verify_credentials.return_value = False
    client1.is_ip_banned = True
    client1.auth_cooldown_until = 0.0
    client1.last_auth_error = "IP ban"

    client2 = MagicMock()
    client2.verify_credentials.return_value = False
    client2.is_ip_banned = False
    client2.auth_cooldown_until = 9999999999.0
    client2.last_auth_error = None

    client3 = MagicMock()
    client3.verify_credentials.return_value = False
    client3.is_ip_banned = False
    client3.auth_cooldown_until = 0.0
    client3.last_auth_error = "Wrong password"

    client4 = MagicMock()
    client4.verify_credentials.return_value = False
    client4.is_ip_banned = False
    client4.auth_cooldown_until = 0.0
    client4.last_auth_error = None

    client_exc_banned = MagicMock()
    client_exc_banned.verify_credentials.side_effect = Exception("Host banned our ip")
    client_exc_banned.is_ip_banned = True

    client_exc_auth = MagicMock()
    client_exc_auth.verify_credentials.side_effect = Exception("Auth failed: bad token")
    client_exc_auth.last_auth_error = "Auth failed: bad token"

    clients_dict = {
        "c1": client1,
        "c2": client2,
        "c3": client3,
        "c4": client4,
        "c5": client_exc_banned,
        "c6": client_exc_auth,
    }

    with patch.object(torrent_manager, "clients", clients_dict):
        with patch("audiobook_automated.scraper.network.check_mirror", return_value="audiobookbay.lu"):
            resp = _fresh_get(client)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["clients"][0]["status"] == "IP Banned"
            assert data["clients"][1]["status"] == "Auth Cooldown"
            assert data["clients"][2]["status"] == "Auth Failed"
            assert data["clients"][3]["status"] == "Disconnected"
            assert data["clients"][4]["status"] == "IP Banned"
            assert data["clients"][5]["status"] == "Auth Failed"


def test_diagnostics_health_api_resource_exception(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/health handles resource getrusage exceptions gracefully."""
    app.config["ENABLE_DIAGNOSTICS"] = True

    with patch.object(torrent_manager, "clients", {}):
        with patch("resource.getrusage", side_effect=Exception("ru_maxrss error")):
            with patch("audiobook_automated.scraper.network.check_mirror", return_value=None):
                resp = _fresh_get(client)
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["system"]["memory_rss_mb"] == 0.0


def test_diagnostics_inspect_missing_params(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/inspect requires url or query."""
    app.config["ENABLE_DIAGNOSTICS"] = True
    resp = client.get("/api/diagnostics/inspect")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Either 'url' or 'query' parameter is required"}


def test_diagnostics_inspect_query(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/inspect works for search queries."""
    app.config["ENABLE_DIAGNOSTICS"] = True

    mock_results = [{"title": "Test Book", "link": "/abss/test/"}]
    with patch("audiobook_automated.scraper.core.search_audiobookbay", return_value=mock_results) as search:
        resp = client.get("/api/diagnostics/inspect?query=Test")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["type"] == "search"
        assert data["count"] == 1
        assert data["data"] == mock_results
        search.assert_called_once_with("test", max_pages=1)


def test_diagnostics_inspect_url(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/inspect works for book detail URLs."""
    app.config["ENABLE_DIAGNOSTICS"] = True

    mock_details = {"title": "Inspect Book", "category": ["Teens & Young Adults"]}
    with patch("audiobook_automated.scraper.core.get_book_details", return_value=mock_details):
        resp = client.get("/api/diagnostics/inspect?url=/abss/test-book/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["type"] == "details"
        assert data["data"]["title"] == "Inspect Book"
        assert data["data"]["category"] == ["Teens & Young Adults"]


def test_diagnostics_inspect_url_not_found(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/inspect handles missing/failed details."""
    app.config["ENABLE_DIAGNOSTICS"] = True

    with patch("audiobook_automated.scraper.core.get_book_details", return_value=None):
        resp = client.get("/api/diagnostics/inspect?url=/abss/missing/")
        assert resp.status_code == 404
        assert "Failed to retrieve book details" in resp.get_json()["error"]


def test_diagnostics_inspect_exception(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/inspect handles internal scraping exceptions gracefully."""
    app.config["ENABLE_DIAGNOSTICS"] = True

    with patch("audiobook_automated.scraper.core.search_audiobookbay", side_effect=RuntimeError("Scraper boom")):
        resp = client.get("/api/diagnostics/inspect?query=crash")
        assert resp.status_code == 500
        assert resp.get_json() == {"error": "Scraper boom"}


def test_diagnostics_logs_endpoints(app: Flask, client: FlaskClient) -> None:
    """Ensure /api/diagnostics/logs and download work correctly."""
    app.config["ENABLE_DIAGNOSTICS"] = True
    app.logger.info("Test log entry for diagnostics endpoint")

    # JSON logs endpoint
    resp = client.get("/api/diagnostics/logs?limit=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "logs" in data
    assert data["count"] > 0

    # Invalid limit defaults gracefully
    resp_invalid = client.get("/api/diagnostics/logs?limit=notanumber")
    assert resp_invalid.status_code == 200

    # Download logs endpoint
    resp_dl = client.get("/api/diagnostics/logs/download")
    assert resp_dl.status_code == 200
    assert resp_dl.mimetype == "text/plain"
    assert "Content-Disposition" in resp_dl.headers
    assert "audiobookbay-automated-logs.txt" in resp_dl.headers["Content-Disposition"]
    assert b"Test log entry for diagnostics endpoint" in resp_dl.data


def test_diagnostics_health_polling_is_passive_and_manual_refresh_probes(app: Flask, client: FlaskClient) -> None:
    """Polling never probes mirrors; only a throttled manual refresh does. Client checks use a jittered TTL."""
    app.config["ENABLE_DIAGNOSTICS"] = True
    network.get_mirror_stat("a.example").record_success(50.0)  # already tested: no seeding probe
    with (
        patch("audiobook_automated.diagnostics._start_background_probe") as mirrors,
        patch("audiobook_automated.diagnostics._collect_client_diagnostics", return_value=[]) as clients,
        patch("audiobook_automated.diagnostics.network.get_mirrors", return_value=["a.example"]),
    ):
        assert client.get("/api/diagnostics/health").status_code == 200
        _wait_for_client_check()
        body = client.get("/api/diagnostics/health").get_json()
        assert mirrors.call_count == 0
        assert clients.call_count == 1
        assert body["mirrors"]["mirrors"][0]["hostname"] == "a.example"
        assert "probe_age_seconds" in body

        # Forced refresh inside the throttle window is ignored.
        client.get("/api/diagnostics/health?refresh=1")
        _wait_for_client_check()
        assert mirrors.call_count == 0

        # Once the throttle window has passed, a forced refresh actively probes.
        diagnostics.probe_cache["taken"] -= diagnostics.MANUAL_REFRESH_MIN_INTERVAL_SECONDS + 1
        diagnostics.probe_cache["manual"] = diagnostics.probe_cache["taken"]
        client.get("/api/diagnostics/health?refresh=1")
        _wait_for_client_check()
        assert mirrors.call_count == 1
        assert clients.call_count == 2


def test_probe_candidate_mirrors_reports_stats() -> None:
    """The active probe runs check_mirror and reports the resulting stats."""

    def checked(host: str) -> str:
        """A successful low-level probe records its observation before the snapshot is read."""
        network.get_mirror_stat(host).record_success(50)
        return host

    with patch("audiobook_automated.diagnostics.network.check_mirror", side_effect=checked):
        results = diagnostics._probe_candidate_mirrors(["p.example"])  # pyright: ignore[reportPrivateUsage]
    assert results[0]["hostname"] == "p.example"
    assert results[0]["reachable"] is True


def test_background_probe_runs_once_and_clears_flag() -> None:
    """The background probe runs on a thread, ignores overlapping requests and always resets its flag."""
    started: list[Any] = []

    class _InlineThread:
        def __init__(self, target: Any, **_: Any) -> None:
            self.target = target

        def start(self) -> None:
            started.append(self)
            self.target()

    with (
        patch("audiobook_automated.diagnostics.threading.Thread", _InlineThread),
        patch("audiobook_automated.diagnostics._probe_candidate_mirrors") as probe,
    ):
        diagnostics._start_background_probe(["a.example"])  # pyright: ignore[reportPrivateUsage]
        assert probe.call_count == 1
        assert diagnostics.probe_state["running"] is False

        probe.side_effect = RuntimeError("boom")
        diagnostics._start_background_probe(["a.example"])  # pyright: ignore[reportPrivateUsage]
        assert diagnostics.probe_state["running"] is False

        diagnostics.probe_state["running"] = True
        diagnostics._start_background_probe(["a.example"])  # pyright: ignore[reportPrivateUsage]
        assert len(started) == 2
        diagnostics.probe_state["running"] = False


def test_snapshot_marks_untested_mirrors_and_seeds_probe(app: Flask, client: FlaskClient) -> None:
    """Mirrors with no traffic report tested=False and trigger a single background probe."""
    app.config["ENABLE_DIAGNOSTICS"] = True
    with (
        patch("audiobook_automated.diagnostics._start_background_probe") as probe,
        patch("audiobook_automated.diagnostics._collect_client_diagnostics", return_value=[]),
        patch("audiobook_automated.diagnostics.network.get_mirrors", return_value=["untested-zzz.example"]),
    ):
        body = client.get("/api/diagnostics/health").get_json()
    assert body["mirrors"]["mirrors"][0]["tested"] is False
    assert body["mirrors"]["mirrors"][0]["reachable"] is False
    probe.assert_called_once()


@pytest.mark.parametrize("query", ["a", " ", "  a  "])
def test_inspector_rejects_short_queries_without_network(app: Flask, client: FlaskClient, query: str) -> None:
    """Diagnostics must enforce the same minimum and trim rules as normal search."""
    app.config["ENABLE_DIAGNOSTICS"] = True
    with patch("audiobook_automated.scraper.core.search_audiobookbay") as search:
        response = client.get("/api/diagnostics/inspect", query_string={"query": query})
    assert response.status_code == 400
    search.assert_not_called()


@pytest.mark.parametrize("limit", ["0", "-1", "-500"])
def test_log_export_limit_never_expands_on_negative_input(app: Flask, client: FlaskClient, limit: str) -> None:
    """A zero/negative log limit must not export the whole real ring buffer."""
    app.config["ENABLE_DIAGNOSTICS"] = True
    with patch.object(log_ring_buffer, "get_logs") as logs:
        response = client.get("/api/diagnostics/logs", query_string={"limit": limit})
    assert response.get_json() == {"logs": [], "count": 0}
    logs.assert_not_called()


def test_health_poll_returns_before_client_connections_finish(app: Flask, client: FlaskClient) -> None:
    """A slow Download Client must not hold a Diagnostics HTTP request or its cache lock."""
    jobs = []

    class DeferredThread:
        """Capture work without running it on the request thread."""

        def __init__(self, **kwargs: Any) -> None:
            jobs.append(kwargs)

        def start(self) -> None:
            """Leave the captured operation pending."""

    with (
        patch("audiobook_automated.diagnostics.threading.Thread", DeferredThread),
        patch.object(diagnostics, "_collect_client_diagnostics", return_value=[]) as collect,
        patch.object(diagnostics, "_start_background_probe"),
        patch.object(network, "get_mirrors", return_value=["passive.example"]),
    ):
        response = client.get("/api/diagnostics/health")
        assert response.status_code == 200
        collect.assert_not_called()
        assert response.json is not None and response.json["client_probe_running"] is True
        diagnostics._start_client_probe()  # pyright: ignore[reportPrivateUsage]
        assert len(jobs) == 1
        jobs[0]["target"]()
        collect.assert_called_once()


def test_health_poll_never_fetches_remote_mirror_metadata(app: Flask, client: FlaskClient) -> None:
    """A passive dashboard poll must not perform a potentially slow remote mirror-list request."""
    diagnostics.probe_cache["expires"] = float("inf")
    with (
        patch.object(
            network, "fetch_remote_mirrors", side_effect=AssertionError("Passive polling performed network I/O")
        ),
        patch.object(diagnostics, "_start_background_probe"),
    ):
        assert client.get("/api/diagnostics/health").status_code == 200


def test_background_client_failure_releases_running_flag_and_backs_off(app: Flask) -> None:
    """A failed client diagnostic refresh cannot wedge polling or retry on every HTTP request."""

    class InlineThread:
        """Execute the isolated worker body deterministically for its failure path."""

        def __init__(self, target: Any, **_: Any) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    with (
        app.app_context(),
        patch("audiobook_automated.diagnostics.threading.Thread", InlineThread),
        patch.object(diagnostics, "_collect_client_diagnostics", side_effect=RuntimeError("Client check failed")),
    ):
        diagnostics._start_client_probe()  # pyright: ignore[reportPrivateUsage]
    assert diagnostics.probe_state["clients_running"] is False
    assert diagnostics.probe_cache["expires"] > time.monotonic()
