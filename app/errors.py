from __future__ import annotations

import logging


class AppError(Exception):
    status_code = 500
    public_message = "Internal server error"
    log_level = logging.ERROR

    def __init__(self, public_message: str | None = None):
        super().__init__(public_message or self.public_message)
        self.public_message = public_message or self.public_message


class ValidationError(AppError):
    status_code = 400
    public_message = "Invalid request"
    log_level = logging.INFO


class ConfigurationError(AppError):
    status_code = 500
    public_message = "Application is not configured correctly"


class ExternalServiceError(AppError):
    status_code = 502
    public_message = "External service request failed"
