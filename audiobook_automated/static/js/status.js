// File: audiobook_automated/static/js/status.js
/**
 * Polling logic for the status page.
 * Fetches JSON status updates and refreshes the table DOM to avoid full page reloads.
 */

// Explicitly expose functions and state to the global scope for testing
window.updateTable = updateTable;
window.escapeHtml = escapeHtml;
window.getStatusBadgeClass = getStatusBadgeClass;
window.statusInterval = null; // Exposed for testing cleanup

document.addEventListener("DOMContentLoaded", () => {
    const tableBody = document.getElementById("status-table-body");
    // Only run if we are on the status page and the table is present
    if (!tableBody) return;

    const pollIndicator = document.getElementById("status-poll-indicator");
    const countBadge = document.getElementById("status-count-badge");
    const clientPill = document.getElementById("status-client-pill");
    const clientPillText = clientPill ? clientPill.querySelector(".client-pill-text") : null;
    const pollCountdownNum = document.getElementById("poll-countdown-num");
    const autoRefreshToggle = document.getElementById("auto-refresh-toggle");

    const updateNote = document.getElementById("status-update-note");
    const params = new URLSearchParams(location.search);
    const client = params.get("client");
    const pollUrl = "/status?json=1" + (client ? "&client=" + encodeURIComponent(client) : "");
    let lastSuccess = document.getElementById("status-initial-error") ? null : new Date().toLocaleTimeString();
    const markStale = () => {
        tableBody.classList.add("is-stale");
        if (updateNote)
            updateNote.textContent =
                (document.getElementById("status-initial-error") && !lastSuccess
                    ? "Download status is unavailable"
                    : "Couldn’t refresh. Showing previous results") +
                (lastSuccess ? " from " + lastSuccess : "") +
                ". Use Refresh to retry.";
    };
    let countdown = 5;
    let isFetching = false;

    // Poll every 5 seconds
    const pollStatus = async () => {
        if (isFetching) return;
        isFetching = true;
        countdown = 5;
        if (pollCountdownNum) pollCountdownNum.textContent = "";
        try {
            if (pollIndicator) pollIndicator.classList.add("polling");
            const response = await fetch(pollUrl);
            if (!response.ok) {
                markStale();
                let errData = {};
                try {
                    errData = await response.json();
                } catch (_) {}
                if (clientPill && clientPillText) {
                    clientPill.className = "status-client-pill";
                    if (errData.client_status === "banned") {
                        clientPill.classList.add("banned");
                        clientPillText.textContent = "IP Banned";
                    } else if (errData.client_status === "auth_failed") {
                        clientPill.classList.add("warning");
                        clientPillText.textContent = "Auth Failed";
                    } else {
                        clientPill.classList.add("disconnected");
                        clientPillText.textContent = "Client Disconnected";
                    }
                }
                console.error("Status poll failed:", response.status);
                return;
            }
            const data = await response.json();
            if (Array.isArray(data)) {
                updateTable(tableBody, data);
                const errorPanel = document.getElementById("status-initial-error");
                if (errorPanel) errorPanel.hidden = true;
                const wrapper = document.getElementById("status-table-wrapper");
                if (wrapper) wrapper.hidden = false;
                tableBody.classList.remove("is-stale");
                lastSuccess = new Date().toLocaleTimeString();
                if (updateNote) updateNote.textContent = "Last updated: " + lastSuccess;
                if (countBadge) {
                    countBadge.textContent = `${data.length} Active`;
                }
                if (clientPill && clientPillText) {
                    clientPill.className = "status-client-pill";
                    clientPillText.textContent = "Client Connected";
                }
            }
        } catch (error) {
            markStale();
            console.error("Failed to fetch status:", error);
            if (clientPill && clientPillText) {
                clientPill.className = "status-client-pill disconnected";
                clientPillText.textContent = "Client Disconnected";
            }
        } finally {
            isFetching = false;
            countdown = 5;
            if (pollCountdownNum) {
                const isAuto = autoRefreshToggle ? autoRefreshToggle.checked : true;
                pollCountdownNum.textContent = isAuto ? "5" : "";
            }
            if (pollIndicator) {
                setTimeout(() => pollIndicator.classList.remove("polling"), 400);
            }
        }
    };

    // Countdown timer ticking every second
    const countdownInterval = setInterval(() => {
        const isAuto = autoRefreshToggle ? autoRefreshToggle.checked : true;
        if (!isAuto) {
            if (pollCountdownNum && pollCountdownNum.textContent !== "") {
                pollCountdownNum.textContent = "";
            }
            return;
        }

        if (!isFetching) {
            countdown -= 1;
            if (countdown <= 0) {
                pollStatus();
            } else if (pollCountdownNum) {
                pollCountdownNum.textContent = String(countdown);
            }
        }
    }, 1000);
    window.statusInterval = countdownInterval;

    // Allow user to click refresh indicator to refresh immediately
    if (pollIndicator) {
        pollIndicator.addEventListener("click", () => {
            pollStatus();
        });
    }

    if (autoRefreshToggle) {
        autoRefreshToggle.addEventListener("change", () => {
            const label = autoRefreshToggle.closest("label")?.querySelector(".auto-refresh-text");
            if (label) label.textContent = autoRefreshToggle.checked ? "Live" : "Paused";
            if (autoRefreshToggle.checked) {
                countdown = 5;
                if (pollCountdownNum) pollCountdownNum.textContent = "5";
                if (pollIndicator) {
                    pollIndicator.title = "Click to refresh status immediately (auto-refreshes every 5s)";
                }
            } else {
                if (pollCountdownNum) pollCountdownNum.textContent = "";
                if (pollIndicator) {
                    pollIndicator.title = "Click to refresh status immediately (auto-refresh paused)";
                }
            }
        });
    }

    pollStatus();
});

/**
 * Maps a torrent state string to an appropriate badge CSS class.
 * @param {string} state - The raw state string.
 * @returns {string} CSS class name.
 */
function getStatusBadgeClass(state) {
    const s = String(state || "").toLowerCase();
    if (s.includes("download")) return "badge-downloading";
    if (s.includes("seed") || s.includes("finish") || s.includes("complete")) return "badge-seeding";
    if (s.includes("pause") || s.includes("stop")) return "badge-paused";
    if (s.includes("error") || s.includes("fail")) return "badge-error";
    return "badge-other";
}

/**
 * Updates the table body with new torrent data.
 * @param {HTMLElement} tbody - The table body element.
 * @param {Array<{id: string|number, name: string, progress: number, state: string, size: string}>} torrents - List of torrent objects.
 */
function updateTable(tbody, torrents) {
    const snapshot = JSON.stringify(torrents || []);
    if (tbody.dataset.snapshot === snapshot) return;
    tbody.dataset.snapshot = snapshot;
    const focused = tbody.contains(document.activeElement) ? document.activeElement : null;
    const restoreFocus = () => {
        if (!focused) return;
        const replacement = [...tbody.querySelectorAll(".remove-torrent-btn")].find(
            (button) =>
                button.dataset.torrentId === focused.dataset.torrentId &&
                button.dataset.client === focused.dataset.client
        );
        (replacement || document.getElementById("status-poll-indicator"))?.focus();
    };
    // If empty list, show empty message
    if (!torrents || torrents.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-message" style="text-align: center; padding: 40px; color: var(--text-muted)">No active downloads found.</td>
            </tr>`;
        restoreFocus();
        return;
    }

    // Build HTML string for rows
    // SECURITY: Ensure ALL dynamic fields are escaped to prevent XSS.
    const rowsHtml = torrents
        .map((torrent) => {
            const progress = typeof torrent.progress === "number" ? torrent.progress : 0;
            const badgeClass = getStatusBadgeClass(torrent.state);
            const fillCompleteClass = progress >= 100 ? "fill-complete" : "";

            return `
        <tr>
            <td class="cell-title">
                <div class="title-with-icon">
                    <span class="book-media-icon" aria-hidden="true">🎧</span>
                    <div class="title-text-group">
                        <span class="title-text">${escapeHtml(torrent.name)}</span>
                        ${torrent.client ? `<span class="torrent-client-tag">${escapeHtml(torrent.client)}</span>` : ""}
                    </div>
                </div>
            </td>
            <td class="cell-progress">
                <div class="progress-cell-wrap">
                    <div class="progress-bar-container" role="progressbar" aria-label="Download progress for ${escapeHtml(torrent.name)}" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
                        <div class="progress-bar-fill ${fillCompleteClass}" style="width: ${progress}%"></div>
                    </div>
                    <span class="progress-percentage">${progress}%</span>
                </div>
            </td>
            <td class="cell-state">
                <span class="status-badge ${badgeClass}">${escapeHtml(torrent.state)}</span>
            </td>
            <td class="cell-size">${escapeHtml(torrent.size)}</td>
            <td class="cell-action">
                <button class="remove-button remove-torrent-btn btn-glass-danger" data-torrent-id="${escapeHtml(String(torrent.id))}" data-client="${escapeHtml(torrent.client || "")}" title="Remove download">
                    <svg class="action-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                    <span>Remove</span>
                </button>
            </td>
        </tr>
    `;
        })
        .join("");

    tbody.innerHTML = rowsHtml;
    restoreFocus();
}

/**
 * Helper to escape HTML to prevent XSS.
 * @param {string} str - Raw string.
 * @returns {string} Safe HTML string.
 */
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
