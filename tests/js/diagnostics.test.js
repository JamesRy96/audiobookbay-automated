// File: tests/js/diagnostics.test.js
/**
 * @jest-environment jsdom
 */

// Mock fetch before loading the script
const mockFetch = jest.fn();
global.fetch = mockFetch;

const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});

beforeAll(() => {
    eval(global.diagnosticsJsContent);
});

async function flushPromises() {
    await jest.advanceTimersByTimeAsync(0);
}

function setupDom() {
    document.body.innerHTML = `
        <div class="diag-header-glass">
            <span class="status-client-pill" id="diag-status-pill">
                <span class="pulse-dot"></span>
                <span class="client-pill-text">Live System</span>
            </span>
            <span id="last-updated-badge" class="diag-badge">Last updated: -</span>
            <input type="checkbox" id="auto-refresh-toggle" checked />
            <button id="diag-poll-indicator" class="status-poll-indicator">
                <span id="poll-countdown-num">5</span>
            </button>
        </div>
        <div class="diag-container">
            <span id="health-spinner"></span>
            <span id="logs-spinner"></span>
            <span id="diag-status"></span>
            <span id="diag-memory"></span>
            <span id="diag-active-mirror"></span>
            <span id="diag-cache"></span>
            <div id="mirror-metrics"></div>
            <div id="client-metrics"></div>
            <input type="text" id="log-filter-input" />
            <input type="checkbox" id="auto-scroll-toggle" checked />
            <button id="download-logs-btn"></button>
            <pre id="log-viewer-pre"></pre>
            <input type="text" id="inspect-input" />
            <button id="run-inspect-btn"></button>
            <pre id="inspect-output"></pre>
        </div>
    `;
}

describe("diagnostics.js - Dashboard Controller", () => {
    beforeEach(() => {
        setupDom();
        jest.useFakeTimers();
        mockFetch.mockReset();
        mockFetch.mockImplementation((url) => {
            if (url.includes("/health")) {
                return Promise.resolve({
                    ok: true,
                    json: () =>
                        Promise.resolve({
                            status: "healthy",
                            system: { memory_rss_mb: 45.2 },
                            mirrors: {
                                active_mirror: "audiobookbay.lu",
                                mirrors: [
                                    { hostname: "audiobookbay.lu", reachable: true, score: 98, latency_ms: 45 },
                                    { hostname: "abb.fail", reachable: false, is_parked: true },
                                ],
                            },
                            cache: { details_cache_size: 12, details_cache_max: 200 },
                            clients: [{ name: "transmission", status: "Connected", connected: true }],
                        }),
                });
            }
            if (url.includes("/logs")) {
                return Promise.resolve({
                    ok: true,
                    json: () =>
                        Promise.resolve({
                            logs: [{ message: "First test log" }, { message: "Error in worker" }],
                        }),
                });
            }
            if (url.includes("/inspect")) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ type: "search", count: 1 }),
                });
            }
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });
    });

    afterEach(() => {
        if (window.diagState && window.diagState.interval) {
            clearInterval(window.diagState.interval);
            window.diagState.interval = null;
        }
        jest.useRealTimers();
    });

    test("Initial load renders health, mirrors, clients, and logs", async () => {
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await flushPromises();

        expect(document.getElementById("diag-status").textContent).toBe("HEALTHY");
        expect(document.getElementById("diag-status-pill").className).toBe("status-client-pill");
        expect(document.getElementById("diag-status-pill").querySelector(".client-pill-text").textContent).toBe(
            "Live System"
        );
        expect(document.getElementById("diag-memory").textContent).toBe("45.2 MB");
        expect(document.getElementById("diag-active-mirror").textContent).toBe("audiobookbay.lu");
        expect(document.getElementById("diag-cache").textContent).toBe("12 / 200");

        const mirrorMetrics = document.getElementById("mirror-metrics");
        expect(mirrorMetrics.children.length).toBe(2);
        expect(mirrorMetrics.innerHTML).toContain("audiobookbay.lu");
        expect(mirrorMetrics.innerHTML).toContain("Parked / Invalid");

        const clientMetrics = document.getElementById("client-metrics");
        expect(clientMetrics.children.length).toBe(1);
        expect(clientMetrics.innerHTML).toContain("transmission");
        expect(clientMetrics.innerHTML).toContain("Connected");

        const logViewer = document.getElementById("log-viewer-pre");
        expect(logViewer.textContent).toContain("First test log");
    });

    test("Filter input dynamically filters rendered log lines", async () => {
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await flushPromises();

        const filterInput = document.getElementById("log-filter-input");
        const logViewer = document.getElementById("log-viewer-pre");

        filterInput.value = "Error";
        filterInput.dispatchEvent(new Event("input"));

        expect(logViewer.textContent).toContain("Error in worker");
        expect(logViewer.textContent).not.toContain("First test log");
    });

    test("Countdown timer counts down and auto-refreshes every 5 seconds", async () => {
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await flushPromises();

        const countdownNum = document.getElementById("poll-countdown-num");
        expect(countdownNum.textContent).toBe("5");

        // Advance 1s -> 4
        jest.advanceTimersByTime(1000);
        expect(countdownNum.textContent).toBe("4");

        // Advance 4s -> triggers refreshAll()
        mockFetch.mockClear();
        jest.advanceTimersByTime(4000);
        expect(mockFetch).toHaveBeenCalled();
    });

    test("Toggling auto-refresh off pauses countdown indicator", async () => {
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await flushPromises();

        const toggle = document.getElementById("auto-refresh-toggle");
        const countdownNum = document.getElementById("poll-countdown-num");

        toggle.checked = false;
        toggle.dispatchEvent(new Event("change"));

        expect(countdownNum.textContent).toBe("");

        mockFetch.mockClear();
        jest.advanceTimersByTime(10000);
        expect(mockFetch).not.toHaveBeenCalled();

        // Toggling back on resumes countdown
        toggle.checked = true;
        toggle.dispatchEvent(new Event("change"));
        expect(countdownNum.textContent).toBe("5");
    });

    test("Clicking poll indicator triggers immediate refresh", async () => {
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await flushPromises();

        const pollBtn = document.getElementById("diag-poll-indicator");
        mockFetch.mockClear();

        pollBtn.dispatchEvent(new Event("click"));
        expect(mockFetch).toHaveBeenCalledWith("/api/diagnostics/health?refresh=1");
        expect(mockFetch).toHaveBeenCalledWith("/api/diagnostics/logs?limit=150");
    });

    test("Inspector triggers inspect API and displays JSON", async () => {
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await flushPromises();

        const input = document.getElementById("inspect-input");
        const inspectBtn = document.getElementById("run-inspect-btn");
        const output = document.getElementById("inspect-output");

        input.value = "Martian";
        inspectBtn.dispatchEvent(new Event("click"));
        await flushPromises();

        expect(mockFetch).toHaveBeenCalledWith("/api/diagnostics/inspect?query=Martian");
        expect(output.style.display).toBe("block");
        expect(output.textContent).toContain('"type": "search"');
    });
});

describe("mirror observations", () => {
    test("untested candidates never outrank verified mirrors or show invented measurements", () => {
        document.body.innerHTML = '<p id="mirror-summary"></p><div id="mirror-metrics"></div>';
        window.renderMirrors({
            active_mirror: "ready.example",
            mirrors: [
                { hostname: "unknown.example", tested: false, reachable: false, score: 1140, success_rate: 100 },
                {
                    hostname: "ready.example",
                    tested: true,
                    reachable: true,
                    score: 800,
                    ema_latency_ms: 250,
                    success_rate: 90,
                    total_requests: 10,
                },
            ],
        });
        const rows = document.querySelectorAll(".mirror-row");
        expect(rows[0].dataset.hostname).toBe("ready.example");
        expect(rows[0].textContent).toContain("250 ms average");
        expect(rows[0].textContent).toContain("10 checks");
        expect(rows[1].textContent).toContain("No observations");
        expect(rows[1].textContent).not.toContain("100%");
        expect(rows[1].querySelector(".mirror-tags").textContent).not.toContain("Rank");
    });
    test("polling preserves an expanded mirror explanation and keyboard focus", () => {
        document.body.innerHTML = '<div id="mirror-metrics"></div>';
        const mirror = { hostname: "ready.example", tested: true, reachable: true, score: 800, latency_ms: 250 };
        window.renderMirrors({ mirrors: [mirror] });
        const details = document.querySelector(".mirror-details");
        details.open = true;
        details.querySelector("summary").focus();
        window.renderMirrors({ mirrors: [{ ...mirror, latency_ms: 300 }] });
        expect(document.querySelector(".mirror-details").open).toBe(true);
        expect(document.activeElement.tagName).toBe("SUMMARY");
    });
});
