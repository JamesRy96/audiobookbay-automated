from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from config import get_settings
from services.audiobookbay import search_audiobookbay
from services.downloads import (
    UnsupportedDownloadClientError,
    fetch_torrent_status,
)

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET", "POST"])
def search():
    books = []
    query = ""
    settings = get_settings()

    try:
        if request.method == "POST":
            query = request.form["query"]
            if query:
                books = search_audiobookbay(query, settings)
        return render_template("search.html", books=books, query=query)
    except Exception as exc:
        print(f"[ERROR] Failed to search: {exc}")
        return render_template(
            "search.html",
            books=books,
            error=f"Failed to search. {str(exc)}",
            query=query,
        )


@pages_bp.route("/status")
def status():
    settings = get_settings()

    try:
        torrents = fetch_torrent_status(settings)
        return render_template("status.html", torrents=torrents)
    except UnsupportedDownloadClientError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"message": f"Failed to fetch torrent status: {exc}"}), 500
