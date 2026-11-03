// File: audiobook_automated/static/js/ui.js
// Shared browser preferences and accessible dialog lifecycle.
window.UI = {
    storage(kind, operation, key, value) {
        try {
            return window[kind][operation](key, value);
        } catch (_) {
            return null;
        }
    },
    reducedMotion() {
        return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    },
    bindFloatingControls() {
        if (this.floatingListener) window.removeEventListener("scroll", this.floatingListener);
        let scheduled = false;
        const update = () => {
            const visible = window.scrollY > 300;
            document
                .querySelectorAll(".floating-control, #floating-filter-hud, #scroll-to-top-btn")
                .forEach((control) => {
                    control.classList.toggle("visible", visible);
                    control.inert = !visible;
                });
            if (this.floatingVisible !== visible) {
                this.floatingVisible = visible;
                document.dispatchEvent(new CustomEvent("floatingcontrolschange", { detail: { visible } }));
            }
            scheduled = false;
        };
        this.floatingListener = () => {
            if (scheduled) return;
            scheduled = true;
            if (typeof requestAnimationFrame === "function") requestAnimationFrame(update);
            else update();
        };
        window.addEventListener("scroll", this.floatingListener, { passive: true });
        update();
    },
    openDialog(panel, trigger, close, includeTrigger = false) {
        if (!panel) return () => {};
        window.UI.activeDialog?.();
        const previous = trigger || document.activeElement;
        const hidden = [...document.body.children].filter((el) => !el.contains(panel) && !el.contains(trigger));
        const inertStates = hidden.map((el) => [el, el.inert]);
        hidden.forEach((el) => {
            el.inert = true;
        });
        const selector = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex="0"]';
        const focusables = () =>
            [...panel.querySelectorAll(selector)].filter((el) => !el.hidden && !el.closest("[hidden]"));
        const keyHandler = (event) => {
            if (event.key === "Escape") {
                event.preventDefault();
                event.stopImmediatePropagation();
                close();
                return;
            }
            if (event.key !== "Tab") return;
            const items = focusables();
            if (includeTrigger && trigger) items.unshift(trigger);
            if (!items.length) {
                event.preventDefault();
                panel.focus();
                return;
            }
            const index = items.indexOf(document.activeElement);
            if (event.shiftKey && index <= 0) {
                event.preventDefault();
                items.at(-1).focus();
            } else if (!event.shiftKey && (index < 0 || index === items.length - 1)) {
                event.preventDefault();
                items[0].focus();
            }
        };
        document.addEventListener("keydown", keyHandler, true);
        (focusables()[0] || panel).focus();
        let released = false;
        const release = () => {
            if (released) return;
            released = true;
            document.removeEventListener("keydown", keyHandler, true);
            inertStates.forEach(([el, state]) => {
                el.inert = state;
            });
            const replacement = previous?.dataset?.torrentId
                ? [...document.querySelectorAll(".remove-torrent-btn")].find(
                      (button) =>
                          button.dataset.torrentId === previous.dataset.torrentId &&
                          button.dataset.client === previous.dataset.client
                  )
                : document.getElementById(previous?.id || "");
            const candidates = [
                previous,
                replacement,
                document.getElementById("mobile-menu-btn"),
                document.getElementById("status-poll-indicator"),
                document.getElementById("main-content"),
            ];
            candidates
                .find(
                    (element) =>
                        element?.isConnected &&
                        !element.closest("[hidden]") &&
                        getComputedStyle(element).visibility !== "hidden" &&
                        getComputedStyle(element).display !== "none"
                )
                ?.focus({ preventScroll: true });
            if (window.UI.activeDialog === release) window.UI.activeDialog = null;
        };
        window.UI.activeDialog = release;
        return release;
    },
};
