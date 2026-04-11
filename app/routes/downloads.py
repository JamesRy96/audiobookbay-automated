from flask import Blueprint, jsonify, request

from config import get_settings
from errors import ValidationError
from services.downloads import add_download

downloads_bp = Blueprint("downloads", __name__)


@downloads_bp.route("/send", methods=["POST"])
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
