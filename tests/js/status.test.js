// File: tests/js/status.test.js
/**
 * @jest-environment jsdom
 */

// NOTE: statusJsContent is available globally from jest.setup.js

// Mock fetch before loading the script
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Spy on console.error
const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});

// Add deleteTorrent to window so status.js can call it (it's defined in actions.js, but we mock it here)
window.deleteTorrent = jest.fn();

// --- SETUP ---
// Evaluate the script ONCE for the entire suite.
// This attaches the DOMContentLoaded listener one time.
beforeAll(() => {
    eval(global.statusJsContent);
});

describe("status.js - UI Logic", () => {
    let tbody;

    beforeEach(() => {
        document.body.innerHTML = '<table><tbody id="status-table-body"></tbody></table>';
        tbody = document.getElementById("status-table-body");
        mockFetch.mockClear();
        window.deleteTorrent.mockClear();
    });

    test("updateTable should show empty message for empty list", () => {
        window.updateTable(tbody, []);
        expect(tbody.innerHTML).toContain("No active downloads found");
        expect(tbody.querySelectorAll("tr").length).toBe(1); // 1 row for the message
    });

    test("updateTable should show empty message for null/undefined", () => {
        window.updateTable(tbody, null);
        expect(tbody.innerHTML).toContain("No active downloads found");
    });

    test("updateTable should render rows for torrents", () => {
        const torrents = [
            { id: "123", name: "Book A", progress: 50.5, state: "Downloading", size: "1 GB" },
            { id: "456", name: "Book B", progress: 100, state: "Seeding", size: "500 MB" },
        ];

        window.updateTable(tbody, torrents);

        const rows = tbody.querySelectorAll("tr");
        expect(rows.length).toBe(2);

        // Check content of first row
        expect(rows[0].innerHTML).toContain("Book A");
        expect(rows[0].innerHTML).toContain("50.5%");
        expect(rows[0].innerHTML).toContain("Downloading");
        expect(rows[0].innerHTML).toContain("1 GB");

        // Check action button
        const btn = rows[0].querySelector("button");
        expect(btn).not.toBeNull();
        expect(btn.classList.contains("remove-torrent-btn")).toBe(true);
        expect(btn.dataset.torrentId).toBe("123");
        // Ensure inline handler is gone
        expect(btn.getAttribute("onclick")).toBeNull();
    });

    test("updateTable should escape XSS in names", () => {
        const malicious = [
            { id: "666", name: "<script>alert('xss')</script>", progress: 0, state: "Bad", size: "0 B" },
        ];

        window.updateTable(tbody, malicious);

        // The innerHTML should NOT contain the script tag literally interpreted
        expect(tbody.innerHTML).toContain("&lt;script&gt;alert('xss')&lt;/script&gt;");
        expect(tbody.querySelector("script")).toBeNull();
    });

    test("getStatusBadgeClass should return appropriate badge class for various states", () => {
        expect(window.getStatusBadgeClass("downloading")).toBe("badge-downloading");
        expect(window.getStatusBadgeClass("Seeding")).toBe("badge-seeding");
        expect(window.getStatusBadgeClass("Finished")).toBe("badge-seeding");
        expect(window.getStatusBadgeClass("Paused")).toBe("badge-paused");
        expect(window.getStatusBadgeClass("Error")).toBe("badge-error");
        expect(window.getStatusBadgeClass("unknown_state")).toBe("badge-other");
    });

    test("updateTable should render progress bar elements and badge classes", () => {
        const torrents = [
            { id: "101", name: "Downloading Book", progress: 42.5, state: "downloading", size: "350 MB" },
            { id: "102", name: "Completed Book", progress: 100, state: "seeding", size: "1.2 GB" },
        ];

        window.updateTable(tbody, torrents);

        const rows = tbody.querySelectorAll("tr");
        expect(rows.length).toBe(2);

        // Verify progress bar markup in row 1
        const progressBar1 = rows[0].querySelector(".progress-bar-fill");
        expect(progressBar1).not.toBeNull();
        expect(progressBar1.style.width).toBe("42.5%");
        expect(progressBar1.classList.contains("fill-complete")).toBe(false);

        const badge1 = rows[0].querySelector(".status-badge");
        expect(badge1.classList.contains("badge-downloading")).toBe(true);

        // Verify row 2 is marked complete
        const progressBar2 = rows[1].querySelector(".progress-bar-fill");
        expect(progressBar2.classList.contains("fill-complete")).toBe(true);
        const badge2 = rows[1].querySelector(".status-badge");
        expect(badge2.classList.contains("badge-seeding")).toBe(true);
    });

    test("updateTable should render client tag when client is present", () => {
        const torrents = [
            { id: "201", name: "Book on Putio", progress: 80, state: "downloading", size: "1 GB", client: "putio" },
            { id: "202", name: "Book without client", progress: 20, state: "downloading", size: "500 MB" },
        ];

        window.updateTable(tbody, torrents);

        const rows = tbody.querySelectorAll("tr");
        const clientTag1 = rows[0].querySelector(".torrent-client-tag");
        expect(clientTag1).not.toBeNull();
        expect(clientTag1.textContent).toBe("putio");

        const clientTag2 = rows[1].querySelector(".torrent-client-tag");
        expect(clientTag2).toBeNull();
    });
});

describe("status.js - Polling Mechanism", () => {
    beforeEach(() => {
        document.body.innerHTML = '<table><tbody id="status-table-body"></tbody></table>';
        jest.useFakeTimers();
        mockFetch.mockReset();
        mockFetch.mockResolvedValue({ ok: true, json: async () => [] });
        consoleErrorSpy.mockClear();
    });

    afterEach(() => {
        jest.clearAllTimers();
        window.statusInterval = null;
        history.replaceState(null, "", "/");
        jest.useRealTimers();
    });

    test("Polling should fetch initially and exactly every 5 seconds", async () => {
        document.dispatchEvent(new Event("DOMContentLoaded"));
        expect(mockFetch).toHaveBeenCalledWith("/status?json=1");
        expect(mockFetch).toHaveBeenCalledTimes(1);
        await jest.advanceTimersByTimeAsync(0);
        for (let count = 2; count <= 4; count++) {
            await jest.advanceTimersByTimeAsync(4999);
            expect(mockFetch).toHaveBeenCalledTimes(count - 1);
            await jest.advanceTimersByTimeAsync(1);
            expect(mockFetch).toHaveBeenCalledTimes(count);
        }
    });

    test("Polling waits for a slow response before starting another request", async () => {
        let resolveBody;
        const body = new Promise((resolve) => {
            resolveBody = resolve;
        });
        mockFetch.mockResolvedValueOnce({ ok: true, json: () => body });
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await jest.advanceTimersByTimeAsync(15000);
        expect(mockFetch).toHaveBeenCalledTimes(1);
        resolveBody([]);
        await jest.advanceTimersByTimeAsync(0);
        await jest.advanceTimersByTimeAsync(4999);
        expect(mockFetch).toHaveBeenCalledTimes(1);
        await jest.advanceTimersByTimeAsync(1);
        expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    test("Polling reports network errors and retries after 5 seconds", async () => {
        mockFetch.mockRejectedValueOnce(new Error("Network Error"));
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await jest.advanceTimersByTimeAsync(0);
        expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to fetch status:", expect.any(Error));
        await jest.advanceTimersByTimeAsync(4999);
        expect(mockFetch).toHaveBeenCalledTimes(1);
        await jest.advanceTimersByTimeAsync(1);
        expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    test("Polling should handle non-200 responses", async () => {
        document.body.innerHTML = `
            <div id="status-client-pill" class="status-client-pill">
                <span class="client-pill-text">Client Connected</span>
            </div>
            <table><tbody id="status-table-body"></tbody></table>
        `;
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 500,
            json: async () => ({ error: "Banned", client_status: "banned" }),
        });
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await jest.advanceTimersByTimeAsync(0);
        expect(consoleErrorSpy).toHaveBeenCalledWith("Status poll failed:", 500);
        const pill = document.getElementById("status-client-pill");
        expect(pill.classList.contains("banned")).toBe(true);
        expect(pill.textContent).toContain("IP Banned");
        await jest.advanceTimersByTimeAsync(5000);
        expect(mockFetch).toHaveBeenCalledTimes(2);
        expect(pill.textContent).toContain("Client Connected");
    });

    test("Polling should NOT start if table body is missing", async () => {
        document.body.innerHTML = "<div>No Table Here</div>";
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await jest.advanceTimersByTimeAsync(5000);
        expect(mockFetch).not.toHaveBeenCalled();
        expect(jest.getTimerCount()).toBe(0);
    });

    test("Toggling auto-refresh pauses polling and resumes after 5 seconds", async () => {
        document.body.innerHTML = `
            <input type="checkbox" id="auto-refresh-toggle" checked />
            <span id="poll-countdown-num">5</span>
            <table><tbody id="status-table-body"></tbody></table>
        `;
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await jest.advanceTimersByTimeAsync(0);
        const toggle = document.getElementById("auto-refresh-toggle");
        toggle.checked = false;
        toggle.dispatchEvent(new Event("change"));
        expect(document.getElementById("poll-countdown-num").textContent).toBe("");
        await jest.advanceTimersByTimeAsync(10000);
        expect(mockFetch).toHaveBeenCalledTimes(1);
        toggle.checked = true;
        toggle.dispatchEvent(new Event("change"));
        await jest.advanceTimersByTimeAsync(4999);
        expect(mockFetch).toHaveBeenCalledTimes(1);
        await jest.advanceTimersByTimeAsync(1);
        expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    test("polling preserves a selected Download Client and marks failures stale", async () => {
        history.replaceState(null, "", "/status?client=qbittorrent");
        document.body.innerHTML =
            '<p id="status-update-note"></p><table><tbody id="status-table-body"></tbody></table>';
        mockFetch.mockResolvedValue({ ok: false, json: async () => ({}) });
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await jest.advanceTimersByTimeAsync(0);
        expect(mockFetch).toHaveBeenCalledWith("/status?json=1&client=qbittorrent");
        expect(document.getElementById("status-table-body").classList.contains("is-stale")).toBe(true);
        expect(document.getElementById("status-update-note").textContent).toContain("previous results");
    });
});

test("changing download progress preserves keyboard focus on the same client row", () => {
    document.body.innerHTML = '<table><tbody id="status-table-body"></tbody></table>';
    const tbody = document.getElementById("status-table-body");
    const download = {
        id: "shared",
        client: "transmission",
        name: "A book",
        progress: 10,
        state: "Downloading",
        size: "1 GB",
    };
    window.updateTable(tbody, [download]);
    tbody.querySelector("button").focus();
    window.updateTable(tbody, [{ ...download, progress: 20 }]);
    expect(document.activeElement.dataset.torrentId).toBe("shared");
    expect(document.activeElement.dataset.client).toBe("transmission");
    expect(tbody.querySelector('[role="progressbar"]').getAttribute("aria-label")).toContain("A book");
});
