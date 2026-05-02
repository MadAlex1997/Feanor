"""SDK exception types."""
from __future__ import annotations


class FeanorAPIError(Exception):
    """Raised when the Fëanor API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
