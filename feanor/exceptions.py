"""SDK exception types."""
from __future__ import annotations


class FeanorAPIError(Exception):
    """Raised when the Fëanor API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class FeanorQueryError(Exception):
    """Raised when a Trino query fails or exceeds limits."""

    def __init__(self, message: str, error_name: str | None = None) -> None:
        full = f"{error_name}: {message}" if error_name else message
        super().__init__(full)
        self.error_name = error_name
        self.message = message
