# File: audiobook_automated/scraper/core.py
"""Core scraper logic for retrieving search results and details."""

import logging
import random
import re
import time
from collections.abc import Sequence
from typing import Any, cast
from urllib.parse import quote, urljoin, urlparse

from ..constants import ERROR_HASH_NOT_FOUND
from ..extensions import executor
from . import network, parser
from .parser import BookSummary

logger = logging.getLogger(__name__)

# Used to synchronize access to the details cache across threads
CACHE_LOCK: Any = network.threading.Lock()  # pragma: no cover


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
          'author:<author>'     -> /audio-books/author/<author>/page/<N>/
          'narrator:<narrator>' -> /audio-books/narrator/<narrator>/page/<N>/
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
        "author:": "author",
        "narrator:": "narrator",
    }
    for prefix, tax_type in taxonomy_prefixes.items():
        if q_strip.lower().startswith(prefix):
            raw_val = q_strip[len(prefix) :].strip()
            slug = slugify_taxonomy(raw_val)
            path = f"/audio-books/{tax_type}/{slug}"
            if page > 1:
                return f"{base_url}{path}/page/{page}/"
            return f"{base_url}{path}/"

    # Case 3: Standard WordPress keyword search parameter
    return f"{base_url}/page/{page}/?s={q_strip}"


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

    # 1. Find a working mirror
    base_url = network.find_best_mirror()
    if not base_url:
        logger.error("Search: No working mirror found. Aborting.")
        raise ConnectionError("No working AudiobookBay mirrors found. Check network connectivity or try again shortly.")

    # Check Cache
    cache_key = f"{query}::pages_{start_page}_{max_pages}"
    with network.CACHE_LOCK:
        if cache_key in network.search_cache:
            logger.debug("Search: Cache hit for '%s'", cache_key)
            return cast(Sequence[BookSummary], network.search_cache[cache_key])

    results: list[BookSummary] = []
    seen_links: set[str] = set()

    # Create a queue to hold futures (async tasks)
    futures = []

    # Use Executor from extensions (passed via current_app if needed, or import)
    # However, since this function runs in a request context or background task,
    # we need to be careful. The current implementation uses the global executor.

    # Submit tasks for each page
    # We use a loop to submit tasks, but we need to handle the fact that
    # the site might have fewer pages than max_pages.
    # To optimize, we could fetch page 1 first, check total pages, then fetch the rest.
    # For now, we will submit all and handle empty results gracefully.

    # Loop through requested pages
    for page in range(start_page, start_page + max_pages):
        url = get_search_url(base_url, query, page)
        future = executor.submit(fetch_page_results, url)
        futures.append(future)

    # Collect results as they complete
    # Note: We don't guarantee order here, but search results are usually sorted by the site.
    # If order matters strictly, we should map futures to page numbers.
    encountered_http_error: network.requests.HTTPError | None = None

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
            encountered_http_error = e
            logger.error(f"Search: HTTP Error (5xx/4xx) from mirror: {e}. Invalidating mirror.")
            with network.CACHE_LOCK:
                if "active_mirror" in network.mirror_cache:
                    del network.mirror_cache["active_mirror"]
        except Exception:
            logger.exception("Search: Error processing page result.")

    # If all pages failed due to mirror HTTP 4xx/5xx errors, raise rather than swallowing into empty results
    if not results and encountered_http_error is not None:
        raise ConnectionError(
            f"AudiobookBay mirror is currently unreachable or blocking requests ({encountered_http_error}). "
            "Please check your proxy or try another mirror."
        ) from encountered_http_error

    logger.info("Search: Completed. Found %d unique results.", len(results))

    # Update Cache only for successful queries
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
    # Compliance: Rate limiting and concurrency control (Rule 0)
    with network.get_semaphore():
        # Jitter for scraping, not crypto
        time.sleep(random.uniform(0.5, 1.5))  # noqa: S311
        try:
            session = network.get_session()
            started = time.perf_counter()
            response = session.get(url, timeout=10)
            response.raise_for_status()
            network.record_request_outcome(url, True, round((time.perf_counter() - started) * 1000, 2))

            soup = parser.parse_html(response.text)
            parsed_results = parser.parse_search_results(soup, url)
            return parsed_results

        except (network.requests.ConnectionError, network.requests.Timeout):
            # Do not expose raw URL in logs if it contains sensitive info (unlikely here)
            logger.warning("Search: Connection error fetching page: %s", url)
            network.record_request_outcome(url, False, error="Connection error or timeout")
            return []
        except network.requests.HTTPError as e:
            network.record_request_outcome(url, False, error=str(e))
            # Re-raise HTTP errors (4xx/5xx) to allow search_audiobookbay to handle invalidation
            raise
        except Exception:
            # Catch-all for parsing errors
            logger.exception("Search: Unexpected error fetching page: %s", url)
            return []


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
        with CACHE_LOCK:
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
        session = network.get_session()
        started = time.perf_counter()
        response = session.get(url, timeout=15)
        response.raise_for_status()
        network.record_request_outcome(url, True, round((time.perf_counter() - started) * 1000, 2))

        # 3. Parse Content
        soup = parser.parse_html(response.text)
        book_details = parser.parse_book_details(soup, url)

        # 4. Update Cache
        if book_details:
            with CACHE_LOCK:
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
        # Add trackers from details
        if isinstance(trackers, list):
            for tr in trackers:
                magnet += f"&tr={tr}"

            # Add default trackers if not present
            default_trackers = network.get_trackers()
            for tr in default_trackers:
                if tr not in trackers:
                    magnet += f"&tr={tr}"

        return magnet, None

    except Exception as e:
        logger.error(f"Magnet: Error generating link for {url}: {e}")
        return None, f"Error generating magnet link: {e}"
