"""Tests for the Greenhouse API client adapter.

Uses httpx MockTransport to simulate Greenhouse API responses.
No live API calls, no unittest.mock.patch.
"""

from __future__ import annotations

import base64
import json
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

import httpx
import pytest

import greenhouse_mcp.client as client_module
from greenhouse_mcp.client import GreenhouseClient
from greenhouse_mcp.exceptions import (
    AuthenticationError,
    GreenhouseError,
    GreenhousePermissionError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


def _make_response(
    *,
    status_code: int = 200,
    json_data: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Build an httpx Response for MockTransport handlers."""
    response_headers = {
        "X-RateLimit-Limit": "50",
        "X-RateLimit-Remaining": "49",
        "X-RateLimit-Reset": str(int(time.time()) + 10),
    }
    if headers:
        response_headers.update(headers)
    body = json.dumps(json_data if json_data is not None else []).encode()
    return httpx.Response(
        status_code=status_code,
        content=body,
        headers=response_headers,
    )


async def _noop_sleep(_seconds: float) -> None:
    """No-op sleep for testing -- avoids real delays."""


def _build_client(
    handler: httpx.MockTransport | None = None,
    *,
    api_token: str = "test-token-abc",  # noqa: S107
    max_retries: int = 0,
    rate_limit_safety_margin: int = 5,
    sleep_fn: Callable[[float], Awaitable[None]] = _noop_sleep,
) -> GreenhouseClient:
    """Build a GreenhouseClient with a MockTransport."""
    if handler is None:
        handler = httpx.MockTransport(lambda _request: _make_response(json_data=[]))
    return GreenhouseClient(
        api_token=api_token,
        http_client=httpx.AsyncClient(transport=handler, base_url="https://harvest.greenhouse.io/v1"),
        max_retries=max_retries,
        rate_limit_safety_margin=rate_limit_safety_margin,
        sleep_fn=sleep_fn,
    )


@pytest.mark.small
class DescribeGreenhouseAuth:
    @pytest.mark.anyio
    async def it_sends_basic_auth_header_with_token_as_username(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[{"id": 1, "name": "Engineer"}])

        client = _build_client(httpx.MockTransport(handler), api_token="my-secret-token")  # noqa: S106
        await client.get_jobs()

        assert captured_request is not None
        auth_header = captured_request.headers["authorization"]
        expected = "Basic " + base64.b64encode(b"my-secret-token:").decode()
        assert auth_header == expected

    @pytest.mark.anyio
    async def it_uses_blank_password_in_basic_auth(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler), api_token="token123")  # noqa: S106
        await client.get_jobs()

        assert captured_request is not None
        auth_header = captured_request.headers["authorization"]
        decoded = base64.b64decode(auth_header.split(" ")[1]).decode()
        assert decoded == "token123:"
        assert decoded.endswith(":")


@pytest.mark.small
class DescribeRateLimiting:
    @pytest.mark.anyio
    async def it_tracks_remaining_requests_from_response_headers(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[],
                headers={"X-RateLimit-Remaining": "7"},
            )
        )
        client = _build_client(transport)
        await client.get_jobs()
        assert client.rate_limit_remaining == 7

    @pytest.mark.anyio
    async def it_tracks_rate_limit_reset_timestamp(self) -> None:
        reset_time = str(int(time.time()) + 30)
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[],
                headers={
                    "X-RateLimit-Remaining": "3",
                    "X-RateLimit-Reset": reset_time,
                },
            )
        )
        client = _build_client(transport)
        await client.get_jobs()
        assert client.rate_limit_reset == int(reset_time)


@pytest.mark.small
class DescribeErrorHandling:
    @pytest.mark.anyio
    async def it_raises_authentication_error_on_401(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=401,
                json_data={"message": "Invalid API key"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(AuthenticationError, match="Invalid API key"):
            await client.get_jobs()

    @pytest.mark.anyio
    async def it_raises_permission_error_on_403(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=403,
                json_data={"message": "Access denied"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(GreenhousePermissionError, match="Access denied"):
            await client.get_jobs()

    @pytest.mark.anyio
    async def it_raises_not_found_error_on_404(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=404,
                json_data={"message": "Resource not found"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(NotFoundError, match="Resource not found"):
            await client.get_candidate(999)

    @pytest.mark.anyio
    async def it_raises_validation_error_on_422_with_errors_array(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=422,
                json_data={
                    "message": "Validation error",
                    "errors": [{"field": "type", "message": "Must be one of: candidate, prospect"}],
                },
            )
        )
        client = _build_client(transport)
        with pytest.raises(ValidationError) as exc_info:
            await client.get_jobs()
        assert exc_info.value.errors == [{"field": "type", "message": "Must be one of: candidate, prospect"}]

    @pytest.mark.anyio
    async def it_raises_rate_limit_error_on_429_with_retry_after(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=429,
                json_data={"message": "Rate limit exceeded"},
                headers={"Retry-After": "5"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_jobs()
        assert exc_info.value.retry_after == 5.0

    @pytest.mark.anyio
    async def it_raises_server_error_on_500(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=500,
                json_data={"message": "Internal server error"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(ServerError):
            await client.get_jobs()

    @pytest.mark.anyio
    async def it_raises_server_error_on_502(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=502,
                json_data={"message": "Bad gateway"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(ServerError) as exc_info:
            await client.get_jobs()
        assert exc_info.value.status_code == 502


@pytest.mark.small
class DescribeRetries:
    @pytest.mark.anyio
    async def it_retries_on_429_up_to_max_retries(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return _make_response(
                    status_code=429,
                    json_data={"message": "Rate limit"},
                    headers={"Retry-After": "0"},
                )
            return _make_response(json_data=[{"id": 1}])

        client = _build_client(httpx.MockTransport(handler), max_retries=3)
        result = await client.get_jobs()
        assert result == [{"id": 1}]
        assert call_count == 3

    @pytest.mark.anyio
    async def it_raises_after_exhausting_retries_on_429(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return _make_response(
                status_code=429,
                json_data={"message": "Rate limit"},
                headers={"Retry-After": "0"},
            )

        client = _build_client(httpx.MockTransport(handler), max_retries=2)
        with pytest.raises(RateLimitError):
            await client.get_jobs()

    @pytest.mark.anyio
    async def it_retries_on_500_up_to_max_retries(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return _make_response(
                    status_code=500,
                    json_data={"message": "Server error"},
                )
            return _make_response(json_data=[{"id": 2}])

        client = _build_client(httpx.MockTransport(handler), max_retries=2)
        result = await client.get_jobs()
        assert result == [{"id": 2}]
        assert call_count == 2

    @pytest.mark.anyio
    async def it_raises_after_exhausting_retries_on_500(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return _make_response(
                status_code=500,
                json_data={"message": "Server error"},
            )

        client = _build_client(httpx.MockTransport(handler), max_retries=1)
        with pytest.raises(ServerError):
            await client.get_jobs()

    @pytest.mark.anyio
    async def it_does_not_retry_on_4xx_other_than_429(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _make_response(
                status_code=401,
                json_data={"message": "Unauthorized"},
            )

        client = _build_client(httpx.MockTransport(handler), max_retries=3)
        with pytest.raises(AuthenticationError):
            await client.get_jobs()
        assert call_count == 1


@pytest.mark.small
class DescribePagination:
    @pytest.mark.anyio
    async def it_follows_link_header_rel_next(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    json_data=[{"id": 1}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=2&per_page=500>; rel="next"',
                    },
                )
            return _make_response(json_data=[{"id": 2}])

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_jobs()
        assert result == [{"id": 1}, {"id": 2}]
        assert call_count == 2

    @pytest.mark.anyio
    async def it_follows_multiple_pages(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    json_data=[{"id": 1}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=2&per_page=500>; rel="next"',
                    },
                )
            if call_count == 2:
                return _make_response(
                    json_data=[{"id": 2}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=3&per_page=500>; rel="next"',
                    },
                )
            return _make_response(json_data=[{"id": 3}])

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_jobs()
        assert result == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert call_count == 3

    @pytest.mark.anyio
    async def it_stops_when_no_link_header_present(self) -> None:
        transport = httpx.MockTransport(lambda _request: _make_response(json_data=[{"id": 1}]))
        client = _build_client(transport)
        result = await client.get_jobs()
        assert result == [{"id": 1}]

    @pytest.mark.anyio
    async def it_stops_when_link_header_has_no_rel_next(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[{"id": 1}],
                headers={
                    "Link": '<https://harvest.greenhouse.io/v1/jobs?page=1&per_page=500>; rel="prev"',
                },
            )
        )
        client = _build_client(transport)
        result = await client.get_jobs()
        assert result == [{"id": 1}]

    @pytest.mark.anyio
    async def it_returns_empty_list_for_empty_collection(self) -> None:
        transport = httpx.MockTransport(lambda _request: _make_response(json_data=[]))
        client = _build_client(transport)
        result = await client.get_jobs()
        assert result == []

    @pytest.mark.anyio
    async def it_requests_per_page_500_and_skip_count_true(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_jobs()

        assert captured_request is not None
        url = str(captured_request.url)
        assert "per_page=500" in url
        assert "skip_count=true" in url


@pytest.mark.small
class DescribeEndpoints:
    @pytest.mark.anyio
    async def it_calls_jobs_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_jobs()

        assert captured_request is not None
        assert captured_request.url.path == "/v1/jobs"

    @pytest.mark.anyio
    async def it_passes_status_filter_to_jobs(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_jobs(status="open")

        assert captured_request is not None
        assert "status=open" in str(captured_request.url)

    @pytest.mark.anyio
    async def it_passes_department_id_filter_to_jobs(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_jobs(department_id=42)

        assert captured_request is not None
        assert "department_id=42" in str(captured_request.url)

    @pytest.mark.anyio
    async def it_calls_single_job_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data={"id": 10, "name": "Engineer"})

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_job(10)

        assert captured_request is not None
        assert captured_request.url.path == "/v1/jobs/10"
        assert result == {"id": 10, "name": "Engineer"}

    @pytest.mark.anyio
    async def it_calls_job_stages_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[{"id": 1, "name": "Phone Screen"}])

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_job_stages(10)

        assert captured_request is not None
        assert captured_request.url.path == "/v1/jobs/10/stages"
        assert result == [{"id": 1, "name": "Phone Screen"}]

    @pytest.mark.anyio
    async def it_calls_applications_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_applications()

        assert captured_request is not None
        assert captured_request.url.path == "/v1/applications"

    @pytest.mark.anyio
    async def it_passes_job_id_filter_to_applications(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_applications(job_id=5)

        assert captured_request is not None
        assert "job_id=5" in str(captured_request.url)

    @pytest.mark.anyio
    async def it_passes_status_filter_to_applications(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_applications(status="active")

        assert captured_request is not None
        assert "status=active" in str(captured_request.url)

    @pytest.mark.anyio
    async def it_passes_created_after_filter_to_applications(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_applications(created_after="2024-01-01T00:00:00Z")

        assert captured_request is not None
        assert "created_after=" in str(captured_request.url)

    @pytest.mark.anyio
    async def it_calls_single_candidate_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data={"id": 42, "first_name": "Jane"})

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_candidate(42)

        assert captured_request is not None
        assert captured_request.url.path == "/v1/candidates/42"
        assert result == {"id": 42, "first_name": "Jane"}

    @pytest.mark.anyio
    async def it_calls_candidates_list_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_candidates()

        assert captured_request is not None
        assert captured_request.url.path == "/v1/candidates"

    @pytest.mark.anyio
    async def it_passes_email_filter_to_candidates(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_candidates(email="jane@example.com")

        assert captured_request is not None
        assert "email=jane" in str(captured_request.url)

    @pytest.mark.anyio
    async def it_calls_scorecards_endpoint_for_application(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_scorecards(100)

        assert captured_request is not None
        assert captured_request.url.path == "/v1/applications/100/scorecards"

    @pytest.mark.anyio
    async def it_calls_scheduled_interviews_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_scheduled_interviews()

        assert captured_request is not None
        assert captured_request.url.path == "/v1/scheduled_interviews"

    @pytest.mark.anyio
    async def it_calls_scheduled_interviews_for_application(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_scheduled_interviews(application_id=200)

        assert captured_request is not None
        assert captured_request.url.path == "/v1/applications/200/scheduled_interviews"

    @pytest.mark.anyio
    async def it_calls_offers_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_offers()

        assert captured_request is not None
        assert captured_request.url.path == "/v1/offers"

    @pytest.mark.anyio
    async def it_calls_offers_for_application(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_offers(application_id=300)

        assert captured_request is not None
        assert captured_request.url.path == "/v1/applications/300/offers"

    @pytest.mark.anyio
    async def it_passes_status_filter_to_offers(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_offers(status="accepted")

        assert captured_request is not None
        assert "status=accepted" in str(captured_request.url)

    @pytest.mark.anyio
    async def it_calls_activity_feed_endpoint(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data={"notes": [], "emails": [], "activities": []})

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_activity_feed(42)

        assert captured_request is not None
        assert captured_request.url.path == "/v1/candidates/42/activity_feed"
        assert result == {"notes": [], "emails": [], "activities": []}

    @pytest.mark.anyio
    async def it_passes_job_id_filter_to_candidates(self) -> None:
        captured_request: httpx.Request | None = None

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = _request
            return _make_response(json_data=[])

        client = _build_client(httpx.MockTransport(handler))
        await client.get_candidates(job_id=77)

        assert captured_request is not None
        assert "job_id=77" in str(captured_request.url)


@pytest.mark.small
class DescribeErrorExtraction:
    @pytest.mark.anyio
    async def it_returns_response_text_when_body_is_not_json(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(
                status_code=401,
                content=b"Unauthorized - bad token",
                headers={
                    "X-RateLimit-Remaining": "49",
                    "X-RateLimit-Reset": str(int(time.time()) + 10),
                },
            )
        )
        client = _build_client(transport)
        with pytest.raises(AuthenticationError, match="Unauthorized - bad token"):
            await client.get_jobs()

    @pytest.mark.anyio
    async def it_returns_empty_list_when_error_body_is_not_json(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(
                status_code=422,
                content=b"Not valid JSON at all",
                headers={
                    "X-RateLimit-Remaining": "49",
                    "X-RateLimit-Reset": str(int(time.time()) + 10),
                },
            )
        )
        client = _build_client(transport)
        with pytest.raises(ValidationError) as exc_info:
            await client.get_jobs()
        assert exc_info.value.errors == []

    @pytest.mark.anyio
    async def it_returns_response_text_when_json_body_is_not_a_dict(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=401,
                json_data=["not", "a", "dict"],
            )
        )
        client = _build_client(transport)
        with pytest.raises(AuthenticationError) as exc_info:
            await client.get_jobs()
        assert '["not", "a", "dict"]' in str(exc_info.value)

    @pytest.mark.anyio
    async def it_returns_empty_errors_when_422_json_body_is_not_a_dict(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=422,
                json_data=["not", "a", "dict"],
            )
        )
        client = _build_client(transport)
        with pytest.raises(ValidationError) as exc_info:
            await client.get_jobs()
        assert exc_info.value.errors == []

    @pytest.mark.anyio
    async def it_returns_empty_errors_when_errors_field_is_not_a_list(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=422,
                json_data={"message": "Bad request", "errors": "not a list"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(ValidationError) as exc_info:
            await client.get_jobs()
        assert exc_info.value.errors == []


@pytest.mark.small
class DescribeRateLimitHeaderAbsence:
    @pytest.mark.anyio
    async def it_preserves_default_remaining_when_header_is_absent(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(
                status_code=200,
                content=b"[]",
                headers={},
            )
        )
        client = _build_client(transport)
        assert client.rate_limit_remaining == 50
        await client.get_jobs()
        assert client.rate_limit_remaining == 50

    @pytest.mark.anyio
    async def it_preserves_default_reset_when_header_is_absent(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(
                status_code=200,
                content=b"[]",
                headers={},
            )
        )
        client = _build_client(transport)
        assert client.rate_limit_reset == 0
        await client.get_jobs()
        assert client.rate_limit_reset == 0

    @pytest.mark.anyio
    async def it_updates_remaining_but_not_reset_when_only_remaining_present(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(
                status_code=200,
                content=b"[]",
                headers={"X-RateLimit-Remaining": "25"},
            )
        )
        client = _build_client(transport)
        await client.get_jobs()
        assert client.rate_limit_remaining == 25
        assert client.rate_limit_reset == 0

    @pytest.mark.anyio
    async def it_updates_reset_but_not_remaining_when_only_reset_present(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(
                status_code=200,
                content=b"[]",
                headers={"X-RateLimit-Reset": "1700000000"},
            )
        )
        client = _build_client(transport)
        await client.get_jobs()
        assert client.rate_limit_remaining == 50
        assert client.rate_limit_reset == 1700000000


@pytest.mark.small
class DescribeUnknownStatusCodes:
    @pytest.mark.anyio
    async def it_raises_greenhouse_error_for_unknown_non_2xx_status(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=418,
                json_data={"message": "I'm a teapot"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(GreenhouseError, match="I'm a teapot") as exc_info:
            await client.get_jobs()
        assert exc_info.value.status_code == 418
        assert type(exc_info.value) is GreenhouseError


@pytest.mark.small
class DescribeNonListPageData:
    @pytest.mark.anyio
    async def it_returns_empty_list_when_first_page_is_not_a_list(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data={"error": "unexpected format"},
            )
        )
        client = _build_client(transport)
        result = await client.get_jobs()
        assert result == []

    @pytest.mark.anyio
    async def it_skips_subsequent_page_when_data_is_not_a_list(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    json_data=[{"id": 1}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=2&per_page=500>; rel="next"',
                    },
                )
            return _make_response(
                json_data={"error": "unexpected format on page 2"},
            )

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_jobs()
        assert result == [{"id": 1}]


@pytest.mark.small
class DescribePaginationRetry:
    @pytest.mark.anyio
    async def it_retries_429_on_second_page_instead_of_crashing(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    json_data=[{"id": 1}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=2&per_page=500>; rel="next"',
                    },
                )
            if call_count == 2:
                return _make_response(
                    status_code=429,
                    json_data={"message": "Rate limit"},
                    headers={"Retry-After": "0"},
                )
            return _make_response(json_data=[{"id": 2}])

        client = _build_client(httpx.MockTransport(handler), max_retries=2)
        result = await client.get_jobs()
        assert result == [{"id": 1}, {"id": 2}]
        assert call_count == 3

    @pytest.mark.anyio
    async def it_retries_500_on_second_page_instead_of_crashing(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    json_data=[{"id": 1}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=2&per_page=500>; rel="next"',
                    },
                )
            if call_count == 2:
                return _make_response(
                    status_code=500,
                    json_data={"message": "Server error"},
                )
            return _make_response(json_data=[{"id": 2}])

        client = _build_client(httpx.MockTransport(handler), max_retries=2)
        result = await client.get_jobs()
        assert result == [{"id": 1}, {"id": 2}]
        assert call_count == 3

    @pytest.mark.anyio
    async def it_raises_after_exhausting_retries_on_paginated_429(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    json_data=[{"id": 1}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=2&per_page=500>; rel="next"',
                    },
                )
            return _make_response(
                status_code=429,
                json_data={"message": "Rate limit"},
                headers={"Retry-After": "0"},
            )

        client = _build_client(httpx.MockTransport(handler), max_retries=1)
        with pytest.raises(RateLimitError):
            await client.get_jobs()


@pytest.mark.small
class DescribeExponentialBackoff:
    @pytest.mark.anyio
    async def it_sleeps_with_increasing_delays_between_retries_on_5xx(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return _make_response(
                    status_code=500,
                    json_data={"message": "Server error"},
                )
            return _make_response(json_data=[{"id": 1}])

        client = _build_client(
            httpx.MockTransport(handler),
            max_retries=3,
            sleep_fn=tracking_sleep,
        )
        result = await client.get_jobs()
        assert result == [{"id": 1}]
        assert len(sleep_durations) == 3
        assert sleep_durations[1] > sleep_durations[0]
        assert sleep_durations[2] > sleep_durations[1]

    @pytest.mark.anyio
    async def it_honors_retry_after_header_on_429(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    status_code=429,
                    json_data={"message": "Rate limit"},
                    headers={"Retry-After": "7"},
                )
            return _make_response(json_data=[{"id": 1}])

        client = _build_client(
            httpx.MockTransport(handler),
            max_retries=2,
            sleep_fn=tracking_sleep,
        )
        result = await client.get_jobs()
        assert result == [{"id": 1}]
        assert len(sleep_durations) == 1
        assert sleep_durations[0] == 7.0

    @pytest.mark.anyio
    async def it_does_not_sleep_before_the_first_attempt(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        def handler(_request: httpx.Request) -> httpx.Response:
            return _make_response(json_data=[{"id": 1}])

        client = _build_client(
            httpx.MockTransport(handler),
            max_retries=3,
            sleep_fn=tracking_sleep,
        )
        await client.get_jobs()
        assert sleep_durations == []


@pytest.mark.small
class DescribeProactiveRateLimitBackoff:
    @pytest.mark.anyio
    async def it_sleeps_when_remaining_requests_at_safety_margin(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[],
                headers={
                    "X-RateLimit-Remaining": "50",
                    "X-RateLimit-Reset": str(int(time.time()) + 10),
                },
            )
        )
        client = _build_client(
            transport,
            rate_limit_safety_margin=5,
            sleep_fn=tracking_sleep,
        )
        client.rate_limit_remaining = 3
        client.rate_limit_reset = int(time.time()) + 5

        await client.get_jobs()

        assert len(sleep_durations) == 1
        assert sleep_durations[0] > 0

    @pytest.mark.anyio
    async def it_does_not_sleep_when_remaining_above_safety_margin(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        transport = httpx.MockTransport(lambda _request: _make_response(json_data=[]))
        client = _build_client(
            transport,
            rate_limit_safety_margin=5,
            sleep_fn=tracking_sleep,
        )
        client.rate_limit_remaining = 20

        await client.get_jobs()

        assert sleep_durations == []

    @pytest.mark.anyio
    async def it_does_not_sleep_when_reset_time_is_in_the_past(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[],
                headers={
                    "X-RateLimit-Remaining": "50",
                    "X-RateLimit-Reset": str(int(time.time()) + 10),
                },
            )
        )
        client = _build_client(
            transport,
            rate_limit_safety_margin=5,
            sleep_fn=tracking_sleep,
        )
        client.rate_limit_remaining = 0
        client.rate_limit_reset = int(time.time()) - 10

        await client.get_jobs()

        assert sleep_durations == [] or all(d <= 0 for d in sleep_durations)


@pytest.mark.small
class DescribeProactiveBackoffBoundary:
    @pytest.mark.anyio
    async def it_triggers_backoff_when_remaining_equals_safety_margin(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[],
                headers={
                    "X-RateLimit-Remaining": "50",
                    "X-RateLimit-Reset": str(int(time.time()) + 10),
                },
            )
        )
        client = _build_client(
            transport,
            rate_limit_safety_margin=5,
            sleep_fn=tracking_sleep,
        )
        client.rate_limit_remaining = 5
        client.rate_limit_reset = int(time.time()) + 5

        await client.get_jobs()

        assert len(sleep_durations) == 1
        assert sleep_durations[0] > 0

    @pytest.mark.anyio
    async def it_does_not_trigger_backoff_when_remaining_equals_margin_plus_one(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        transport = httpx.MockTransport(lambda _request: _make_response(json_data=[]))
        client = _build_client(
            transport,
            rate_limit_safety_margin=5,
            sleep_fn=tracking_sleep,
        )
        client.rate_limit_remaining = 6
        client.rate_limit_reset = int(time.time()) + 5

        await client.get_jobs()

        assert sleep_durations == []

    @pytest.mark.anyio
    async def it_does_not_sleep_when_wait_seconds_is_exactly_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        monkeypatch.setattr(client_module.time, "time", lambda: 1000.0)

        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[],
                headers={
                    "X-RateLimit-Remaining": "50",
                    "X-RateLimit-Reset": "2000",
                },
            )
        )
        client = _build_client(
            transport,
            rate_limit_safety_margin=5,
            sleep_fn=tracking_sleep,
        )
        client.rate_limit_remaining = 0
        client.rate_limit_reset = 1000

        await client.get_jobs()

        assert sleep_durations == []

    @pytest.mark.anyio
    async def it_does_not_sleep_when_wait_seconds_is_slightly_negative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        monkeypatch.setattr(client_module.time, "time", lambda: 1000.5)

        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[],
                headers={
                    "X-RateLimit-Remaining": "50",
                    "X-RateLimit-Reset": "2000",
                },
            )
        )
        client = _build_client(
            transport,
            rate_limit_safety_margin=5,
            sleep_fn=tracking_sleep,
        )
        client.rate_limit_remaining = 0
        client.rate_limit_reset = 1000

        await client.get_jobs()

        assert sleep_durations == []

    @pytest.mark.anyio
    async def it_sleeps_when_wait_seconds_is_slightly_positive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        monkeypatch.setattr(client_module.time, "time", lambda: 999.5)

        transport = httpx.MockTransport(
            lambda _request: _make_response(
                json_data=[],
                headers={
                    "X-RateLimit-Remaining": "50",
                    "X-RateLimit-Reset": "2000",
                },
            )
        )
        client = _build_client(
            transport,
            rate_limit_safety_margin=5,
            sleep_fn=tracking_sleep,
        )
        client.rate_limit_remaining = 0
        client.rate_limit_reset = 1000

        await client.get_jobs()

        assert len(sleep_durations) == 1
        assert sleep_durations[0] == pytest.approx(0.5)


@pytest.mark.small
class DescribeExactRetryCount:
    @pytest.mark.anyio
    async def it_makes_exactly_max_retries_plus_one_total_attempts(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _make_response(
                status_code=500,
                json_data={"message": "Server error"},
            )

        client = _build_client(httpx.MockTransport(handler), max_retries=3)
        with pytest.raises(ServerError):
            await client.get_jobs()
        assert call_count == 4

    @pytest.mark.anyio
    async def it_makes_exactly_one_attempt_when_max_retries_is_zero(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _make_response(
                status_code=500,
                json_data={"message": "Server error"},
            )

        client = _build_client(httpx.MockTransport(handler), max_retries=0)
        with pytest.raises(ServerError):
            await client.get_jobs()
        assert call_count == 1

    @pytest.mark.anyio
    async def it_performs_exactly_max_retries_sleeps_not_more(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        def handler(_request: httpx.Request) -> httpx.Response:
            return _make_response(
                status_code=500,
                json_data={"message": "Server error"},
            )

        client = _build_client(
            httpx.MockTransport(handler),
            max_retries=3,
            sleep_fn=tracking_sleep,
        )
        with pytest.raises(ServerError):
            await client.get_jobs()
        assert len(sleep_durations) == 3


@pytest.mark.small
class DescribeRetryableStatusBoundary:
    @pytest.mark.anyio
    async def it_does_not_retry_status_499(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _make_response(
                status_code=499,
                json_data={"message": "Client error"},
            )

        client = _build_client(httpx.MockTransport(handler), max_retries=3)
        with pytest.raises(GreenhouseError):
            await client.get_jobs()
        assert call_count == 1

    @pytest.mark.anyio
    async def it_retries_status_500(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    status_code=500,
                    json_data={"message": "Server error"},
                )
            return _make_response(json_data=[{"id": 1}])

        client = _build_client(httpx.MockTransport(handler), max_retries=3)
        result = await client.get_jobs()
        assert result == [{"id": 1}]
        assert call_count == 2

    @pytest.mark.anyio
    async def it_retries_status_501(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    status_code=501,
                    json_data={"message": "Not implemented"},
                )
            return _make_response(json_data=[{"id": 1}])

        client = _build_client(httpx.MockTransport(handler), max_retries=3)
        result = await client.get_jobs()
        assert result == [{"id": 1}]
        assert call_count == 2


@pytest.mark.small
class DescribeStatusCodeBoundary:
    @pytest.mark.anyio
    async def it_raises_error_for_status_300(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=300,
                json_data={"message": "Multiple choices"},
            )
        )
        client = _build_client(transport)
        with pytest.raises(GreenhouseError, match="Multiple choices"):
            await client.get_jobs()

    @pytest.mark.anyio
    async def it_accepts_status_299_as_success(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=299,
                json_data=[{"id": 1}],
            )
        )
        client = _build_client(transport)
        result = await client.get_jobs()
        assert result == [{"id": 1}]

    @pytest.mark.anyio
    async def it_accepts_status_200_as_success(self) -> None:
        transport = httpx.MockTransport(
            lambda _request: _make_response(
                status_code=200,
                json_data=[{"id": 1}],
            )
        )
        client = _build_client(transport)
        result = await client.get_jobs()
        assert result == [{"id": 1}]


@pytest.mark.small
class DescribePaginationIterationCount:
    @pytest.mark.anyio
    async def it_makes_exactly_three_requests_for_three_pages(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(
                    json_data=[{"id": 1}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=2&per_page=500>; rel="next"',
                    },
                )
            if call_count == 2:
                return _make_response(
                    json_data=[{"id": 2}],
                    headers={
                        "Link": '<https://harvest.greenhouse.io/v1/jobs?page=3&per_page=500>; rel="next"',
                    },
                )
            return _make_response(json_data=[{"id": 3}])

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_jobs()
        assert len(result) == 3
        assert call_count == 3

    @pytest.mark.anyio
    async def it_makes_exactly_one_request_for_single_page(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _make_response(json_data=[{"id": 1}])

        client = _build_client(httpx.MockTransport(handler))
        result = await client.get_jobs()
        assert len(result) == 1
        assert call_count == 1


@pytest.mark.small
class DescribeExponentialBackoffValues:
    @pytest.mark.anyio
    async def it_uses_exponential_not_linear_backoff_delays(self) -> None:
        sleep_durations: list[float] = []

        async def tracking_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)

        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 4:
                return _make_response(
                    status_code=500,
                    json_data={"message": "Server error"},
                )
            return _make_response(json_data=[{"id": 1}])

        client = _build_client(
            httpx.MockTransport(handler),
            max_retries=4,
            sleep_fn=tracking_sleep,
        )
        result = await client.get_jobs()
        assert result == [{"id": 1}]
        assert len(sleep_durations) == 4
        # 2**0=1, 2**1=2, 2**2=4, 2**3=8
        # If mutated to 2*attempt: 2*0=0, 2*1=2, 2*2=4, 2*3=6
        # Attempt 3 distinguishes: 2**3=8 vs 2*3=6
        assert sleep_durations[0] == pytest.approx(1.0)
        assert sleep_durations[1] == pytest.approx(2.0)
        assert sleep_durations[2] == pytest.approx(4.0)
        assert sleep_durations[3] == pytest.approx(8.0)


@pytest.mark.small
class DescribeLastExceptionTracking:
    @pytest.mark.anyio
    async def it_raises_the_last_exception_after_exhausting_retries(self) -> None:
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return _make_response(
                    status_code=500,
                    json_data={"message": f"Server error attempt {call_count}"},
                )
            return _make_response(
                status_code=502,
                json_data={"message": "Bad gateway final"},
            )

        client = _build_client(httpx.MockTransport(handler), max_retries=2)
        with pytest.raises(ServerError, match="Bad gateway final") as exc_info:
            await client.get_jobs()
        assert exc_info.value.status_code == 502
        assert call_count == 3
