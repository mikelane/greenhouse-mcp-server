"""Tests for the needs_attention tool."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from greenhouse_mcp.tools.attention import needs_attention


class FakeGreenhouseClient:
    """In-memory fake satisfying GreenhousePort for needs_attention tests."""

    def __init__(self) -> None:
        self.applications: list[dict[str, Any]] = []
        self.scorecards: dict[int, list[dict[str, Any]]] = {}
        self.offers: list[dict[str, Any]] = []
        self.job_stages: dict[int, list[dict[str, Any]]] = {}
        self.candidates: dict[int, dict[str, Any]] = {}
        self.jobs: dict[int, dict[str, Any]] = {}

    async def get_applications(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        _created_after: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self.applications
        if job_id is not None:
            result = [a for a in result if any(j["id"] == job_id for j in a.get("jobs", []))]
        if status is not None:
            result = [a for a in result if a.get("status") == status]
        return result

    async def get_scorecards(self, application_id: int) -> list[dict[str, Any]]:
        return self.scorecards.get(application_id, [])

    async def get_offers(
        self,
        *,
        application_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self.offers
        if application_id is not None:
            result = [o for o in result if o.get("application_id") == application_id]
        if status is not None:
            result = [o for o in result if o.get("status") == status]
        return result

    async def get_job_stages(self, job_id: int) -> list[dict[str, Any]]:
        return self.job_stages.get(job_id, [])

    async def get_candidate(self, candidate_id: int) -> dict[str, Any]:
        return self.candidates.get(
            candidate_id,
            {"id": candidate_id, "first_name": "Unknown", "last_name": "Candidate"},
        )

    async def get_job(self, job_id: int) -> dict[str, Any]:
        return self.jobs.get(job_id, {"id": job_id, "name": f"Job {job_id}"})

    async def get_jobs(
        self,
        *,
        _status: str | None = None,
        _department_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return list(self.jobs.values())

    async def get_candidates(
        self,
        *,
        _job_id: int | None = None,
        _email: str | None = None,
    ) -> list[dict[str, Any]]:
        return list(self.candidates.values())

    async def get_scheduled_interviews(
        self,
        *,
        _application_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def get_activity_feed(self, _candidate_id: int) -> dict[str, Any]:
        return {"notes": [], "emails": [], "activities": []}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _make_application(  # noqa: PLR0913
    *,
    app_id: int = 1,
    candidate_id: int = 100,
    job_id: int = 10,
    job_name: str = "Software Engineer",
    stage_id: int = 1,
    stage_name: str = "Phone Screen",
    last_activity_at: datetime | None = None,
    status: str = "active",
    prospect: bool = False,
) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    return {
        "id": app_id,
        "candidate_id": candidate_id,
        "prospect": prospect,
        "status": status,
        "last_activity_at": _iso(last_activity_at or now),
        "current_stage": {"id": stage_id, "name": stage_name},
        "jobs": [{"id": job_id, "name": job_name}],
    }


def _make_scorecard(  # noqa: PLR0913
    *,
    scorecard_id: int = 1,
    application_id: int = 1,
    candidate_id: int = 100,
    interviewed_at: datetime | None = None,
    submitted_at: datetime | str | None = "filled",
    interview_name: str = "Technical Interview",
) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    interviewed = interviewed_at or now
    submitted: str | None
    if submitted_at == "filled":
        submitted = _iso(interviewed + timedelta(hours=1))
    elif isinstance(submitted_at, datetime):
        submitted = _iso(submitted_at)
    else:
        submitted = submitted_at
    return {
        "id": scorecard_id,
        "application_id": application_id,
        "candidate_id": candidate_id,
        "interviewed_at": _iso(interviewed),
        "submitted_at": submitted,
        "interview": interview_name,
        "interviewer": {
            "id": 500,
            "first_name": "Interviewer",
            "last_name": "Person",
            "name": "Interviewer Person",
        },
    }


def _make_offer(  # noqa: PLR0913
    *,
    offer_id: int = 1,
    application_id: int = 1,
    candidate_id: int = 100,
    job_id: int = 10,
    status: str = "unresolved",
    created_at: datetime | None = None,
    sent_at: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    return {
        "id": offer_id,
        "application_id": application_id,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "status": status,
        "created_at": _iso(created_at or now),
        "sent_at": sent_at,
    }


@pytest.mark.small
class DescribeNeedsAttention:
    @pytest.mark.anyio
    async def it_returns_empty_when_nothing_needs_attention(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        result = await needs_attention(client=client, now=now)
        assert result["total_items"] == 0
        assert result["items"] == []

    @pytest.mark.anyio
    async def it_returns_structured_response_with_summary(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        result = await needs_attention(client=client, now=now)
        assert "total_items" in result
        assert "items" in result
        assert "summary" in result
        assert "missing_scorecards" in result["summary"]
        assert "stuck_applications" in result["summary"]
        assert "pending_offers" in result["summary"]


@pytest.mark.small
class DescribeStaleApplications:
    @pytest.mark.anyio
    async def it_detects_applications_stuck_beyond_threshold(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=10),
                stage_name="Phone Screen",
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
                {"id": 2, "name": "Onsite", "priority": 1, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        assert result["total_items"] >= 1
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 1
        assert stuck[0]["candidate_name"] == "Jane Doe"
        assert stuck[0]["days_overdue"] == 3  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_excludes_applications_within_threshold(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(days=5)),
        ]
        result = await needs_attention(client=client, days_stale=7, now=now)
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 0

    @pytest.mark.anyio
    async def it_excludes_rejected_applications(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=10),
                status="rejected",
            ),
        ]
        result = await needs_attention(client=client, days_stale=7, now=now)
        assert result["total_items"] == 0

    @pytest.mark.anyio
    async def it_excludes_applications_without_current_stage(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        app = _make_application(last_activity_at=now - timedelta(days=10))
        app["current_stage"] = None
        client.applications = [app]
        result = await needs_attention(client=client, days_stale=7, now=now)
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 0


@pytest.mark.small
class DescribeMissingScoreCards:
    @pytest.mark.anyio
    async def it_detects_unsubmitted_scorecards_past_threshold(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    interviewed_at=now - timedelta(days=3),
                    submitted_at=None,
                ),
            ],
        }
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 1
        assert missing[0]["candidate_name"] == "Jane Doe"
        assert result["summary"]["missing_scorecards"] == 1

    @pytest.mark.anyio
    async def it_excludes_submitted_scorecards(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    interviewed_at=now - timedelta(days=3),
                    submitted_at=now - timedelta(days=2),
                ),
            ],
        }
        result = await needs_attention(client=client, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 0

    @pytest.mark.anyio
    async def it_excludes_scorecards_within_threshold(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    interviewed_at=now - timedelta(hours=12),
                    submitted_at=None,
                ),
            ],
        }
        result = await needs_attention(client=client, scorecard_hours=48, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 0


@pytest.mark.small
class DescribePendingOffers:
    @pytest.mark.anyio
    async def it_detects_unresolved_offers_past_threshold(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.offers = [
            _make_offer(
                created_at=now - timedelta(days=5),
                status="unresolved",
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, now=now)
        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 1
        assert result["summary"]["pending_offers"] == 1

    @pytest.mark.anyio
    async def it_excludes_resolved_offers(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.offers = [
            _make_offer(
                created_at=now - timedelta(days=5),
                status="accepted",
            ),
        ]
        result = await needs_attention(client=client, now=now)
        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 0

    @pytest.mark.anyio
    async def it_excludes_recent_offers_within_threshold(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.offers = [
            _make_offer(
                created_at=now - timedelta(days=1),
                status="unresolved",
            ),
        ]
        result = await needs_attention(client=client, offer_draft_days=2, now=now)
        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 0

    @pytest.mark.anyio
    async def it_uses_sent_at_when_offer_was_sent(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        sent_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")
        client.offers = [
            _make_offer(
                created_at=now - timedelta(days=10),
                status="unresolved",
                sent_at=sent_date,
            ),
        ]
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, offer_sent_days=3, now=now)
        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 1
        assert pending[0]["days_overdue"] == 2  # noqa: PLR2004


@pytest.mark.small
class DescribePriorityScoring:
    @pytest.mark.anyio
    async def it_ranks_missing_scorecards_above_stuck_applications(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                app_id=1,
                candidate_id=100,
                last_activity_at=now - timedelta(days=10),
                stage_id=1,
                stage_name="Phone Screen",
            ),
            _make_application(
                app_id=2,
                candidate_id=200,
                last_activity_at=now - timedelta(hours=1),
                stage_id=1,
                stage_name="Phone Screen",
            ),
        ]
        client.scorecards = {
            1: [],
            2: [
                _make_scorecard(
                    application_id=2,
                    candidate_id=200,
                    interviewed_at=now - timedelta(days=3),
                    submitted_at=None,
                ),
            ],
        }
        client.candidates = {
            100: {"id": 100, "first_name": "Stuck", "last_name": "Person"},
            200: {"id": 200, "first_name": "Missing", "last_name": "Scorecard"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
                {"id": 2, "name": "Onsite", "priority": 1, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        assert result["total_items"] >= 2  # noqa: PLR2004
        assert result["items"][0]["type"] == "missing_scorecard"

    @pytest.mark.anyio
    async def it_computes_priority_score_between_0_and_100(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=10),
                stage_name="Phone Screen",
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
                {"id": 2, "name": "Onsite", "priority": 1, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        for item in result["items"]:
            assert 0 <= item["priority_score"] <= 100  # noqa: PLR2004


@pytest.mark.small
class DescribeFiltering:
    @pytest.mark.anyio
    async def it_filters_by_job_id(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                app_id=1,
                candidate_id=100,
                job_id=10,
                last_activity_at=now - timedelta(days=10),
            ),
            _make_application(
                app_id=2,
                candidate_id=200,
                job_id=20,
                last_activity_at=now - timedelta(days=10),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
            200: {"id": 200, "first_name": "John", "last_name": "Smith"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
            20: [
                {"id": 3, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, job_id=10, days_stale=7, now=now)
        for item in result["items"]:
            assert item["application_id"] == 1

    @pytest.mark.anyio
    async def it_uses_custom_days_stale_threshold(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=5),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result_default = await needs_attention(
            client=client,
            days_stale=7,
            now=now,
        )
        result_custom = await needs_attention(
            client=client,
            days_stale=3,
            now=now,
        )
        default_stuck = [i for i in result_default["items"] if i["type"] == "stuck_application"]
        custom_stuck = [i for i in result_custom["items"] if i["type"] == "stuck_application"]
        assert len(default_stuck) == 0
        assert len(custom_stuck) == 1


@pytest.mark.small
class DescribeEdgeCases:
    @pytest.mark.anyio
    async def it_handles_no_applications(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        result = await needs_attention(client=client, now=now)
        assert result["total_items"] == 0
        assert result["items"] == []

    @pytest.mark.anyio
    async def it_handles_all_healthy_applications(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                app_id=i,
                candidate_id=100 + i,
                last_activity_at=now - timedelta(hours=1),
            )
            for i in range(5)
        ]
        for app in client.applications:
            app_id = app["id"]
            client.scorecards[app_id] = [
                _make_scorecard(
                    application_id=app_id,
                    interviewed_at=now - timedelta(days=1),
                    submitted_at=now - timedelta(hours=12),
                ),
            ]
        result = await needs_attention(client=client, now=now)
        assert result["total_items"] == 0

    @pytest.mark.anyio
    async def it_includes_application_id_in_each_item(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                app_id=42,
                last_activity_at=now - timedelta(days=10),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        for item in result["items"]:
            assert "application_id" in item
            assert item["application_id"] == 42  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_includes_candidate_id_in_each_item(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                candidate_id=99,
                last_activity_at=now - timedelta(days=10),
            ),
        ]
        client.candidates = {
            99: {"id": 99, "first_name": "Test", "last_name": "User"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        for item in result["items"]:
            assert item["candidate_id"] == 99  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_includes_job_name_in_each_item(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                job_name="Backend Engineer",
                last_activity_at=now - timedelta(days=10),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        for item in result["items"]:
            assert item["job_name"] == "Backend Engineer"

    @pytest.mark.anyio
    async def it_includes_suggested_action_in_each_item(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=10),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        for item in result["items"]:
            assert "suggested_action" in item
            assert len(item["suggested_action"]) > 0

    @pytest.mark.anyio
    async def it_includes_detail_in_each_item(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=10),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        for item in result["items"]:
            assert "detail" in item
            assert len(item["detail"]) > 0

    @pytest.mark.anyio
    async def it_deduplicates_no_activity_against_stuck_application(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=20),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [
                {"id": 1, "name": "Phone Screen", "priority": 0, "active": True},
            ],
        }
        result = await needs_attention(
            client=client,
            days_stale=7,
            no_activity_days=14,
            now=now,
        )
        app_types = [i["type"] for i in result["items"] if i["application_id"] == 1]
        assert "no_activity" in app_types
        assert "stuck_application" not in app_types
