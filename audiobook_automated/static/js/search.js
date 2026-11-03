// File: audiobook_automated/static/js/search.js
// app/static/js/search.js

// Define functions in the global scope (or attach to window) so tests and other scripts (actions.js) can use them.

// Expose these core functions to the global scope for testing and external use (e.g., actions.js)
window.parseFileSizeToMB = parseFileSizeToMB;
window.formatFileSize = formatFileSize;
window.initializeFilters = initializeFilters;
window.applyFilters = applyFilters;
window.clearFilters = clearFilters;
window.showLoadingSpinner = showLoadingSpinner;
window.hideLoadingSpinner = hideLoadingSpinner;
window.setViewMode = setViewMode;
window.initFloatingHud = initFloatingHud;
window.initTopFilterDrawer = initTopFilterDrawer;
window.updateFilterBadges = updateFilterBadges;
window.streamRemainingPages = streamRemainingPages;
window.createResultRowElement = createResultRowElement;
window.initHoverPrefetch = initHoverPrefetch;
window.initInfiniteScroll = initInfiniteScroll;
window.loadNextPage = loadNextPage;
window.resetPaginationState = resetPaginationState;

// Global variables defined in the file
let messageIndex = 0;
let intervalId = null;
let messageDelayId = null;
const prefetchedQueries = new Set();
let currentPage = 1;
let isLoadingMore = false;
let hasMorePages = true;
let infiniteScrollObserver = null;

function resetPaginationState() {
    currentPage = 1;
    isLoadingMore = false;
    hasMorePages = true;
    if (infiniteScrollObserver) {
        infiniteScrollObserver.disconnect();
        infiniteScrollObserver = null;
    }
}

document.addEventListener("DOMContentLoaded", function () {
    initRecentSearches();
    const searchInput = document.getElementById("main-search-input");
    const clearSearch = document.getElementById("clear-search-btn");
    if (searchInput) {
        const wrapper = searchInput.closest(".search-input-wrapper");
        const updateOverflow = () =>
            wrapper?.classList.toggle(
                "has-overflow",
                Boolean(searchInput.value) && searchInput.scrollWidth > searchInput.clientWidth + 1
            );
        const updateQuery = () => {
            const query = searchInput.value.trim();
            searchInput.setCustomValidity(query.length === 1 ? "Enter at least 2 characters." : "");
            wrapper?.classList.toggle("has-query", Boolean(searchInput.value));
            if (clearSearch) clearSearch.hidden = !searchInput.value;
            requestAnimationFrame(updateOverflow);
        };
        searchInput.addEventListener("input", updateQuery);
        searchInput.addEventListener("change", updateQuery);
        searchInput.addEventListener("focus", updateQuery);
        searchInput.addEventListener("blur", () => {
            searchInput.scrollLeft = 0;
            updateQuery();
        });
        searchInput.addEventListener("invalid", () => searchInput.setCustomValidity("Enter at least 2 characters."));
        clearSearch?.addEventListener("click", () => {
            searchInput.value = "";
            searchInput.dispatchEvent(new Event("input", { bubbles: true }));
            searchInput.focus();
        });
        if (typeof ResizeObserver !== "undefined") new ResizeObserver(updateOverflow).observe(searchInput);
        updateQuery();
    }

    // Initialize filtering if results are present
    if (document.querySelectorAll(".result-row").length > 0) {
        initializeFilters();
        refreshFilterOptions();
        applyFilters();
    }

    // Initialize View Mode (defaults to grid view)
    const savedView = window.UI?.storage("localStorage", "getItem", "viewMode") || "grid";
    setViewMode(savedView);

    // Bind Toggle Buttons
    const listBtn = document.getElementById("view-list-btn");
    const gridBtn = document.getElementById("view-grid-btn");

    if (listBtn)
        listBtn.addEventListener("click", function () {
            setViewMode("list");
        });
    if (gridBtn)
        gridBtn.addEventListener("click", function () {
            setViewMode("grid");
        });

    // Search Form Handler
    const searchForm = document.getElementById("search-form");
    if (searchForm) {
        searchForm.addEventListener("submit", function () {
            showLoadingSpinner();
        });
    }

    // Initialize Top Filter Drawer & Floating HUD
    initTopFilterDrawer();
    initFloatingHud();

    // Infinite Scroll Auto-loader & Progressive Search Streaming
    const resultsContainer = document.getElementById("results-container");
    if (resultsContainer && resultsContainer.dataset.query && resultsContainer.dataset.hasResults === "true") {
        const query = resultsContainer.dataset.query;
        initInfiniteScroll(query);
    }

    document.getElementById("reset-empty-filters")?.addEventListener("click", clearFilters);
    initHoverPrefetch();
});

function setViewMode(mode) {
    const container = document.getElementById("results-container");
    const listBtn = document.getElementById("view-list-btn");
    const gridBtn = document.getElementById("view-grid-btn");

    if (!container || !listBtn || !gridBtn) return;

    // Update localStorage
    window.UI?.storage("localStorage", "setItem", "viewMode", mode);

    // Update Container Class
    container.classList.remove("view-list", "view-grid");
    container.classList.add("view-" + mode);
    container.querySelectorAll(".result-row").forEach((row) => positionPostedDate(row, mode));

    // Update Buttons
    if (mode === "list") {
        listBtn.setAttribute("aria-pressed", "true");
        gridBtn.setAttribute("aria-pressed", "false");
        listBtn.classList.add("active");
        gridBtn.classList.remove("active");
    } else {
        gridBtn.setAttribute("aria-pressed", "true");
        listBtn.setAttribute("aria-pressed", "false");
        gridBtn.classList.add("active");
        listBtn.classList.remove("active");
    }
}

function positionPostedDate(row, mode) {
    const date = row.querySelector(".book-posted");
    const destination = row.querySelector(mode === "list" ? ".col-info" : ".col-actions");
    if (date && destination) destination.append(date);
}

// ROBUSTNESS: Handle Browser Back/Forward Cache (BFCache)
// If the user searches, navigates away, and clicks "Back", the page might load
// from cache with the spinner still active. This forces a reset.
window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
        hideLoadingSpinner();
    }
});

// --- Helper Functions ---

/**
 * Initializes all filter components (Native Date and Size inputs).
 */
function initializeFilters() {
    // Native HTML5 inputs require no vendor initialization.
    // If needed, set date input constraints based on DOM rows.
    const dateFromEl = document.getElementById("date-from-filter");
    const dateToEl = document.getElementById("date-to-filter");

    if (dateFromEl && dateToEl) {
        // Clear any stale constraints or re-sync
        dateFromEl.addEventListener("change", () => {
            if (dateFromEl.value) {
                dateToEl.min = dateFromEl.value;
            } else {
                dateToEl.removeAttribute("min");
            }
        });
        dateToEl.addEventListener("change", () => {
            if (dateToEl.value) {
                dateFromEl.max = dateToEl.value;
            } else {
                dateFromEl.removeAttribute("max");
            }
        });
    }
}

/**
 * Parses a file size string (e.g., "1.5 GB") into Megabytes.
 * @param {string} sizeString - The file size string.
 * @returns {number|null} - Size in MB or null if invalid.
 */
function parseFileSizeToMB(sizeString) {
    if (!sizeString || sizeString.trim().toLowerCase() === "unknown") return null;

    const match = sizeString.trim().match(/^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$/);
    if (!match) return null;

    const size = parseFloat(match[1]);
    const unit = match[2].toUpperCase();

    if (isNaN(size)) return null;

    if (unit.startsWith("PB")) return size * 1024 * 1024 * 1024;
    if (unit.startsWith("TB")) return size * 1024 * 1024;
    if (unit.startsWith("GB")) return size * 1024;
    if (unit.startsWith("KB")) return size / 1024;
    if (unit.startsWith("B")) return size / (1024 * 1024);

    if (unit.startsWith("MB")) return size;

    console.warn("Unrecognized file size unit:", unit, "in string:", sizeString);
    return size;
}

/**
 * Formats a size in MB to a human-readable string (MB/GB/TB).
 * @param {number} mb - Size in Megabytes.
 * @returns {string} - Formatted string.
 */
function formatFileSize(mb) {
    if (mb === null || isNaN(mb)) return "Unknown";
    if (mb >= 1024 * 1024) {
        return (mb / (1024 * 1024)).toFixed(2) + " TB";
    }
    if (mb >= 1024) {
        return (mb / 1024).toFixed(2) + " GB";
    }
    return mb.toFixed(2) + " MB";
}

/**
 * Parses any date format string from AudiobookBay or ISO into a Date object at midnight UTC.
 * @param {string} dateStr - Date string.
 * @returns {Date|null}
 */
function parsePostDate(dateStr) {
    if (!dateStr || dateStr === "Unknown") return null;
    try {
        let date;
        if (/^\d{1,2}\s[a-zA-Z]{3}\s\d{4}$/.test(dateStr)) {
            const formattedStr = dateStr.replace(/(\d{1,2})\s(\w{3})\s(\d{4})/, "$2 $1, $3");
            date = new Date(formattedStr);
        } else if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
            date = new Date(dateStr + "T00:00:00");
        } else {
            date = new Date(dateStr);
        }
        return isNaN(date.getTime()) ? null : date;
    } catch {
        return null;
    }
}

/**
 * Applies all active filters to the result table.
 */
function applyFilters() {
    const author = document.getElementById("author-filter")?.value || "";
    const category = document.getElementById("category-filter")?.value || "";
    const language = document.getElementById("language-filter")?.value || "";
    const bitrate = document.getElementById("bitrate-filter")?.value || "";
    const format = document.getElementById("format-filter")?.value || "";
    const fileSizeFilter = document.getElementById("file-size-filter")?.value || "";

    const dateFromVal = document.getElementById("date-from-filter")?.value || "";
    const dateToVal = document.getElementById("date-to-filter")?.value || "";

    const validation = document.getElementById("filter-validation");
    const valid = !dateFromVal || !dateToVal || dateFromVal <= dateToVal;
    if (validation) {
        validation.hidden = valid;
        validation.textContent = valid ? "" : "Choose an end date on or after the start date.";
    }
    if (!valid) {
        document.getElementById("date-to-filter")?.focus();
        return false;
    }
    const dateFrom = dateFromVal ? new Date(dateFromVal + "T00:00:00") : null;
    const dateTo = dateToVal ? new Date(dateToVal + "T23:59:59") : null;

    let hasMatches = false;
    const rows = document.querySelectorAll(".result-row");
    rows.forEach((row) => {
        let visible = true;

        if (author && !JSON.parse(row.dataset.credits || "[]").includes(author)) visible = false;

        // Exact Token Match for Category
        if (category) {
            const rowCategories = (row.dataset.category || "").split(/[|,]/).map((t) => t.trim());
            if (!rowCategories.includes(category)) {
                visible = false;
            }
        }

        if (language && row.dataset.language !== language) visible = false;
        if (bitrate && row.dataset.bitrate !== bitrate) visible = false;
        if (format && row.dataset.format !== format) visible = false;

        // File size filter presets
        if (fileSizeFilter) {
            const rowSizeMB = parseFileSizeToMB(row.dataset.fileSize);
            if (rowSizeMB === null) {
                visible = false;
            } else if (fileSizeFilter === "under_500mb" && rowSizeMB >= 500) {
                visible = false;
            } else if (fileSizeFilter === "500mb_2gb" && (rowSizeMB < 500 || rowSizeMB > 2048)) {
                visible = false;
            } else if (fileSizeFilter === "2gb_5gb" && (rowSizeMB < 2048 || rowSizeMB > 5120)) {
                visible = false;
            } else if (fileSizeFilter === "over_5gb" && rowSizeMB < 5120) {
                visible = false;
            }
        }

        // Native Date Range filter
        if (dateFrom || dateTo) {
            const rowDate = parsePostDate(row.dataset.postDate);
            if (!rowDate) {
                visible = false;
            } else {
                if (dateFrom && rowDate < dateFrom) visible = false;
                if (dateTo && rowDate > dateTo) visible = false;
            }
        }

        row.style.display = visible ? "" : "none";
        if (visible) hasMatches = true;
    });
    const empty = document.getElementById("filtered-empty");
    if (empty) empty.hidden = hasMatches || rows.length === 0;
    updateFilterBadges();
    return true;
}

/**
 * Resets all filters to their default state.
 */
function clearFilters() {
    const fields = [
        "author-filter",
        "category-filter",
        "language-filter",
        "bitrate-filter",
        "format-filter",
        "file-size-filter",
        "date-from-filter",
        "date-to-filter",
    ];

    fields.forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });

    const dateFromEl = document.getElementById("date-from-filter");
    const dateToEl = document.getElementById("date-to-filter");
    if (dateFromEl) dateFromEl.removeAttribute("max");
    if (dateToEl) dateToEl.removeAttribute("min");

    applyFilters();
}

/**
 * Shows the loading spinner and initializes the funny message scroller.
 */
function showLoadingSpinner() {
    const button = document.querySelector(".search-button");
    if (button) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        if (!button.dataset.originalText) {
            // FIX: Use textContent instead of innerText for JSDOM compatibility
            button.dataset.originalText = button.querySelector(".button-text").textContent;
        }
        button.querySelector(".button-text").textContent = "Searching...";
    }

    const buttonSpinner = document.getElementById("button-spinner");
    if (buttonSpinner) buttonSpinner.style.display = "inline-flex";

    clearTimeout(messageDelayId);
    messageDelayId = setTimeout(showScrollingMessages, 3000);
}

/**
 * Hides the loading spinner and stops the message scroller.
 */
function hideLoadingSpinner() {
    clearTimeout(messageDelayId);
    messageDelayId = null;
    const button = document.querySelector(".search-button");
    if (button) {
        button.disabled = false;
        button.setAttribute("aria-busy", "false");
        if (button.dataset.originalText) {
            // FIX: Use textContent instead of innerText for JSDOM compatibility
            button.querySelector(".button-text").textContent = button.dataset.originalText;
        }
    }

    const buttonSpinner = document.getElementById("button-spinner");
    if (buttonSpinner) buttonSpinner.style.display = "none";

    hideScrollingMessages();
}

const messages = [
    "Checking the book catalog...",
    "Still searching. Some catalog pages take longer to respond.",
    "Results will appear as soon as the catalog responds.",
];

function showScrollingMessages() {
    const messageScroller = document.getElementById("message-scroller");
    const scrollingMessage = document.getElementById("scrolling-message");
    if (!scrollingMessage) return;

    const shuffledMessages = messages.sort(() => Math.random() - 0.5);
    messageScroller.style.display = "block";
    scrollingMessage.textContent = shuffledMessages[messageIndex];

    if (intervalId) clearInterval(intervalId);
    intervalId = setInterval(() => {
        messageIndex = (messageIndex + 1) % messages.length;
        scrollingMessage.textContent = shuffledMessages[messageIndex];
    }, 4000);
}

function hideScrollingMessages() {
    const messageScroller = document.getElementById("message-scroller");
    if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
    }
    if (messageScroller) messageScroller.style.display = "none";
}

/**
 * Escapes HTML entities to prevent XSS.
 * @param {string} str - Raw string.
 * @returns {string} - Escaped string.
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

/**
 * Creates a DOM table row for a book summary.
 * @param {Object} book - The BookSummary dictionary.
 * @returns {HTMLTableRowElement} - The created .result-row element.
 */
function createResultRowElement(book) {
    const row = document.createElement("tr");
    row.className = "result-row";
    row.dataset.credits = JSON.stringify(Array.isArray(book.credited_contributors) ? book.credited_contributors : []);
    row.dataset.category = Array.isArray(book.category) ? book.category.join("|") : book.category || "";
    row.dataset.language = book.language || "Unknown";
    row.dataset.bitrate = book.bitrate || "Unknown";
    row.dataset.format = book.format || "Unknown";
    row.dataset.fileSize = book.file_size || "Unknown";
    row.dataset.postDate = book.post_date || "Unknown";

    const defaultCover =
        document.querySelector(".cover[data-default-cover]")?.getAttribute("data-default-cover") ||
        "/static/images/cover-placeholder.svg";
    const coverSrc = book.cover ? escapeHtml(book.cover) : defaultCover;
    const detailsUrl = "/details?link=" + encodeURIComponent(book.link || "");
    const title = escapeHtml(book.title || "Untitled Audiobook");

    // Category pills HTML
    let categoryHtml = "";
    if (Array.isArray(book.category)) {
        book.category.forEach((rawCat) => {
            const parts = rawCat.split(",");
            parts.forEach((cat) => {
                const clean = cat.trim();
                if (clean && clean !== "Unknown") {
                    categoryHtml += `<a href="/?query=${encodeURIComponent("category:" + clean)}" class="category-tag category-link" title="Browse ${escapeHtml(clean)} category">${escapeHtml(clean)}</a>\n`;
                }
            });
        });
    }

    row.innerHTML = `
        <td class="col-cover">
            <a href="${detailsUrl}">
                ${book.cover ? `<img src="${coverSrc}" alt="Cover of ${title}" class="cover" width="100" loading="lazy" decoding="async" data-default-cover="${defaultCover}" />` : '<span class="cover-placeholder" role="img" aria-label="Cover Unavailable"></span>'}
            </a>
        </td>
        <td class="col-info">
            <p class="book-title" title="${title}">${escapeHtml(book.display_title || book.title || "Untitled Audiobook")}</p>
<p class="book-attribution${book.author_credit ? "" : " book-attribution-empty"}" title="${escapeHtml(book.author_credit || "")}"${book.author_credit ? "" : ' aria-hidden="true"'}>${escapeHtml(book.author_credit || "")}</p>
            <div class="categories-container">
                ${categoryHtml}
            </div>
<dl class="property-results-container">
<div class="book-property"><dt>Language</dt><dd class="book-language">${escapeHtml(book.language || "Unknown")}</dd></div>
<div class="book-property"><dt>Bitrate</dt><dd class="book-bitrate">${escapeHtml(book.bitrate || "Unknown")}</dd></div>
<div class="book-property"><dt>Format</dt><dd class="book-format">${escapeHtml(book.format || "Unknown")}</dd></div>
<div class="book-property"><dt>File size</dt><dd class="book-file_size">${escapeHtml(book.file_size || "Unknown")}</dd></div>

</dl>
        </td>
        <td class="col-actions">
            <div class="action-buttons">
                <a href="${detailsUrl}" class="btn-glass details-button">Details</a>
                <button class="btn-primary send-torrent-btn" data-link="${escapeHtml(book.link || "")}" data-title="${title}">Download</button>
            </div>
<p class="book-posted" title="Posted to catalog">
<svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></svg>
<span class="sr-only">Posted to catalog </span><span class="book-post_date">${escapeHtml(book.post_date || "Unknown")}</span>
</p>
        </td>
    `;
    positionPostedDate(
        row,
        document.getElementById("results-container")?.classList.contains("view-list") ? "list" : "grid"
    );
    return row;
}

/**
 * Loads the next page of search results asynchronously and appends to the table.
 * @param {string} query - The search query term.
 * @returns {Promise<boolean>} - True if more results might exist, false if exhausted or errored.
 */
let paginationState = "idle";

function setPaginationState(state) {
    paginationState = state;
    const indicator = document.getElementById("load-more-indicator");
    const spinner = document.getElementById("load-more-loading");
    const button = document.getElementById("load-more-btn");
    const end = document.getElementById("load-more-end");
    const message = document.getElementById("pagination-message");
    if (indicator) {
        indicator.style.display = "flex";
        indicator.setAttribute("aria-busy", String(state === "loading"));
    }
    if (spinner) spinner.style.display = state === "loading" ? "flex" : "none";
    if (button) {
        button.style.display = state === "exhausted" ? "none" : "inline-block";
        button.disabled = state === "loading";
        button.textContent =
            state === "error"
                ? "Retry loading audiobooks"
                : state === "loading"
                  ? "Loading audiobooks…"
                  : "Load more audiobooks";
    }
    if (end) {
        end.style.display = state === "exhausted" ? "block" : "none";
        end.textContent = "End of results";
    }
    if (message) message.hidden = state === "exhausted";
    if (message)
        message.textContent = {
            idle: "More results load as you scroll. You can also load them below.",
            loading: "Finding more audiobooks…",
            error: "Couldn’t load more audiobooks. Your results are still here. Please retry.",
            exhausted: "",
        }[state];
}

function showEndOfResults() {
    setPaginationState("exhausted");
}

async function loadNextPage(query) {
    if (isLoadingMore || !hasMorePages || !query) return false;
    const tbody = document.getElementById("results-table-body");
    if (!tbody) return false;
    isLoadingMore = true;
    setPaginationState("loading");
    const nextPage = currentPage + 1;
    try {
        const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&page=${nextPage}`);
        if (!response.ok) throw new Error("Page request failed");
        const data = await response.json();
        if (!Array.isArray(data.books)) throw new Error("Invalid search response");
        data.books.forEach((book) => tbody.appendChild(createResultRowElement(book)));
        currentPage = nextPage;
        hasMorePages = data.books.length > 0 && Boolean(data.has_more);
        refreshFilterOptions();
        initHoverPrefetch();
        applyFilters();
        setPaginationState(hasMorePages ? "idle" : "exhausted");
        const indicator = document.getElementById("load-more-indicator");
        if (hasMorePages && infiniteScrollObserver && indicator) {
            infiniteScrollObserver.unobserve(indicator);
            infiniteScrollObserver.observe(indicator);
        }
        return hasMorePages;
    } catch (error) {
        setPaginationState("error");
        return false;
    } finally {
        isLoadingMore = false;
    }
}

function initInfiniteScroll(query) {
    resetPaginationState();
    setPaginationState("idle");
    const indicator = document.getElementById("load-more-indicator");
    const button = document.getElementById("load-more-btn");
    if (button) button.onclick = () => loadNextPage(query);
    if ("IntersectionObserver" in window && indicator) {
        infiniteScrollObserver = new IntersectionObserver(
            (entries) => {
                if (entries[0]?.isIntersecting && !isLoadingMore && hasMorePages && paginationState !== "error")
                    loadNextPage(query);
            },
            { root: null, rootMargin: "300px", threshold: 0.1 }
        );
        infiniteScrollObserver.observe(indicator);
    }
}

async function streamRemainingPages(query, startPage = 2, maxPage = 5) {
    currentPage = startPage - 1;
    for (let page = startPage; page <= maxPage; page++) {
        if (!(await loadNextPage(query))) break;
    }
}

function refreshFilterOptions() {
    ["author", "category", "language", "bitrate", "format"].forEach((field) => {
        const values = new Set();
        document.querySelectorAll(".result-row").forEach((row) => {
            const value = row.dataset[field] || "";
            (field === "author"
                ? JSON.parse(row.dataset.credits || "[]")
                : field === "category"
                  ? value.split(/[|,]/)
                  : [value]
            ).forEach((item) => {
                const clean = item.trim();
                if (clean && clean !== "Unknown" && clean !== "None") values.add(clean);
            });
        });
        [field + "-filter"].forEach((id) => {
            const select = document.getElementById(id);
            if (!select) return;
            const existing = new Set([...select.options].map((option) => option.value));
            [...values].sort().forEach((value) => {
                if (!existing.has(value)) select.add(new Option(value, value));
            });
        });
    });
}

function initRecentSearches() {
    const panel = document.getElementById("recent-searches");
    const query = document.querySelector(".search-bar")?.value.trim();
    if (query && document.querySelector(".result-row"))
        window.UI?.storage("sessionStorage", "setItem", "resultsUrl", location.pathname + location.search);
    if (!panel) return;
    let recent = [];
    try {
        recent = JSON.parse(window.UI?.storage("sessionStorage", "getItem", "recentSearches") || "[]");
    } catch (_) {
        /* Empty history. */
    }
    if (!Array.isArray(recent)) recent = [];
    recent = recent.filter((item) => typeof item === "string");
    if (query) recent = [query, ...recent.filter((item) => item !== query)].slice(0, 5);
    window.UI?.storage("sessionStorage", "setItem", "recentSearches", JSON.stringify(recent));
    panel.replaceChildren();
    panel.hidden = recent.length === 0;
    if (!recent.length) return;
    const header = document.createElement("div");
    header.className = "recent-searches-header";
    const label = document.createElement("span");
    label.textContent = "Recent searches";
    header.append(label);
    const list = document.createElement("ul");
    list.className = "recent-search-list";
    recent.forEach((item) => {
        const link = document.createElement("a");
        link.href = "/?query=" + encodeURIComponent(item);
        link.textContent = item;
        link.title = item;
        const itemElement = document.createElement("li");
        itemElement.append(link);
        list.append(itemElement);
    });
    const clear = document.createElement("button");
    clear.type = "button";
    clear.innerHTML =
        '<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></svg>';
    clear.className = "recent-history-clear";
    clear.setAttribute("aria-label", "Clear recent searches");
    clear.title = "Clear recent searches";
    clear.onclick = () => {
        window.UI?.storage("sessionStorage", "removeItem", "recentSearches");
        panel.replaceChildren();
        panel.hidden = true;
        document.getElementById("main-search-input")?.focus();
    };
    header.append(clear);
    panel.append(header, list);
}

/**
 * Prefetches search results or book details into browser cache and server cache.
 * @param {string} url - The URL to prefetch.
 */
function prefetchUrl(url) {
    if (!url || prefetchedQueries.has(url)) return;
    prefetchedQueries.add(url);

    // Use low priority background fetch
    fetch(url, { priority: "low" }).catch(() => {});
}

/**
 * Initializes hover prefetching for all Category, Author, Narrator, and Details links.
 * When the user hovers for 120ms, or when results scroll into view, a prefetch request is sent to warm caches.
 */
function initHoverPrefetch() {
    // 1. Prefetch Category & Search links
    const categoryLinks = document.querySelectorAll("a.category-link");
    categoryLinks.forEach((link) => {
        if (link.dataset.prefetchBound) return;
        link.dataset.prefetchBound = "true";

        let hoverTimer = null;
        link.addEventListener("mouseenter", function () {
            const href = link.getAttribute("href");
            if (!href || !href.includes("query=")) return;
            const match = href.match(/[?&]query=([^&]+)/);
            if (!match) return;
            const query = decodeURIComponent(match[1].replace(/\+/g, " ")).trim();
            if (query.length < 2 || prefetchedQueries.has(query)) return;

            hoverTimer = setTimeout(() => {
                prefetchUrl(`/api/search?query=${encodeURIComponent(query)}&page=1`);
            }, 120);
        });

        link.addEventListener("mouseleave", function () {
            if (hoverTimer) {
                clearTimeout(hoverTimer);
                hoverTimer = null;
            }
        });
    });

    // 2. Prefetch Details links for fast private view loading
    const detailsLinks = document.querySelectorAll("a.details-button, .col-cover a");
    detailsLinks.forEach((link) => {
        if (link.dataset.prefetchBound) return;
        link.dataset.prefetchBound = "true";

        let hoverTimer = null;
        link.addEventListener("mouseenter", function () {
            const href = link.getAttribute("href");
            if (!href || !href.includes("link=")) return;

            hoverTimer = setTimeout(() => {
                prefetchUrl(href);
            }, 120);
        });

        link.addEventListener("mouseleave", function () {
            if (hoverTimer) {
                clearTimeout(hoverTimer);
                hoverTimer = null;
            }
        });
    });
}

/**
 * Updates both entry-point badges from the shared filter controls.
 */
function updateFilterBadges() {
    let activeFilterCount = ["author", "category", "language", "bitrate", "format", "file-size"].filter(
        (field) => document.getElementById(field + "-filter")?.value
    ).length;

    // Include date range in the shared active-filter count
    const dateFrom = document.getElementById("date-from-filter")?.value;
    const dateTo = document.getElementById("date-to-filter")?.value;
    if (dateFrom || dateTo) {
        activeFilterCount++;
    }

    // Update active filter badges on both toolbar and floating HUD
    const hudBadge = document.getElementById("hud-filter-badge");
    if (hudBadge) {
        if (activeFilterCount > 0) {
            hudBadge.textContent = activeFilterCount;
            hudBadge.style.display = "inline-block";
        } else {
            hudBadge.style.display = "none";
        }
    }

    const toolbarBadge = document.getElementById("toolbar-filter-badge");
    if (toolbarBadge) {
        if (activeFilterCount > 0) {
            toolbarBadge.textContent = activeFilterCount;
            toolbarBadge.style.display = "inline-block";
        } else {
            toolbarBadge.style.display = "none";
        }
    }
}

/**
 * Initializes the floating condensed HUD bar that slides into view upon scrolling.
 */
function initFloatingHud() {
    if (!document.getElementById("floating-filter-hud")) return;
    window.UI.bindFloatingControls();
    const form = document.getElementById("hud-search-form");
    const input = document.getElementById("hud-search-input");
    form?.addEventListener("submit", () => {
        const main = document.querySelector(".search-bar");
        if (main && input) main.value = input.value;
        showLoadingSpinner();
    });
}

/** Both entry points open the same controls, including date range. */
function initTopFilterDrawer() {
    const triggers = [
        document.getElementById("toolbar-filter-toggle"),
        document.getElementById("hud-filter-toggle"),
    ].filter(Boolean);
    const overlay = document.getElementById("filter-drawer-overlay");
    if (!triggers.length || !overlay) return;
    let release = null;
    const controls = ["author", "category", "language", "bitrate", "format", "file-size", "date-from", "date-to"]
        .map((name) => document.getElementById(name + "-filter"))
        .filter(Boolean);
    let committed = [];
    const close = (apply = false) => {
        if (!apply) {
            controls.forEach((control, index) => {
                control.value = committed[index] || "";
                control.dispatchEvent(new Event("change"));
            });
            applyFilters();
        }
        overlay.classList.remove("open");
        overlay.setAttribute("aria-hidden", "true");
        triggers.forEach((trigger) => trigger.setAttribute("aria-expanded", "false"));
        document.body.classList.remove("filters-open");
        release?.();
        release = null;
    };
    triggers.forEach((trigger) =>
        trigger.addEventListener("click", (event) => {
            event.stopPropagation();
            committed = controls.map((control) => control.value);
            overlay.classList.add("open");
            overlay.setAttribute("aria-hidden", "false");
            triggers.forEach((button) => button.setAttribute("aria-expanded", "true"));
            document.body.classList.add("filters-open");
            release = window.UI.openDialog(overlay.querySelector("[role=dialog]") || overlay, trigger, () => close());
        })
    );
    document.getElementById("filter-drawer-close")?.addEventListener("click", () => close());
    document.getElementById("filter-button")?.addEventListener("click", () => {
        if (applyFilters()) close(true);
    });
    document.getElementById("clear-button")?.addEventListener("click", () => {
        clearFilters();
        committed = controls.map((control) => control.value);
    });
    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) close();
    });
}
