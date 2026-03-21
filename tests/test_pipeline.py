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

        assert result["job_id"] == 100  # noqa: PLR2004
        assert result["job_name"] == "Software Engineer"
        assert result["total_active"] == 10  # noqa: PLR2004
        assert len(result["stages"]) == 4  # noqa: PLR2004
        stage_names = [s["stage_name"] for s in result["stages"]]
        assert stage_names == [
            "Application Review",
            "Phone Screen",
            "Technical Interview",
            "Onsite",
        ]
        assert result["stages"][0]["count"] == 3  # noqa: PLR2004
        assert result["stages"][1]["count"] == 2  # noqa: PLR2004
        assert result["stages"][2]["count"] == 3  # noqa: PLR2004
        assert result["stages"][3]["count"] == 2  # noqa: PLR2004

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

        assert result["stages"][0]["cold_count"] == 2  # noqa: PLR2004

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
        assert len(result["jobs"]) == 2  # noqa: PLR2004
        job_ids = [j["job_id"] for j in result["jobs"]]
        assert 100 in job_ids  # noqa: PLR2004
        assert 200 in job_ids  # noqa: PLR2004

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

        assert 100 in result["jobs_needing_attention"]  # noqa: PLR2004
        assert 200 not in result["jobs_needing_attention"]  # noqa: PLR2004


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

        assert result["total_active"] == 2  # noqa: PLR2004
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
