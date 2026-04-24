from __future__ import annotations

from flask import Blueprint, jsonify, request

from config import get_settings
from errors import ValidationError
from services.audiobookbay import search_audiobookbay
from services.downloads import add_download, fetch_torrent_status

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"books": []})

    settings = get_settings()
    books = search_audiobookbay(query, settings)
    return jsonify({
        "books": [
            {
                "title": b.title,
                "author": b.author,
                "link": b.link,
                "cover": b.cover,
                "language": b.language,
                "post_date": b.post_date,
                "format": b.format,
                "bitrate": b.bitrate,
                "file_size": b.file_size,
            }
            for b in books
        ]
    })


@api_bp.route("/status")
def status():
    settings = get_settings()
    torrents = fetch_torrent_status(settings)
    return jsonify({
        "torrents": [
            {
                "name": t.name,
                "progress": t.progress,
                "state": t.state,
                "size": t.size,
            }
            for t in torrents
        ]
    })


@api_bp.route("/send", methods=["POST"])
def send():
    data = request.json or {}
    details_url = data.get("link")
    title = data.get("title")
    author = data.get("author")

    if not details_url or not title:
        raise ValidationError("Invalid request")

    book_details = {
        "title": title,
        "link": details_url,
        "author": author,
    }

    message = add_download(book_details, get_settings())
    return jsonify({"message": message})


@api_bp.route("/config")
def config():
    settings = get_settings()
    return jsonify({
        "nav_link_name": settings.nav_link_name,
        "nav_link_url": settings.nav_link_url,
    })
