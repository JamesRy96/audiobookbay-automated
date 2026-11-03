# File: audiobook_automated/routes.py
"""Routes module handling all web endpoints."""

import logging
import os
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import requests
from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from audiobook_automated.constants import (
    ABS_TIMEOUT_SECONDS,
    ERROR_HASH_NOT_FOUND,
    MIN_SEARCH_QUERY_LENGTH,
)
from audiobook_automated.errors import AppError, InvalidRequestError, TorrentClientError

from .contributors import catalog_credit, split_contributors
from .extensions import limiter, talisman, torrent_manager
from .scraper import extract_magnet_link, get_book_details, search_audiobookbay
from .scraper.parser import BookSummary
from .utils import (
    build_github_issue_url,
    construct_safe_save_path,
    format_user_error,
    parse_bool,
    sanitize_title,
)

logger = logging.getLogger(__name__)

# Create the Blueprint
main_bp = Blueprint("main", __name__)
main_bp.add_app_template_filter(catalog_credit)
main_bp.add_app_template_filter(split_contributors)


@main_bp.errorhandler(AppError)
def handle_app_error(error: AppError) -> tuple[Response, int]:
    """Handle custom application errors and return JSON response."""
    logger.error(f"AppError: {error.message}")
    return jsonify({"message": error.message}), error.status_code


@main_bp.context_processor
def inject_global_vars() -> dict[str, Any]:
    """Inject global variables into all templates.

    Uses current_app.config to access settings loaded in config.py.

    Returns:
        dict[str, Any]: A dictionary of context variables available to templates.
    """
    # Retrieve version hash from app config (calculated at startup)
    static_version = current_app.config.get("STATIC_VERSION", "v1")

    # Retrieve pre-calculated flag from config instead of re-evaluating
    # Now uses the property defined in Config class
    library_reload_enabled = current_app.config.get("LIBRARY_RELOAD_ENABLED", False)

    return {
        "nav_link_name": current_app.config.get("NAV_LINK_NAME"),
        "nav_link_url": current_app.config.get("NAV_LINK_URL"),
        "library_reload_enabled": library_reload_enabled,
        "static_version": static_version,
        "default_cover_filename": "cover-placeholder.svg",
        "splash_enabled": current_app.config.get("SPLASH_ENABLED", True),
        "splash_title": current_app.config.get("SPLASH_TITLE", ""),
        "splash_message": current_app.config.get("SPLASH_MESSAGE", ""),
        "splash_duration": current_app.config.get("SPLASH_DURATION", 4500),
    }


@main_bp.route("/<path:filename>")
def serve_root_asset(filename: str) -> Response | tuple[Response, int]:
    """Serve static asset fallbacks requested at the root path (e.g. /custom-logo.jpg).

    Handles reverse proxies, Docker configurations, or custom logo configurations
    where an asset is requested without the '/static/images/' prefix.
    Only allows supported media extensions (.jpg, .jpeg, .png, .gif, .webp, .ico, .mp4, .webm).

    Args:
        filename: Requested relative asset filename.

    Returns:
        Response: Static file or 404 response.
    """
    safe_name = Path(filename).name
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".ico", ".mp4", ".webm"}
    ext = os.path.splitext(safe_name)[1].lower()

    if ext in allowed_extensions:
        images_dir = Path(current_app.static_folder or "static") / "images"
        target_file = images_dir / safe_name
        if target_file.is_file():
            return send_from_directory(str(images_dir), safe_name)

    return jsonify({"error": "Not Found"}), 404


@main_bp.route("/health")
@talisman(force_https=False)  # type: ignore[untyped-decorator, unused-ignore]
def health() -> Response | tuple[Response, int]:
    """Check HTTP availability without contacting Download Clients or the catalog."""
    return jsonify({"status": "ok", "app": "healthy"}), 200


@main_bp.route("/api/clients")
def api_clients() -> Response | tuple[Response, int]:
    """Return available configured clients and their connectivity status.

    Returns:
        Response: JSON with client list and primary client name.
    """
    client_names = torrent_manager.list_clients()
    selected = request.args.get("client", "").lower()
    if selected:
        if selected not in client_names:
            return jsonify(message="The selected Download Client is not configured."), 400
        client_names = [selected]
    clients_data = []
    for name in client_names:
        is_connected = torrent_manager.verify_credentials(name)
        clients_data.append({"name": name, "connected": is_connected})

    primary = torrent_manager.client_type.lower().replace("client", "")
    return jsonify({"clients": clients_data, "primary": primary})


@main_bp.route("/", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def search() -> str | Response:
    """Handle the search interface.

    Processes search queries and renders the search results page.
    Enforces a minimum query length of 2 characters.

    Query Params:
        query (str): The search term passed via GET or POST.

    Returns:
        str | Response: Rendered HTML template or Response object.
    """
    books: Sequence[BookSummary] = []
    query = ""
    error_message = None

    try:
        query = request.args.get("query") or request.form.get("query") or ""
        query = query.strip()

        if query:
            # Minimum length check to prevent scraping spam
            if len(query) < MIN_SEARCH_QUERY_LENGTH:
                error_message = f"Enter at least {MIN_SEARCH_QUERY_LENGTH} characters."
                return render_template("search.html", books=[], error=error_message, query=query)

            # AudiobookBay requires lowercase search terms
            search_query = query.lower()
            logger.info(f"Received search query: '{query}' (normalized to '{search_query}')")
            books = search_audiobookbay(search_query)

        # Optimization: Pre-calculate filter lists to avoid slow client-side DOM scraping
        categories: set[str] = set()
        languages: set[str] = set()
        formats: set[str] = set()
        bitrates: set[str] = set()

        for book in books:
            for cat in book["category"]:
                clean_cat = cat.strip()
                if len(clean_cat) > 1 and clean_cat not in ("Unknown", "None") and any(c.isalnum() for c in clean_cat):
                    categories.add(clean_cat)

            if book["language"] and book["language"] not in ("Unknown", "None"):
                languages.add(book["language"])

            if book["format"] and book["format"] not in ("Unknown", "None"):
                formats.add(book["format"])

            if book["bitrate"] and book["bitrate"] not in ("Unknown", "None"):
                bitrates.add(book["bitrate"])

        return render_template(
            "search.html",
            books=books,
            query=query,
            categories=sorted(categories),
            languages=sorted(languages),
            formats=sorted(formats),
            bitrates=sorted(bitrates),
        )

    except ConnectionError as ce:
        # Specific handling for when mirrors are unreachable
        logger.error(f"Search failed due to connection error: {ce}")
        is_debug = bool(
            current_app.config.get("FLASK_DEBUG", False)
            or current_app.config.get("DEBUG", False)
            or current_app.config.get("TESTING", False)
        )
        friendly_message, _ = format_user_error(ce, context="search")
        debug_details: str | None = f"Could not connect to AudiobookBay mirrors: {ce}"
        error_message = debug_details if is_debug else friendly_message
        github_issue_url = build_github_issue_url(friendly_message, debug_details, context="search")
        return render_template(
            "search.html",
            books=books,
            error=error_message,
            debug_details=debug_details,
            github_issue_url=github_issue_url,
            query=query,
        )

    except Exception as e:
        logger.error(f"Failed to search: {e}", exc_info=True)
        is_debug = bool(
            current_app.config.get("FLASK_DEBUG", False)
            or current_app.config.get("DEBUG", False)
            or current_app.config.get("TESTING", False)
        )
        friendly_message, debug_details = format_user_error(e, context="search")
        error_message = f"Search Failed: {str(e)}" if is_debug else friendly_message
        github_issue_url = build_github_issue_url(friendly_message, debug_details or str(e), context="search")
        return render_template(
            "search.html",
            books=books,
            error=error_message,
            debug_details=debug_details,
            github_issue_url=github_issue_url,
            query=query,
        )


@main_bp.route("/api/search")
@limiter.limit("60 per minute")
def api_search() -> Response | tuple[Response, int]:
    """Asynchronous search endpoint for background page streaming and prefetching.

    Query Params:
        query (str): The search term.
        page (int): Page number to fetch (defaults to 1).

    Returns:
        Response: JSON payload containing book summaries and pagination metadata.
    """
    query = (request.args.get("query") or "").strip()
    if not query or len(query) < MIN_SEARCH_QUERY_LENGTH:
        return jsonify({"books": [], "has_more": False, "page": 1}), 200

    try:
        page = int(request.args.get("page", 1))
        page = max(page, 1)
    except ValueError:
        page = 1

    try:
        search_query = query.lower()
        books = search_audiobookbay(search_query, max_pages=1, start_page=page)
        return jsonify(
            {
                "books": [{**book, **catalog_credit(book["title"])} for book in books],
                "has_more": len(books) > 0,
                "page": page,
            }
        ), 200
    except Exception as e:
        logger.error(f"API search failed for '{query}' (page {page}): {e}")
        return jsonify({"error": str(e), "books": [], "has_more": False, "page": page}), 500


@main_bp.route("/details")
@limiter.limit("30 per minute")
def details() -> str | Response:
    """Fetch and render the details page internally via the server.

    Acts as a proxy to fetch book details from AudiobookBay without exposing the
    client's IP address to the external site.

    Query Params:
        link (str): The URL of the book details page.

    Returns:
        str | Response: Rendered HTML template or Redirect.
    """
    link = request.args.get("link")
    if not link:
        return cast(Response, redirect(url_for("main.search")))

    try:
        book_details = get_book_details(link)
        if not book_details:
            raise ConnectionError("Audiobook details could not be retrieved. Please try again.")
        return render_template("details.html", book=book_details)
    except Exception as e:
        logger.error(f"Failed to fetch details: {e}", exc_info=True)
        error_message, debug_details = format_user_error(e, context="details")
        github_issue_url = build_github_issue_url(error_message, debug_details or str(e), context="details")
        return render_template(
            "details.html",
            error=error_message,
            debug_details=debug_details,
            github_issue_url=github_issue_url,
        )


def _validate_send_payload(data: dict[str, Any]) -> tuple[str, str, str | None]:
    """Validate incoming JSON payload for /send endpoint."""
    if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        logger.warning("Invalid send request: JSON body is not a dictionary.")
        raise InvalidRequestError("Invalid JSON format")

    details_url = data.get("link") if data else None
    title = data.get("title") if data else None
    client_name = data.get("client") if data else None

    # Ensure link and title are strings before proceeding.
    if details_url is not None and not isinstance(details_url, str):
        logger.warning(f"Invalid send request: Link is not a string (Type: {type(details_url)}).")
        raise InvalidRequestError("Invalid request: Link must be a string")

    # Search cards carry catalog-relative paths; Details resolves them through the mirror allowlist.
    # Reject network-path URLs and backslashes rather than treating external hosts as catalog paths.
    relative_path = bool(
        details_url and details_url.startswith("/") and not details_url.startswith("//") and "\\" not in details_url
    )
    if details_url and not (relative_path or details_url.startswith(("http://", "https://"))):
        logger.warning("Invalid send request: Unsupported catalog link.")
        raise InvalidRequestError("Invalid book link. Search again and retry the download.")

    # Ensure title is a string before calling string methods.
    if title is not None and not isinstance(title, str):
        logger.warning(f"Invalid send request: Title is not a string (Type: {type(title)}).")
        raise InvalidRequestError("Invalid request: Title must be a string")

    # Ensure client is a string if supplied
    if client_name is not None and not isinstance(client_name, str):
        logger.warning(f"Invalid send request: Client is not a string (Type: {type(client_name)}).")
        raise InvalidRequestError("Invalid request: Client must be a string")

    # Check raw title existence. We must allow titles that sanitize to FALLBACK_TITLE (e.g. "...")
    # to proceed to the collision handler, rather than blocking them as "Invalid".
    if not details_url or not title:
        logger.warning("Invalid send request received: missing link or valid title")
        raise InvalidRequestError("Invalid request: Title or Link missing")

    return details_url, title, client_name


@main_bp.route("/send", methods=["POST"])
@limiter.limit("60 per minute")
def send() -> Response | tuple[Response, int]:
    """Initiate a download.

    Generates a magnet link and sends it to the configured torrent client.

    JSON Body:
        link (str): The details URL of the book.
        title (str): The title of the book.

    Returns:
        Response: JSON indicating success or failure.
    """
    data = cast(dict[str, Any], request.json)
    details_url, title, client_name = _validate_send_payload(data)

    # Logging raw title before processing
    logger.info(f"Received download request for '{sanitize_title(title)}'")

    try:
        # Security: Use scraped title to prevent path spoofing
        # We fetch details explicitly to get the title. extract_magnet_link will hit cache.
        try:
            details = get_book_details(details_url)
            if details:  # Ensure details is not None
                # Fallback to user provided title ONLY if scraped title is missing or "Unknown Title"
                scraped_title = details.get("title")
                if scraped_title and scraped_title != "Unknown Title":
                    title = str(scraped_title)
        except Exception as e:
            # If fetching details fails, we proceed. extract_magnet_link will likely fail too
            # and return an error which handles the flow gracefully.
            logger.warning(f"Could not fetch details for title verification: {e}")

        magnet_link, error = extract_magnet_link(details_url)

        if not magnet_link:
            logger.error(f"Failed to extract magnet link for '{title}': {error}")
            # Map specific errors to 404/400 to avoid alerting on 500s
            status_code = 404 if error == ERROR_HASH_NOT_FOUND else 400
            raise TorrentClientError(f"Download failed: {error}", status_code=status_code)

        # Construct and validate final destination path
        selected_client = client_name or current_app.config["DL_CLIENT"].split(",")[0].strip()
        settings = current_app.config.get("CLIENT_CONNECTIONS", {}).get(selected_client.lower(), {})
        save_path_base = settings.get("SAVE_PATH_BASE") or current_app.config.get("SAVE_PATH_BASE")
        save_path = construct_safe_save_path(save_path_base, title) if save_path_base else None
        if client_name:
            torrent_manager.add_magnet(magnet_link, save_path, client_name=client_name)
        else:
            torrent_manager.add_magnet(magnet_link, save_path)

        target_client = client_name or torrent_manager.client_type
        logger.info(f"Successfully sent '{title}' to {target_client}")
        return (
            jsonify({"message": "Sent to your Download Client. Check Downloads for progress."}),
            200,
        )
    except AppError:
        # Re-raise known app errors to be handled by the error handler
        raise
    except Exception as e:
        logger.error(f"Send failed: {e}", exc_info=True)
        raise TorrentClientError(str(e)) from e


@main_bp.route("/delete", methods=["POST"])
def delete_torrent() -> Response | tuple[Response, int]:
    """Remove a torrent.

    Requires a JSON payload with the torrent ID.

    JSON Payload:
        id (str): The ID or Hash of the torrent to remove.

    Returns:
        Response: JSON Response indicating success or failure.
    """
    data = cast(dict[str, Any], request.json)

    if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise InvalidRequestError("Invalid JSON format")

    torrent_id = data.get("id") if data else None
    client_name = data.get("client")
    if client_name is not None and (not isinstance(client_name, str) or not client_name.strip()):
        raise InvalidRequestError("A valid Download Client is required")

    if not torrent_id:
        raise InvalidRequestError("Torrent ID is required")

    try:
        # Security: only delete torrents managed by this application (matched by our category label)
        torrents = torrent_manager.get_status()
        matches = [
            torrent
            for torrent in torrents
            if str(torrent.id) == str(torrent_id) and (not client_name or torrent.client == client_name)
        ]
        if len(matches) > 1:
            return jsonify({"status": "error", "message": "Choose the Download Client for this download."}), 409
        target_torrent = matches[0] if matches else None

        if not target_torrent:
            return jsonify({"status": "error", "message": "Torrent not found"}), 404

        app_category = current_app.config.get("DL_CATEGORY", "abb-automated")
        # Robustness: Some clients (like Deluge) might not return category if label plugin missing
        # We check specific category match OR if the client doesn't support categories at all (fallback)
        if target_torrent.category and target_torrent.category != app_category:
            return jsonify(
                {
                    "status": "error",
                    "message": f"Security: Torrent category '{target_torrent.category}' does not match current app category '{app_category}'.",
                }
            ), 403

        if target_torrent.client:
            removed = torrent_manager.remove_torrent(str(torrent_id), client_name=target_torrent.client)
        else:
            removed = torrent_manager.remove_torrent(str(torrent_id))
        if not removed:
            return jsonify({"status": "error", "message": "The Download Client could not remove this download."}), 502
        return jsonify({"message": "Torrent removed successfully."})
    except Exception as e:
        logger.error(f"Failed to remove torrent: {e}", exc_info=True)
        raise TorrentClientError(f"Failed to remove torrent: {str(e)}") from e


@main_bp.route("/reload_library", methods=["POST"])
def reload_library() -> Response | tuple[Response, int]:
    """Trigger an Audiobookshelf library scan.

    Returns:
        Response: JSON indicating success or failure of the trigger request.
    """
    abs_url = current_app.config.get("ABS_URL")
    abs_key = current_app.config.get("ABS_KEY")
    abs_lib = current_app.config.get("ABS_LIB")

    if not all([abs_url, abs_key, abs_lib]):
        return jsonify({"message": "Audiobookshelf integration not configured."}), 400

    try:
        url = f"{abs_url}/api/libraries/{abs_lib}/scan"
        headers = {"Authorization": f"Bearer {abs_key}"}
        # Explicit timeout used to prevent hanging
        response = requests.post(url, headers=headers, timeout=ABS_TIMEOUT_SECONDS)
        response.raise_for_status()
        logger.info("Audiobookshelf library scan initiated successfully.")
        return jsonify({"message": "Audiobookshelf library scan initiated."})
    except requests.exceptions.HTTPError as e:
        # Pass upstream errors (4xx/5xx) directly to the user
        status_code = e.response.status_code if e.response is not None else 500
        error_message = f"{status_code} {e.response.reason}: {e.response.text}" if e.response is not None else str(e)
        logger.error(f"ABS Scan Failed (Upstream Error): {error_message}", exc_info=True)
        return jsonify({"message": f"Library scan failed: {error_message}"}), status_code
    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if e.response is not None:
            error_message = f"{e.response.status_code} {e.response.reason}: {e.response.text}"
        logger.error(f"ABS Scan Failed: {error_message}", exc_info=True)
        return jsonify({"message": f"Failed to trigger library scan: {error_message}"}), 500


@main_bp.route("/status")
def status() -> str | Response | tuple[Response, int]:
    """Render the current status of downloads.

    Supports returning JSON for frontend polling via ?json=1.
    Supports filtering by client via ?client=<name>.

    Query Params:
        json (str): If set to "1", "true", "yes", or "on", returns JSON instead of HTML.
        client (str): Optional client name to filter by.

    Returns:
        str | Response: Rendered HTML, JSON data, or Error Response.
    """
    # Robust boolean parsing
    is_json = parse_bool(request.args.get("json", ""))
    client_filter = request.args.get("client")

    try:
        torrent_list = torrent_manager.get_status(client_name=client_filter)

        if is_json:
            # Assumes torrent_manager.get_status returns Dataclasses as per architectural requirements.
            return jsonify([asdict(t) for t in torrent_list])

        logger.debug(f"Retrieved status for {len(torrent_list)} torrents.")
        return render_template(
            "status.html",
            torrents=torrent_list,
            clients=torrent_manager.list_clients(),
            active_client=client_filter,
            client_status="connected",
            client_status_label="Client Connected",
        )
    except Exception as e:
        logger.error(f"Failed to fetch torrent status: {e}", exc_info=True)

        if is_json:
            err_type = "disconnected"
            err_str = str(e).lower()
            if "banned" in err_str:
                err_type = "banned"
            elif "cooldown" in err_str or "auth" in err_str or "password" in err_str or "key" in err_str:
                err_type = "auth_failed"
            return jsonify({"error": str(e), "client_status": err_type}), 500

        error_message, debug_details = format_user_error(e, context="client")
        status_slug = "disconnected"
        status_label = "Client Disconnected"
        err_lower = (str(e) + " " + (debug_details or "")).lower()
        if "banned" in err_lower:
            status_slug = "banned"
            status_label = "IP Banned"
        elif "cooldown" in err_lower or "auth" in err_lower or "password" in err_lower or "key" in err_lower:
            status_slug = "warning"
            status_label = "Auth Failed"

        return render_template(
            "status.html",
            torrents=[],
            clients=torrent_manager.list_clients(),
            active_client=client_filter,
            error=error_message,
            debug_details=debug_details,
            client_status=status_slug,
            client_status_label=status_label,
        )
