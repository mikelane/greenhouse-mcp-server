"""Pipeline health tool -- answers 'where are things stuck?'.

Composes job stages and applications to produce per-stage candidate
counts, staleness metrics, and bottleneck detection with severity levels.
See ADR 0005 for the bottleneck algorithm and design rationale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from greenhouse_mcp.ports import GreenhousePort

_STALE_FRACTION_THRESHOLD = 0.50


def _days_since(iso_timestamp: str) -> float:
    """Compute days elapsed since an ISO 8601 timestamp."""
    then = datetime.fromisoformat(iso_timestamp)
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    return (datetime.now(tz=UTC) - then).total_seconds() / 86400


def _classify_severity(
    share: float,
    stale_fraction: float,
    bottleneck_threshold: float,
) -> str | None:
    """Assign bottleneck severity based on share and staleness.

    Args:
        share: Fraction of total active applications in this stage.
        stale_fraction: Fraction of stage applications that are stale.
        bottleneck_threshold: Share threshold for bottleneck detection.

    Returns:
        Severity string (HIGH, MEDIUM, LOW) or None if healthy.
    """
    is_concentrated = share >= bottleneck_threshold
    is_stale = stale_fraction >= _STALE_FRACTION_THRESHOLD

    if is_concentrated and is_stale:
        return "HIGH"
    if is_concentrated:
        return "MEDIUM"
    if is_stale:
        return "LOW"
    return None


def _analyze_single_job(
    job: dict[str, Any],
    raw_stages: list[dict[str, Any]],
    all_applications: list[dict[str, Any]],
    bottleneck_threshold: float,
    staleness_days: int,
) -> dict[str, Any]:
    """Produce pipeline health report for a single job.

    Args:
        job: Job dict with id and name.
        raw_stages: Stage dicts from the API.
        all_applications: Application dicts (pre-filtered to this job).
        bottleneck_threshold: Share threshold for bottleneck detection.
        staleness_days: Days without activity to consider stale.

    Returns:
        Single-job pipeline health report.
    """
    active_stages = sorted(
        [s for s in raw_stages if s.get("active", True)],
        key=lambda s: s.get("priority", 0),
    )
    active_stage_ids = {s["id"] for s in active_stages}

    active_apps = [
        a
        for a in all_applications
        if a.get("status") == "active" and not a.get("prospect", False) and a.get("current_stage") is not None
    ]

    apps_by_stage: dict[int, list[dict[str, Any]]] = {}
    unknown_apps: list[dict[str, Any]] = []
    for app in active_apps:
        stage_id = app["current_stage"]["id"]
        if stage_id in active_stage_ids:
            apps_by_stage.setdefault(stage_id, []).append(app)
        else:
            unknown_apps.append(app)

    total_active = len(active_apps)

    stage_results: list[dict[str, Any]] = []
    bottleneck_names: list[str] = []

    for stage in active_stages:
        stage_apps = apps_by_stage.get(stage["id"], [])
        count = len(stage_apps)
        share = count / total_active if total_active > 0 else 0.0

        days_values = [_days_since(a["last_activity_at"]) for a in stage_apps]
        avg_days = sum(days_values) / len(days_values) if days_values else 0.0
        cold_count = sum(1 for d in days_values if d >= staleness_days)  # gremlin: pardon[untestable] float from _days_since never equals int staleness_days
        stale_fraction = cold_count / count if count > 0 else 0.0

        severity = _classify_severity(share, stale_fraction, bottleneck_threshold)
        is_bottleneck = severity in {"HIGH", "MEDIUM"}

        if is_bottleneck:
            bottleneck_names.append(stage["name"])

        stage_results.append(
            {
                "stage_id": stage["id"],
                "stage_name": stage["name"],
                "count": count,
                "share": share,
                "avg_days_since_activity": avg_days,
                "cold_count": cold_count,
                "is_bottleneck": is_bottleneck,
                "severity": severity,
            }
        )

    if unknown_apps:
        unknown_count = len(unknown_apps)
        unknown_share = unknown_count / total_active if total_active > 0 else 0.0  # gremlin: pardon[equivalent] total_active>0 and >=0 identical for non-negative len()
        unknown_days = [_days_since(a["last_activity_at"]) for a in unknown_apps]
        unknown_avg = sum(unknown_days) / len(unknown_days) if unknown_days else 0.0
        unknown_cold = sum(1 for d in unknown_days if d >= staleness_days)  # gremlin: pardon[untestable] float from _days_since never equals int staleness_days
        unknown_stale_frac = unknown_cold / unknown_count if unknown_count > 0 else 0.0  # gremlin: pardon[equivalent] unknown_count>0 and >=0 identical for non-negative len()
        unknown_severity = _classify_severity(unknown_share, unknown_stale_frac, bottleneck_threshold)
        unknown_is_bottleneck = unknown_severity in {"HIGH", "MEDIUM"}

        if unknown_is_bottleneck:
            bottleneck_names.append("Unknown/Deleted Stage")

        stage_results.append(
            {
                "stage_id": None,
                "stage_name": "Unknown/Deleted Stage",
                "count": unknown_count,
                "share": unknown_share,
                "avg_days_since_activity": unknown_avg,
                "cold_count": unknown_cold,
                "is_bottleneck": unknown_is_bottleneck,
                "severity": unknown_severity,
            }
        )

    return {
        "job_id": job["id"],
        "job_name": job["name"],
        "total_active": total_active,
        "stages": stage_results,
        "bottlenecks": bottleneck_names,
    }


async def pipeline_health(
    job_id: int | None = None,
    bottleneck_threshold: float = 0.30,
    staleness_days: int = 7,
    client: GreenhousePort | None = None,
) -> dict[str, Any]:
    """Analyze hiring pipeline health with bottleneck detection.

    Answers "where are things stuck?" by grouping active applications
    by stage, computing staleness, and flagging bottlenecks.

    Args:
        job_id: Specific job to analyze. All open jobs if omitted.
        bottleneck_threshold: Share of pipeline to flag as bottleneck.
        staleness_days: Days without activity to consider an app stale.
        client: GreenhousePort implementation (injected via Depends).

    Returns:
        Pipeline health report with per-stage counts and bottleneck flags.

    Raises:
        NotFoundError: If the specified job_id does not exist.
    """
    assert client is not None  # noqa: S101

    if job_id is not None:
        job = await client.get_job(job_id)
        stages = await client.get_job_stages(job_id)
        applications = await client.get_applications(job_id=job_id, status="active")
        return _analyze_single_job(job, stages, applications, bottleneck_threshold, staleness_days)

    jobs = await client.get_jobs(status="open")
    if not jobs:
        return {"jobs": [], "jobs_needing_attention": []}

    job_reports: list[dict[str, Any]] = []
    jobs_needing_attention: list[int] = []

    for job in jobs:
        jid = job["id"]
        stages = await client.get_job_stages(jid)
        applications = await client.get_applications(job_id=jid, status="active")
        report = _analyze_single_job(job, stages, applications, bottleneck_threshold, staleness_days)
        job_reports.append(report)

        has_high = any(s["severity"] == "HIGH" for s in report["stages"])
        if has_high:
            jobs_needing_attention.append(jid)

    return {
        "jobs": job_reports,
        "jobs_needing_attention": jobs_needing_attention,
    }
