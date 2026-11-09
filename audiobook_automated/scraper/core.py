# File: audiobook_automated/scraper/core.py
"""Core scraper logic for retrieving search results and details."""

import logging
import re
from collections.abc import Sequence
from typing import Any, cast
from urllib.parse import quote, urljoin, urlparse

from flask import current_app, has_app_context

from ..constants import ERROR_HASH_NOT_FOUND, SCRAPER_REQUEST_TIMEOUT_SECONDS
from ..extensions import executor
from . import network, parser
from .parser import BookSummary

logger = logging.getLogger(__name__)


def slugify_taxonomy(text: str) -> str:
    """Normalize text into an AudiobookBay-compatible URL slug."""
    # Convert spaces/underscores/slashes to hyphens, lowercase, and strip punctuation
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    cleaned = re.sub(r"[\s_]+", "-", cleaned)
    return cleaned.strip("-")


def get_search_url(base_url: str, query: str | None, page: int = 1) -> str:
    """Construct the search or taxonomy URL for a given query and page number.

    Supports:
      - Direct taxonomy prefixes:
          'category:<category>' -> /audio-books/type/<category>/page/<N>/
          'language:<language>' -> /audio-books/tag/<language>/page/<N>/
      - Contributor searches use the catalog's keyword search, not fabricated archive paths.
        Dotted initials are omitted to match both compact and spaced catalog spellings.
      - Direct path input:
          '/audio-books/...'    -> /audio-books/.../page/<N>/
      - General keyword search:
          'query'               -> /page/<N>/?s=query
      - Browse mode (no query):
          None                  -> /page/<N>/
    """
    # Ensure scheme: if not specified in base_url, check network mirror stat or fallback to https
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        host_clean = base_url.split("/", maxsplit=1)[0]
        stat = network.get_mirror_stat(host_clean)
        scheme = getattr(stat, "protocol", "https")
        base_url = f"{scheme}://{base_url}"
    base_url = base_url.rstrip("/")

    if not query:
        return f"{base_url}/page/{page}/"

    q_strip = query.strip()

    # Case 1: Direct path provided (e.g. /audio-books/type/action/)
    if q_strip.startswith("/audio-books/"):
        path = q_strip.rstrip("/")
        if page > 1:
            return f"{base_url}{path}/page/{page}/"
        return f"{base_url}{path}/"

    # Case 2: Taxonomy prefix detected
    taxonomy_prefixes = {
        "category:": "type",
        "language:": "tag",
    }
    for prefix, tax_type in taxonomy_prefixes.items():
        if q_strip.lower().startswith(prefix):
            raw_val = q_strip[len(prefix) :].strip()
            slug = slugify_taxonomy(raw_val)
            path = f"/audio-books/{tax_type}/{slug}"
            if page > 1:
                return f"{base_url}{path}/page/{page}/"
            return f"{base_url}{path}/"

    # The catalog has no author/narrator archive links. Search existing catalog text without enrichment.
    for prefix in ("author:", "narrator:"):
        if q_strip.lower().startswith(prefix):
            contributor = q_strip[len(prefix) :].strip()
            without_initials = re.sub(r"(?<!\w)(?:[^\W\d_]\.\s*)+", "", contributor).strip()
            q_strip = without_initials or contributor
            break

    # Encode the whole search value so ampersands and punctuation stay inside the query.
    return f"{base_url}/page/{page}/?s={quote(q_strip, safe='')}"


def search_audiobookbay(query: str, max_pages: int = 1, start_page: int = 1) -> Sequence[BookSummary]:
    """Search AudiobookBay for the given query across multiple pages.

    Args:
        query: Search term (e.g. "Harry Potter")
        max_pages: Maximum number of pages to scrape (default: 1 for fast progressive render)
        start_page: The starting page number (default: 1)

    Returns:
        A list of dictionaries containing book summaries.
    """
    logger.info("Search: Starting search for '%s' (Pages %d-%d)", query, start_page, start_page + max_pages - 1)

    # Check Cache
    cache_key = f"{query}::pages_{start_page}_{max_pages}"
    with network.CACHE_LOCK:
        if cache_key in network.search_cache:
            logger.debug("Search: Cache hit for '%s'", cache_key)
            return cast(Sequence[BookSummary], network.search_cache[cache_key])

    # 1. Find a working mirror
    base_url = network.find_best_mirror()
    if not base_url:
        logger.error("Search: No working mirror found. Aborting.")
        raise ConnectionError("No working AudiobookBay mirrors found. Check network connectivity or try again shortly.")

    results: list[BookSummary] = []
    seen_links: set[str] = set()

    futures = []
    # UI requests one page; explicit multi-page callers retain bounded executor dispatch.
    for page in range(start_page, start_page + max_pages):
        url = get_search_url(base_url, query, page)
        future = executor.submit(fetch_page_results, url)
        futures.append(future)

    # Collect results as they complete
    encountered_error: Exception | None = None

    for future in futures:
        try:
            page_results = future.result()
            if not page_results:
                continue

            for item in page_results:
                link = item.get("link")
                if link and link not in seen_links:
                    seen_links.add(link)
                    results.append(item)

        except network.requests.HTTPError as e:
            encountered_error = e
            logger.error(f"Search: HTTP Error (5xx/4xx) from mirror: {e}. Invalidating mirror.")
            with network.CACHE_LOCK:
                if "active_mirror" in network.mirror_cache:
                    del network.mirror_cache["active_mirror"]
        except Exception as e:
            encountered_error = e
            logger.exception("Search: Error processing page result.")

    # A failed page is not an empty catalog page; propagate it so the UI can offer retry.
    if not results and encountered_error is not None:
        raise ConnectionError(
            f"AudiobookBay mirror is currently unreachable or blocking requests ({encountered_error}). "
            "Please check your proxy or try another mirror."
        ) from encountered_error

    logger.info("Search: Completed. Found %d unique results.", len(results))

    # Never cache a partial multi-page response after an upstream failure.
    if encountered_error is None:
        with network.CACHE_LOCK:
            network.search_cache[cache_key] = results

    return results


def fetch_page_results(url: str) -> list[BookSummary]:
    """Fetch and parse a single search results page.

    Args:
        url: The full URL to fetch.

    Returns:
        A list of book summary dictionaries.
    """
    try:
        session = network.get_thread_session()
        timeout = current_app.config["SCRAPER_TIMEOUT"] if has_app_context() else SCRAPER_REQUEST_TIMEOUT_SECONDS
        response, latency = network.request_external(session, url, timeout=timeout)
        response.raise_for_status()
        soup = parser.parse_html(response.text)
        parsed_results = parser.parse_search_results(soup, url)
        if not parsed_results and soup.select_one("#content") is None:
            raise network.requests.ConnectionError("Catalog search returned an unexpected page instead of results.")
        network.record_request_outcome(url, True, latency)
        return parsed_results
    except network.requests.HTTPError as error:
        if error.response is not None and error.response.status_code == 404:  # noqa: PLR2004
            logger.info("Search: Catalog page not found; no results on this page.")
            return []
        network.record_request_outcome(url, False, error=str(error))
        raise
    except network.requests.RequestException as error:
        network.record_request_outcome(url, False, error=type(error).__name__)
        raise
    except Exception as error:
        network.record_request_outcome(url, False, error=type(error).__name__)
        logger.warning("Search: Could not fetch or parse catalog results for %s", url, exc_info=True)
        raise ConnectionError("Could not read catalog results. Try again shortly.") from error


def get_book_details(url: str, refresh: bool = False) -> dict[str, Any] | None:
    """Fetch detailed information for a specific book.

    Args:
        url: The URL of the book page.
        refresh: If True, bypass the cache and re-fetch.

    Returns:
        A dictionary containing book details, or None if fetching fails.
    """
    # 1. Normalize relative URLs from search results (e.g., /abss/book-title/)
    if url.startswith("/"):
        active_mirror = network.find_best_mirror() or network.get_mirrors()[0]
        if not active_mirror.startswith("http://") and not active_mirror.startswith("https://"):
            host_clean = active_mirror.split("/")[0]
            stat = network.get_mirror_stat(host_clean)
            scheme = getattr(stat, "protocol", "https")
            active_mirror = f"{scheme}://{active_mirror}"
        url = urljoin(active_mirror, url)

    # 2. Check Cache
    if not refresh:
        with network.CACHE_LOCK:
            if url in network.details_cache:
                logger.debug("Details: Cache hit for %s", url)
                return cast(dict[str, Any], network.details_cache[url])

    logger.info("Details: Fetching %s", url)

    # SSRF Protection: Ensure URL belongs to allowed domains
    domain = urlparse(url).netloc
    allowed_mirrors = network.get_mirrors()
    if domain not in allowed_mirrors:
        logger.warning("Details: Blocked SSRF attempt to %s", url)
        # Raising ValueError as expected by security tests
        raise ValueError(f"Invalid domain: {domain}")

    try:
        # 2. Fetch Page
        # Ensure we have a valid session with headers (User-Agent)
        session = network.get_thread_session()
        timeout = current_app.config["SCRAPER_TIMEOUT"] if has_app_context() else SCRAPER_REQUEST_TIMEOUT_SECONDS
        response, latency = network.request_external(session, url, timeout=timeout)
        response.raise_for_status()
        network.record_request_outcome(url, True, latency)

        # 3. Parse Content
        soup = parser.parse_html(response.text)
        book_details = parser.parse_book_details(soup, url)

        # 4. Update Cache
        if book_details:
            with network.CACHE_LOCK:
                network.details_cache[url] = book_details
            return cast(dict[str, Any], book_details)

    except (network.requests.ConnectionError, network.requests.Timeout, network.requests.HTTPError) as e:
        network.record_request_outcome(url, False, error=str(e))
        logger.error("Details: Failed to fetch details for %s: %s", url, e)
    except Exception as e:
        logger.error("Details: Failed to fetch details for %s: %s", url, e)

    return None


def extract_magnet_link(url: str) -> tuple[str | None, str | None]:
    """Extract and construct the magnet link from the book details page.

    Args:
        url: The URL of the book details page.

    Returns:
        tuple: (magnet_link, error_message). Both are None on success, or (None, error) on failure.
    """
    try:
        details = get_book_details(url)
        if not details:  # pragma: no cover
            return None, "Failed to retrieve book details"

        info_hash = details.get("info_hash")
        if not info_hash or info_hash == "Unknown":
            return None, ERROR_HASH_NOT_FOUND

        # Construct Magnet Link
        # urn:btih:<hash>&dn=<title>&tr=<tracker>
        magnet = f"magnet:?xt=urn:btih:{info_hash}"

        title = details.get("title")
        if title and title != "Unknown Title":
            magnet += f"&dn={quote(str(title))}"

        trackers = details.get("trackers", [])
        if isinstance(trackers, list):
            for tracker in dict.fromkeys(trackers + network.get_trackers()):
                magnet += f"&tr={quote(str(tracker), safe='')}"

        return magnet, None

    except Exception as e:
        logger.error(f"Magnet: Error generating link for {url}: {e}")
        return None, f"Error generating magnet link: {e}"
