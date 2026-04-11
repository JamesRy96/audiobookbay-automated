from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, Mapping
from urllib.parse import urlparse

from config import AppSettings
from errors import ValidationError
from repositories.settings import SettingsRepository

PUBLIC_SETTING_FIELDS = tuple(
    field.name for field in fields(AppSettings) if field.name != "database_path"
)
INTEGER_FIELDS = {"page_limit", "dl_port", "flask_port"}
SECRET_SETTING_FIELDS = {"dl_password"}


class SettingsService:
    def __init__(self, repository: SettingsRepository):
        self.repository = repository

    def get_settings(self, base_settings: AppSettings) -> dict[str, Any]:
        settings = self._effective_settings(base_settings)
        return self._sanitize_settings(settings)

    def update_settings(
        self,
        base_settings: AppSettings,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise ValidationError("Invalid request")

        updated_settings = self._effective_settings(base_settings)
        normalized_payload = self._normalize_payload(payload)
        updated_settings.update(normalized_payload)
        updated_settings = self._normalize_transport_fields(updated_settings)
        self.repository.save_all(updated_settings)
        return self._sanitize_settings(updated_settings)

    def _public_settings(self, base_settings: AppSettings) -> dict[str, Any]:
        data = asdict(base_settings)
        data.pop("database_path", None)
        return {key: data[key] for key in PUBLIC_SETTING_FIELDS}

    def _effective_settings(self, base_settings: AppSettings) -> dict[str, Any]:
        settings = self._public_settings(base_settings)
        settings.update(self.repository.load_all())
        return self._normalize_transport_fields(settings)

    def _normalize_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}

        for key, value in payload.items():
            if key not in PUBLIC_SETTING_FIELDS:
                raise ValidationError(f"Unknown setting: {key}")
            normalized[key] = self._coerce_value(key, value)

        return normalized

    def _coerce_value(self, key: str, value: Any) -> Any:
        if value is None:
            return None

        if key in INTEGER_FIELDS:
            if isinstance(value, bool):
                raise ValidationError(f"Invalid value for {key}")
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip():
                try:
                    return int(value)
                except ValueError as exc:
                    raise ValidationError(f"Invalid value for {key}") from exc
            raise ValidationError(f"Invalid value for {key}")

        if not isinstance(value, str):
            raise ValidationError(f"Invalid value for {key}")

        return value

    def _normalize_transport_fields(self, settings: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(settings)
        dl_url = normalized.get("dl_url")
        dl_scheme = normalized.get("dl_scheme")
        dl_host = normalized.get("dl_host")
        dl_port = normalized.get("dl_port")

        if isinstance(dl_url, str) and dl_url:
            parsed_url = urlparse(dl_url)
            if parsed_url.scheme and parsed_url.hostname:
                normalized["dl_scheme"] = parsed_url.scheme
                normalized["dl_host"] = parsed_url.hostname
                normalized["dl_port"] = parsed_url.port
            return normalized

        if dl_scheme and dl_host and dl_port is not None:
            normalized["dl_url"] = f"{dl_scheme}://{dl_host}:{dl_port}"

        return normalized

    def _sanitize_settings(self, settings: Mapping[str, Any]) -> dict[str, Any]:
        sanitized = {
            key: value
            for key, value in settings.items()
            if key not in SECRET_SETTING_FIELDS
        }
        sanitized["dl_password_configured"] = bool(settings.get("dl_password"))
        return sanitized
