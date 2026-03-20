"""Tests for the Greenhouse exception hierarchy."""

import pytest

from greenhouse_mcp.exceptions import (
    AuthenticationError,
    GreenhouseError,
    GreenhousePermissionError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


@pytest.mark.small
class DescribeGreenhouseError:
    def it_is_a_base_exception_for_all_greenhouse_errors(self) -> None:
        error = GreenhouseError("something went wrong", status_code=500)
        assert str(error) == "something went wrong"
        assert error.status_code == 500  # noqa: PLR2004

    def it_defaults_status_code_to_zero(self) -> None:
        error = GreenhouseError("generic error")
        assert error.status_code == 0


@pytest.mark.small
class DescribeAuthenticationError:
    def it_inherits_from_greenhouse_error(self) -> None:
        error = AuthenticationError("bad token")
        assert isinstance(error, GreenhouseError)

    def it_defaults_to_status_code_401(self) -> None:
        error = AuthenticationError("invalid credentials")
        assert error.status_code == 401  # noqa: PLR2004


@pytest.mark.small
class DescribeGreenhousePermissionError:
    def it_inherits_from_greenhouse_error(self) -> None:
        error = GreenhousePermissionError("no access")
        assert isinstance(error, GreenhouseError)

    def it_defaults_to_status_code_403(self) -> None:
        error = GreenhousePermissionError("forbidden")
        assert error.status_code == 403  # noqa: PLR2004


@pytest.mark.small
class DescribeNotFoundError:
    def it_inherits_from_greenhouse_error(self) -> None:
        error = NotFoundError("not found")
        assert isinstance(error, GreenhouseError)

    def it_defaults_to_status_code_404(self) -> None:
        error = NotFoundError("resource missing")
        assert error.status_code == 404  # noqa: PLR2004


@pytest.mark.small
class DescribeValidationError:
    def it_inherits_from_greenhouse_error(self) -> None:
        error = ValidationError("invalid data", errors=[{"field": "name", "message": "required"}])
        assert isinstance(error, GreenhouseError)

    def it_defaults_to_status_code_422(self) -> None:
        error = ValidationError("validation failed", errors=[])
        assert error.status_code == 422  # noqa: PLR2004

    def it_carries_the_errors_array(self) -> None:
        errors = [{"field": "type", "message": "Must be one of: candidate, prospect"}]
        error = ValidationError("validation failed", errors=errors)
        assert error.errors == errors


@pytest.mark.small
class DescribeRateLimitError:
    def it_inherits_from_greenhouse_error(self) -> None:
        error = RateLimitError("slow down", retry_after=5.0)
        assert isinstance(error, GreenhouseError)

    def it_defaults_to_status_code_429(self) -> None:
        error = RateLimitError("rate limited", retry_after=10.0)
        assert error.status_code == 429  # noqa: PLR2004

    def it_carries_retry_after_seconds(self) -> None:
        error = RateLimitError("rate limited", retry_after=7.5)
        assert error.retry_after == 7.5  # noqa: PLR2004


@pytest.mark.small
class DescribeServerError:
    def it_inherits_from_greenhouse_error(self) -> None:
        error = ServerError("internal error")
        assert isinstance(error, GreenhouseError)

    def it_defaults_to_status_code_500(self) -> None:
        error = ServerError("server blew up")
        assert error.status_code == 500  # noqa: PLR2004

    def it_accepts_other_5xx_status_codes(self) -> None:
        error = ServerError("bad gateway", status_code=502)
        assert error.status_code == 502  # noqa: PLR2004
