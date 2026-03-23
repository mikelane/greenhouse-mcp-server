"""Tests for the hiring_velocity tool."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from greenhouse_mcp.tools.velocity import hiring_velocity


def _iso_at(dt: datetime) -> str:
    return dt.isoformat()


class FakeGreenhouseClient:
    """In-memory fake satisfying GreenhousePort for velocity tests."""

    def __init__(self) -> None:
        self.applications: list[dict[str, Any]] = []
        self.offers: list[dict[str, Any]] = []
        self.jobs: list[dict[str, Any]] = []

    async def get_applications(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,  # noqa: ARG002
        created_after: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self.applications
        if job_id is not None:
            result = [a for a in result if any(j["id"] == job_id for j in a.get("jobs", []))]
        if created_after is not None:
            cutoff = datetime.fromisoformat(created_after)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
            filtered = []
            for a in result:
                created = datetime.fromisoformat(a["created_at"])
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                if created >= cutoff:
                    filtered.append(a)
            result = filtered
        return result

    async def get_offers(
        self,
        *,
        application_id: int | None = None,  # noqa: ARG002
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self.offers
        if status is not None:
            result = [o for o in result if o.get("status") == status]
        return result

    async def get_jobs(
        self,
        *,
        status: str | None = None,  # noqa: ARG002
        department_id: int | None = None,
    ) -> list[dict[str, Any]]:
        result = self.jobs
        if department_id is not None:
            result = [j for j in result if any(d.get("id") == department_id for d in j.get("departments", []))]
        return result

    async def get_job(self, job_id: int) -> dict[str, Any]:
        for job in self.jobs:
            if job["id"] == job_id:
                return job
        msg = f"Job {job_id} not found"
        raise ValueError(msg)

    async def get_job_stages(self, job_id: int) -> list[dict[str, Any]]:  # noqa: ARG002
        return []

    async def get_candidate(self, candidate_id: int) -> dict[str, Any]:  # noqa: ARG002
        return {}

    async def get_scorecards(self, application_id: int) -> list[dict[str, Any]]:  # noqa: ARG002
        return []

    async def get_scheduled_interviews(
        self,
        *,
        application_id: int | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return []

    async def get_activity_feed(self, candidate_id: int) -> dict[str, Any]:  # noqa: ARG002
        return {}

    async def get_candidates(
        self,
        *,
        job_id: int | None = None,  # noqa: ARG002
        email: str | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return []


@pytest.mark.small
class DescribeHiringVelocityWithNoApplications:
    @pytest.mark.anyio
    async def it_returns_zero_total_applications(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime(2026, 3, 15, tzinfo=UTC)

        result = await hiring_velocity(
            job_id=1,
            client=client,
            now=now,
        )

        assert result["total_applications"] == 0

    @pytest.mark.anyio
    async def it_returns_weekly_buckets_all_with_zero_counts(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime(2026, 3, 15, tzinfo=UTC)

        result = await hiring_velocity(
            job_id=1,
            client=client,
            now=now,
        )

        assert all(b["count"] == 0 for b in result["weekly_buckets"])

    @pytest.mark.anyio
    async def it_returns_stable_trend(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime(2026, 3, 15, tzinfo=UTC)

        result = await hiring_velocity(
            job_id=1,
            client=client,
            now=now,
        )

        assert result["trend"] == "stable"

    @pytest.mark.anyio
    async def it_flags_insufficient_data(self) -> None:
        client = FakeGreenhouseClient()
        now = datetime(2026, 3, 15, tzinfo=UTC)

        result = await hiring_velocity(
            job_id=1,
            client=client,
            now=now,
        )

        assert result["insufficient_data"] is True
        assert result["warning"] is not None


@pytest.mark.small
class DescribeWeeklyBucketing:
    @pytest.mark.anyio
    async def it_places_applications_in_correct_weekly_buckets(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=3)), "jobs": [{"id": 10}]},
            {"id": 2, "created_at": _iso_at(now - timedelta(days=4)), "jobs": [{"id": 10}]},
            {"id": 3, "created_at": _iso_at(now - timedelta(days=10)), "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now, days=21)

        buckets = result["weekly_buckets"]
        counts = [b["count"] for b in buckets]
        assert sum(counts) == 3

    @pytest.mark.anyio
    async def it_returns_bucket_start_dates_as_iso_strings(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=1)), "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now, days=14)

        for bucket in result["weekly_buckets"]:
            datetime.fromisoformat(bucket["week_start"])

    @pytest.mark.anyio
    async def it_creates_correct_number_of_buckets_for_time_range(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()

        result = await hiring_velocity(job_id=10, client=client, now=now, days=28)

        assert len(result["weekly_buckets"]) == 4

    @pytest.mark.anyio
    async def it_handles_applications_without_timezone(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        naive_ts = (now - timedelta(days=2)).replace(tzinfo=None).isoformat()
        client.applications = [
            {"id": 1, "created_at": naive_ts, "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now, days=7)

        assert result["total_applications"] == 1
        assert sum(b["count"] for b in result["weekly_buckets"]) == 1


@pytest.mark.small
class DescribeTrendDirection:
    @pytest.mark.anyio
    async def it_reports_improving_when_recent_buckets_have_more_applications(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        # 8 weeks of data: first 4 weeks have 1 app each, last 4 weeks have 3 each
        apps = []
        app_id = 1
        for week in range(8):
            week_start = now - timedelta(days=(8 - week) * 7)
            count = 1 if week < 4 else 3
            for day_offset in range(count):
                apps.append(
                    {
                        "id": app_id,
                        "created_at": _iso_at(week_start + timedelta(days=day_offset)),
                        "jobs": [{"id": 10}],
                    }
                )
                app_id += 1
        client.applications = apps

        result = await hiring_velocity(
            job_id=10,
            client=client,
            now=now,
            days=56,
            trend_window=4,
        )

        assert result["trend"] == "improving"
        assert result["trend_details"]["recent_avg"] > result["trend_details"]["previous_avg"]
        assert result["trend_details"]["change_pct"] > 0

    @pytest.mark.anyio
    async def it_reports_worsening_when_recent_buckets_have_fewer_applications(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        apps = []
        app_id = 1
        for week in range(8):
            week_start = now - timedelta(days=(8 - week) * 7)
            count = 3 if week < 4 else 1
            for day_offset in range(count):
                apps.append(
                    {
                        "id": app_id,
                        "created_at": _iso_at(week_start + timedelta(days=day_offset)),
                        "jobs": [{"id": 10}],
                    }
                )
                app_id += 1
        client.applications = apps

        result = await hiring_velocity(
            job_id=10,
            client=client,
            now=now,
            days=56,
            trend_window=4,
        )

        assert result["trend"] == "worsening"
        assert result["trend_details"]["recent_avg"] < result["trend_details"]["previous_avg"]
        assert result["trend_details"]["change_pct"] < 0

    @pytest.mark.anyio
    async def it_reports_stable_when_not_enough_buckets_for_trend_window(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=3)), "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(
            job_id=10,
            client=client,
            now=now,
            days=14,
            trend_window=4,
        )

        assert result["trend"] == "stable"

    @pytest.mark.anyio
    async def it_computes_change_pct_relative_to_previous_avg(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        apps = []
        app_id = 1
        for week in range(8):
            week_start = now - timedelta(days=(8 - week) * 7)
            count = 2 if week < 4 else 4
            for day_offset in range(count):
                apps.append(
                    {
                        "id": app_id,
                        "created_at": _iso_at(week_start + timedelta(days=day_offset)),
                        "jobs": [{"id": 10}],
                    }
                )
                app_id += 1
        client.applications = apps

        result = await hiring_velocity(
            job_id=10,
            client=client,
            now=now,
            days=56,
            trend_window=4,
        )

        details = result["trend_details"]
        expected_pct = ((details["recent_avg"] - details["previous_avg"]) / details["previous_avg"]) * 100
        assert details["change_pct"] == pytest.approx(expected_pct)


@pytest.mark.small
class DescribeOfferMetrics:
    @pytest.mark.anyio
    async def it_computes_acceptance_rate_from_accepted_and_rejected(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.offers = [
            {"id": 1, "status": "accepted"},
            {"id": 2, "status": "accepted"},
            {"id": 3, "status": "accepted"},
            {"id": 4, "status": "rejected"},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now)

        assert result["offer_metrics"]["accepted"] == 3
        assert result["offer_metrics"]["rejected"] == 1
        assert result["offer_metrics"]["total_offers"] == 4
        assert result["offer_metrics"]["acceptance_rate_pct"] == pytest.approx(75.0)

    @pytest.mark.anyio
    async def it_ignores_unresolved_offers_in_acceptance_rate(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.offers = [
            {"id": 1, "status": "accepted"},
            {"id": 2, "status": "rejected"},
            {"id": 3, "status": "unresolved"},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now)

        assert result["offer_metrics"]["accepted"] == 1
        assert result["offer_metrics"]["rejected"] == 1
        assert result["offer_metrics"]["total_offers"] == 2
        assert result["offer_metrics"]["acceptance_rate_pct"] == pytest.approx(50.0)

    @pytest.mark.anyio
    async def it_ignores_deprecated_offers(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.offers = [
            {"id": 1, "status": "accepted"},
            {"id": 2, "status": "deprecated"},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now)

        assert result["offer_metrics"]["total_offers"] == 1
        assert result["offer_metrics"]["acceptance_rate_pct"] == pytest.approx(100.0)

    @pytest.mark.anyio
    async def it_documents_offer_scope_as_organization_wide(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()

        result = await hiring_velocity(job_id=10, client=client, now=now)

        assert result["offer_metrics"]["offer_scope"] == "organization-wide"

    @pytest.mark.anyio
    async def it_returns_zero_acceptance_rate_when_no_decided_offers(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.offers = [
            {"id": 1, "status": "unresolved"},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now)

        assert result["offer_metrics"]["total_offers"] == 0
        assert result["offer_metrics"]["acceptance_rate_pct"] == pytest.approx(0.0)


@pytest.mark.small
class DescribeDepartmentAggregation:
    @pytest.mark.anyio
    async def it_groups_metrics_by_department_when_no_job_id(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.jobs = [
            {"id": 10, "departments": [{"id": 1, "name": "Engineering"}]},
            {"id": 20, "departments": [{"id": 2, "name": "Design"}]},
        ]
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=5)), "jobs": [{"id": 10}]},
            {"id": 2, "created_at": _iso_at(now - timedelta(days=3)), "jobs": [{"id": 10}]},
            {"id": 3, "created_at": _iso_at(now - timedelta(days=2)), "jobs": [{"id": 20}]},
        ]

        result = await hiring_velocity(client=client, now=now, days=14)

        assert "departments" in result
        assert "overall" in result
        dept_names = {d["department_name"] for d in result["departments"]}
        assert dept_names == {"Engineering", "Design"}

    @pytest.mark.anyio
    async def it_includes_overall_summary_across_all_departments(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.jobs = [
            {"id": 10, "departments": [{"id": 1, "name": "Engineering"}]},
        ]
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=5)), "jobs": [{"id": 10}]},
            {"id": 2, "created_at": _iso_at(now - timedelta(days=3)), "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(client=client, now=now, days=14)

        assert result["overall"]["total_applications"] == 2

    @pytest.mark.anyio
    async def it_groups_jobs_without_department_under_unassigned(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.jobs = [
            {"id": 10, "departments": []},
        ]
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=2)), "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(client=client, now=now, days=14)

        dept_names = {d["department_name"] for d in result["departments"]}
        assert "Unassigned" in dept_names

    @pytest.mark.anyio
    async def it_filters_by_department_id_when_specified(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.jobs = [
            {"id": 10, "departments": [{"id": 1, "name": "Engineering"}]},
            {"id": 20, "departments": [{"id": 2, "name": "Design"}]},
        ]
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=5)), "jobs": [{"id": 10}]},
            {"id": 2, "created_at": _iso_at(now - timedelta(days=3)), "jobs": [{"id": 20}]},
        ]

        result = await hiring_velocity(department_id=1, client=client, now=now, days=14)

        assert result["total_applications"] == 1


@pytest.mark.small
class DescribeEdgeCases:
    @pytest.mark.anyio
    async def it_groups_application_with_no_jobs_under_unassigned(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.jobs = [
            {"id": 10, "departments": [{"id": 1, "name": "Engineering"}]},
        ]
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=2)), "jobs": []},
        ]

        result = await hiring_velocity(client=client, now=now, days=14)

        dept_names = {d["department_name"] for d in result["departments"]}
        assert "Unassigned" in dept_names

    @pytest.mark.anyio
    async def it_returns_time_range_with_start_end_and_days(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()

        result = await hiring_velocity(job_id=10, client=client, now=now, days=30)

        assert result["time_range"]["days"] == 30
        assert result["time_range"]["start"] == "2026-02-13"
        assert result["time_range"]["end"] == "2026-03-15"

    @pytest.mark.anyio
    async def it_clears_insufficient_data_flag_with_five_or_more_applications(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.applications = [
            {"id": i, "created_at": _iso_at(now - timedelta(days=i)), "jobs": [{"id": 10}]} for i in range(1, 6)
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now, days=14)

        assert result["insufficient_data"] is False
        assert result["warning"] is None

    @pytest.mark.anyio
    async def it_includes_warning_message_with_application_count(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=1)), "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now, days=7)

        assert "1 applications" in result["warning"]

    @pytest.mark.anyio
    async def it_handles_zero_previous_avg_in_change_pct(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        # 8 weeks: first 4 have 0 apps, last 4 have some
        apps = []
        app_id = 1
        for week in range(4, 8):
            week_start = now - timedelta(days=(8 - week) * 7)
            apps.append(
                {
                    "id": app_id,
                    "created_at": _iso_at(week_start + timedelta(days=1)),
                    "jobs": [{"id": 10}],
                }
            )
            app_id += 1
        client.applications = apps

        result = await hiring_velocity(
            job_id=10,
            client=client,
            now=now,
            days=56,
            trend_window=4,
        )

        assert result["trend_details"]["change_pct"] == 0.0

    @pytest.mark.anyio
    async def it_assigns_application_with_unknown_job_to_unassigned(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.jobs = [
            {"id": 10, "departments": [{"id": 1, "name": "Engineering"}]},
        ]
        # Application references job_id 999 which is not in the jobs list
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=2)), "jobs": [{"id": 999}]},
        ]

        result = await hiring_velocity(client=client, now=now, days=14)

        dept_names = {d["department_name"] for d in result["departments"]}
        assert "Unassigned" in dept_names


@pytest.mark.small
class DescribeMutantKillers:
    @pytest.mark.anyio
    async def it_ignores_department_filter_when_job_id_is_set(self) -> None:
        """When both job_id and department_id are provided, job_id takes precedence."""
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        client.jobs = [
            {"id": 10, "departments": [{"id": 1, "name": "Engineering"}]},
            {"id": 20, "departments": [{"id": 999, "name": "Marketing"}]},
        ]
        client.applications = [
            {"id": 1, "created_at": _iso_at(now - timedelta(days=5)), "jobs": [{"id": 10}]},
            {"id": 2, "created_at": _iso_at(now - timedelta(days=3)), "jobs": [{"id": 20}]},
        ]

        result = await hiring_velocity(
            job_id=10,
            department_id=999,
            client=client,
            now=now,
            days=14,
        )

        assert result["total_applications"] == 1

    @pytest.mark.anyio
    async def it_counts_application_created_exactly_at_bucket_start(self) -> None:
        """An application created at exactly a bucket boundary lands in that bucket."""
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        bucket_start = now - timedelta(days=7)
        client.applications = [
            {"id": 1, "created_at": _iso_at(bucket_start), "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now, days=14)

        buckets = result["weekly_buckets"]
        bucket_for_start = next(b for b in buckets if b["week_start"] == bucket_start.date().isoformat())
        assert bucket_for_start["count"] == 1


@pytest.mark.small
class DescribeBuildBucketsEdgeCases:
    @pytest.mark.anyio
    async def it_returns_empty_buckets_when_days_is_zero(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()

        result = await hiring_velocity(job_id=10, client=client, now=now, days=0)

        assert result["weekly_buckets"] == []
        assert result["total_applications"] == 0

    @pytest.mark.anyio
    async def it_excludes_application_created_before_time_range_from_all_buckets(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        client = FakeGreenhouseClient()
        # Application created well before the 14-day lookback window (starts March 1)
        client.applications = [
            {"id": 1, "created_at": _iso_at(datetime(2026, 2, 20, tzinfo=UTC)), "jobs": [{"id": 10}]},
        ]

        result = await hiring_velocity(job_id=10, client=client, now=now, days=14)

        assert all(b["count"] == 0 for b in result["weekly_buckets"])
