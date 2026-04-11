from flask import Blueprint, jsonify, request

from config import get_settings
from services.downloads import UnsupportedDownloadClientError, add_download

downloads_bp = Blueprint("downloads", __name__)


@downloads_bp.route("/send", methods=["POST"])
def send():
    data = request.json or {}
    details_url = data.get("link")
    title = data.get("title")

    if not details_url or not title:
        return jsonify({"message": "Invalid request"}), 400

    try:
        message = add_download(details_url, title, get_settings())
        return jsonify({"message": message})
    except UnsupportedDownloadClientError as exc:
        return jsonify({"message": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 500
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500
