// File: tests/js/actions.test.js
/**
 * @jest-environment jsdom
 */

// NOTE: actionsJsContent is available globally from jest.setup.js

// Mock fetch before loading the script
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock window functions
const mockConfirm = jest.fn();
const mockOpen = jest.fn();
global.confirm = mockConfirm;
global.open = mockOpen;

// Mock reload function (to bypass JSDOM window.location restrictions)
window.__mockReload = jest.fn();

// Mock requestAnimationFrame used by showNotification
global.requestAnimationFrame = jest.fn((cb) => cb());

// Spy on console.error to detect swallowed errors
const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});

// Add a required meta tag for CSRF token into the DOM
document.head.innerHTML = '<meta name="csrf-token" content="test-csrf-token" />';

// FIX: Patch the source code string before evaluation.
// We replace 'location.reload()' with 'window.__mockReload()' to intercept the call.
// We also redirect setTimeout to a custom mock to reliably test callbacks regardless of context binding.
function getPatchedActionsContent() {
    return global.actionsJsContent
        .replace(/location\.reload\(\)/g, "window.__mockReload()")
        .replace(/setTimeout\(/g, "window.__customSetTimeout(");
}

// --- MOCK UTILITIES ---

function getNotificationText() {
    const container = document.getElementById("notification-container");
    return container ? container.textContent : "";
}

// Helper to drain the microtask queue completely.
async function flushPromises() {
    await jest.advanceTimersByTimeAsync(0);
}

// Custom setTimeout mock
window.__customSetTimeout = jest.fn();

// Modal setup helper
function setupModal() {
    const modalHTML = `
        <div id="confirmation-modal" class="modal-overlay" aria-hidden="true">
            <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="modal-title">
                <div class="modal-header">
                    <h3 class="modal-title" id="modal-title">Confirm Action</h3>
                </div>
                <div class="modal-body" id="modal-body">
                    Are you sure you want to proceed?
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="modal-cancel">Cancel</button>
                    <button class="btn-primary" id="modal-confirm">Confirm</button>
                </div>
            </div>
        </div>
    `;
    document.body.innerHTML += modalHTML;
}

// ----------------------

// Reset mocks before each test
beforeEach(() => {
    window.UI.activeDialog?.();
    window.matchMedia = jest.fn(() => ({ matches: false }));
    HTMLMediaElement.prototype.play = jest.fn().mockResolvedValue(undefined);
    mockFetch.mockClear();
    mockConfirm.mockClear();
    mockOpen.mockClear();
    window.__mockReload.mockClear();
    window.__customSetTimeout.mockClear();

    // Default mock response for success
    mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: "Success" }),
        status: 200,
    });
    // Ensure notification container exists and is empty
    document.body.innerHTML = '<div id="notification-container"></div>';

    // Inject modal structure
    setupModal();

    window.__customSetTimeout.mockImplementation((cb, delay) => {
        // We use the real setTimeout (or Jest's fake one if enabled) to simulate behavior
        return setTimeout(cb, delay);
    });

    jest.useFakeTimers();

    // Evaluate the script content
    eval(getPatchedActionsContent());
});

afterAll(() => {
    jest.useRealTimers();
    consoleErrorSpy.mockRestore();
});

describe("actions.js - Core Functionality", () => {
    test("showNotification should display and remove a toast", () => {
        showNotification("Test message", "success");
        expect(getNotificationText()).toContain("Test message");

        const toast = document.querySelector("#notification-container > div");
        jest.advanceTimersByTime(3000);

        const transitionEndEvent = new Event("transitionend");
        if (toast) {
            toast.dispatchEvent(transitionEndEvent);
        }

        expect(document.querySelector("#notification-container > div")).toBeNull();
        expect(getNotificationText()).toBe("");
    });

    test("showNotification should handle error type", () => {
        showNotification("Error message", "error");
        const toast = document.querySelector("#notification-container > div");
        expect(toast.classList.contains("toast-error")).toBe(true);
        expect(toast.getAttribute("role")).toBe("alert");
    });

    test("showModal should display modal and set content", () => {
        const modal = document.getElementById("confirmation-modal");
        const titleEl = document.getElementById("modal-title");
        const bodyEl = document.getElementById("modal-body");

        showModal("Test Title", "Test Message", () => {});

        expect(modal.classList.contains("active")).toBe(true);
        expect(titleEl.textContent).toBe("Test Title");
        expect(bodyEl.textContent).toBe("Test Message");
    });
});

describe("actions.js - API Interactions", () => {
    // --- reloadLibrary ---

    test("reloadLibrary should send POST request if user confirms via modal", async () => {
        // Trigger action
        reloadLibrary();

        // Assert modal is shown
        const modal = document.getElementById("confirmation-modal");
        expect(modal.classList.contains("active")).toBe(true);

        // Click confirm
        const confirmBtn = document.getElementById("modal-confirm");
        confirmBtn.click();

        // Check callback execution
        jest.runAllTimers();

        expect(mockFetch).toHaveBeenCalledWith(
            "/reload_library",
            expect.objectContaining({
                method: "POST",
                headers: expect.objectContaining({
                    "X-CSRFToken": "test-csrf-token",
                }),
            })
        );

        // Modal should be closed
        expect(modal.classList.contains("active")).toBe(false);

        const toast = document.querySelector("#notification-container > div");
        if (toast) toast.dispatchEvent(new Event("transitionend"));
        expect(getNotificationText()).toBe("");
    });

    test("reloadLibrary should do nothing if user cancels via modal", async () => {
        reloadLibrary();

        // Click cancel
        const cancelBtn = document.getElementById("modal-cancel");
        cancelBtn.click();

        // Check fetch was not called
        expect(mockFetch).not.toHaveBeenCalled();

        // Modal should be closed
        const modal = document.getElementById("confirmation-modal");
        expect(modal.classList.contains("active")).toBe(false);
    });

    // --- deleteTorrent ---

    test("deleteTorrent should send DELETE request and reload on success via modal", async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ message: "Torrent removed successfully." }),
            status: 200,
        });

        deleteTorrent("test-hash-123");

        // Click confirm
        const confirmBtn = document.getElementById("modal-confirm");
        confirmBtn.click();

        await flushPromises();
        jest.runAllTimers();

        expect(window.__mockReload).toHaveBeenCalled();
    });

    // --- sendTorrent ---

    test("sendTorrent should change button text to Sent! then revert", async () => {
        const mockButton = document.createElement("button");
        mockButton.innerHTML = "Download";

        expect(mockButton.disabled).toBe(false);

        sendTorrent("http://link", "Book Title", mockButton);

        // Check for substring because innerHTML now contains a spinner span
        expect(mockButton.innerHTML).toContain("Sending...");
        expect(mockButton.innerHTML).toContain('class="spinner"');
        expect(mockButton.disabled).toBe(true);

        await flushPromises();

        expect(mockButton.innerText).toBe("Sent!");
        expect(mockButton.disabled).toBe(true);

        // Manually trigger the revert callback via our custom mock
        // We expect __customSetTimeout to have been called with delay 3000
        // NOTE: showNotification also uses setTimeout(..., 3000), so we must run ALL matching callbacks
        const calls = window.__customSetTimeout.mock.calls;
        const matchingCalls = calls.filter((call) => call[1] === 3000);

        if (matchingCalls.length > 0) {
            matchingCalls.forEach((call) => {
                const callback = call[0];
                callback();
            });
        } else {
            // Fallback to time advance if it was queued (should be queued via implementation)
            jest.advanceTimersByTime(3500);
        }

        // Updated logic: Button resets after 3 seconds
        expect(mockButton.disabled).toBe(false);
        // Use innerHTML to avoid JSDOM innerText visibility quirks on detached elements
        expect(mockButton.innerHTML).toBe("Download");
    });

    test("sendTorrent should include client in fetch body when specified", async () => {
        mockFetch.mockClear();
        sendTorrent("http://link", "Book Title", null, "putio");

        expect(mockFetch).toHaveBeenCalledWith(
            "/send",
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({ link: "http://link", title: "Book Title", client: "putio" }),
            })
        );
    });

    test("sendTorrent should show error on non-ok status code", async () => {
        const mockButton = document.createElement("button");
        mockButton.innerText = "Download";
        // innerHTML is used to restore the original state, so we check innerHTML or ensure initial innerHTML matches innerText
        const originalHTML = mockButton.innerHTML;

        mockFetch.mockResolvedValue({
            ok: false,
            status: 500,
            json: () => Promise.resolve({ message: "Server Error" }),
        });

        sendTorrent("http://link", "Book Title", mockButton);

        await flushPromises();
        jest.advanceTimersByTime(3000);

        const toast = document.querySelector("#notification-container > div");
        if (toast) toast.dispatchEvent(new Event("transitionend"));
        expect(getNotificationText()).toBe("");

        expect(consoleErrorSpy).toHaveBeenCalled();
        expect(mockButton.disabled).toBe(false);
        // The implementation restores innerHTML
        expect(mockButton.innerHTML).toBe(originalHTML);
    });

    test("sendTorrent should show error on fetch rejection", async () => {
        mockFetch.mockRejectedValue(new Error("Network Failed"));

        sendTorrent("http://link", "Book Title", null);

        await flushPromises();
        jest.runAllTimers();

        const toast = document.querySelector("#notification-container > div");
        if (toast) toast.dispatchEvent(new Event("transitionend"));
        expect(getNotificationText()).toBe("");
    });
});

describe("actions.js - Browser Interactions", () => {
    test("openExternalLink should call window.open if confirmed via modal", () => {
        openExternalLink("http://external.site");

        // Assert modal is active
        const modal = document.getElementById("confirmation-modal");
        expect(modal.classList.contains("active")).toBe(true);

        // Confirm
        document.getElementById("modal-confirm").click();

        expect(mockOpen).toHaveBeenCalledWith("http://external.site", "_blank", "noopener,noreferrer");
    });

    test("openExternalLink should normalize relative path with window.ABB_HOST", () => {
        window.ABB_HOST = "audiobookbay.is";
        openExternalLink("/abss/test-book/");
        document.getElementById("modal-confirm").click();
        expect(mockOpen).toHaveBeenCalledWith(
            "https://audiobookbay.is/abss/test-book/",
            "_blank",
            "noopener,noreferrer"
        );
    });

    test("openExternalLink should do nothing if canceled via modal", () => {
        openExternalLink("http://external.site");

        // Cancel
        document.getElementById("modal-cancel").click();

        expect(mockOpen).not.toHaveBeenCalled();
    });
});

describe("actions.js - Splash Screen & Morph Animation", () => {
    beforeEach(() => {
        sessionStorage.clear();
        localStorage.clear();
        document.documentElement.className = "";
    });

    test("initSplashScreen does nothing if splash overlay does not exist", () => {
        expect(() => initSplashScreen()).not.toThrow();
    });

    test("initSplashScreen immediately hides overlay if splashShown is in sessionStorage or localStorage", () => {
        sessionStorage.setItem("splashShown", "true");
        document.body.innerHTML += '<div id="splash-overlay"></div>';

        initSplashScreen();

        const overlay = document.getElementById("splash-overlay");
        expect(overlay.classList.contains("hidden")).toBe(true);
        expect(overlay.style.display).toBe("none");

        // Now test via localStorage
        sessionStorage.clear();
        localStorage.setItem("splashShown", "true");
        document.body.innerHTML = '<div id="splash-overlay"></div>';
        initSplashScreen();
        const overlay2 = document.getElementById("splash-overlay");
        expect(overlay2.classList.contains("hidden")).toBe(true);
        expect(overlay2.style.display).toBe("none");
    });

    test("initSplashScreen immediately hides overlay if no-splash class on html", () => {
        document.documentElement.classList.add("no-splash");
        document.body.innerHTML += '<div id="splash-overlay"></div>';

        initSplashScreen();

        const overlay = document.getElementById("splash-overlay");
        expect(overlay.classList.contains("hidden")).toBe(true);
        expect(overlay.style.display).toBe("none");
    });

    test("initSplashScreen adds no-splash class if overlay is absent (e.g. diagnostics page)", () => {
        document.documentElement.classList.remove("no-splash");
        document.body.innerHTML = '<div class="content">Diagnostics</div>';

        initSplashScreen();

        expect(document.documentElement.classList.contains("no-splash")).toBe(true);
    });

    test("initSplashScreen dismisses text splash after configured duration", () => {
        document.body.innerHTML += `
            <div id="splash-overlay" data-splash-duration="2000">
                <div id="splash-content">Welcome</div>
            </div>
        `;

        initSplashScreen();

        const overlay = document.getElementById("splash-overlay");
        expect(overlay.classList.contains("hidden")).toBe(false);

        jest.advanceTimersByTime(2000);
        expect(overlay.classList.contains("hidden")).toBe(true);

        jest.advanceTimersByTime(400);
        expect(overlay.style.display).toBe("none");
        expect(sessionStorage.getItem("splashShown")).toBe("true");
    });

    test("initSplashScreen handles video timeupdate and skip button", () => {
        document.body.innerHTML += `
            <div id="splash-overlay">
                <video id="splash-video"></video>
                <button id="skip-splash-btn">Skip</button>
            </div>
        `;

        const video = document.getElementById("splash-video");
        video.pause = jest.fn();
        const skipBtn = document.getElementById("skip-splash-btn");

        initSplashScreen();

        // Clicking skip button pauses video and dismisses splash
        skipBtn.click();
        expect(video.pause).toHaveBeenCalled();

        const overlay = document.getElementById("splash-overlay");
        expect(overlay.classList.contains("hidden")).toBe(true);

        jest.advanceTimersByTime(400);
        expect(overlay.style.display).toBe("none");
    });

    test("dismissSplash performs FLIP morph animation when video and logo have dimensions", () => {
        document.body.innerHTML += `
            <a href="/" class="nav-logo">
                <img class="nav-logo-img" src="/logo.png" style="border-radius: 12px;" />
            </a>
            <div id="splash-overlay">
                <video id="splash-video"></video>
            </div>
        `;

        const overlay = document.getElementById("splash-overlay");
        const video = document.getElementById("splash-video");
        const logo = document.querySelector(".nav-logo-img");

        // Mock getBoundingClientRect
        logo.getBoundingClientRect = jest.fn(() => ({
            left: 20,
            top: 10,
            width: 240,
            height: 80,
        }));
        video.getBoundingClientRect = jest.fn(() => ({
            left: 0,
            top: 200,
            width: 1200,
            height: 400,
        }));

        dismissSplash(overlay);

        expect(overlay.classList.contains("morphing")).toBe(true);
        expect(video.style.transform).toContain("translate3d(");
        expect(video.style.transform).toContain("scale(");
        expect(video.style.opacity).toBe("0");

        // Cleanup waits until the staggered content fade has completed.
        jest.advanceTimersByTime(650);
        expect(overlay.classList.contains("hidden")).toBe(false);
        jest.advanceTimersByTime(400);
        expect(overlay.classList.contains("hidden")).toBe(true);
        expect(overlay.style.display).toBe("none");
        expect(sessionStorage.getItem("splashShown")).toBe("true");
        expect(document.documentElement.classList.contains("no-splash")).toBe(true);
    });

    test("dismissSplash performs FLIP morph animation targeting .masthead-logo-img", () => {
        sessionStorage.clear();
        document.documentElement.classList.remove("no-splash");
        document.body.innerHTML += `
            <div class="header-editorial-masthead">
                <img class="masthead-logo-img" src="/banner.jpg" style="border-radius: 16px;" />
            </div>
            <div id="splash-overlay">
                <video id="splash-video"></video>
            </div>
        `;

        const overlay = document.getElementById("splash-overlay");
        const video = document.getElementById("splash-video");
        const logo = document.querySelector(".masthead-logo-img");

        logo.getBoundingClientRect = jest.fn(() => ({
            left: 100,
            top: 20,
            width: 800,
            height: 250,
        }));
        video.getBoundingClientRect = jest.fn(() => ({
            left: 0,
            top: 0,
            width: 1920,
            height: 1080,
        }));

        dismissSplash(overlay);

        expect(overlay.classList.contains("morphing")).toBe(true);
        expect(video.style.transform).toContain("translate3d(");
        expect(video.style.transform).toContain("scale(");
        expect(video.style.opacity).toBe("0");

        // At 150ms, logo begins cross-fade
        jest.advanceTimersByTime(150);
        expect(document.documentElement.classList.contains("splash-reveal-logo")).toBe(true);

        // At 350ms, remaining page content fades in
        jest.advanceTimersByTime(200);
        expect(document.documentElement.classList.contains("splash-reveal-content")).toBe(true);

        // At 1050ms, the content has finished fading before cleanup.
        jest.advanceTimersByTime(700);
        expect(overlay.classList.contains("hidden")).toBe(true);
        expect(overlay.style.display).toBe("none");
        expect(sessionStorage.getItem("splashShown")).toBe("true");
        expect(document.documentElement.classList.contains("no-splash")).toBe(true);
        expect(document.documentElement.classList.contains("splash-reveal-logo")).toBe(false);
        expect(document.documentElement.classList.contains("splash-reveal-content")).toBe(false);
    });

    test("dismissSplash skips morph animation if prefers-reduced-motion is active", () => {
        window.matchMedia = jest.fn().mockImplementation((query) => ({
            matches: query === "(prefers-reduced-motion: reduce)",
            media: query,
        }));

        document.body.innerHTML += `
            <a href="/" class="nav-logo">
                <img class="nav-logo-img" src="/logo.png" />
            </a>
            <div id="splash-overlay">
                <video id="splash-video"></video>
            </div>
        `;

        const overlay = document.getElementById("splash-overlay");
        const video = document.getElementById("splash-video");
        const logo = document.querySelector(".nav-logo-img");

        logo.getBoundingClientRect = jest.fn(() => ({
            left: 20,
            top: 10,
            width: 240,
            height: 80,
        }));
        video.getBoundingClientRect = jest.fn(() => ({
            left: 0,
            top: 200,
            width: 1200,
            height: 400,
        }));

        dismissSplash(overlay);

        expect(overlay.classList.contains("morphing")).toBe(false);
        expect(overlay.classList.contains("hidden")).toBe(true);

        jest.advanceTimersByTime(400);
        expect(overlay.style.display).toBe("none");
    });

    describe("Mobile Navigation Menu", () => {
        beforeEach(() => {
            document.body.innerHTML = `
                <div class="navbar">
                    <button class="mobile-menu-btn" id="mobile-menu-btn" aria-label="Toggle navigation" aria-expanded="false" aria-controls="nav-links">
                        <span class="bar"></span>
                        <span class="bar"></span>
                        <span class="bar"></span>
                    </button>
                    <div class="nav-backdrop" id="nav-backdrop"></div>
                    <div class="nav-links" id="nav-links">
                        <a href="/search" id="link-search">Search</a>
                        <a href="/status" id="link-status">Status</a>
                    </div>
                </div>
            `;
            initMobileMenu();
        });

        test("clicking mobile menu button toggles active state and aria-expanded", () => {
            const btn = document.getElementById("mobile-menu-btn");
            const navLinks = document.getElementById("nav-links");
            const backdrop = document.getElementById("nav-backdrop");

            expect(btn.classList.contains("active")).toBe(false);
            expect(navLinks.classList.contains("active")).toBe(false);
            expect(backdrop.classList.contains("active")).toBe(false);
            expect(btn.getAttribute("aria-expanded")).toBe("false");
            expect(document.body.classList.contains("nav-open")).toBe(false);

            // Click to open
            btn.click();
            expect(btn.classList.contains("active")).toBe(true);
            expect(navLinks.classList.contains("active")).toBe(true);
            expect(backdrop.classList.contains("active")).toBe(true);
            expect(btn.getAttribute("aria-expanded")).toBe("true");
            expect(document.body.classList.contains("nav-open")).toBe(true);

            // Click to close
            btn.click();
            expect(btn.classList.contains("active")).toBe(false);
            expect(navLinks.classList.contains("active")).toBe(false);
            expect(backdrop.classList.contains("active")).toBe(false);
            expect(btn.getAttribute("aria-expanded")).toBe("false");
            expect(document.body.classList.contains("nav-open")).toBe(false);
        });

        test("clicking backdrop closes mobile menu", () => {
            const btn = document.getElementById("mobile-menu-btn");
            const navLinks = document.getElementById("nav-links");
            const backdrop = document.getElementById("nav-backdrop");

            btn.click();
            expect(navLinks.classList.contains("active")).toBe(true);

            backdrop.click();
            expect(navLinks.classList.contains("active")).toBe(false);
            expect(btn.getAttribute("aria-expanded")).toBe("false");
            expect(document.body.classList.contains("nav-open")).toBe(false);
        });

        test("pressing Escape key closes mobile menu", () => {
            const btn = document.getElementById("mobile-menu-btn");
            const navLinks = document.getElementById("nav-links");

            btn.click();
            expect(navLinks.classList.contains("active")).toBe(true);

            document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
            expect(navLinks.classList.contains("active")).toBe(false);
            expect(btn.getAttribute("aria-expanded")).toBe("false");
        });

        test("clicking a link inside nav-links auto-closes menu", () => {
            const btn = document.getElementById("mobile-menu-btn");
            const navLinks = document.getElementById("nav-links");
            const linkSearch = document.getElementById("link-search");

            btn.click();
            expect(navLinks.classList.contains("active")).toBe(true);

            linkSearch.click();
            expect(navLinks.classList.contains("active")).toBe(false);
            expect(btn.getAttribute("aria-expanded")).toBe("false");
        });
    });

    describe("Scroll to Top Shortcut", () => {
        beforeEach(() => {
            document.body.innerHTML = `
                <button id="scroll-to-top-btn" class="scroll-to-top-btn" type="button" aria-label="Scroll back to top">Top</button>
            `;
            window.scrollTo = jest.fn();
            window.requestAnimationFrame = (cb) => cb();
            initScrollToTop();
        });

        test("scroll to top button becomes visible when window.scrollY > 300", () => {
            const btn = document.getElementById("scroll-to-top-btn");
            expect(btn.classList.contains("visible")).toBe(false);

            // Mock scrollY > 300
            Object.defineProperty(window, "scrollY", { value: 350, writable: true });
            window.dispatchEvent(new Event("scroll"));

            expect(btn.classList.contains("visible")).toBe(true);

            // Mock scrollY back to top
            Object.defineProperty(window, "scrollY", { value: 50, writable: true });
            window.dispatchEvent(new Event("scroll"));

            expect(btn.classList.contains("visible")).toBe(false);
        });

        test("clicking button smoothly scrolls window to top", () => {
            const btn = document.getElementById("scroll-to-top-btn");
            btn.click();

            expect(window.scrollTo).toHaveBeenCalledWith({
                top: 0,
                behavior: "smooth",
            });
        });
    });
});

describe("shared UI accessibility", () => {
    test("dialog traps Tab, closes on Escape, restores focus and background", () => {
        document.body.innerHTML =
            '<button id="trigger">Open</button><main id="background"></main><div id="panel"><button id="first">One</button><button id="last">Two</button></div>';
        const trigger = document.getElementById("trigger");
        trigger.focus();
        let release;
        release = window.UI.openDialog(document.getElementById("panel"), trigger, () => release());
        expect(document.activeElement.id).toBe("first");
        expect(document.getElementById("background").inert).toBe(true);
        document.getElementById("last").focus();
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
        expect(document.activeElement.id).toBe("first");
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        expect(document.activeElement).toBe(trigger);
        expect(document.getElementById("background").inert).not.toBe(true);
    });
    test("blocked browser storage returns a fallback without throwing", () => {
        const spy = jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
            throw new Error("Blocked");
        });
        expect(window.UI.storage("localStorage", "getItem", "theme")).toBeNull();
        spy.mockRestore();
    });
});

describe("release interaction regressions", () => {
    test("removal includes the row Download Client and does not report HTTP failures as success", async () => {
        const button = document.createElement("button");
        button.dataset.client = "transmission";
        document.body.append(button);
        mockFetch.mockResolvedValue({ ok: false, json: async () => ({ message: "Could not remove" }) });
        deleteTorrent("shared-id", button);
        document.getElementById("modal-confirm").click();
        await flushPromises();
        expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({ id: "shared-id", client: "transmission" });
        expect(button.isConnected).toBe(true);
        expect(document.querySelector(".toast-error")).not.toBeNull();
    });
});

test("releasing an old dialog twice cannot make the active dialog background interactive", () => {
    document.body.innerHTML =
        '<button id="trigger">Open</button><main></main><div id="one"><button>One</button></div><div id="two"><button>Two</button></div>';
    const trigger = document.getElementById("trigger");
    const first = window.UI.openDialog(document.getElementById("one"), trigger, () => {});
    const second = window.UI.openDialog(document.getElementById("two"), trigger, () => {});
    first();
    expect(document.querySelector("main").inert).toBe(true);
    second();
    expect(document.querySelector("main").inert).not.toBe(true);
});

test("returning visits do not play the hidden intro video", () => {
    document.body.innerHTML = '<div id="splash-overlay"><video id="splash-video"></video></div>';
    document.documentElement.classList.add("no-splash");
    initSplashScreen();
    expect(document.getElementById("splash-video").play).not.toHaveBeenCalled();
});

test.each(["download", "remove", "scan"])("%s explains page expiry without repeating the action", async (action) => {
    mockFetch.mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ code: "page_expired", message: "Page expired. Refresh and try again." }),
    });
    const button = document.createElement("button");
    button.textContent = "Download";
    document.body.append(button);
    if (action === "download") sendTorrent("https://catalog.example/book", "A book", button);
    else {
        if (action === "remove") deleteTorrent("test-id", button);
        else reloadLibrary();
        document.getElementById("modal-confirm").click();
    }
    await flushPromises();
    expect(getNotificationText()).toContain("Page expired. Refresh and try again.");
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(button.disabled).toBe(false);
});
