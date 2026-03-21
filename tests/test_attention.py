"""Tests for the needs_attention tool."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from greenhouse_mcp.tools.attention import (
    _compute_priority_score,
    _get_stage_position,
    needs_attention,
)


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
        created_after: str | None = None,  # noqa: ARG002
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
        status: str | None = None,  # noqa: ARG002
        department_id: int | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return list(self.jobs.values())

    async def get_candidates(
        self,
        *,
        job_id: int | None = None,  # noqa: ARG002
        email: str | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return list(self.candidates.values())

    async def get_scheduled_interviews(
        self,
        *,
        application_id: int | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return []

    async def get_activity_feed(self, candidate_id: int) -> dict[str, Any]:  # noqa: ARG002
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
        assert stuck[0]["days_overdue"] == 3

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
        assert pending[0]["days_overdue"] == 2


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
        assert result["total_items"] >= 2
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
            assert 0 <= item["priority_score"] <= 100


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
            assert item["application_id"] == 42

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
            assert item["candidate_id"] == 99

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
    async def it_skips_offers_with_missing_created_at(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.offers = [
            _make_offer(
                status="unresolved",
                created_at=now - timedelta(days=5),
            ),
        ]
        # Remove created_at and sent_at to trigger the guard
        client.offers[0]["created_at"] = ""
        client.offers[0]["sent_at"] = None
        result = await needs_attention(client=client, now=now)
        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 0

    @pytest.mark.anyio
    async def it_skips_offers_with_no_created_at_key(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.offers = [
            _make_offer(
                status="unresolved",
                created_at=now - timedelta(days=5),
            ),
        ]
        # Remove the key entirely
        del client.offers[0]["created_at"]
        client.offers[0]["sent_at"] = None
        result = await needs_attention(client=client, now=now)
        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 0

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
    async def it_skips_stuck_application_with_null_last_activity(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        app = _make_application(last_activity_at=now - timedelta(days=10))
        app["last_activity_at"] = None
        client.applications = [app]
        result = await needs_attention(client=client, days_stale=7, now=now)
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 0

    @pytest.mark.anyio
    async def it_skips_no_activity_with_null_last_activity(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        app = _make_application(last_activity_at=now - timedelta(days=20))
        app["last_activity_at"] = None
        client.applications = [app]
        result = await needs_attention(
            client=client,
            no_activity_days=14,
            now=now,
        )
        no_act = [i for i in result["items"] if i["type"] == "no_activity"]
        assert len(no_act) == 0

    @pytest.mark.anyio
    async def it_skips_scorecards_with_null_interviewed_at(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        sc = _make_scorecard(
            application_id=1,
            interviewed_at=now - timedelta(days=3),
            submitted_at=None,
        )
        sc["interviewed_at"] = None
        client.scorecards = {1: [sc]}
        result = await needs_attention(client=client, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 0

    @pytest.mark.anyio
    async def it_reuses_candidate_cache_across_multiple_stuck_apps(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                app_id=1,
                candidate_id=100,
                last_activity_at=now - timedelta(days=10),
            ),
            _make_application(
                app_id=2,
                candidate_id=100,
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
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 2
        assert all(s["candidate_name"] == "Jane Doe" for s in stuck)

    @pytest.mark.anyio
    async def it_reuses_stages_cache_across_multiple_stuck_apps(self) -> None:
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
                job_id=10,
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
                {"id": 2, "name": "Onsite", "priority": 1, "active": True},
            ],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 2

    @pytest.mark.anyio
    async def it_uses_stage_position_zero_when_stage_not_found(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                stage_id=999,
                stage_name="Unknown Stage",
                last_activity_at=now - timedelta(days=10),
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
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 1
        assert 0 <= stuck[0]["priority_score"] <= 100

    @pytest.mark.anyio
    async def it_reuses_candidate_cache_in_missing_scorecards(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                app_id=1,
                candidate_id=100,
                last_activity_at=now - timedelta(hours=1),
            ),
            _make_application(
                app_id=2,
                candidate_id=100,
                last_activity_at=now - timedelta(hours=1),
            ),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    candidate_id=100,
                    interviewed_at=now - timedelta(days=3),
                    submitted_at=None,
                ),
            ],
            2: [
                _make_scorecard(
                    scorecard_id=2,
                    application_id=2,
                    candidate_id=100,
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
        assert len(missing) == 2
        assert all(m["candidate_name"] == "Jane Doe" for m in missing)

    @pytest.mark.anyio
    async def it_resolves_candidate_and_job_for_pending_offers(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                app_id=1,
                candidate_id=100,
                job_id=10,
                job_name="Backend Engineer",
                last_activity_at=now - timedelta(hours=1),
            ),
        ]
        client.offers = [
            _make_offer(
                application_id=1,
                candidate_id=100,
                job_id=10,
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
        assert pending[0]["candidate_name"] == "Jane Doe"
        assert pending[0]["job_name"] == "Backend Engineer"

    @pytest.mark.anyio
    async def it_handles_pending_offer_without_matching_application(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = []
        client.offers = [
            _make_offer(
                application_id=999,
                candidate_id=100,
                job_id=10,
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
        assert pending[0]["job_name"] == "Unknown"

    @pytest.mark.anyio
    async def it_reuses_caches_across_no_activity_detection(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                app_id=1,
                candidate_id=100,
                last_activity_at=now - timedelta(days=20),
            ),
            _make_application(
                app_id=2,
                candidate_id=100,
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
            no_activity_days=14,
            days_stale=100,
            now=now,
        )
        no_act = [i for i in result["items"] if i["type"] == "no_activity"]
        assert len(no_act) == 2
        assert all(n["candidate_name"] == "Jane Doe" for n in no_act)

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


@pytest.mark.small
class DescribeComputePriorityScore:
    """Triangulation tests for _compute_priority_score (lines 67-69).

    Kills mutants: / vs *, * vs /, + vs -, boundary checks on total_stages.
    """

    def it_computes_overdue_score_with_division_not_multiplication(self) -> None:
        """Line 67: (days_overdue / threshold) * 50.

        With days_overdue=2, threshold=4: division gives 0.5*50=25.
        Mutant (* instead of /): 2*4=8, 8*50=400, min(100,400)=100.
        Mutant (/ instead of *): 0.5/50=0.01, min(100,0.01)=0.01.
        """
        score = _compute_priority_score(
            severity=0,
            days_overdue=2,
            threshold=4,
            stage_index=0,
            total_stages=0,
        )
        # severity=0 -> 0*0.4=0, stage_score=0 (total_stages=0)
        # overdue_score = min(100, (2/4)*50) = min(100, 25) = 25
        # result = 0 + 25*0.4 + 0 = 10.0
        assert score == pytest.approx(10.0)

    def it_computes_overdue_score_multiplication_not_division(self) -> None:
        """Line 67: second * mutant — (ratio) * 50 not (ratio) / 50."""
        score = _compute_priority_score(
            severity=0,
            days_overdue=6,
            threshold=3,
            stage_index=0,
            total_stages=0,
        )
        # overdue_score = min(100, (6/3)*50) = min(100, 100) = 100
        # result = 0 + 100*0.4 + 0 = 40.0
        assert score == pytest.approx(40.0)

    def it_uses_zero_stage_score_when_total_stages_is_zero(self) -> None:
        """Line 68: total_stages > 0 boundary — 0 gives else branch (0.0).

        Mutant (>= instead of >): total_stages=0 would enter the if-branch
        and compute (0/max(0,1))*100 = 0, same result. So we need total_stages=0
        with nonzero stage_index to detect >= mutant... but stage_index doesn't
        matter when total_stages=0 because we go to else. We need to verify
        the else branch returns 0.0 specifically.

        Mutant (< instead of >): total_stages=0 would satisfy < 0? No, 0 < 0 is false.
        So for total_stages=1, < would be false (1 < 0 is false), giving 0.0.
        """
        score = _compute_priority_score(
            severity=0,
            days_overdue=0,
            threshold=1,
            stage_index=5,
            total_stages=0,
        )
        # total_stages=0 -> stage_score=0.0 (else branch)
        # result = 0 + 0 + 0 = 0.0
        assert score == pytest.approx(0.0)

    def it_computes_nonzero_stage_score_when_total_stages_is_positive(self) -> None:
        """Line 68: with total_stages=1, > 0 is true.

        Mutant (< instead of >): 1 < 0 is false -> stage_score=0.0.
        Mutant (>= with boundary +1): total_stages >= 1 is true, same. Need separate.

        stage_index=3, total_stages=4: (3/4)*100 = 75.
        Mutant (/ to *): (3*4)*100 = 1200 -> different.
        Mutant (* to /): (3/4)/100 = 0.0075 -> different.
        """
        score = _compute_priority_score(
            severity=0,
            days_overdue=0,
            threshold=1,
            stage_index=3,
            total_stages=4,
        )
        # stage_score = (3/4)*100 = 75
        # result = 0 + 0 + 75*0.2 = 15.0
        assert score == pytest.approx(15.0)

    def it_combines_all_three_factors_with_correct_weights(self) -> None:
        """Line 69: severity*0.4 + overdue*0.4 + stage*0.2.

        Mutant (+ to -): would subtract instead of add.
        Mutant (* to /): severity/0.4 = 250 instead of 40.
        """
        score = _compute_priority_score(
            severity=100,
            days_overdue=4,
            threshold=2,
            stage_index=1,
            total_stages=2,
        )
        # overdue_score = min(100, (4/2)*50) = min(100, 100) = 100
        # stage_score = (1/2)*100 = 50
        # result = 100*0.4 + 100*0.4 + 50*0.2 = 40 + 40 + 10 = 90.0
        assert score == pytest.approx(90.0)

    def it_applies_severity_weight_as_multiplication(self) -> None:
        """Line 69: severity * 0.4, not severity / 0.4.

        severity=50: 50*0.4=20 vs 50/0.4=125.
        """
        score = _compute_priority_score(
            severity=50,
            days_overdue=0,
            threshold=1,
            stage_index=0,
            total_stages=0,
        )
        # result = 50*0.4 + 0 + 0 = 20.0
        assert score == pytest.approx(20.0)

    def it_applies_overdue_weight_as_multiplication(self) -> None:
        """Line 69: overdue_score * 0.4, not overdue_score / 0.4."""
        score = _compute_priority_score(
            severity=0,
            days_overdue=1,
            threshold=1,
            stage_index=0,
            total_stages=0,
        )
        # overdue_score = min(100, (1/1)*50) = 50
        # result = 0 + 50*0.4 + 0 = 20.0
        assert score == pytest.approx(20.0)

    def it_applies_stage_weight_as_multiplication(self) -> None:
        """Line 69: stage_score * 0.2, not stage_score / 0.2."""
        score = _compute_priority_score(
            severity=0,
            days_overdue=0,
            threshold=1,
            stage_index=1,
            total_stages=1,
        )
        # stage_score = (1/1)*100 = 100
        # result = 0 + 0 + 100*0.2 = 20.0
        assert score == pytest.approx(20.0)

    def it_adds_not_subtracts_overdue_and_stage_components(self) -> None:
        """Line 69: + not - between components.

        If subtraction: 40 - 40 - 10 = -10 vs 40 + 40 + 10 = 90.
        """
        score = _compute_priority_score(
            severity=100,
            days_overdue=4,
            threshold=2,
            stage_index=1,
            total_stages=2,
        )
        assert score > 0
        assert score == pytest.approx(90.0)


@pytest.mark.small
class DescribeGetStagePosition:
    """Triangulation tests for _get_stage_position (lines 85, 89)."""

    def it_defaults_inactive_stages_to_active_true(self) -> None:
        """Line 85: s.get("active", True) — default True not False.

        If mutated to False, stages without 'active' key would be excluded.
        """
        stages = [
            {"id": 1, "priority": 0},  # no "active" key -> default True
            {"id": 2, "priority": 1, "active": True},
        ]
        idx, total = _get_stage_position(1, stages)
        # Both stages included (default True), total=2
        assert total == 2
        assert idx == 0

    def it_excludes_explicitly_inactive_stages(self) -> None:
        """Line 85: active=False stages are excluded."""
        stages = [
            {"id": 1, "priority": 0, "active": True},
            {"id": 2, "priority": 1, "active": False},
            {"id": 3, "priority": 2, "active": True},
        ]
        idx, total = _get_stage_position(3, stages)
        assert total == 2
        # Stage 3 is second among active stages (id=1 at priority 0, id=3 at priority 2)
        assert idx == 1

    def it_returns_matching_stage_on_equality(self) -> None:
        """Line 89: == not !=.

        If mutated to !=, first non-matching stage would be returned.
        """
        stages = [
            {"id": 10, "priority": 0, "active": True},
            {"id": 20, "priority": 1, "active": True},
            {"id": 30, "priority": 2, "active": True},
        ]
        idx, total = _get_stage_position(20, stages)
        assert idx == 1
        assert total == 3

    def it_returns_zero_index_for_first_stage(self) -> None:
        """Line 89: ensure exact match returns correct index, not just any."""
        stages = [
            {"id": 5, "priority": 0, "active": True},
            {"id": 10, "priority": 1, "active": True},
        ]
        idx, total = _get_stage_position(5, stages)
        assert idx == 0
        assert total == 2


@pytest.mark.small
class DescribeStuckApplicationThresholdBoundary:
    """Line 130: elapsed <= threshold — test exact boundary."""

    @pytest.mark.anyio
    async def it_excludes_application_at_exact_threshold(self) -> None:
        """elapsed == threshold (7 days exactly) -> <= is True -> skip.

        Mutant (< instead of <=): 7 < 7 is False -> would NOT skip.
        Uses microsecond=0 to avoid _iso() truncation creating sub-second drift.
        """
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC).replace(microsecond=0)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=7),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 0

    @pytest.mark.anyio
    async def it_includes_application_one_second_past_threshold(self) -> None:
        """elapsed just over threshold -> <= is False -> include."""
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=7, seconds=1),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, days_stale=7, now=now)
        stuck = [i for i in result["items"] if i["type"] == "stuck_application"]
        assert len(stuck) == 1


@pytest.mark.small
class DescribeMissingScorecardThresholdBoundary:
    """Line 214: elapsed <= threshold — test exact boundary."""

    @pytest.mark.anyio
    async def it_excludes_scorecard_at_exact_threshold(self) -> None:
        """elapsed == 48h exactly -> <= is True -> skip.

        Mutant (< instead of <=): 48 < 48 is False -> would NOT skip.
        Uses microsecond=0 to avoid _iso() truncation creating sub-second drift.
        """
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC).replace(microsecond=0)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    interviewed_at=now - timedelta(hours=48),
                    submitted_at=None,
                ),
            ],
        }
        result = await needs_attention(client=client, scorecard_hours=48, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 0

    @pytest.mark.anyio
    async def it_includes_scorecard_one_second_past_threshold(self) -> None:
        """elapsed just over 48h -> <= is False -> include."""
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    interviewed_at=now - timedelta(hours=48, seconds=1),
                    submitted_at=None,
                ),
            ],
        }
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, scorecard_hours=48, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 1


@pytest.mark.small
class DescribeMissingScorecardDaysOverdue:
    """Lines 217, 240: days_overdue and threshold arithmetic for scorecards."""

    @pytest.mark.anyio
    async def it_computes_days_overdue_with_subtraction_and_integer_division(self) -> None:
        """Line 217: max(1, elapsed.days - (scorecard_hours // 24)).

        scorecard_hours=48 -> 48//24=2.
        elapsed=5 days -> days_overdue = max(1, 5 - 2) = 3.
        Mutant (- to +): max(1, 5 + 2) = 7.
        Mutant (// to /): 48/24=2.0 (same for even). Use odd hours.
        """
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    interviewed_at=now - timedelta(days=5),
                    submitted_at=None,
                ),
            ],
        }
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, scorecard_hours=48, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 1
        assert missing[0]["days_overdue"] == 3

    @pytest.mark.anyio
    async def it_uses_integer_division_for_scorecard_hours_to_days(self) -> None:
        """Lines 217, 240: scorecard_hours // 24.

        scorecard_hours=50 -> 50//24=2 (integer division).
        Mutant (// to /): 50/24=2.0833... -> different in max() and priority.

        elapsed=4 days -> days_overdue = max(1, 4 - 2) = 2.
        threshold = max(1, 50//24) = max(1, 2) = 2.
        Mutant: max(1, 50/24) = max(1, 2.083) = 2.083.

        Priority differs because threshold=2 vs 2.083 changes the overdue_score.
        """
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    interviewed_at=now - timedelta(days=4),
                    submitted_at=None,
                ),
            ],
        }
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, scorecard_hours=50, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 1
        # days_overdue = max(1, 4 - (50//24)) = max(1, 4-2) = 2
        assert missing[0]["days_overdue"] == 2

    @pytest.mark.anyio
    async def it_uses_subtraction_not_addition_for_days_overdue(self) -> None:
        """Line 217: elapsed.days - (scorecard_hours // 24).

        Mutant (- to +): would give much larger days_overdue.
        scorecard_hours=72, elapsed=4 days.
        Correct: max(1, 4 - 3) = 1.
        Mutant: max(1, 4 + 3) = 7.
        """
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.scorecards = {
            1: [
                _make_scorecard(
                    application_id=1,
                    interviewed_at=now - timedelta(days=4),
                    submitted_at=None,
                ),
            ],
        }
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, scorecard_hours=72, now=now)
        missing = [i for i in result["items"] if i["type"] == "missing_scorecard"]
        assert len(missing) == 1
        assert missing[0]["days_overdue"] == 1


@pytest.mark.small
class DescribePendingOfferThresholdBoundary:
    """Line 305: elapsed <= threshold — test exact boundary."""

    @pytest.mark.anyio
    async def it_excludes_offer_at_exact_threshold(self) -> None:
        """elapsed == threshold (2 days exactly) -> <= True -> skip.

        Mutant (< instead of <=): 2 < 2 is False -> would NOT skip.
        Uses microsecond=0 to avoid _iso() truncation creating sub-second drift.
        """
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC).replace(microsecond=0)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.offers = [
            _make_offer(
                created_at=now - timedelta(days=2),
                status="unresolved",
            ),
        ]
        result = await needs_attention(client=client, offer_draft_days=2, now=now)
        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 0

    @pytest.mark.anyio
    async def it_includes_offer_one_second_past_threshold(self) -> None:
        """elapsed just over 2 days -> <= False -> include."""
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(last_activity_at=now - timedelta(hours=1)),
        ]
        client.offers = [
            _make_offer(
                created_at=now - timedelta(days=2, seconds=1),
                status="unresolved",
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, offer_draft_days=2, now=now)
        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 1


@pytest.mark.small
class DescribeNoActivityThresholdBoundary:
    """Lines 401, 405: elapsed <= threshold and days_overdue arithmetic."""

    @pytest.mark.anyio
    async def it_excludes_application_at_exact_no_activity_threshold(self) -> None:
        """Line 401: elapsed == threshold (14 days) -> <= True -> skip.

        Mutant (< instead of <=): 14 < 14 is False -> would NOT skip.
        Uses microsecond=0 to avoid _iso() truncation creating sub-second drift.
        """
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC).replace(microsecond=0)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=14),
            ),
        ]
        result = await needs_attention(client=client, days_stale=100, no_activity_days=14, now=now)
        no_act = [i for i in result["items"] if i["type"] == "no_activity"]
        assert len(no_act) == 0

    @pytest.mark.anyio
    async def it_includes_application_one_second_past_no_activity_threshold(self) -> None:
        """Line 401: elapsed just over 14 days -> <= False -> include."""
        client = FakeGreenhouseClient()
        now = datetime.now(tz=UTC)
        client.applications = [
            _make_application(
                last_activity_at=now - timedelta(days=14, seconds=1),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, days_stale=100, no_activity_days=14, now=now)
        no_act = [i for i in result["items"] if i["type"] == "no_activity"]
        assert len(no_act) == 1

    @pytest.mark.anyio
    async def it_computes_no_activity_days_overdue_with_subtraction(self) -> None:
        """Line 405: days_overdue = (elapsed - threshold).days.

        Mutant (- to +): (elapsed + threshold).days would be much larger.
        elapsed=20 days, threshold=14: (20d - 14d).days = 6.
        Mutant: (20d + 14d).days = 34.
        """
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
            10: [{"id": 1, "name": "Screen", "priority": 0, "active": True}],
        }
        result = await needs_attention(client=client, days_stale=100, no_activity_days=14, now=now)
        no_act = [i for i in result["items"] if i["type"] == "no_activity"]
        assert len(no_act) == 1
        assert no_act[0]["days_overdue"] == 6


@pytest.mark.small
class DescribeCacheHitBranches:
    """Cover the cache-hit branches for candidate_cache and stages_cache."""

    @pytest.mark.anyio
    async def it_reuses_cached_candidate_and_stages_on_second_offer(self) -> None:
        """Lines 319->321, 326->328: second pending offer for same candidate hits cache."""
        now = datetime.now(tz=UTC)
        client = FakeGreenhouseClient()
        client.applications = [
            _make_application(app_id=1, candidate_id=100),
        ]
        # Two pending offers from same candidate/job → second hits cache
        client.offers = [
            _make_offer(
                offer_id=1,
                sent_at=(now - timedelta(days=5)).strftime("%Y-%m-%d"),
                created_at=now - timedelta(days=6),
            ),
            _make_offer(
                offer_id=2,
                sent_at=(now - timedelta(days=8)).strftime("%Y-%m-%d"),
                created_at=now - timedelta(days=9),
            ),
        ]
        client.candidates = {
            100: {"id": 100, "first_name": "Jane", "last_name": "Doe"},
        }
        client.job_stages = {
            10: [{"id": 1, "name": "Phone Screen", "priority": 0, "active": True}],
        }

        result = await needs_attention(client=client, days_stale=100, now=now)

        pending = [i for i in result["items"] if i["type"] == "pending_offer"]
        assert len(pending) == 2
        assert all(i["candidate_name"] == "Jane Doe" for i in pending)
