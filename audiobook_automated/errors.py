# File: audiobook_automated/errors.py
"""Custom exceptions for the application."""


class AppError(Exception):
    """Base class for application-specific exceptions."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        """Initialize the exception.

        Args:
            message: The error message.
            status_code: The HTTP status code to return.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TorrentClientError(AppError):
    """Raised when the torrent client operation fails."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        """Initialize the exception."""
        super().__init__(message, status_code)


class InvalidRequestError(AppError):
    """Raised when the client request is invalid (400)."""

    def __init__(self, message: str) -> None:
        """Initialize the exception with 400 Bad Request."""
        super().__init__(message, status_code=400)


class ScrapingError(AppError):
    """Raised when scraping fails."""

    pass
