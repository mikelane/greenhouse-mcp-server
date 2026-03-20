"""Greenhouse API exception hierarchy.

Each exception maps to a specific HTTP status code from the Harvest API,
carrying relevant context for callers to handle errors distinctly.
"""


class GreenhouseError(Exception):
    """Base exception for all Greenhouse API errors."""

    def __init__(self, message: str, *, status_code: int = 0) -> None:
        """Initialize with a message and optional status code.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code from the API response.
        """
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(GreenhouseError):
    """Raised on HTTP 401 -- missing or invalid API token."""

    def __init__(self, message: str, *, status_code: int = 401) -> None:
        """Initialize with a message and status code defaulting to 401.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code, defaults to 401.
        """
        super().__init__(message, status_code=status_code)


class GreenhousePermissionError(GreenhouseError):
    """Raised on HTTP 403 -- valid token but insufficient permissions."""

    def __init__(self, message: str, *, status_code: int = 403) -> None:
        """Initialize with a message and status code defaulting to 403.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code, defaults to 403.
        """
        super().__init__(message, status_code=status_code)


class NotFoundError(GreenhouseError):
    """Raised on HTTP 404 -- requested resource does not exist."""

    def __init__(self, message: str, *, status_code: int = 404) -> None:
        """Initialize with a message and status code defaulting to 404.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code, defaults to 404.
        """
        super().__init__(message, status_code=status_code)


class ValidationError(GreenhouseError):
    """Raised on HTTP 422 -- request validation failed.

    Carries the structured errors array from the Greenhouse API response.
    """

    def __init__(
        self,
        message: str,
        *,
        errors: list[dict[str, str]],
        status_code: int = 422,
    ) -> None:
        """Initialize with a message, errors array, and status code defaulting to 422.

        Args:
            message: Human-readable error description.
            errors: Array of field-level validation errors from the API.
            status_code: HTTP status code, defaults to 422.
        """
        super().__init__(message, status_code=status_code)
        self.errors = errors


class RateLimitError(GreenhouseError):
    """Raised on HTTP 429 -- rate limit exceeded.

    Carries the retry_after value indicating when it is safe to retry.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float,
        status_code: int = 429,
    ) -> None:
        """Initialize with a message, retry_after delay, and status code defaulting to 429.

        Args:
            message: Human-readable error description.
            retry_after: Seconds to wait before retrying.
            status_code: HTTP status code, defaults to 429.
        """
        super().__init__(message, status_code=status_code)
        self.retry_after = retry_after


class ServerError(GreenhouseError):
    """Raised on HTTP 5xx -- server-side error, safe to retry with backoff."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        """Initialize with a message and status code defaulting to 500.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code, defaults to 500.
        """
        super().__init__(message, status_code=status_code)
