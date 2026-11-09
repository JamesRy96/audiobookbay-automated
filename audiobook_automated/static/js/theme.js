// File: audiobook_automated/static/js/theme.js

(function () {
    // Immediate execution to prevent FOUC (Flash of Unstyled Content)
    const fallbackTheme = window.DEFAULT_THEME || "purple";
    const savedTheme = window.UI.storage("localStorage", "getItem", "theme") || fallbackTheme;
    document.documentElement.setAttribute("data-theme", savedTheme);

    function setTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        window.UI.storage("localStorage", "setItem", "theme", theme);
    }

    window.setTheme = setTheme; // Expose for testing if needed

    // Run once on load to set initial dropdown state
    document.addEventListener("DOMContentLoaded", function () {
        const selector = document.getElementById("theme-selector");

        if (selector) {
            // Set initial value
            selector.value = savedTheme;

            // Bind change event
            selector.addEventListener("change", function (e) {
                setTheme(e.target.value);
            });
        }
    });
})();
