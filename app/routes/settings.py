from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from config import APP_SETTINGS_KEY, AppSettings
from errors import AppError, ValidationError
from repositories.settings import SettingsRepository
from services.settings_service import SettingsService

settings_bp = Blueprint("settings", __name__, url_prefix="/api")


def _build_service() -> tuple[SettingsService, AppSettings]:
    base_settings = current_app.config[APP_SETTINGS_KEY]
    repository = SettingsRepository(base_settings.database_path)
    return SettingsService(repository), base_settings


@settings_bp.errorhandler(AppError)
def handle_settings_error(error: AppError):
    return jsonify({"message": error.public_message}), error.status_code


@settings_bp.route("/settings", methods=["GET"])
def get_settings_route():
    service, base_settings = _build_service()
    return jsonify({"settings": service.get_settings(base_settings)})


@settings_bp.route("/settings", methods=["POST"])
def update_settings_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("Invalid request")

    service, base_settings = _build_service()
    return jsonify({"settings": service.update_settings(base_settings, payload)})
