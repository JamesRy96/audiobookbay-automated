from __future__ import annotations

from flask import Blueprint, render_template, request

from config import get_settings
from services.audiobookbay import search_audiobookbay
from services.downloads import fetch_torrent_status

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET", "POST"])
def search():
    books = []
    query = ""
    settings = get_settings()

    if request.method == "POST":
        query = request.form["query"]
        if query:
            books = search_audiobookbay(query, settings)
    return render_template("search.html", books=books, query=query)


@pages_bp.route("/status")
def status():
    torrents = fetch_torrent_status(get_settings())
    return render_template("status.html", torrents=torrents)
