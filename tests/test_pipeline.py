"""Tests for the pipeline_health tool."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from greenhouse_mcp.exceptions import NotFoundError
from greenhouse_mcp.tools.pipeline import pipeline_health


def _iso(days_ago: int) -> str:
    return (datetime.now(tz=UTC) - timedelta(days=days_ago)).isoformat()


class FakeGreenhouseClient:
    """Test double implementing GreenhousePort for pipeline tests."""

    def __init__(
        self,
        *,
        jobs: list[dict[str, Any]] | None = None,
        stages: dict[int, list[dict[str, Any]]] | None = None,
        applications: list[dict[str, Any]] | None = None,
        raise_on_get_job: Exception | None = None,
    ) -> None:
        self._jobs = jobs or []
        self._stages = stages or {}
        self._applications = applications or []
        self._raise_on_get_job = raise_on_get_job

    async def get_jobs(
        self,
        *,
        status: str | None = None,
        department_id: int | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        result = self._jobs
        if status:
            result = [j for j in result if j.get("status") == status]
        return result

    async def get_job(self, job_id: int) -> dict[str, Any]:
        if self._raise_on_get_job:
            raise self._raise_on_get_job
        for job in self._jobs:
            if job["id"] == job_id:
                return job
        msg = f"Job {job_id} not found"
        raise NotFoundError(msg)

    async def get_job_stages(self, job_id: int) -> list[dict[str, Any]]:
        return self._stages.get(job_id, [])

    async def get_applications(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        created_after: str | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        result = self._applications
        if job_id:
            result = [a for a in result if any(j["id"] == job_id for j in a.get("jobs", []))]
        if status:
            result = [a for a in result if a.get("status") == status]
        return result

    async def get_candidate(self, candidate_id: int) -> dict[str, Any]:
        return {"id": candidate_id}

    async def get_candidates(
        self,
        *,
        job_id: int | None = None,  # noqa: ARG002
        email: str | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return []

    async def get_scorecards(self, application_id: int) -> list[dict[str, Any]]:  # noqa: ARG002
        return []

    async def get_scheduled_interviews(
        self,
        *,
        application_id: int | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return []

    async def get_offers(
        self,
        *,
        application_id: int | None = None,  # noqa: ARG002
        status: str | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return []

    async def get_activity_feed(self, candidate_id: int) -> dict[str, Any]:  # noqa: ARG002
        return {"notes": [], "emails": [], "activities": []}


def _make_application(  # noqa: PLR0913
    app_id: int,
    job_id: int,
    stage_id: int | None,
    stage_name: str | None,
    days_since_activity: int,
    *,
    prospect: bool = False,
    status: str = "active",
) -> dict[str, Any]:
    current_stage = {"id": stage_id, "name": stage_name} if stage_id is not None else None
    return {
        "id": app_id,
        "status": status,
        "prospect": prospect,
        "current_stage": current_stage,
        "last_activity_at": _iso(days_since_activity),
        "jobs": [{"id": job_id, "name": f"Job {job_id}"}],
    }


def _make_stage(
    stage_id: int,
    name: str,
    priority: int,
    *,
    active: bool = True,
) -> dict[str, Any]:
    return {
        "id": stage_id,
        "name": name,
        "priority": priority,
        "active": active,
        "job_id": 100,
        "interviews": [],
    }


@pytest.mark.small
class DescribePipelineHealth:
    """pipeline_health returns per-stage counts and staleness for a job."""

    @pytest.mark.anyio
    async def it_returns_stage_counts_for_a_single_job(self) -> None:
        stages = [
            _make_stage(1, "Application Review", 0),
            _make_stage(2, "Phone Screen", 1),
            _make_stage(3, "Technical Interview", 2),
            _make_stage(4, "Onsite", 3),
        ]
        applications = [
            _make_application(101, 100, 1, "Application Review", 2),
            _make_application(102, 100, 1, "Application Review", 3),
            _make_application(103, 100, 1, "Application Review", 1),
            _make_application(104, 100, 2, "Phone Screen", 5),
            _make_application(105, 100, 2, "Phone Screen", 4),
            _make_application(106, 100, 3, "Technical Interview", 10),
            _make_application(107, 100, 3, "Technical Interview", 12),
            _make_application(108, 100, 3, "Technical Interview", 8),
            _make_application(109, 100, 4, "Onsite", 1),
            _make_application(110, 100, 4, "Onsite", 2),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Software Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["job_id"] == 100
        assert result["job_name"] == "Software Engineer"
        assert result["total_active"] == 10
        assert len(result["stages"]) == 4
        stage_names = [s["stage_name"] for s in result["stages"]]
        assert stage_names == [
            "Application Review",
            "Phone Screen",
            "Technical Interview",
            "Onsite",
        ]
        assert result["stages"][0]["count"] == 3
        assert result["stages"][1]["count"] == 2
        assert result["stages"][2]["count"] == 3
        assert result["stages"][3]["count"] == 2

    @pytest.mark.anyio
    async def it_computes_share_for_each_stage(self) -> None:
        stages = [
            _make_stage(1, "Stage A", 0),
            _make_stage(2, "Stage B", 1),
        ]
        applications = [
            _make_application(1, 100, 1, "Stage A", 1),
            _make_application(2, 100, 1, "Stage A", 1),
            _make_application(3, 100, 1, "Stage A", 1),
            _make_application(4, 100, 2, "Stage B", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["stages"][0]["share"] == pytest.approx(0.75)
        assert result["stages"][1]["share"] == pytest.approx(0.25)

    @pytest.mark.anyio
    async def it_computes_avg_days_since_activity(self) -> None:
        stages = [_make_stage(1, "Review", 0)]
        applications = [
            _make_application(1, 100, 1, "Review", 3),
            _make_application(2, 100, 1, "Review", 9),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["stages"][0]["avg_days_since_activity"] == pytest.approx(6.0, abs=1.0)

    @pytest.mark.anyio
    async def it_counts_cold_applications(self) -> None:
        stages = [_make_stage(1, "Review", 0)]
        applications = [
            _make_application(1, 100, 1, "Review", 1),
            _make_application(2, 100, 1, "Review", 10),
            _make_application(3, 100, 1, "Review", 14),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, staleness_days=7, client=client)

        assert result["stages"][0]["cold_count"] == 2

    @pytest.mark.anyio
    async def it_sorts_stages_by_priority(self) -> None:
        stages = [
            _make_stage(3, "Last", 99),
            _make_stage(1, "First", 0),
            _make_stage(2, "Middle", 50),
        ]
        applications = [
            _make_application(1, 100, 1, "First", 1),
            _make_application(2, 100, 2, "Middle", 1),
            _make_application(3, 100, 3, "Last", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert [s["stage_name"] for s in result["stages"]] == [
            "First",
            "Middle",
            "Last",
        ]

    @pytest.mark.anyio
    async def it_excludes_prospect_applications(self) -> None:
        stages = [_make_stage(1, "Review", 0)]
        applications = [
            _make_application(1, 100, 1, "Review", 1),
            _make_application(2, 100, 1, "Review", 1, prospect=True),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["total_active"] == 1
        assert result["stages"][0]["count"] == 1


@pytest.mark.small
class DescribeBottleneckDetection:
    """Bottleneck detection uses share threshold and staleness."""

    @pytest.mark.anyio
    async def it_flags_high_severity_when_share_and_staleness_exceed_thresholds(
        self,
    ) -> None:
        stages = [
            _make_stage(1, "Bottleneck Stage", 0),
            _make_stage(2, "Other", 1),
        ]
        applications = [
            _make_application(1, 100, 1, "Bottleneck Stage", 10),
            _make_application(2, 100, 1, "Bottleneck Stage", 14),
            _make_application(3, 100, 1, "Bottleneck Stage", 12),
            _make_application(4, 100, 2, "Other", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        bottleneck_stage = result["stages"][0]
        assert bottleneck_stage["is_bottleneck"] is True
        assert bottleneck_stage["severity"] == "HIGH"
        assert "Bottleneck Stage" in result["bottlenecks"]

    @pytest.mark.anyio
    async def it_flags_medium_severity_when_share_high_but_not_stale(
        self,
    ) -> None:
        stages = [
            _make_stage(1, "Busy Stage", 0),
            _make_stage(2, "Other", 1),
        ]
        applications = [
            _make_application(1, 100, 1, "Busy Stage", 1),
            _make_application(2, 100, 1, "Busy Stage", 2),
            _make_application(3, 100, 1, "Busy Stage", 1),
            _make_application(4, 100, 2, "Other", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        busy_stage = result["stages"][0]
        assert busy_stage["is_bottleneck"] is True
        assert busy_stage["severity"] == "MEDIUM"

    @pytest.mark.anyio
    async def it_flags_low_severity_when_stale_but_share_below_threshold(
        self,
    ) -> None:
        stages = [
            _make_stage(1, "Stale Stage", 0),
            _make_stage(2, "Other", 1),
            _make_stage(3, "Other2", 2),
        ]
        applications = [
            _make_application(1, 100, 1, "Stale Stage", 14),
            _make_application(2, 100, 2, "Other", 1),
            _make_application(3, 100, 2, "Other", 1),
            _make_application(4, 100, 3, "Other2", 1),
            _make_application(5, 100, 3, "Other2", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        stale_stage = result["stages"][0]
        assert stale_stage["is_bottleneck"] is False
        assert stale_stage["severity"] == "LOW"

    @pytest.mark.anyio
    async def it_assigns_none_severity_when_healthy(self) -> None:
        stages = [
            _make_stage(1, "A", 0),
            _make_stage(2, "B", 1),
            _make_stage(3, "C", 2),
            _make_stage(4, "D", 3),
        ]
        applications = [
            _make_application(1, 100, 1, "A", 1),
            _make_application(2, 100, 2, "B", 1),
            _make_application(3, 100, 3, "C", 1),
            _make_application(4, 100, 4, "D", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        for stage in result["stages"]:
            assert stage["is_bottleneck"] is False
            assert stage["severity"] is None
        assert result["bottlenecks"] == []

    @pytest.mark.anyio
    async def it_uses_custom_bottleneck_threshold(self) -> None:
        stages = [
            _make_stage(1, "A", 0),
            _make_stage(2, "B", 1),
        ]
        applications = [
            _make_application(1, 100, 1, "A", 1),
            _make_application(2, 100, 1, "A", 1),
            _make_application(3, 100, 2, "B", 1),
            _make_application(4, 100, 2, "B", 1),
            _make_application(5, 100, 2, "B", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result_strict = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.50,
            client=client,
        )
        result_relaxed = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.70,
            client=client,
        )

        assert result_strict["stages"][1]["is_bottleneck"] is True
        assert result_relaxed["stages"][1]["is_bottleneck"] is False

    @pytest.mark.anyio
    async def it_uses_custom_staleness_days(self) -> None:
        stages = [_make_stage(1, "A", 0)]
        applications = [
            _make_application(1, 100, 1, "A", 5),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result_strict = await pipeline_health(job_id=100, staleness_days=3, client=client)
        result_relaxed = await pipeline_health(job_id=100, staleness_days=7, client=client)

        assert result_strict["stages"][0]["cold_count"] == 1
        assert result_relaxed["stages"][0]["cold_count"] == 0

    @pytest.mark.anyio
    async def it_triggers_bottleneck_when_share_exactly_equals_threshold(self) -> None:
        """Line 42: share >= threshold must trigger at equality, not just above."""
        # 3 apps in stage A, 7 in stage B => share of A = 3/10 = 0.30 exactly
        stages = [
            _make_stage(1, "A", 0),
            _make_stage(2, "B", 1),
        ]
        applications = [
            _make_application(1, 100, 1, "A", 1),
            _make_application(2, 100, 1, "A", 1),
            _make_application(3, 100, 1, "A", 1),
            _make_application(4, 100, 2, "B", 1),
            _make_application(5, 100, 2, "B", 1),
            _make_application(6, 100, 2, "B", 1),
            _make_application(7, 100, 2, "B", 1),
            _make_application(8, 100, 2, "B", 1),
            _make_application(9, 100, 2, "B", 1),
            _make_application(10, 100, 2, "B", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        stage_a = result["stages"][0]
        assert stage_a["share"] == pytest.approx(0.30)
        assert stage_a["severity"] == "MEDIUM"
        assert stage_a["is_bottleneck"] is True

    @pytest.mark.anyio
    async def it_does_not_trigger_bottleneck_when_share_just_below_threshold(self) -> None:
        """Line 42: share < threshold must NOT trigger bottleneck."""
        # 2 apps in stage A, 7 in stage B => share of A = 2/9 ≈ 0.222
        stages = [
            _make_stage(1, "A", 0),
            _make_stage(2, "B", 1),
        ]
        applications = [
            _make_application(1, 100, 1, "A", 1),
            _make_application(2, 100, 1, "A", 1),
            _make_application(3, 100, 2, "B", 1),
            _make_application(4, 100, 2, "B", 1),
            _make_application(5, 100, 2, "B", 1),
            _make_application(6, 100, 2, "B", 1),
            _make_application(7, 100, 2, "B", 1),
            _make_application(8, 100, 2, "B", 1),
            _make_application(9, 100, 2, "B", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        stage_a = result["stages"][0]
        assert stage_a["share"] < 0.30
        assert stage_a["severity"] is None
        assert stage_a["is_bottleneck"] is False

    @pytest.mark.anyio
    async def it_triggers_staleness_when_stale_fraction_exactly_equals_threshold(self) -> None:
        """Line 43: stale_fraction >= 0.50 must trigger at equality."""
        # 2 apps in one stage: 1 stale, 1 fresh => stale_fraction = 1/2 = 0.50 exactly
        # Low share to isolate staleness -> severity LOW
        stages = [
            _make_stage(1, "StaleTest", 0),
            _make_stage(2, "Other1", 1),
            _make_stage(3, "Other2", 2),
            _make_stage(4, "Other3", 3),
        ]
        applications = [
            _make_application(1, 100, 1, "StaleTest", 10),  # stale (>=7)
            _make_application(2, 100, 1, "StaleTest", 1),  # fresh
            _make_application(3, 100, 2, "Other1", 1),
            _make_application(4, 100, 3, "Other2", 1),
            _make_application(5, 100, 4, "Other3", 1),
            _make_application(6, 100, 4, "Other3", 1),
            _make_application(7, 100, 4, "Other3", 1),
            _make_application(8, 100, 4, "Other3", 1),
            _make_application(9, 100, 4, "Other3", 1),
            _make_application(10, 100, 4, "Other3", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        stale_stage = result["stages"][0]
        assert stale_stage["cold_count"] == 1
        assert stale_stage["count"] == 2
        # stale_fraction = 1/2 = 0.50, share = 2/10 = 0.20 (below threshold)
        # So severity should be LOW (stale but not concentrated)
        assert stale_stage["severity"] == "LOW"

    @pytest.mark.anyio
    async def it_does_not_trigger_staleness_when_stale_fraction_just_below_threshold(self) -> None:
        """Line 43: stale_fraction < 0.50 must NOT flag as stale."""
        # 3 apps: 1 stale, 2 fresh => stale_fraction = 1/3 ≈ 0.333
        # Low share to isolate staleness
        stages = [
            _make_stage(1, "NotStale", 0),
            _make_stage(2, "Other", 1),
        ]
        applications = [
            _make_application(1, 100, 1, "NotStale", 10),
            _make_application(2, 100, 1, "NotStale", 1),
            _make_application(3, 100, 1, "NotStale", 1),
            _make_application(4, 100, 2, "Other", 1),
            _make_application(5, 100, 2, "Other", 1),
            _make_application(6, 100, 2, "Other", 1),
            _make_application(7, 100, 2, "Other", 1),
            _make_application(8, 100, 2, "Other", 1),
            _make_application(9, 100, 2, "Other", 1),
            _make_application(10, 100, 2, "Other", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        stage = result["stages"][0]
        # stale_fraction = 1/3 ≈ 0.333 < 0.50, share = 3/10 = 0.30 (at threshold)
        # Concentrated but not stale => MEDIUM
        assert stage["severity"] == "MEDIUM"

    @pytest.mark.anyio
    async def it_counts_cold_when_days_exactly_equal_staleness_days(self) -> None:
        """Line 106: d >= staleness_days must count at equality boundary."""
        stages = [_make_stage(1, "Review", 0)]
        applications = [
            _make_application(1, 100, 1, "Review", 7),  # exactly 7 days
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, staleness_days=7, client=client)

        assert result["stages"][0]["cold_count"] == 1

    @pytest.mark.anyio
    async def it_computes_stale_fraction_with_division_not_multiplication(self) -> None:
        """Line 107: cold_count / count must be division, not multiplication.

        With 3 cold out of 10 total: 3/10 = 0.30, but 3*10 = 30.
        If stale_fraction were 30 instead of 0.30, severity would differ.
        """
        stages = [
            _make_stage(1, "TestStage", 0),
            _make_stage(2, "Other", 1),
        ]
        # 10 apps in TestStage: 3 stale, 7 fresh
        applications = [
            _make_application(1, 100, 1, "TestStage", 10),  # stale
            _make_application(2, 100, 1, "TestStage", 10),  # stale
            _make_application(3, 100, 1, "TestStage", 10),  # stale
            _make_application(4, 100, 1, "TestStage", 1),
            _make_application(5, 100, 1, "TestStage", 1),
            _make_application(6, 100, 1, "TestStage", 1),
            _make_application(7, 100, 1, "TestStage", 1),
            _make_application(8, 100, 1, "TestStage", 1),
            _make_application(9, 100, 1, "TestStage", 1),
            _make_application(10, 100, 1, "TestStage", 1),
            _make_application(11, 100, 2, "Other", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        test_stage = result["stages"][0]
        assert test_stage["cold_count"] == 3
        assert test_stage["count"] == 10
        # stale_fraction = 3/10 = 0.30 < 0.50 threshold => NOT stale
        # share = 10/11 ≈ 0.91 > 0.30 => concentrated
        # Concentrated but not stale => MEDIUM (not HIGH)
        assert test_stage["severity"] == "MEDIUM"

    @pytest.mark.anyio
    async def it_computes_share_correctly_with_exactly_one_active_app(self) -> None:
        """Line 102: total_active > 0 boundary -- exactly 1 app must yield share 1.0."""
        stages = [_make_stage(1, "Review", 0)]
        applications = [_make_application(1, 100, 1, "Review", 1)]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        assert result["total_active"] == 1
        assert result["stages"][0]["share"] == pytest.approx(1.0)
        assert result["stages"][0]["count"] == 1


@pytest.mark.small
class DescribeMultiJobAggregation:
    """When no job_id is provided, aggregate across all open jobs."""

    @pytest.mark.anyio
    async def it_returns_results_for_all_open_jobs(self) -> None:
        jobs = [
            {"id": 100, "name": "SWE", "status": "open"},
            {"id": 200, "name": "PM", "status": "open"},
            {"id": 300, "name": "Closed Role", "status": "closed"},
        ]
        stages = {
            100: [_make_stage(1, "Review", 0)],
            200: [_make_stage(2, "Screen", 0)],
        }
        applications = [
            _make_application(1, 100, 1, "Review", 1),
            _make_application(2, 200, 2, "Screen", 1),
        ]
        client = FakeGreenhouseClient(jobs=jobs, stages=stages, applications=applications)

        result = await pipeline_health(client=client)

        assert "jobs" in result
        assert len(result["jobs"]) == 2
        job_ids = [j["job_id"] for j in result["jobs"]]
        assert 100 in job_ids
        assert 200 in job_ids

    @pytest.mark.anyio
    async def it_includes_jobs_needing_attention(self) -> None:
        jobs = [
            {"id": 100, "name": "SWE", "status": "open"},
            {"id": 200, "name": "PM", "status": "open"},
        ]
        stages = {
            100: [
                _make_stage(1, "Bottleneck", 0),
                _make_stage(2, "Other", 1),
            ],
            200: [
                _make_stage(3, "Healthy A", 0),
                _make_stage(4, "Healthy B", 1),
            ],
        }
        applications = [
            _make_application(1, 100, 1, "Bottleneck", 10),
            _make_application(2, 100, 1, "Bottleneck", 14),
            _make_application(3, 100, 1, "Bottleneck", 12),
            _make_application(4, 100, 2, "Other", 1),
            _make_application(5, 200, 3, "Healthy A", 1),
            _make_application(6, 200, 4, "Healthy B", 1),
        ]
        client = FakeGreenhouseClient(jobs=jobs, stages=stages, applications=applications)

        result = await pipeline_health(
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        assert 100 in result["jobs_needing_attention"]
        assert 200 not in result["jobs_needing_attention"]


@pytest.mark.small
class DescribeEdgeCases:
    """Edge cases: empty pipelines, missing stages, deleted stages."""

    @pytest.mark.anyio
    async def it_handles_job_with_no_applications(self) -> None:
        stages = [
            _make_stage(1, "Review", 0),
            _make_stage(2, "Screen", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=[],
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["total_active"] == 0
        assert all(s["count"] == 0 for s in result["stages"])
        assert result["bottlenecks"] == []

    @pytest.mark.anyio
    async def it_handles_job_not_found(self) -> None:
        client = FakeGreenhouseClient(
            jobs=[],
            raise_on_get_job=NotFoundError("Job 999 not found"),
        )

        with pytest.raises(NotFoundError, match="Job 999 not found"):
            await pipeline_health(job_id=999, client=client)

    @pytest.mark.anyio
    async def it_filters_out_inactive_stages(self) -> None:
        stages = [
            _make_stage(1, "Active Stage", 0, active=True),
            _make_stage(2, "Deleted Stage", 1, active=False),
        ]
        applications = [
            _make_application(1, 100, 1, "Active Stage", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        stage_names = [s["stage_name"] for s in result["stages"]]
        assert "Active Stage" in stage_names
        assert "Deleted Stage" not in stage_names

    @pytest.mark.anyio
    async def it_groups_apps_in_deleted_stages_under_unknown(self) -> None:
        stages = [
            _make_stage(1, "Active Stage", 0, active=True),
        ]
        applications = [
            _make_application(1, 100, 1, "Active Stage", 1),
            _make_application(2, 100, 999, "Ghost Stage", 5),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["total_active"] == 2
        unknown_stages = [s for s in result["stages"] if s["stage_name"] == "Unknown/Deleted Stage"]
        assert len(unknown_stages) == 1
        assert unknown_stages[0]["count"] == 1

    @pytest.mark.anyio
    async def it_excludes_non_active_applications_from_pipeline(self) -> None:
        stages = [_make_stage(1, "Review", 0)]
        applications = [
            _make_application(1, 100, 1, "Review", 1, status="active"),
            _make_application(2, 100, 1, "Review", 1, status="rejected"),
            _make_application(3, 100, None, None, 1, status="hired"),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["total_active"] == 1

    @pytest.mark.anyio
    async def it_handles_application_with_null_current_stage(self) -> None:
        stages = [_make_stage(1, "Review", 0)]
        applications = [
            _make_application(1, 100, 1, "Review", 1),
            _make_application(2, 100, None, None, 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["total_active"] == 1

    @pytest.mark.anyio
    async def it_handles_all_open_jobs_with_no_jobs(self) -> None:
        client = FakeGreenhouseClient(jobs=[], stages={}, applications=[])

        result = await pipeline_health(client=client)

        assert result["jobs"] == []
        assert result["jobs_needing_attention"] == []

    @pytest.mark.anyio
    async def it_handles_timestamps_without_timezone_info(self) -> None:
        naive_timestamp = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(days=3)
        stages = [_make_stage(1, "Review", 0)]
        applications = [
            {
                "id": 1,
                "status": "active",
                "prospect": False,
                "current_stage": {"id": 1, "name": "Review"},
                "last_activity_at": naive_timestamp.isoformat(),
                "jobs": [{"id": 100, "name": "Job 100"}],
            },
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["total_active"] == 1
        assert result["stages"][0]["avg_days_since_activity"] == pytest.approx(3.0, abs=1.0)

    @pytest.mark.anyio
    async def it_does_not_flag_unknown_stage_when_share_below_threshold_and_fresh(self) -> None:
        stages = [_make_stage(1, "Active Stage", 0)]
        applications = [
            _make_application(1, 100, 999, "Ghost Stage", 1),
            _make_application(2, 100, 1, "Active Stage", 1),
            _make_application(3, 100, 1, "Active Stage", 1),
            _make_application(4, 100, 1, "Active Stage", 1),
            _make_application(5, 100, 1, "Active Stage", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        unknown_stages = [s for s in result["stages"] if s["stage_name"] == "Unknown/Deleted Stage"]
        assert len(unknown_stages) == 1
        assert unknown_stages[0]["is_bottleneck"] is False
        assert "Unknown/Deleted Stage" not in result["bottlenecks"]

    @pytest.mark.anyio
    async def it_flags_unknown_stage_as_bottleneck_when_concentrated_and_stale(self) -> None:
        stages = [_make_stage(1, "Active Stage", 0)]
        applications = [
            _make_application(1, 100, 999, "Ghost Stage", 14),
            _make_application(2, 100, 999, "Ghost Stage", 10),
            _make_application(3, 100, 999, "Ghost Stage", 12),
            _make_application(4, 100, 1, "Active Stage", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        unknown_stages = [s for s in result["stages"] if s["stage_name"] == "Unknown/Deleted Stage"]
        assert len(unknown_stages) == 1
        assert unknown_stages[0]["is_bottleneck"] is True
        assert unknown_stages[0]["severity"] == "HIGH"
        assert "Unknown/Deleted Stage" in result["bottlenecks"]

    @pytest.mark.anyio
    async def it_computes_unknown_share_correctly_with_exactly_one_total_app(self) -> None:
        """Line 130: unknown_share = unknown_count / total_active if total_active > 0.

        Boundary: exactly 1 total_active app (which is in the unknown stage).
        Must yield share=1.0, not 0.0.
        """
        stages = [_make_stage(1, "Active Stage", 0)]
        applications = [
            _make_application(1, 100, 999, "Ghost Stage", 10),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        unknown = [s for s in result["stages"] if s["stage_name"] == "Unknown/Deleted Stage"]
        assert len(unknown) == 1
        assert unknown[0]["share"] == pytest.approx(1.0)
        assert unknown[0]["count"] == 1

    @pytest.mark.anyio
    async def it_computes_unknown_stale_fraction_with_division_not_multiplication(self) -> None:
        """Line 132: unknown_cold / unknown_count must be division.

        3 cold out of 10 unknown apps: 3/10=0.30 (below 0.50 threshold).
        If multiplication: 3*10=30 (above threshold). Severity would differ.
        """
        stages = [_make_stage(1, "Active Stage", 0)]
        applications = [
            # 10 unknown apps: 3 stale, 7 fresh
            _make_application(1, 100, 999, "Ghost", 10),
            _make_application(2, 100, 999, "Ghost", 10),
            _make_application(3, 100, 999, "Ghost", 10),
            _make_application(4, 100, 999, "Ghost", 1),
            _make_application(5, 100, 999, "Ghost", 1),
            _make_application(6, 100, 999, "Ghost", 1),
            _make_application(7, 100, 999, "Ghost", 1),
            _make_application(8, 100, 999, "Ghost", 1),
            _make_application(9, 100, 999, "Ghost", 1),
            _make_application(10, 100, 999, "Ghost", 1),
            # 1 in active stage to keep active stage present
            _make_application(11, 100, 1, "Active Stage", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        unknown = [s for s in result["stages"] if s["stage_name"] == "Unknown/Deleted Stage"]
        assert len(unknown) == 1
        assert unknown[0]["cold_count"] == 3
        assert unknown[0]["count"] == 10
        # stale_fraction = 3/10 = 0.30 < 0.50 => NOT stale
        # share = 10/11 ≈ 0.91 > 0.30 => concentrated
        # Concentrated but not stale => MEDIUM (not HIGH)
        assert unknown[0]["severity"] == "MEDIUM"

    @pytest.mark.anyio
    async def it_triggers_unknown_staleness_when_stale_fraction_exactly_equals_threshold(self) -> None:
        """Line 133: unknown stale_fraction >= 0.50 must trigger at equality.

        2 unknown apps: 1 stale, 1 fresh => stale_fraction = 0.50 exactly.
        Low share to isolate => severity LOW.
        """
        stages = [_make_stage(1, "Active Stage", 0)]
        applications = [
            _make_application(1, 100, 999, "Ghost", 10),  # stale
            _make_application(2, 100, 999, "Ghost", 1),  # fresh
            # 8 more in active stage to make unknown share = 2/10 = 0.20
            _make_application(3, 100, 1, "Active Stage", 1),
            _make_application(4, 100, 1, "Active Stage", 1),
            _make_application(5, 100, 1, "Active Stage", 1),
            _make_application(6, 100, 1, "Active Stage", 1),
            _make_application(7, 100, 1, "Active Stage", 1),
            _make_application(8, 100, 1, "Active Stage", 1),
            _make_application(9, 100, 1, "Active Stage", 1),
            _make_application(10, 100, 1, "Active Stage", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        unknown = [s for s in result["stages"] if s["stage_name"] == "Unknown/Deleted Stage"]
        assert len(unknown) == 1
        assert unknown[0]["cold_count"] == 1
        assert unknown[0]["count"] == 2
        # stale_fraction = 1/2 = 0.50 (exactly at threshold), share = 2/10 = 0.20 (below)
        assert unknown[0]["severity"] == "LOW"

    @pytest.mark.anyio
    async def it_computes_unknown_cold_count_at_staleness_days_boundary(self) -> None:
        """Line 134: unknown cold_count uses d >= staleness_days.

        An unknown app with activity exactly staleness_days ago must be counted cold.
        """
        stages = [_make_stage(1, "Active Stage", 0)]
        applications = [
            _make_application(1, 100, 999, "Ghost", 7),  # exactly 7 days
            _make_application(2, 100, 1, "Active Stage", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=applications,
        )

        result = await pipeline_health(
            job_id=100,
            bottleneck_threshold=0.30,
            staleness_days=7,
            client=client,
        )

        unknown = [s for s in result["stages"] if s["stage_name"] == "Unknown/Deleted Stage"]
        assert len(unknown) == 1
        assert unknown[0]["cold_count"] == 1

    @pytest.mark.anyio
    async def it_returns_zero_share_when_no_applications(self) -> None:
        stages = [_make_stage(1, "Review", 0)]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=[],
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["stages"][0]["share"] == 0.0
        assert result["stages"][0]["avg_days_since_activity"] == 0.0
        assert result["stages"][0]["cold_count"] == 0

    @pytest.mark.anyio
    async def it_treats_stage_without_active_key_as_active(self) -> None:
        """Line 74: s.get('active', True) -- default True must include keyless stages."""
        stage_without_key = {"id": 1, "name": "No Active Key", "priority": 0, "job_id": 100, "interviews": []}
        applications = [_make_application(1, 100, 1, "No Active Key", 1)]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: [stage_without_key]},
            applications=applications,
        )

        result = await pipeline_health(job_id=100, client=client)

        stage_names = [s["stage_name"] for s in result["stages"]]
        assert "No Active Key" in stage_names
        assert result["stages"][0]["count"] == 1

    @pytest.mark.anyio
    async def it_includes_application_without_prospect_key(self) -> None:
        """Line 82: a.get('prospect', False) -- default False must include keyless apps."""
        stages = [_make_stage(1, "Review", 0)]
        app_without_prospect = {
            "id": 1,
            "status": "active",
            "current_stage": {"id": 1, "name": "Review"},
            "last_activity_at": _iso(1),
            "jobs": [{"id": 100, "name": "Job 100"}],
        }
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Engineer", "status": "open"}],
            stages={100: stages},
            applications=[app_without_prospect],
        )

        result = await pipeline_health(job_id=100, client=client)

        assert result["total_active"] == 1
        assert result["stages"][0]["count"] == 1


@pytest.mark.small
class DescribeUnknownStageMutantTriangulation:
    """Kill mutants on the unknown/deleted stage code path (lines 106, 130-134)."""

    @pytest.mark.anyio
    async def it_counts_cold_at_exact_staleness_boundary_for_known_stage(self) -> None:
        """Line 106: d >= staleness_days — 9-day app with staleness_days=8 counts as cold."""
        stages = [_make_stage(1, "Review", 0)]
        apps = [
            _make_application(1, 100, 1, "Review", 9),  # clearly >= 8
            _make_application(2, 100, 1, "Review", 6),  # clearly < 8
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Eng", "status": "open"}],
            stages={100: stages},
            applications=apps,
        )

        result = await pipeline_health(job_id=100, staleness_days=8, client=client)

        stage = result["stages"][0]
        assert stage["cold_count"] == 1

    @pytest.mark.anyio
    async def it_does_not_count_cold_when_days_below_staleness(self) -> None:
        """Line 106: d >= staleness_days — 5-day app with staleness_days=7 is NOT cold."""
        stages = [_make_stage(1, "Review", 0)]
        apps = [_make_application(1, 100, 1, "Review", 5)]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Eng", "status": "open"}],
            stages={100: stages},
            applications=apps,
        )

        result = await pipeline_health(job_id=100, staleness_days=7, client=client)

        stage = result["stages"][0]
        assert stage["cold_count"] == 0

    @pytest.mark.anyio
    async def it_computes_unknown_share_as_division_not_multiplication(self) -> None:
        """Line 130: unknown_count / total_active — 3/10=0.3, not 3*10=30."""
        stages = [_make_stage(1, "Review", 0)]
        known_apps = [_make_application(i, 100, 1, "Review", 1) for i in range(7)]
        # stage_id=999 not in active_stages → goes to unknown bucket
        unknown_apps = [_make_application(i + 100, 100, 999, "Deleted", 1) for i in range(3)]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Eng", "status": "open"}],
            stages={100: stages},
            applications=known_apps + unknown_apps,
        )

        result = await pipeline_health(job_id=100, client=client)

        unknown_stage = next(s for s in result["stages"] if s["stage_id"] is None)
        assert unknown_stage["share"] == pytest.approx(0.3, abs=0.01)

    @pytest.mark.anyio
    async def it_computes_unknown_avg_days_as_division_not_multiplication(self) -> None:
        """Line 132: sum()/len() — avg of [3,9]=6.0, not 3*9=27."""
        stages = [_make_stage(1, "Review", 0)]
        unknown_apps = [
            _make_application(1, 100, 999, "Deleted", 3),
            _make_application(2, 100, 999, "Deleted", 9),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Eng", "status": "open"}],
            stages={100: stages},
            applications=unknown_apps,
        )

        result = await pipeline_health(job_id=100, client=client)

        unknown_stage = next(s for s in result["stages"] if s["stage_id"] is None)
        assert unknown_stage["avg_days_since_activity"] == pytest.approx(6.0, abs=0.5)

    @pytest.mark.anyio
    async def it_counts_unknown_cold_at_exact_staleness_boundary(self) -> None:
        """Line 133: d >= staleness_days on unknown path — d==7 counts."""
        stages = [_make_stage(1, "Review", 0)]
        unknown_apps = [
            _make_application(1, 100, 999, "Deleted", 7),
            _make_application(2, 100, 999, "Deleted", 6),
            _make_application(3, 100, 999, "Deleted", 8),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Eng", "status": "open"}],
            stages={100: stages},
            applications=unknown_apps,
        )

        result = await pipeline_health(job_id=100, staleness_days=7, client=client)

        unknown_stage = next(s for s in result["stages"] if s["stage_id"] is None)
        assert unknown_stage["cold_count"] == 2

    @pytest.mark.anyio
    async def it_computes_unknown_stale_fraction_as_division(self) -> None:
        """Line 134: unknown_cold / unknown_count — 2/3 not 2*3."""
        stages = [_make_stage(1, "Review", 0)]
        unknown_apps = [
            _make_application(1, 100, 999, "Deleted", 10),
            _make_application(2, 100, 999, "Deleted", 10),
            _make_application(3, 100, 999, "Deleted", 1),
        ]
        client = FakeGreenhouseClient(
            jobs=[{"id": 100, "name": "Eng", "status": "open"}],
            stages={100: stages},
            applications=unknown_apps,
        )

        result = await pipeline_health(job_id=100, staleness_days=7, bottleneck_threshold=0.01, client=client)

        unknown_stage = next(s for s in result["stages"] if s["stage_id"] is None)
        assert unknown_stage["severity"] == "HIGH"
