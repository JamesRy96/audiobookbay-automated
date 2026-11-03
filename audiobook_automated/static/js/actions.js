// File: audiobook_automated/static/js/actions.js
/**
 * Global application actions (Reload ABS, Delete Torrent, Send Torrent, Open External)
 */

// Explicitly expose functions to the global scope (window) for testability and consistency.
window.showNotification = showNotification;
window.reloadLibrary = reloadLibrary;
window.deleteTorrent = deleteTorrent;
window.sendTorrent = sendTorrent;
window.openExternalLink = openExternalLink;
window.showModal = showModal;
window.initSplashScreen = initSplashScreen;
window.dismissSplash = dismissSplash;
window.initMobileMenu = initMobileMenu;
window.initScrollToTop = initScrollToTop;
window.initClientBannerCheck = initClientBannerCheck;

function initMobileMenu() {
    const mobileMenuBtn = document.getElementById("mobile-menu-btn");
    const navLinks = document.getElementById("nav-links");
    const navBackdrop = document.getElementById("nav-backdrop");

    let releaseMenu = null;
    if (mobileMenuBtn && navLinks) {
        navLinks.setAttribute("role", "dialog");
        navLinks.setAttribute("aria-modal", "true");
        navLinks.setAttribute("aria-label", "Navigation");
        navLinks.tabIndex = -1;
        const toggleMobileMenu = function (forceState) {
            const isOpen = typeof forceState === "boolean" ? forceState : !navLinks.classList.contains("active");
            navLinks.classList.toggle("active", isOpen);
            mobileMenuBtn.classList.toggle("active", isOpen);
            mobileMenuBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
            if (navBackdrop) {
                navBackdrop.classList.toggle("active", isOpen);
            }
            document.body.classList.toggle("nav-open", isOpen);
            if (releaseMenu) {
                releaseMenu();
                releaseMenu = null;
            }
            if (isOpen)
                releaseMenu = window.UI?.openDialog(navLinks, mobileMenuBtn, () => toggleMobileMenu(false), true);
        };

        mobileMenuBtn.addEventListener("click", function () {
            toggleMobileMenu();
        });

        if (navBackdrop) {
            navBackdrop.addEventListener("click", function () {
                toggleMobileMenu(false);
            });
        }

        // Close on Escape key
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && navLinks.classList.contains("active")) {
                toggleMobileMenu(false);
            }
        });

        // UX: Auto-close menu when a link is clicked
        navLinks.addEventListener("click", function (event) {
            if (event.target.closest("a")) {
                toggleMobileMenu(false);
            }
        });
    }
}

function initScrollToTop() {
    window.UI.bindFloatingControls();
    const button = document.getElementById("scroll-to-top-btn");
    if (button)
        button.onclick = () => window.scrollTo({ top: 0, behavior: window.UI.reducedMotion() ? "auto" : "smooth" });
}

document.addEventListener("DOMContentLoaded", function () {
    initSplashScreen();
    initMobileMenu();
    initScrollToTop();
    initClientBannerCheck();

    // Reload Library Button
    const reloadBtn = document.getElementById("reload-library-btn");
    if (reloadBtn) {
        reloadBtn.addEventListener("click", function (e) {
            e.preventDefault();
            reloadBtn.focus({ preventScroll: true });
            reloadLibrary();
        });
    }

    // Global Error Handler for Images (Capture Phase)
    window.addEventListener(
        "error",
        function (event) {
            if (event.target && event.target.tagName === "IMG") {
                const img = event.target;
                const defaultCover = img.getAttribute("data-default-cover");
                if (defaultCover) {
                    const placeholder = document.createElement("span");
                    placeholder.className = img.className + " cover-placeholder";
                    placeholder.setAttribute("role", "img");
                    placeholder.setAttribute("aria-label", "Cover Unavailable");
                    img.replaceWith(placeholder);
                }
            }
        },
        true // Capture phase to catch error events which don't bubble
    );

    // Event Delegation for Buttons
    document.body.addEventListener("click", function (event) {
        const target = event.target;

        // Send Torrent
        const sendBtn = target.closest(".send-torrent-btn");
        if (sendBtn) {
            const link = sendBtn.dataset.link;
            const title =
                sendBtn.dataset.title ||
                sendBtn.getAttribute("aria-label") ||
                document.querySelector("h1")?.textContent?.trim() ||
                "Audiobook";
            const client = sendBtn.dataset.client;
            if (link) {
                requestDownload(link, title, sendBtn, client);
            }
        }

        // Remove Torrent
        const removeBtn = target.closest(".remove-torrent-btn");
        if (removeBtn) {
            const id = removeBtn.dataset.torrentId;
            if (id) {
                deleteTorrent(id, removeBtn);
            }
        }

        // Download (Details Page)
        const detailsBtn = target.closest(".details-download-btn");
        if (detailsBtn) {
            const link = detailsBtn.dataset.link;
            const title = detailsBtn.dataset.title;
            const client = detailsBtn.dataset.client;
            if (link && title) {
                requestDownload(link, title, detailsBtn, client);
            }
        }

        // External Link
        const externalBtn = target.closest(".direct-link-btn");
        if (externalBtn) {
            const link = externalBtn.dataset.externalLink;
            if (link) {
                externalBtn.focus({ preventScroll: true });
                openExternalLink(link);
            }
        }

        // Back Button
        const backBtn = target.closest(".back-link-btn");
        if (backBtn) {
            event.preventDefault();
            try {
                const referring = new URL(document.referrer);
                if (referring.origin === location.origin && referring.pathname === "/" && history.length > 1) {
                    history.back();
                    return;
                }
            } catch (_) {
                /* Direct visits use the Search fallback below. */
            }
            let destination = "/";
            try {
                const saved = new URL(
                    window.UI?.storage("sessionStorage", "getItem", "resultsUrl") || "/",
                    location.origin
                );
                if (saved.origin === location.origin && saved.pathname === "/")
                    destination = saved.pathname + saved.search;
            } catch (_) {
                /* Fall back to Search for direct visits. */
            }
            location.assign(destination);
        }
    });
});

/**
 * Initializes the splash screen logic.
 * Shows only on first visit (sessionStorage).
 */
function initSplashScreen() {
    const splashOverlay = document.getElementById("splash-overlay");
    if (!splashOverlay) {
        document.documentElement.classList.add("no-splash");
        return;
    }

    if (window.UI?.reducedMotion()) {
        dismissSplash(splashOverlay, { skipAnimation: true });
        return;
    }
    const masthead = document.querySelector(".masthead-logo-img");
    const brandFrame = document.getElementById("splash-brand-frame");
    const matchBrandRatio = () => {
        const bounds = masthead?.getBoundingClientRect();
        if (brandFrame && bounds?.width && bounds?.height)
            brandFrame.style.setProperty("--splash-brand-ratio", String(bounds.width / bounds.height));
    };
    matchBrandRatio();
    masthead?.addEventListener("load", matchBrandRatio, { once: true });
    masthead
        ?.decode?.()
        .then(matchBrandRatio)
        .catch(() => {});

    // If "no-splash" is present on HTML (handled by inline script),
    // we ensure overlay is hidden and return.
    if (document.documentElement.classList.contains("no-splash")) {
        splashOverlay.classList.add("hidden");
        splashOverlay.style.display = "none";
        return;
    }

    // Also double-check sessionStorage / localStorage here (redundant but safe)
    if (
        window.UI?.storage("sessionStorage", "getItem", "splashShown") ||
        window.UI?.storage("localStorage", "getItem", "splashShown")
    ) {
        splashOverlay.classList.add("hidden");
        splashOverlay.style.display = "none";
        return;
    }

    // Click to dismiss immediately on overlay or skip button
    splashOverlay.addEventListener("click", () => {
        if (splashVideo) {
            splashVideo.pause();
        }
        dismissSplash(splashOverlay, { skipAnimation: true });
    });

    const skipBtn = document.getElementById("skip-splash-btn");
    if (skipBtn) {
        skipBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            if (splashVideo) {
                splashVideo.pause();
            }
            dismissSplash(splashOverlay, { skipAnimation: true });
        });
    }

    const splashVideo = document.getElementById("splash-video");
    if (splashVideo) {
        // Begin the handoff using the actual media duration.
        let fadingStarted = false;
        const triggerFade = () => {
            if (!fadingStarted) {
                fadingStarted = true;
                dismissSplash(splashOverlay);
            }
        };

        splashVideo.addEventListener("timeupdate", () => {
            const duration = Number.isFinite(splashVideo.duration) ? splashVideo.duration : 4;
            if (splashVideo.currentTime >= Math.max(0, duration - 0.65)) {
                triggerFade();
            }
        });

        if (typeof splashVideo.requestVideoFrameCallback === "function") {
            const checkFrame = () => {
                const duration = splashVideo.duration;
                if (Number.isFinite(duration) && splashVideo.currentTime >= Math.max(0, duration - 0.65)) triggerFade();
                else if (!fadingStarted && !splashOverlay.classList.contains("hidden"))
                    splashVideo.requestVideoFrameCallback(checkFrame);
            };
            splashVideo.requestVideoFrameCallback(checkFrame);
        }
        splashVideo.addEventListener("error", triggerFade);
        const playback = splashVideo.play();
        playback?.catch(triggerFade);
        splashVideo.addEventListener("ended", () => {
            triggerFade();
        });

        // Safety fallback timer if video fails to play or load
        setTimeout(() => {
            triggerFade();
        }, 5000);
    } else {
        // Text splash: Fade out after configured duration
        const duration = parseInt(splashOverlay.dataset.splashDuration) || 3500;
        setTimeout(() => {
            dismissSplash(splashOverlay);
        }, duration);
    }
}

function dismissSplash(overlay, options = {}) {
    if (overlay.classList.contains("hidden") || overlay.classList.contains("morphing")) return;

    const skipAnimation = options.skipAnimation || false;
    const splashVideo = document.getElementById("splash-video");
    const targetLogo =
        document.querySelector(".masthead-logo-img") ||
        document.querySelector(".nav-logo-img") ||
        document.querySelector(".nav-logo");

    const prefersReducedMotion =
        typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (!skipAnimation && !prefersReducedMotion && targetLogo?.decode && !overlay.dataset.logoDecoded) {
        overlay.dataset.logoDecoded = "pending";
        targetLogo
            .decode()
            .catch(() => {})
            .then(() => {
                overlay.dataset.logoDecoded = "ready";
                dismissSplash(overlay, options);
            });
        return;
    }
    if (overlay.dataset.logoDecoded === "pending" && !skipAnimation) return;

    const movingFrame = document.getElementById("splash-brand-frame") || splashVideo;
    // Check if FLIP morph animation should be played
    let shouldMorph = false;
    let translateX = 0;
    let translateY = 0;
    let scaleX = 1;
    let scaleY = 1;
    let targetRadius = "16px";

    if (!skipAnimation && !prefersReducedMotion && splashVideo && targetLogo) {
        const targetRect = targetLogo.getBoundingClientRect();
        const videoRect = movingFrame.getBoundingClientRect();

        // Ensure valid visible bounding rectangles
        if (targetRect.width > 0 && targetRect.height > 0 && videoRect.width > 0 && videoRect.height > 0) {
            shouldMorph = true;

            const targetCenterX = targetRect.left + targetRect.width / 2;
            const targetCenterY = targetRect.top + targetRect.height / 2;
            const videoCenterX = videoRect.left + videoRect.width / 2;
            const videoCenterY = videoRect.top + videoRect.height / 2;

            translateX = targetCenterX - videoCenterX;
            translateY = targetCenterY - videoCenterY;

            scaleX = Math.min(targetRect.width / videoRect.width, targetRect.height / videoRect.height);
            scaleY = scaleX;

            targetRadius = window.getComputedStyle(targetLogo).borderRadius || "16px";
        }
    }

    if (shouldMorph) {
        overlay.classList.add("morphing");
        movingFrame.style.borderRadius = `${parseFloat(targetRadius) / scaleX}px`;
        movingFrame.style.transform = `translate3d(${translateX}px, ${translateY}px, 0) scale(${scaleX}, ${scaleY})`;
        splashVideo.style.opacity = "0";

        // Cross-fade the target logo in as the morph reaches exact target size and position
        setTimeout(
            () => {
                document.documentElement.classList.add("splash-reveal-logo");
                if (movingFrame !== splashVideo) {
                    targetLogo.style.transition = "none";
                    targetLogo.style.opacity = "1";
                    movingFrame.style.visibility = "hidden";
                }
            },
            movingFrame !== splashVideo ? 650 : 150
        );

        // Stagger the fade-in of the remaining page elements slightly behind the logo
        setTimeout(() => {
            document.documentElement.classList.add("splash-reveal-content");
        }, 350);

        setTimeout(() => {
            targetLogo?.style.removeProperty("transition");
            targetLogo?.style.removeProperty("opacity");
            overlay.classList.add("hidden");
            overlay.style.display = "none";
            window.UI?.storage("sessionStorage", "setItem", "splashShown", "true");
            window.UI?.storage("localStorage", "setItem", "splashShown", "true");
            document.documentElement.classList.add("no-splash");
            document.documentElement.classList.remove("splash-reveal-logo", "splash-reveal-content");
        }, 1050);
    } else {
        overlay.classList.add("hidden");
        window.UI?.storage("sessionStorage", "setItem", "splashShown", "true");
        window.UI?.storage("localStorage", "setItem", "splashShown", "true");
        document.documentElement.classList.add("no-splash");

        setTimeout(() => {
            overlay.style.display = "none";
        }, 400);
    }
}

/**
 * Displays a toast notification.
 * @param {string} message - The message to display.
 * @param {string} type - 'info' (green) or 'error' (red).
 */
function showNotification(message, type = "info") {
    // Create a notification container if it doesn't exist
    let container = document.getElementById("notification-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "notification-container";
        document.body.appendChild(container);
    }

    // Apply styles to ensure it floats correctly (fixes issue if element exists in HTML but isn't styled)
    container.style.position = "fixed";
    container.style.top = "20px";
    container.style.left = "50%";
    container.style.transform = "translateX(-50%)";
    container.style.zIndex = "10000";
    container.style.display = "flex";
    container.style.flexDirection = "column";
    container.style.gap = "10px";

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.classList.add(`toast-${type}`);
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.style.opacity = "0";
    toast.textContent = message;
    container.appendChild(toast);

    // Fade in
    requestAnimationFrame(() => {
        toast.style.opacity = "1";
    });

    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.addEventListener("transitionend", () => toast.remove(), { once: true });
        setTimeout(() => toast.remove(), 400);
    }, 3000);
}

/**
 * Shows a custom modal confirmation dialog.
 * @param {string} title - The title of the modal.
 * @param {string} message - The message body.
 * @param {Function} onConfirm - Callback function if user confirms.
 * @param {string} confirmText - Text for the confirm button.
 * @param {string} type - 'primary' or 'danger' for button styling.
 */
let releaseConfirmation = null;
function showModal(title, message, onConfirm, confirmText = "Confirm", type = "primary", chooseClient = false) {
    const modal = document.getElementById("confirmation-modal");
    if (!modal) {
        console.error("Modal element not found!");
        // Fallback to native confirm if modal is missing (safety)
        if (confirm(message)) {
            onConfirm();
        }
        return;
    }

    const titleEl = document.getElementById("modal-title");
    const bodyEl = document.getElementById("modal-body");
    const confirmBtn = document.getElementById("modal-confirm");
    const cancelBtn = document.getElementById("modal-cancel");

    const clientPicker = document.getElementById("modal-client-picker");
    if (clientPicker) clientPicker.hidden = !chooseClient;
    if (titleEl) titleEl.textContent = title;
    if (bodyEl) bodyEl.textContent = message;

    if (confirmBtn) {
        confirmBtn.textContent = confirmText;
        confirmBtn.disabled = false;
        // Reset classes
        confirmBtn.className = "";
        if (type === "danger") {
            confirmBtn.classList.add("btn-danger");
        } else {
            confirmBtn.classList.add("btn-primary");
        }

        // Remove old event listeners by cloning
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

        newConfirmBtn.addEventListener("click", () => {
            closeModal();
            onConfirm();
        });

        // Focus for accessibility
    }

    if (cancelBtn) {
        // Remove old event listeners
        const newCancelBtn = cancelBtn.cloneNode(true);
        cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);

        newCancelBtn.addEventListener("click", closeModal);
    }

    // Close on overlay click
    modal.onclick = (e) => {
        if (e.target === modal) closeModal();
    };

    // Show modal
    modal.classList.add("active");
    modal.setAttribute("aria-hidden", "false");
    releaseConfirmation?.();
    releaseConfirmation = window.UI?.openDialog(
        modal.querySelector("[role=dialog]") || modal,
        document.activeElement,
        closeModal
    );
}

function closeModal() {
    clientCheckGeneration++;
    releaseConfirmation?.();
    releaseConfirmation = null;
    const modal = document.getElementById("confirmation-modal");
    if (modal) {
        modal.classList.remove("active");
        modal.setAttribute("aria-hidden", "true");
    }
}

/** Reads an action response while preserving a recoverable page-expiry error. */
async function readActionResponse(response) {
    const data = await response.json();
    if (!response.ok) {
        const error = new Error(data.message || "Request failed.");
        error.code = data.code;
        throw error;
    }
    return data;
}

/**
 * Triggers an Audiobookshelf library scan.
 */
function reloadLibrary() {
    showModal(
        "Reload Library",
        "Are you sure you want to initiate a library scan?",
        () => {
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";

            fetch("/reload_library", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
            })
                .then(readActionResponse)
                .then((data) => {
                    if (data.message.toLowerCase().includes("failed")) {
                        showNotification(data.message, "error");
                    } else {
                        showNotification(data.message, "success");
                    }
                })
                .catch((error) => {
                    console.error("Error:", error);
                    showNotification(
                        error.code === "page_expired"
                            ? error.message
                            : "Could not refresh your library. Please try again in a moment.",
                        "error"
                    );
                });
        },
        "Scan Now"
    );
}

/**
 * Deletes a torrent from the client (soft delete).
 * @param {string} torrentId - The ID or Hash of the torrent.
 * @param {HTMLElement} [buttonElement] - The button that triggered the action (optional).
 */
function deleteTorrent(torrentId, buttonElement) {
    buttonElement?.focus({ preventScroll: true });
    showModal(
        "Remove download",
        "Remove this download from its Download Client? Your downloaded files will be kept.",
        () => {
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";

            fetch("/delete", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({ id: torrentId, client: buttonElement?.dataset.client || undefined }),
            })
                .then(readActionResponse)
                .then((data) => {
                    showNotification(data.message, "success");
                    if (data.message.includes("successfully")) {
                        // Remove the row from the DOM if buttonElement is provided
                        if (buttonElement) {
                            const row = buttonElement.closest("tr");
                            if (row) {
                                row.remove();
                                const tbody = document.getElementById("status-table-body");
                                const count = tbody?.querySelectorAll(".remove-torrent-btn").length || 0;
                                const badge = document.getElementById("status-count-badge");
                                if (badge) badge.textContent = `${count} Active`;
                                if (!count && tbody) window.updateTable?.(tbody, []);
                                document.getElementById("status-poll-indicator")?.focus();
                            } else {
                                // Fallback if no row found (unlikely in status table)
                                setTimeout(() => location.reload(), 1000);
                            }
                        } else {
                            setTimeout(() => location.reload(), 1000);
                        }
                    }
                })
                .catch((error) => {
                    console.error("Error:", error);
                    showNotification(
                        error.code === "page_expired"
                            ? error.message
                            : "Could not remove this download. Please try again in a moment.",
                        "error"
                    );
                });
        },
        "Remove",
        "danger"
    );
}

/**
 * Sends a magnet link to the configured torrent client.
 * @param {string} link - The URL/Magnet link.
 * @param {string} title - The book title.
 * @param {HTMLElement} [buttonElement] - The button clicked (for state management).
 * @param {string} [client] - Optional target torrent client identifier.
 */
let clientCheckGeneration = 0;

function requestDownload(link, title, button, client) {
    const picker = document.getElementById("modal-client-picker");
    const choices = picker ? [...picker.querySelectorAll('input[name="download-client"]')] : [];
    if (client || choices.length < 2) {
        sendTorrent(link, title, button, client);
        return;
    }
    if (button?.disabled) return;
    const saved = window.UI?.storage("sessionStorage", "getItem", "downloadClient");
    const preferred = choices.find((choice) => choice.value === saved) || choices[0];
    for (const choice of choices) {
        choice.checked = choice === preferred;
        choice.disabled = true;
        choice.closest("label").dataset.state = "checking";
        choice.closest("label").querySelector(".client-choice-status").textContent = "Checking…";
        choice.closest("label").querySelector(".client-choice-help").hidden = true;
    }
    showModal(
        "Choose Download Client",
        `Send “${title}” to a connected client.`,
        () => {
            const selected = choices.find((choice) => choice.checked && !choice.disabled);
            if (!selected) {
                showNotification("Choose a connected Download Client and try again.", "error");
                return;
            }
            window.UI?.storage("sessionStorage", "setItem", "downloadClient", selected.value);
            sendTorrent(link, title, button, selected.value);
        },
        "Download",
        "primary",
        true
    );
    const generation = ++clientCheckGeneration;
    const confirm = document.getElementById("modal-confirm");
    const updateConfirm = () => {
        confirm.disabled = !choices.some((choice) => choice.checked && !choice.disabled);
    };
    updateConfirm();
    picker.onchange = updateConfirm;
    for (const choice of choices) {
        const finish = (
            connected,
            message = "Could not check this client. Check its connection settings and try again."
        ) => {
            if (generation !== clientCheckGeneration) return;
            const label = choice.closest("label");
            choice.disabled = !connected;
            label.dataset.state = connected ? "connected" : "offline";
            label.querySelector(".client-choice-status").textContent = connected ? "Connected" : "Offline";
            const help = label.querySelector(".client-choice-help");
            help.textContent = connected ? "" : message;
            help.hidden = connected;
            const selected = choices.find((item) => item.checked);
            if (!selected || (selected.disabled && selected.closest("label").dataset.state === "offline")) {
                const available = choices.find((item) => !item.disabled);
                if (available) available.checked = true;
            }
            updateConfirm();
        };
        fetch("/api/clients?client=" + encodeURIComponent(choice.value))
            .then((response) => {
                if (!response.ok) throw new Error("Client check failed");
                return response.json();
            })
            .then((data) => {
                const item = data.clients?.find((item) => item.name === choice.value);
                finish(item?.connected === true, item?.message || undefined);
            })
            .catch(() => finish(false));
    }
}

function sendTorrent(link, title, buttonElement, client) {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";

    // Disable specific button to prevent double-clicks
    let originalBtnHTML = "";
    if (buttonElement) {
        buttonElement.disabled = true;
        originalBtnHTML = buttonElement.innerHTML;
        // Use innerHTML to include the spinner div
        buttonElement.innerHTML = '<span class="spinner"></span> Sending...';
    }

    const payload = { link: link, title: title };
    if (client) {
        payload.client = client;
    }

    fetch("/send", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(payload),
    })
        .then(readActionResponse)
        .then((data) => {
            showNotification(data.message, "success");
            // Improve UX: Show "Sent!" state temporarily
            if (buttonElement) {
                buttonElement.innerText = "Sent!";
                // Keep disabled to prevent re-submission
                buttonElement.disabled = true;

                // Add timeout to reset button
                setTimeout(() => {
                    buttonElement.disabled = false;
                    buttonElement.innerHTML = originalBtnHTML;
                }, 3000);
            }
        })
        .catch((error) => {
            console.error("Download failed:", error);
            showNotification(
                error.code === "page_expired"
                    ? error.message
                    : "Could not start download. Please check that your download app is running and try again.",
                "error"
            );
            // Allow retry on error
            if (buttonElement) {
                buttonElement.disabled = false;
                buttonElement.innerHTML = originalBtnHTML;
            }
        });
}

/**
 * Opens a link in a new tab with a security confirmation.
 * @param {string} url - The URL to open.
 */
function openExternalLink(url) {
    if (!url) return;

    let targetUrl = url;
    // If relative URL, construct an absolute URL using configured host or current mirror
    if (url.startsWith("/")) {
        const mirror = window.ABB_HOST || "audiobookbay.lu";
        targetUrl = `https://${mirror}${url}`;
    }

    const warningMessage =
        "You are about to open this link directly in your browser.\n" +
        "This traffic will NOT be routed through the server's connection.\n\n" +
        "Your IP address and traffic may be exposed.";

    showModal(
        "External Link Warning",
        warningMessage,
        () => {
            window.open(targetUrl, "_blank", "noopener,noreferrer");
        },
        "Proceed",
        "primary"
    );
}

/**
 * Checks client connectivity and displays a non-intrusive warning banner if unreachable.
 */
function initClientBannerCheck() {
    const banner = document.getElementById("client-offline-banner");
    if (!banner) return;

    fetch("/api/clients")
        .then((res) => {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
        })
        .then((data) => {
            const clients = data.clients || [];
            const hasConnected = clients.some((c) => c.connected);
            const unavailable = clients.filter((client) => !client.connected);
            if (unavailable.length > 0) {
                banner.style.display = "block";
                banner.querySelector("strong").textContent = hasConnected
                    ? "Some Download Clients unavailable:"
                    : "Download Client unavailable:";
                document.getElementById("client-connection-message").textContent = unavailable
                    .map((client) => client.message || "Check your Download Client address, port and login settings.")
                    .join(" ");
                // A working client remains usable when another client is offline.
                document.querySelectorAll(".send-torrent-btn, .details-download-btn").forEach((btn) => {
                    const hasPicker = document.getElementById("modal-client-picker");
                    btn.disabled = !hasConnected && !hasPicker;
                    btn.classList.toggle("disabled", btn.disabled);
                    btn.title = btn.disabled ? "Download client is offline or credentials require attention" : "";
                });
            } else {
                banner.style.display = "none";
                document.querySelectorAll(".send-torrent-btn, .details-download-btn").forEach((btn) => {
                    btn.disabled = false;
                    btn.classList.remove("disabled");
                    btn.title = "";
                });
            }
        })
        .catch(() => {
            banner.style.display = "block";
            document.getElementById("client-connection-message").textContent =
                "Could not check Download Clients. Refresh to try again; if this continues, check the app and client connection settings.";
        });
}
