"""hiring_velocity tool: answers 'are we getting faster or slower at hiring?'.

Composes applications over time, stage duration trends, and offer
acceptance rates into weekly-bucketed velocity metrics with trend
direction. See ADR 0008 for design rationale.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from greenhouse_mcp.ports import GreenhousePort

_DEFAULT_DAYS = 90
_DEFAULT_BUCKET_SIZE_DAYS = 7
_DEFAULT_TREND_WINDOW = 4
_INSUFFICIENT_DATA_THRESHOLD = 5


async def hiring_velocity(  # noqa: PLR0913
    *,
    job_id: int | None = None,
    department_id: int | None = None,
    days: int = _DEFAULT_DAYS,
    bucket_size_days: int = _DEFAULT_BUCKET_SIZE_DAYS,
    trend_window: int = _DEFAULT_TREND_WINDOW,
    client: GreenhousePort,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute hiring velocity metrics over a time range.

    Args:
        job_id: Filter to a specific job (all jobs if None).
        department_id: Filter to a specific department.
        days: Number of days to look back.
        bucket_size_days: Size of each time bucket in days.
        trend_window: Number of buckets for the moving average window.
        client: Greenhouse API client (injected via Depends).
        now: Current timestamp (injectable for testing).

    Returns:
        Dict with weekly buckets, trend direction, offer metrics,
        and optional department breakdowns.
    """
    if now is None:
        now = datetime.now(tz=UTC)  # pragma: no cover

    end = now
    start = end - timedelta(days=days)

    if job_id is not None or department_id is not None:
        return await _single_scope_metrics(
            client=client,
            job_id=job_id,
            department_id=department_id,
            start=start,
            end=end,
            days=days,
            bucket_size_days=bucket_size_days,
            trend_window=trend_window,
        )

    return await _department_aggregated_metrics(
        client=client,
        start=start,
        end=end,
        days=days,
        bucket_size_days=bucket_size_days,
        trend_window=trend_window,
    )


def _make_metrics(  # noqa: PLR0913
    applications: list[dict[str, Any]],
    offer_metrics: dict[str, Any],
    *,
    start: datetime,
    end: datetime,
    days: int,
    bucket_size_days: int,
    trend_window: int,
) -> dict[str, Any]:
    """Build the velocity metrics dict from pre-fetched data.

    Args:
        applications: Filtered application dicts.
        offer_metrics: Pre-computed offer metrics dict.
        start: Start of the time range.
        end: End of the time range.
        days: Number of days in the range.
        bucket_size_days: Width of each time bucket.
        trend_window: Number of buckets for SMA.

    Returns:
        Complete velocity metrics dict.
    """
    total = len(applications)
    buckets = _build_buckets(applications, start=start, end=end, bucket_size_days=bucket_size_days)
    trend, trend_details = _compute_trend(buckets, trend_window=trend_window)
    insufficient = total < _INSUFFICIENT_DATA_THRESHOLD
    warning = f"Only {total} applications in time range; trends may be unreliable" if insufficient else None

    return {
        "time_range": {"start": start.date().isoformat(), "end": end.date().isoformat(), "days": days},
        "total_applications": total,
        "weekly_buckets": buckets,
        "trend": trend,
        "trend_details": trend_details,
        "offer_metrics": offer_metrics,
        "insufficient_data": insufficient,
        "warning": warning,
    }


async def _single_scope_metrics(  # noqa: PLR0913
    *,
    client: GreenhousePort,
    job_id: int | None,
    department_id: int | None,
    start: datetime,
    end: datetime,
    days: int,
    bucket_size_days: int,
    trend_window: int,
) -> dict[str, Any]:
    """Compute metrics for a single job or department scope.

    Args:
        client: Greenhouse API client.
        job_id: Filter to a specific job.
        department_id: Filter to a specific department.
        start: Start of the time range.
        end: End of the time range.
        days: Number of days in the range.
        bucket_size_days: Width of each time bucket.
        trend_window: Number of buckets for SMA.

    Returns:
        Velocity metrics dict for the specified scope.
    """
    applications = await client.get_applications(
        job_id=job_id,
        created_after=start.isoformat(),
    )

    if department_id is not None and job_id is None:
        dept_jobs = await client.get_jobs(department_id=department_id)
        dept_job_ids = {j["id"] for j in dept_jobs}
        applications = [a for a in applications if any(j["id"] in dept_job_ids for j in a.get("jobs", []))]

    offer_metrics = await _compute_offer_metrics(client)
    return _make_metrics(
        applications,
        offer_metrics,
        start=start,
        end=end,
        days=days,
        bucket_size_days=bucket_size_days,
        trend_window=trend_window,
    )


async def _department_aggregated_metrics(  # noqa: PLR0913
    *,
    client: GreenhousePort,
    start: datetime,
    end: datetime,
    days: int,
    bucket_size_days: int,
    trend_window: int,
) -> dict[str, Any]:
    """Compute metrics grouped by department when no specific scope given.

    Args:
        client: Greenhouse API client.
        start: Start of the time range.
        end: End of the time range.
        days: Number of days in the range.
        bucket_size_days: Width of each time bucket.
        trend_window: Number of buckets for SMA.

    Returns:
        Dict with per-department metrics and overall summary.
    """
    all_applications = await client.get_applications(created_after=start.isoformat())
    all_jobs = await client.get_jobs()
    offer_metrics = await _compute_offer_metrics(client)

    job_to_dept: dict[int, tuple[int | None, str]] = {}
    for job in all_jobs:
        depts = job.get("departments", [])
        if depts:
            job_to_dept[job["id"]] = (depts[0]["id"], depts[0]["name"])
        else:
            job_to_dept[job["id"]] = (None, "Unassigned")

    dept_apps: dict[tuple[int | None, str], list[dict[str, Any]]] = {}
    for app in all_applications:
        app_jobs = app.get("jobs", [])
        dept_key = job_to_dept.get(app_jobs[0]["id"], (None, "Unassigned")) if app_jobs else (None, "Unassigned")
        dept_apps.setdefault(dept_key, []).append(app)

    departments = []
    for (dept_id, dept_name), apps in sorted(dept_apps.items(), key=lambda x: x[0][1]):
        metrics = _make_metrics(
            apps,
            offer_metrics,
            start=start,
            end=end,
            days=days,
            bucket_size_days=bucket_size_days,
            trend_window=trend_window,
        )
        departments.append(
            {
                "department_id": dept_id,
                "department_name": dept_name,
                **metrics,
            }
        )

    overall = _make_metrics(
        all_applications,
        offer_metrics,
        start=start,
        end=end,
        days=days,
        bucket_size_days=bucket_size_days,
        trend_window=trend_window,
    )

    return {
        "departments": departments,
        "overall": overall,
    }


async def _compute_offer_metrics(client: GreenhousePort) -> dict[str, Any]:
    """Fetch offers and compute acceptance rate.

    Only counts accepted and rejected offers. Unresolved and deprecated
    offers are excluded from both the count and the rate calculation.

    Args:
        client: Greenhouse API client.

    Returns:
        Dict with total_offers, accepted, rejected, acceptance_rate_pct.
    """
    all_offers = await client.get_offers()
    accepted = sum(1 for o in all_offers if o.get("status") == "accepted")
    rejected = sum(1 for o in all_offers if o.get("status") == "rejected")
    decided = accepted + rejected

    rate = 0.0 if decided == 0 else (accepted / decided) * 100

    return {
        "total_offers": decided,
        "accepted": accepted,
        "rejected": rejected,
        "acceptance_rate_pct": rate,
        "offer_scope": "organization-wide",
    }


def _build_buckets(
    applications: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
    bucket_size_days: int,
) -> list[dict[str, Any]]:
    """Group applications into time buckets by created_at date.

    Args:
        applications: Application dicts with 'created_at' ISO timestamps.
        start: Start of the time range.
        end: End of the time range.
        bucket_size_days: Width of each bucket in days.

    Returns:
        List of bucket dicts with 'week_start' and 'count'.
    """
    bucket_starts: list[datetime] = []
    cursor = start
    while cursor < end:
        bucket_starts.append(cursor)
        cursor += timedelta(days=bucket_size_days)

    if not bucket_starts:
        return []

    counts: dict[str, int] = {b.date().isoformat(): 0 for b in bucket_starts}

    for app in applications:
        created = datetime.fromisoformat(app["created_at"])
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        bucket_key = _find_bucket(created, bucket_starts)
        if bucket_key is not None:
            counts[bucket_key] += 1

    return [{"week_start": k, "count": v} for k, v in counts.items()]


def _find_bucket(created: datetime, bucket_starts: list[datetime]) -> str | None:
    """Find the bucket key for a given timestamp.

    Searches bucket_starts in reverse order, returning the ISO date string
    of the first bucket whose start is at or before the timestamp.

    Args:
        created: The application creation timestamp.
        bucket_starts: Sorted list of bucket start datetimes.

    Returns:
        ISO date string of the matching bucket, or None if before all buckets.
    """
    for i in range(len(bucket_starts) - 1, -1, -1):
        if created >= bucket_starts[i]:
            return bucket_starts[i].date().isoformat()
    return None


def _compute_trend(
    buckets: list[dict[str, Any]],
    *,
    trend_window: int,
) -> tuple[str, dict[str, Any]]:
    """Compute trend direction from bucket counts using simple moving average.

    Args:
        buckets: List of bucket dicts with 'count' values.
        trend_window: Number of buckets in each SMA window.

    Returns:
        Tuple of (trend_label, trend_details_dict).
    """
    counts = [b["count"] for b in buckets]

    if len(counts) < 2 * trend_window:
        return "stable", {"recent_avg": 0.0, "previous_avg": 0.0, "change_pct": 0.0}

    recent = counts[-trend_window:]
    previous = counts[-2 * trend_window : -trend_window]

    recent_avg = sum(recent) / len(recent)
    previous_avg = sum(previous) / len(previous)

    change_pct = 0.0 if previous_avg == 0 else ((recent_avg - previous_avg) / previous_avg) * 100

    if recent_avg > previous_avg:
        trend = "improving"
    elif recent_avg < previous_avg:
        trend = "worsening"
    else:
        trend = "stable"

    return trend, {
        "recent_avg": recent_avg,
        "previous_avg": previous_avg,
        "change_pct": change_pct,
    }
