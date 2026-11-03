// File: audiobook_automated/static/js/diagnostics.js
/**
 * Real-time Diagnostics Dashboard Controller
 * Handles auto-refresh countdown indicator, unified polling, logs streaming, and inspector.
 */

// Expose state and functions globally for testing
window.diagState = {
    countdown: 5,
    isFetching: false,
    interval: null,
};
window.loadHealth = null;
window.loadLogs = null;
window.refreshAll = null;

document.addEventListener("DOMContentLoaded", () => {
    const diagContainer = document.querySelector(".diag-container");
    if (!diagContainer) return;

    const pollIndicator = document.getElementById("diag-poll-indicator");
    const pollCountdownNum = document.getElementById("poll-countdown-num");
    const autoRefreshToggle = document.getElementById("auto-refresh-toggle");
    const lastUpdatedBadge = document.getElementById("last-updated-badge");
    const healthSpinner = document.getElementById("health-spinner");
    const logsSpinner = document.getElementById("logs-spinner");
    const logViewer = document.getElementById("log-viewer-pre");
    const downloadLogsBtn = document.getElementById("download-logs-btn");
    const autoScrollToggle = document.getElementById("auto-scroll-toggle");
    const logFilterInput = document.getElementById("log-filter-input");
    const inspectBtn = document.getElementById("run-inspect-btn");
    const inspectInput = document.getElementById("inspect-input");
    const inspectOutput = document.getElementById("inspect-output");

    let isFetchingHealth = false;
    let isFetchingLogs = false;
    let currentLogs = [];
    let countdown = 5;
    let initialLoadDone = false;

    function formatTime(date) {
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }

    async function loadHealth(force = false) {
        if (isFetchingHealth) return;
        isFetchingHealth = true;
        if (healthSpinner && !initialLoadDone) healthSpinner.style.display = "inline-block";

        try {
            const res = await fetch(force ? "/api/diagnostics/health?refresh=1" : "/api/diagnostics/health");
            if (!res.ok) throw new Error("Health check returned status " + res.status);
            const data = await res.json();

            // Status & Environment
            const statusEl = document.getElementById("diag-status");
            const statusText = (data.status || "OK").toUpperCase();
            if (statusEl) statusEl.textContent = statusText;

            // Harmonize top status pill with health status
            const statusPill = document.getElementById("diag-status-pill");
            if (statusPill) {
                const pillText = statusPill.querySelector(".client-pill-text");
                if (statusText === "HEALTHY" || statusText === "OK") {
                    statusPill.className = "status-client-pill";
                    if (pillText) pillText.textContent = "Live System";
                } else if (statusText === "DEGRADED" || statusText === "WARNING") {
                    statusPill.className = "status-client-pill warning";
                    if (pillText) pillText.textContent = "System Degraded";
                } else {
                    statusPill.className = "status-client-pill disconnected";
                    if (pillText) pillText.textContent = "System Issue";
                }
            }

            const memEl = document.getElementById("diag-memory");
            if (memEl && data.system) memEl.textContent = data.system.memory_rss_mb + " MB";

            const mirrorEl = document.getElementById("diag-active-mirror");
            if (mirrorEl && data.mirrors) mirrorEl.textContent = data.mirrors.active_mirror || "None";

            const cacheEl = document.getElementById("diag-cache");
            if (cacheEl && data.cache) {
                cacheEl.textContent = `${data.cache.details_cache_size} / ${data.cache.details_cache_max}`;
            }

            renderMirrors(data.mirrors || {});

            // Download Clients
            const clientContainer = document.getElementById("client-metrics");
            if (clientContainer) {
                clientContainer.innerHTML = "";
                (data.clients || []).forEach((c) => {
                    const metric = document.createElement("div");
                    metric.className = "diag-metric";
                    const statusText = c.status || (c.connected ? "Connected" : "Disconnected");
                    let statusColor = "var(--status-success)"; // green
                    if (statusText === "IP Banned") {
                        statusColor = "var(--status-error)"; // red
                    } else if (statusText === "Auth Failed" || statusText === "Auth Cooldown") {
                        statusColor = "var(--status-warning)"; // amber
                    } else if (!c.connected) {
                        statusColor = "var(--status-error)"; // soft red
                    }

                    metric.innerHTML = `
                        <span class="diag-label">${c.name}</span>
                        <span class="diag-val" style="color: ${statusColor}; font-size: 1.15rem;">
                            ${statusText}
                        </span>
                        ${c.error ? `<span style="font-size: 0.78rem; color: #f87171; margin-top: 4px; word-break: break-word;">${c.error}</span>` : ""}
                    `;
                    clientContainer.appendChild(metric);
                });
            }

            if (lastUpdatedBadge) {
                lastUpdatedBadge.textContent = "Last updated: " + formatTime(new Date());
            }
        } catch (e) {
            document.getElementById("mirror-metrics")?.classList.add("is-stale");
            const mirrorNote = document.getElementById("mirror-summary");
            if (mirrorNote)
                mirrorNote.textContent = "Couldn’t update mirror health. Showing the previous observations.";
            console.error("Failed to load health metrics", e);
            if (lastUpdatedBadge) {
                lastUpdatedBadge.textContent = "Update failed: " + formatTime(new Date());
            }
        } finally {
            isFetchingHealth = false;
            if (healthSpinner) healthSpinner.style.display = "none";
        }
    }

    async function loadLogs() {
        if (!logViewer || isFetchingLogs) return;
        isFetchingLogs = true;
        if (logsSpinner && !initialLoadDone) logsSpinner.style.display = "inline-block";

        try {
            const res = await fetch("/api/diagnostics/logs?limit=150");
            if (!res.ok) throw new Error("Logs check returned status " + res.status);
            const data = await res.json();
            currentLogs = data.logs || [];
            renderLogs();
            const note = document.getElementById("logs-update-note");
            if (note) note.textContent = "Logs updated: " + formatTime(new Date());
        } catch (e) {
            const note = document.getElementById("logs-update-note");
            if (note)
                note.textContent = "Couldn’t refresh logs. Showing the last available entries. Use Refresh to retry.";
            console.error("Failed to fetch logs", e);
        } finally {
            isFetchingLogs = false;
            if (logsSpinner) logsSpinner.style.display = "none";
        }
    }

    function renderLogs() {
        if (!logViewer) return;
        const filter = logFilterInput ? logFilterInput.value.trim().toLowerCase() : "";
        const lines = currentLogs.map((entry) => {
            if (typeof entry === "string") return entry;
            return entry && entry.message ? entry.message : JSON.stringify(entry);
        });
        const filtered = filter ? lines.filter((line) => line.toLowerCase().includes(filter)) : lines;

        logViewer.textContent = filtered.join("\n") || "(No logs recorded yet)";
        if (autoScrollToggle && autoScrollToggle.checked) {
            logViewer.scrollTop = logViewer.scrollHeight;
        }
    }

    async function refreshAll(force = false) {
        if (window.diagState.isFetching) return;
        window.diagState.isFetching = true;
        countdown = 5;
        window.diagState.countdown = countdown;

        if (pollCountdownNum) pollCountdownNum.textContent = "";
        if (pollIndicator) pollIndicator.classList.add("polling");

        try {
            await Promise.all([loadHealth(force === true), loadLogs()]);
            initialLoadDone = true;
        } finally {
            window.diagState.isFetching = false;
            countdown = 5;
            window.diagState.countdown = countdown;

            if (pollCountdownNum) {
                const isAuto = autoRefreshToggle ? autoRefreshToggle.checked : true;
                pollCountdownNum.textContent = isAuto ? "5" : "";
            }
            if (pollIndicator) {
                setTimeout(() => pollIndicator.classList.remove("polling"), 400);
            }
        }
    }

    async function runInspect() {
        if (!inspectInput || !inspectBtn || !inspectOutput) return;
        const val = inspectInput.value.trim();
        if (!val) return;

        inspectBtn.disabled = true;
        inspectOutput.style.display = "block";
        inspectOutput.textContent = "Inspecting parser...";

        try {
            const param =
                val.startsWith("http") || val.startsWith("/")
                    ? `url=${encodeURIComponent(val)}`
                    : `query=${encodeURIComponent(val)}`;
            const res = await fetch(`/api/diagnostics/inspect?${param}`);
            const json = await res.json();
            inspectOutput.textContent = JSON.stringify(json, null, 2);
        } catch (e) {
            inspectOutput.textContent = "Error: " + e.message;
        } finally {
            inspectBtn.disabled = false;
        }
    }

    // Countdown interval timer
    const countdownInterval = setInterval(() => {
        const isAuto = autoRefreshToggle ? autoRefreshToggle.checked : true;
        if (!isAuto) {
            if (pollCountdownNum && pollCountdownNum.textContent !== "") {
                pollCountdownNum.textContent = "";
            }
            return;
        }

        if (!window.diagState.isFetching) {
            countdown -= 1;
            window.diagState.countdown = countdown;
            if (countdown <= 0) {
                refreshAll();
            } else if (pollCountdownNum) {
                pollCountdownNum.textContent = String(countdown);
            }
        }
    }, 1000);

    window.diagState.interval = countdownInterval;

    if (pollIndicator) {
        pollIndicator.addEventListener("click", () => {
            refreshAll(true);
        });
    }

    if (autoRefreshToggle) {
        autoRefreshToggle.addEventListener("change", () => {
            const label = autoRefreshToggle.closest("label")?.querySelector(".auto-refresh-text");
            if (label) label.textContent = autoRefreshToggle.checked ? "Live" : "Paused";
            if (autoRefreshToggle.checked) {
                countdown = 5;
                window.diagState.countdown = countdown;
                if (pollCountdownNum) pollCountdownNum.textContent = "5";
                if (pollIndicator) {
                    pollIndicator.title = "Click to refresh diagnostics immediately (auto-refreshes every 5s)";
                }
            } else {
                if (pollCountdownNum) pollCountdownNum.textContent = "";
                if (pollIndicator) {
                    pollIndicator.title = "Click to refresh diagnostics immediately (auto-refresh paused)";
                }
            }
        });
    }

    if (logFilterInput) {
        logFilterInput.addEventListener("input", renderLogs);
    }

    if (downloadLogsBtn) {
        downloadLogsBtn.addEventListener("click", () => {
            window.location.href = "/api/diagnostics/logs/download";
        });
    }

    if (inspectBtn) inspectBtn.addEventListener("click", runInspect);
    if (inspectInput) {
        inspectInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") runInspect();
        });
    }

    // Expose helpers for testing
    window.loadHealth = loadHealth;
    window.loadLogs = loadLogs;
    window.refreshAll = refreshAll;

    // Initial load
    refreshAll();
});

function renderMirrors(data) {
    const container = document.getElementById("mirror-metrics");
    if (!container) return;
    container.classList.remove("is-stale");
    const available = (mirror) =>
        mirror.tested !== false && mirror.reachable && !mirror.cooling_down && !mirror.is_parked;
    const state = (mirror) =>
        available(mirror)
            ? "available"
            : mirror.tested === false
              ? "untested"
              : mirror.is_parked
                ? "invalid"
                : mirror.cooling_down
                  ? "cooldown"
                  : "offline";
    const priority = { available: 0, untested: 1, cooldown: 2, offline: 3, invalid: 4 };
    const mirrors = [...(data.mirrors || [])].sort(
        (a, b) =>
            priority[state(a)] - priority[state(b)] ||
            (b.score || 0) - (a.score || 0) ||
            a.hostname.localeCompare(b.hostname)
    );
    const summary = document.getElementById("mirror-summary");
    const ready = mirrors.filter(available).length;
    const waiting = mirrors.filter((m) => state(m) === "untested").length;
    if (summary)
        summary.textContent = mirrors.length
            ? `${ready} available · ${waiting} awaiting a first check · ${mirrors.length - ready - waiting} unavailable`
            : "No mirror observations yet. Checks run in the background.";
    const signature = JSON.stringify([data.active_mirror, mirrors]);
    if (container.dataset.snapshot === signature) return;
    const expanded = new Set(
        [...container.querySelectorAll("details[open]")].map((el) => el.closest(".mirror-row").dataset.hostname)
    );
    const focused = document.activeElement?.closest(".mirror-row")?.dataset.hostname;
    container.dataset.snapshot = signature;
    container.replaceChildren();
    let rank = 0;
    const activeHost = String(data.active_mirror || "")
        .replace(/^https?:\/\//, "")
        .replace(/\/$/, "");
    mirrors.forEach((m) => {
        const row = document.createElement("article");
        const category = state(m);
        row.className = "mirror-row diag-metric";
        row.dataset.hostname = m.hostname;
        row.innerHTML =
            '<div class="mirror-identity"><strong class="mirror-host"></strong><span class="mirror-tags"></span></div><span class="mirror-state"></span><div class="mirror-latency"></div><div class="mirror-success"></div><details class="mirror-details"><summary>Check details</summary><p></p></details>';
        row.querySelector(".mirror-host").textContent = m.hostname;
        const selected = m.hostname === activeHost;
        const badges = row.querySelector(".mirror-tags");
        const addBadge = (label) => {
            const badge = document.createElement("span");
            badge.className = "diag-badge";
            badge.textContent = label;
            badges.append(badge);
        };
        if (available(m)) addBadge("Rank " + ++rank);
        if (selected) addBadge(available(m) ? "In use" : "Last used");
        if (m.tested !== false) addBadge(String(m.protocol || "https").toUpperCase());
        const status = row.querySelector(".mirror-state");
        status.classList.add("mirror-state-" + category);
        status.textContent = {
            available: "Available",
            untested: "Not tested yet",
            invalid: "Parked / Invalid",
            cooldown: "Retrying after cooldown",
            offline: "Unavailable",
        }[category];
        const average = Number(m.ema_latency_ms);
        const latency = average > 0 ? average : Number(m.latency_ms);
        row.querySelector(".mirror-latency").textContent =
            m.tested === false || !(latency > 0)
                ? "Response time: —"
                : `Response time: ${Math.round(latency)} ms ${average > 0 ? "average" : "latest"}`;
        const observations = Number(m.total_requests);
        const success = Number(m.success_rate);
        row.querySelector(".mirror-success").textContent =
            m.tested === false
                ? "No observations"
                : Number.isFinite(success)
                  ? `${success}% observed success${observations > 0 ? " · " + observations + " check" + (observations === 1 ? "" : "s") : ""}`
                  : "Success rate: —";
        const details = row.querySelector("details");
        details.open = expanded.has(m.hostname);
        details.querySelector("p").textContent =
            m.tested === false
                ? "No measured latency or success rate yet. This mirror will be checked as needed."
                : `Selection score: ${m.score ?? "—"} (higher is better). Reliability, average latency, and protocol contribute to selection. ${m.is_parked ? "This mirror did not return a valid catalog." : m.cooling_down ? "Checks are temporarily backed off to avoid repeated requests." : ""}`;
        container.append(row);
        if (focused === m.hostname) details.querySelector("summary").focus();
    });
}
window.renderMirrors = renderMirrors;
