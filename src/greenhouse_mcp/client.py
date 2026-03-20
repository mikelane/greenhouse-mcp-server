"""Async Greenhouse Harvest API client (adapter).

Implements GreenhousePort with httpx, handling Basic Auth, rate limiting,
Link header pagination, and exponential backoff retries.
"""

from __future__ import annotations

import asyncio
import base64
import re
import time
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from greenhouse_mcp.exceptions import (
    AuthenticationError,
    GreenhouseError,
    GreenhousePermissionError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)

_BASE_URL = "https://harvest.greenhouse.io/v1"
_DEFAULT_PER_PAGE = 500
_LINK_NEXT_PATTERN = re.compile(r'<([^>]+)>;\s*rel="next"')

# HTTP status codes
_HTTP_OK_MIN = 200
_HTTP_OK_MAX = 300
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_NOT_FOUND = 404
_HTTP_UNPROCESSABLE = 422
_HTTP_TOO_MANY_REQUESTS = 429
_HTTP_SERVER_ERROR = 500

# Backoff constants
_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_MULTIPLIER = 2


async def _default_sleep(seconds: float) -> None:
    """Sleep for the given number of seconds using asyncio."""
    await asyncio.sleep(seconds)  # pragma: no cover


def _extract_message(response: httpx.Response) -> str:
    """Extract the error message from a Greenhouse API error response.

    Args:
        response: The HTTP response to extract from.

    Returns:
        The error message string.
    """
    try:
        data = response.json()
        if isinstance(data, dict):
            return str(data.get("message", response.text))
    except Exception:
        return response.text
    return response.text


def _extract_errors(response: httpx.Response) -> list[dict[str, str]]:
    """Extract the validation errors array from a 422 response.

    Args:
        response: The HTTP response to extract from.

    Returns:
        List of error dicts with field and message keys.
    """
    try:
        data = response.json()
        if isinstance(data, dict):
            errors = data.get("errors", [])
            if isinstance(errors, list):
                return errors
    except Exception:
        return []
    return []


def _parse_next_url(link_header: str) -> str | None:
    """Parse the rel="next" URL from a Link header.

    Args:
        link_header: The raw Link header value.

    Returns:
        The next page URL, or None if not found.
    """
    match = _LINK_NEXT_PATTERN.search(link_header)
    return match.group(1) if match else None


class GreenhouseClient:
    """Async Greenhouse Harvest API client.

    Handles Basic Auth, rate limit tracking, Link header pagination,
    and retries with exponential backoff for 429 and 5xx responses.
    """

    def __init__(
        self,
        *,
        api_token: str,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        rate_limit_safety_margin: int = 5,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize the Greenhouse API client.

        Args:
            api_token: Greenhouse Harvest API token.
            http_client: Optional pre-configured httpx AsyncClient (for testing).
            max_retries: Maximum retry attempts for 429 and 5xx errors.
            rate_limit_safety_margin: Minimum remaining requests before backing off.
            sleep_fn: Async callable for delays (injectable for testing).
        """
        self._api_token = api_token
        self._auth_header = "Basic " + base64.b64encode(f"{api_token}:".encode()).decode()
        self._max_retries = max_retries
        self._safety_margin = rate_limit_safety_margin
        self._sleep_fn = sleep_fn or _default_sleep
        self._http_client = http_client or httpx.AsyncClient(base_url=_BASE_URL)
        self.rate_limit_remaining: int = 50
        self.rate_limit_reset: int = 0

    def _update_rate_limits(self, response: httpx.Response) -> None:
        """Update rate limit tracking from response headers.

        Args:
            response: The HTTP response to read headers from.
        """
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            self.rate_limit_remaining = int(remaining)

        reset = response.headers.get("X-RateLimit-Reset")
        if reset is not None:
            self.rate_limit_reset = int(reset)

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Map HTTP error status codes to typed exceptions.

        Args:
            response: The HTTP response to check.

        Raises:
            AuthenticationError: On 401.
            GreenhousePermissionError: On 403.
            NotFoundError: On 404.
            ValidationError: On 422.
            RateLimitError: On 429.
            ServerError: On 5xx.
            GreenhouseError: On other non-2xx status codes.
        """
        status = response.status_code
        if _HTTP_OK_MIN <= status < _HTTP_OK_MAX:
            return

        message = _extract_message(response)

        if status == _HTTP_UNAUTHORIZED:
            raise AuthenticationError(message)
        if status == _HTTP_FORBIDDEN:
            raise GreenhousePermissionError(message)
        if status == _HTTP_NOT_FOUND:
            raise NotFoundError(message)
        if status == _HTTP_UNPROCESSABLE:
            raise ValidationError(message, errors=_extract_errors(response))
        if status == _HTTP_TOO_MANY_REQUESTS:
            retry_after = float(response.headers.get("Retry-After", "1"))
            raise RateLimitError(message, retry_after=retry_after)
        if status >= _HTTP_SERVER_ERROR:
            raise ServerError(message, status_code=status)

        raise GreenhouseError(message, status_code=status)

    async def _proactive_backoff(self) -> None:
        """Sleep until rate limit reset if remaining requests are at or below safety margin."""
        if self.rate_limit_remaining <= self._safety_margin:
            wait_seconds = self.rate_limit_reset - time.time()
            if wait_seconds > 0:
                await self._sleep_fn(wait_seconds)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Execute a single HTTP request with auth and retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: API path relative to base URL, or an absolute URL for pagination.
            params: Query parameters.

        Returns:
            The successful HTTP response.

        Raises:
            RateLimitError: After exhausting retries on 429.
            ServerError: After exhausting retries on 5xx.
        """
        last_exception: GreenhouseError | None = None

        for attempt in range(self._max_retries + 1):
            await self._proactive_backoff()

            response = await self._http_client.request(
                method,
                url,
                params=params,
                headers={"Authorization": self._auth_header},
            )
            self._update_rate_limits(response)

            status = response.status_code
            is_retryable = status == _HTTP_TOO_MANY_REQUESTS or status >= _HTTP_SERVER_ERROR
            has_retries_left = attempt < self._max_retries

            if is_retryable and has_retries_left:
                try:
                    self._raise_for_status(response)
                except (RateLimitError, ServerError) as exc:
                    last_exception = exc
                    if isinstance(exc, RateLimitError):
                        await self._sleep_fn(exc.retry_after)
                    else:
                        delay = _BACKOFF_BASE_SECONDS * (_BACKOFF_MULTIPLIER**attempt)
                        await self._sleep_fn(delay)
                continue

            self._raise_for_status(response)
            return response

        raise last_exception  # type: ignore[misc]  # pragma: no cover

    async def _get_list(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch a paginated list resource, following Link headers.

        Args:
            path: API path for the list endpoint.
            params: Additional query parameters.

        Returns:
            Combined results from all pages.
        """
        all_params = {"per_page": _DEFAULT_PER_PAGE, "skip_count": "true"}
        if params:
            all_params.update(params)

        results: list[dict[str, Any]] = []
        response = await self._request("GET", path, params=all_params)
        page_data = response.json()
        if isinstance(page_data, list):
            results.extend(page_data)

        while True:
            link_header = response.headers.get("Link", "")
            next_url = _parse_next_url(link_header)
            if not next_url:
                break

            response = await self._request("GET", next_url)
            page_data = response.json()
            if isinstance(page_data, list):
                results.extend(page_data)

        return results

    async def _get_single(self, path: str) -> dict[str, Any]:
        """Fetch a single resource by path.

        Args:
            path: API path for the resource.

        Returns:
            The resource as a dictionary.
        """
        response = await self._request("GET", path)
        result: dict[str, Any] = response.json()
        return result

    # --- GreenhousePort implementation ---

    async def get_jobs(
        self,
        *,
        status: str | None = None,
        department_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch jobs, optionally filtered by status or department.

        Args:
            status: Filter by job status (open, closed, draft).
            department_id: Filter by department ID.

        Returns:
            List of job objects.
        """
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if department_id is not None:
            params["department_id"] = department_id
        return await self._get_list("/jobs", params=params)

    async def get_job(self, job_id: int) -> dict[str, Any]:
        """Fetch a single job by ID.

        Args:
            job_id: The Greenhouse job ID.

        Returns:
            Job object.
        """
        return await self._get_single(f"/jobs/{job_id}")

    async def get_job_stages(self, job_id: int) -> list[dict[str, Any]]:
        """Fetch stages for a specific job.

        Args:
            job_id: The Greenhouse job ID.

        Returns:
            List of stage objects.
        """
        return await self._get_list(f"/jobs/{job_id}/stages")

    async def get_applications(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        created_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch applications, optionally filtered.

        Args:
            job_id: Filter by job ID.
            status: Filter by application status.
            created_after: ISO 8601 timestamp lower bound.

        Returns:
            List of application objects.
        """
        params: dict[str, Any] = {}
        if job_id is not None:
            params["job_id"] = job_id
        if status is not None:
            params["status"] = status
        if created_after is not None:
            params["created_after"] = created_after
        return await self._get_list("/applications", params=params)

    async def get_candidate(self, candidate_id: int) -> dict[str, Any]:
        """Fetch a single candidate by ID.

        Args:
            candidate_id: The Greenhouse candidate ID.

        Returns:
            Candidate object.
        """
        return await self._get_single(f"/candidates/{candidate_id}")

    async def get_candidates(
        self,
        *,
        job_id: int | None = None,
        email: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch candidates, optionally filtered.

        Args:
            job_id: Filter by job ID.
            email: Filter by email address.

        Returns:
            List of candidate objects.
        """
        params: dict[str, Any] = {}
        if job_id is not None:
            params["job_id"] = job_id
        if email is not None:
            params["email"] = email
        return await self._get_list("/candidates", params=params)

    async def get_scorecards(self, application_id: int) -> list[dict[str, Any]]:
        """Fetch scorecards for a specific application.

        Args:
            application_id: The Greenhouse application ID.

        Returns:
            List of scorecard objects.
        """
        return await self._get_list(f"/applications/{application_id}/scorecards")

    async def get_scheduled_interviews(
        self,
        *,
        application_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch scheduled interviews, optionally for a specific application.

        Args:
            application_id: Filter by application ID.

        Returns:
            List of scheduled interview objects.
        """
        if application_id is not None:
            return await self._get_list(f"/applications/{application_id}/scheduled_interviews")
        return await self._get_list("/scheduled_interviews")

    async def get_offers(
        self,
        *,
        application_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch offers, optionally filtered.

        Args:
            application_id: Filter by application ID.
            status: Filter by offer status.

        Returns:
            List of offer objects.
        """
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if application_id is not None:
            return await self._get_list(f"/applications/{application_id}/offers", params=params)
        return await self._get_list("/offers", params=params)

    async def get_activity_feed(self, candidate_id: int) -> dict[str, Any]:
        """Fetch the full activity feed for a candidate.

        Args:
            candidate_id: The Greenhouse candidate ID.

        Returns:
            Activity feed object with notes, emails, and activities.
        """
        return await self._get_single(f"/candidates/{candidate_id}/activity_feed")
