# File: audiobook_automated/diagnostics.py
"""Diagnostics module providing real-time system, network, scraper, and client diagnostics.

Disabled by default in production. Enabled via ENABLE_DIAGNOSTICS=true or FLASK_DEBUG=true.
"""

from __future__ import annotations

import logging
import os
import platform
import random
import resource
import threading
import time
from typing import Any, cast

from flask import Blueprint, Flask, Response, abort, current_app, jsonify, render_template, request
from werkzeug.local import LocalProxy

from audiobook_automated.constants import MIN_SEARCH_QUERY_LENGTH
from audiobook_automated.extensions import torrent_manager
from audiobook_automated.logging_buffer import log_ring_buffer
from audiobook_automated.scraper import core, network

logger = logging.getLogger(__name__)

diagnostics_bp = Blueprint("diagnostics", __name__)

# Cache client checks for a few minutes so UI polling does not repeatedly log in.
PROBE_TTL_RANGE_SECONDS = (240.0, 480.0)
MANUAL_REFRESH_MIN_INTERVAL_SECONDS = 30.0
_probe_lock = threading.Lock()
probe_state: dict[str, bool] = {"running": False, "clients_running": False}
probe_cache: dict[str, Any] = {"expires": 0.0, "taken": 0.0, "manual": 0.0, "clients": []}


def _start_background_probe(candidates: list[str]) -> None:
    """Probe mirrors on a worker thread so a slow or timing-out mirror never stalls the HTTP response.

    The probe updates the shared mirror stats, so the next poll reports the fresh results.
    """
    with _probe_lock:
        if probe_state["running"]:
            return
        probe_state["running"] = True

    def _run() -> None:
        try:
            _probe_candidate_mirrors(candidates)
        except Exception:
            logger.exception("Diagnostics: background mirror probe failed")
        finally:
            with _probe_lock:
                probe_state["running"] = False

    threading.Thread(target=_run, name="diagnostics-mirror-probe", daemon=True).start()


def _start_client_probe() -> None:
    """Refresh private client connections off the request thread and retain the last completed snapshot."""
    with _probe_lock:
        if probe_state["clients_running"]:
            return
        probe_state["clients_running"] = True
    app = cast("LocalProxy[Flask]", current_app)._get_current_object()  # pyright: ignore[reportPrivateUsage]

    def _run() -> None:
        try:
            with app.app_context():
                clients = _collect_client_diagnostics(torrent_manager)
            with _probe_lock:
                probe_cache["clients"] = clients
                probe_cache["taken"] = time.monotonic()
                probe_cache["expires"] = probe_cache["taken"] + random.uniform(*PROBE_TTL_RANGE_SECONDS)  # noqa: S311
        except Exception:
            logger.exception("Diagnostics: background client check failed")
            with _probe_lock:
                probe_cache["expires"] = time.monotonic() + MANUAL_REFRESH_MIN_INTERVAL_SECONDS
        finally:
            with _probe_lock:
                probe_state["clients_running"] = False

    threading.Thread(target=_run, name="diagnostics-client-probe", daemon=True).start()


def _get_external_probes(force: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Return cached observations without making external requests on the HTTP request thread."""
    candidates = network.get_mirrors(refresh_remote=False)[:8]
    with _probe_lock:
        now = time.monotonic()
        manual = force and now - max(probe_cache["manual"], probe_cache["taken"]) >= MANUAL_REFRESH_MIN_INTERVAL_SECONDS
        if manual:
            probe_cache["manual"] = now
        refresh_clients = manual or now >= probe_cache["expires"]
    if refresh_clients:
        _start_client_probe()
    never_tested = not any(network.get_mirror_stat(mirror).total_requests for mirror in candidates)
    if manual or never_tested:
        _start_background_probe(candidates)
    mirrors = _snapshot_candidate_mirrors(candidates)
    with _probe_lock:
        age = round(time.monotonic() - probe_cache["taken"], 1) if probe_cache["taken"] else 0.0
        return mirrors, list(probe_cache["clients"]), age


def is_diagnostics_enabled() -> bool:
    """Check if diagnostics are enabled via config or debug mode."""
    return bool(
        current_app.config.get("ENABLE_DIAGNOSTICS", False)
        or current_app.config.get("FLASK_DEBUG", False)
        or current_app.config.get("TESTING", False)
    )


@diagnostics_bp.before_request
def check_diagnostics_enabled() -> None:
    """Abort with 404 Not Found if diagnostics are disabled."""
    if not is_diagnostics_enabled():
        abort(404)


@diagnostics_bp.route("/diagnostics")
def diagnostics_page() -> str:
    """Render the diagnostics dashboard."""
    return render_template(
        "diagnostics.html",
        active_endpoint="diagnostics.diagnostics_page",
    )


def _collect_system_info() -> dict[str, Any]:
    """Collect platform, python, process and memory RSS metrics."""
    try:
        memory_usage_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
    except Exception:
        memory_usage_mb = 0.0

    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pid": os.getpid(),
        "memory_rss_mb": memory_usage_mb,
    }


def _snapshot_candidate_mirrors(candidate_mirrors: list[str]) -> list[dict[str, Any]]:
    """Describe candidate mirrors from already-collected stats without sending any requests."""
    for mirror in candidate_mirrors:
        network.get_mirror_stat(mirror)
    by_host = {stat["hostname"]: stat for stat in network.get_all_mirror_stats()}
    return [by_host[mirror] for mirror in candidate_mirrors]


def _probe_candidate_mirrors(candidate_mirrors: list[str]) -> list[dict[str, Any]]:
    """Probe within the common request limits, then return one consistent observation snapshot."""
    for mirror in candidate_mirrors:
        network.check_mirror(mirror)
    return _snapshot_candidate_mirrors(candidate_mirrors)


def _get_client_status(client_inst: Any, connected: bool, error_msg: str | None) -> str:
    """Determine friendly status label for a torrent download client."""
    if connected:
        return "Connected"
    if getattr(client_inst, "is_ip_banned", False) is True:
        return "IP Banned"
    cooldown = getattr(client_inst, "auth_cooldown_until", 0)
    if isinstance(cooldown, (int, float)) and cooldown > time.time():
        return "Auth Cooldown"
    if error_msg:
        return "Auth Failed"
    return "Disconnected"


def _collect_client_diagnostics(manager: Any) -> list[dict[str, Any]]:
    """Check connectivity and collect detailed diagnostics for configured download clients."""
    clients_info: list[dict[str, Any]] = []
    configured_clients = getattr(manager, "clients", {})
    if configured_clients:
        for name, client_inst in configured_clients.items():
            c_start = time.perf_counter()
            try:
                connected = bool(client_inst.verify_credentials())
                raw_err = getattr(client_inst, "last_auth_error", None)
                c_err = str(raw_err) if raw_err is not None else None
            except Exception as e:
                connected = False
                c_err = str(e)
            c_status_label = _get_client_status(client_inst, connected, c_err)
            c_latency = round((time.perf_counter() - c_start) * 1000, 2)
            clients_info.append(
                {
                    "name": name,
                    "connected": connected,
                    "status": c_status_label,
                    "latency_ms": c_latency,
                    "error": c_err,
                }
            )
    else:
        connected = bool(manager.verify_credentials())
        primary_client = getattr(manager, "client", None)
        c_err_str: str | None = None
        if primary_client:
            raw_err = getattr(primary_client, "last_auth_error", None)
            c_err_str = str(raw_err) if raw_err is not None else None
        c_status = _get_client_status(primary_client, connected, c_err_str)

        clients_info.append(
            {
                "name": current_app.config.get("DL_CLIENT", "default"),
                "connected": connected,
                "status": c_status,
                "error": c_err_str,
            }
        )
    return clients_info


@diagnostics_bp.route("/api/diagnostics/health")
def diagnostics_health() -> Response:
    """Return JSON system health, mirror status, cache metrics, and client connectivity."""
    t0 = time.perf_counter()

    sys_info = _collect_system_info()
    mirror_results, clients_info, probe_age = _get_external_probes(request.args.get("refresh") == "1")

    with network.CACHE_LOCK:
        active_mirror = network.mirror_cache.get("active_mirror")
        negative_cache_active = "failure" in network.failure_cache
        details_cache_size = len(network.details_cache)
        details_cache_max = network.details_cache.maxsize
    top_search_mirrors = network.get_active_search_mirrors(limit=3, refresh_remote=False)

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    return jsonify(
        {
            "status": "healthy",
            "diagnostics_elapsed_ms": elapsed_ms,
            "probe_age_seconds": probe_age,
            "mirror_probe_running": probe_state["running"],
            "client_probe_running": probe_state["clients_running"],
            "system": sys_info,
            "mirrors": {
                "active_mirror": active_mirror,
                "negative_cache_active": negative_cache_active,
                "top_search_mirrors": top_search_mirrors,
                "mirrors": mirror_results,
            },
            "cache": {
                "details_cache_size": details_cache_size,
                "details_cache_max": details_cache_max,
            },
            "clients": clients_info,
        }
    )


@diagnostics_bp.route("/api/diagnostics/logs")
def diagnostics_logs() -> Response:
    """Return recent sanitized application logs as JSON."""
    limit_str = request.args.get("limit", "100")
    try:
        limit = max(0, min(int(limit_str), log_ring_buffer.capacity))
    except ValueError:
        limit = 100

    logs = log_ring_buffer.get_logs(limit=limit) if limit else []
    return jsonify({"logs": logs, "count": len(logs)})


@diagnostics_bp.route("/api/diagnostics/logs/download")
def diagnostics_logs_download() -> Response:
    """Download recent sanitized logs as a text file."""
    text_content = log_ring_buffer.get_text_logs()
    return Response(
        text_content,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=audiobookbay-automated-logs.txt"},
    )


@diagnostics_bp.route("/api/diagnostics/inspect")
def diagnostics_inspect() -> Response | tuple[Response, int]:
    """Inspect parser output for a live URL or query to verify tag and metadata fidelity."""
    url = (request.args.get("url") or "").strip()
    query = (request.args.get("query") or "").strip()

    if not url and not query:
        return jsonify({"error": "Either 'url' or 'query' parameter is required"}), 400

    if not url and len(query) < MIN_SEARCH_QUERY_LENGTH:
        return jsonify({"error": f"Enter at least {MIN_SEARCH_QUERY_LENGTH} characters."}), 400

    try:
        if url:
            details = core.get_book_details(url, refresh=True)
            if not details:
                return jsonify({"error": f"Failed to retrieve book details for '{url}'"}), 404
            return jsonify({"type": "details", "url": url, "data": details})

        # Query inspection
        results = core.search_audiobookbay(query.lower(), max_pages=1)
        return jsonify(
            {
                "type": "search",
                "query": query,
                "count": len(results),
                "data": results,
            }
        )
    except Exception as e:
        logger.error(f"Diagnostics inspect failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
