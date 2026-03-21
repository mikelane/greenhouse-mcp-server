"""needs_attention tool: surfaces items falling through the cracks.

Detects stale applications, missing scorecards, pending offers,
and candidates with no recent activity. Returns priority-scored
action items sorted by urgency.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from greenhouse_mcp.ports import GreenhousePort

# Category severity scores (ADR 0007, Factor 1)
_SEVERITY_MISSING_SCORECARD = 100
_SEVERITY_PENDING_OFFER = 95
_SEVERITY_STUCK_APPLICATION = 60
_SEVERITY_NO_ACTIVITY = 50

# Default thresholds
_DEFAULT_DAYS_STALE = 7
_DEFAULT_SCORECARD_HOURS = 48
_DEFAULT_OFFER_SENT_DAYS = 3
_DEFAULT_OFFER_DRAFT_DAYS = 2
_DEFAULT_NO_ACTIVITY_DAYS = 14


def _parse_iso_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp from the Greenhouse API."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date_string(value: str) -> datetime:
    """Parse a YYYY-MM-DD date string into a UTC datetime at midnight."""
    d = date_type.fromisoformat(value)
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def _compute_priority_score(
    *,
    severity: int,
    days_overdue: int,
    threshold: int,
    stage_index: int,
    total_stages: int,
) -> float:
    """Compute composite priority score (0-100) per ADR 0007.

    Three factors:
    - Category severity (40%): from the category constants
    - Days overdue (40%): min(100, (days_overdue / threshold) * 50)
    - Stage proximity to hire (20%): (stage_index / total_stages) * 100

    Args:
        severity: Category severity score (0-100).
        days_overdue: Days past the threshold.
        threshold: The threshold in days for this category.
        stage_index: 0-based position of current stage.
        total_stages: Total number of stages in the job pipeline.

    Returns:
        Composite priority score between 0 and 100.
    """
    overdue_score = min(100.0, (days_overdue / max(threshold, 1)) * 50)
    stage_score = (stage_index / max(total_stages, 1)) * 100 if total_stages > 0 else 0.0
    return (severity * 0.4) + (overdue_score * 0.4) + (stage_score * 0.2)


def _get_stage_position(
    stage_id: int,
    stages: list[dict[str, Any]],
) -> tuple[int, int]:
    """Find the 0-based index and total count for a stage.

    Args:
        stage_id: The stage ID to find.
        stages: List of stage dicts with 'id' and 'priority' fields.

    Returns:
        Tuple of (stage_index, total_stages). Returns (0, 1) if not found.
    """
    active_stages = [s for s in stages if s.get("active", True)]
    active_stages.sort(key=lambda s: s.get("priority", 0))
    total = len(active_stages)
    for idx, stage in enumerate(active_stages):
        if stage["id"] == stage_id:
            return idx, total
    return 0, max(total, 1)


async def _detect_stuck_applications(  # noqa: PLR0913
    client: GreenhousePort,
    *,
    applications: list[dict[str, Any]],
    days_stale: int,
    now: datetime,
    stages_cache: dict[int, list[dict[str, Any]]],
    candidate_cache: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect applications stuck in stage beyond threshold.

    Args:
        client: Greenhouse API client.
        applications: Active applications to scan.
        days_stale: Threshold in days.
        now: Current timestamp for comparison.
        stages_cache: Cache of job stages by job_id.
        candidate_cache: Cache of candidate data by candidate_id.

    Returns:
        List of attention items for stuck applications.
    """
    items: list[dict[str, Any]] = []
    threshold = timedelta(days=days_stale)

    for app in applications:
        current_stage = app.get("current_stage")
        if current_stage is None:
            continue

        last_activity_str = app.get("last_activity_at")
        if last_activity_str is None:
            continue

        last_activity = _parse_iso_timestamp(last_activity_str)
        elapsed = now - last_activity
        if elapsed <= threshold:
            continue

        days_overdue = (elapsed - threshold).days
        candidate_id = app["candidate_id"]
        job_id = app["jobs"][0]["id"] if app.get("jobs") else 0
        job_name = app["jobs"][0]["name"] if app.get("jobs") else "Unknown"

        if candidate_id not in candidate_cache:
            candidate_cache[candidate_id] = await client.get_candidate(candidate_id)
        candidate = candidate_cache[candidate_id]
        candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

        if job_id not in stages_cache:
            stages_cache[job_id] = await client.get_job_stages(job_id)
        stage_index, total_stages = _get_stage_position(
            current_stage["id"],
            stages_cache[job_id],
        )

        priority = _compute_priority_score(
            severity=_SEVERITY_STUCK_APPLICATION,
            days_overdue=days_overdue,
            threshold=days_stale,
            stage_index=stage_index,
            total_stages=total_stages,
        )

        items.append(
            {
                "type": "stuck_application",
                "priority_score": priority,
                "candidate_name": candidate_name,
                "candidate_id": candidate_id,
                "application_id": app["id"],
                "job_name": job_name,
                "detail": f"In {current_stage['name']} for {elapsed.days} days ({days_overdue} days overdue)",
                "days_overdue": days_overdue,
                "suggested_action": f"Review {candidate_name}'s application in {current_stage['name']}",
            }
        )

    return items


async def _detect_missing_scorecards(  # noqa: PLR0913
    client: GreenhousePort,
    *,
    applications: list[dict[str, Any]],
    scorecard_hours: int,
    now: datetime,
    stages_cache: dict[int, list[dict[str, Any]]],
    candidate_cache: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect unsubmitted scorecards past threshold.

    Args:
        client: Greenhouse API client.
        applications: Active applications to scan.
        scorecard_hours: Threshold in hours since interview.
        now: Current timestamp for comparison.
        stages_cache: Cache of job stages by job_id.
        candidate_cache: Cache of candidate data by candidate_id.

    Returns:
        List of attention items for missing scorecards.
    """
    items: list[dict[str, Any]] = []
    threshold = timedelta(hours=scorecard_hours)

    for app in applications:
        app_id = app["id"]
        scorecards = await client.get_scorecards(app_id)

        for sc in scorecards:
            if sc.get("submitted_at") is not None:
                continue

            interviewed_at_str = sc.get("interviewed_at")
            if interviewed_at_str is None:
                continue

            interviewed_at = _parse_iso_timestamp(interviewed_at_str)
            elapsed = now - interviewed_at
            if elapsed <= threshold:
                continue

            days_overdue = max(1, elapsed.days - (scorecard_hours // 24))
            candidate_id = app["candidate_id"]
            job_id = app["jobs"][0]["id"] if app.get("jobs") else 0
            job_name = app["jobs"][0]["name"] if app.get("jobs") else "Unknown"
            interview_name = sc.get("interview", "Interview")

            if candidate_id not in candidate_cache:
                candidate_cache[candidate_id] = await client.get_candidate(candidate_id)
            candidate = candidate_cache[candidate_id]
            candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

            current_stage = app.get("current_stage")
            stage_id = current_stage["id"] if current_stage else 0
            if job_id not in stages_cache:
                stages_cache[job_id] = await client.get_job_stages(job_id)
            stage_index, total_stages = _get_stage_position(
                stage_id,
                stages_cache[job_id],
            )

            priority = _compute_priority_score(
                severity=_SEVERITY_MISSING_SCORECARD,
                days_overdue=days_overdue,
                threshold=max(1, scorecard_hours // 24),  # gremlin: pardon[equivalent] //vs/ same
                stage_index=stage_index,
                total_stages=total_stages,
            )

            items.append(
                {
                    "type": "missing_scorecard",
                    "priority_score": priority,
                    "candidate_name": candidate_name,
                    "candidate_id": candidate_id,
                    "application_id": app_id,
                    "job_name": job_name,
                    "detail": f"Interview completed {elapsed.days} days ago, scorecard not submitted",
                    "days_overdue": days_overdue,
                    "suggested_action": f"Submit scorecard for {candidate_name}'s {interview_name}",
                }
            )

    return items


async def _detect_pending_offers(  # noqa: PLR0913
    client: GreenhousePort,
    *,
    applications: list[dict[str, Any]],
    offer_sent_days: int,
    offer_draft_days: int,
    now: datetime,
    stages_cache: dict[int, list[dict[str, Any]]],
    candidate_cache: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect unresolved offers past threshold.

    Args:
        client: Greenhouse API client.
        applications: Active applications (used for stage lookup).
        offer_sent_days: Threshold for sent offers.
        offer_draft_days: Threshold for drafted-but-not-sent offers.
        now: Current timestamp for comparison.
        stages_cache: Cache of job stages by job_id.
        candidate_cache: Cache of candidate data by candidate_id.

    Returns:
        List of attention items for pending offers.
    """
    items: list[dict[str, Any]] = []
    offers = await client.get_offers(status="unresolved")

    app_lookup: dict[int, dict[str, Any]] = {a["id"]: a for a in applications}

    for offer in offers:
        sent_at_str = offer.get("sent_at")
        if sent_at_str is not None:
            reference_time = _parse_date_string(sent_at_str)
            threshold_days = offer_sent_days
        else:
            created_at_str = offer.get("created_at")
            if not created_at_str:
                continue
            reference_time = _parse_iso_timestamp(created_at_str)
            threshold_days = offer_draft_days

        threshold = timedelta(days=threshold_days)
        elapsed = now - reference_time
        if elapsed <= threshold:
            continue

        days_overdue = elapsed.days - threshold_days
        app_id = offer.get("application_id", 0)
        candidate_id = offer.get("candidate_id", 0)
        job_id = offer.get("job_id", 0)

        app = app_lookup.get(app_id)
        job_name = "Unknown"
        if app and app.get("jobs"):
            job_name = app["jobs"][0]["name"]
            job_id = app["jobs"][0]["id"]

        if candidate_id not in candidate_cache:
            candidate_cache[candidate_id] = await client.get_candidate(candidate_id)
        candidate = candidate_cache[candidate_id]
        candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

        current_stage = app.get("current_stage") if app else None
        stage_id = current_stage["id"] if current_stage else 0
        if job_id not in stages_cache:
            stages_cache[job_id] = await client.get_job_stages(job_id)
        stage_index, total_stages = _get_stage_position(
            stage_id,
            stages_cache[job_id],
        )

        offer_type = "sent" if sent_at_str is not None else "drafted"
        priority = _compute_priority_score(
            severity=_SEVERITY_PENDING_OFFER,
            days_overdue=days_overdue,
            threshold=threshold_days,
            stage_index=stage_index,
            total_stages=total_stages,
        )

        items.append(
            {
                "type": "pending_offer",
                "priority_score": priority,
                "candidate_name": candidate_name,
                "candidate_id": candidate_id,
                "application_id": app_id,
                "job_name": job_name,
                "detail": f"Offer {offer_type} {elapsed.days} days ago, still unresolved",
                "days_overdue": days_overdue,
                "suggested_action": f"Follow up on {candidate_name}'s pending offer",
            }
        )

    return items


async def _detect_no_activity(  # noqa: PLR0913
    client: GreenhousePort,
    *,
    applications: list[dict[str, Any]],
    no_activity_days: int,
    now: datetime,
    stuck_app_ids: set[int],
    stages_cache: dict[int, list[dict[str, Any]]],
    candidate_cache: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect candidates with no recent activity.

    Deduplicates against stuck applications: if an application already
    appears as stuck AND qualifies as no-activity, only the no-activity
    item is kept (higher severity replaces lower).

    Args:
        client: Greenhouse API client.
        applications: Active applications to scan.
        no_activity_days: Threshold in days.
        now: Current timestamp for comparison.
        stuck_app_ids: Set of application IDs already flagged as stuck.
        stages_cache: Cache of job stages by job_id.
        candidate_cache: Cache of candidate data by candidate_id.

    Returns:
        List of attention items for no-activity applications.
    """
    items: list[dict[str, Any]] = []
    threshold = timedelta(days=no_activity_days)

    for app in applications:
        current_stage = app.get("current_stage")
        if current_stage is None:
            continue

        last_activity_str = app.get("last_activity_at")
        if last_activity_str is None:
            continue

        last_activity = _parse_iso_timestamp(last_activity_str)
        elapsed = now - last_activity
        if elapsed <= threshold:
            continue

        app_id = app["id"]
        days_overdue = (elapsed - threshold).days
        candidate_id = app["candidate_id"]
        job_id = app["jobs"][0]["id"] if app.get("jobs") else 0
        job_name = app["jobs"][0]["name"] if app.get("jobs") else "Unknown"

        if candidate_id not in candidate_cache:
            candidate_cache[candidate_id] = await client.get_candidate(candidate_id)
        candidate = candidate_cache[candidate_id]
        candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

        if job_id not in stages_cache:
            stages_cache[job_id] = await client.get_job_stages(job_id)
        stage_index, total_stages = _get_stage_position(
            current_stage["id"],
            stages_cache[job_id],
        )

        priority = _compute_priority_score(
            severity=_SEVERITY_NO_ACTIVITY,
            days_overdue=days_overdue,
            threshold=no_activity_days,
            stage_index=stage_index,
            total_stages=total_stages,
        )

        if app_id in stuck_app_ids:
            stuck_app_ids.discard(app_id)

        items.append(
            {
                "type": "no_activity",
                "priority_score": priority,
                "candidate_name": candidate_name,
                "candidate_id": candidate_id,
                "application_id": app_id,
                "job_name": job_name,
                "detail": f"No activity for {elapsed.days} days ({days_overdue} days overdue)",
                "days_overdue": days_overdue,
                "suggested_action": f"Check in on {candidate_name}'s application status",
            }
        )

    return items


async def needs_attention(  # noqa: PLR0913
    *,
    job_id: int | None = None,
    days_stale: int = _DEFAULT_DAYS_STALE,
    scorecard_hours: int = _DEFAULT_SCORECARD_HOURS,
    offer_sent_days: int = _DEFAULT_OFFER_SENT_DAYS,
    offer_draft_days: int = _DEFAULT_OFFER_DRAFT_DAYS,
    no_activity_days: int = _DEFAULT_NO_ACTIVITY_DAYS,
    client: GreenhousePort,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Surface items that need recruiter or hiring manager attention.

    Detects four categories of issues:
    1. Applications stuck in stage beyond threshold
    2. Missing scorecards for completed interviews
    3. Offers pending approval beyond threshold
    4. Candidates with no recent activity

    Items are priority-scored using a 3-factor composite:
    severity (40%) + days overdue (40%) + stage proximity (20%).

    Args:
        job_id: Filter to a specific job (all jobs if None).
        days_stale: Days before an application is considered stuck.
        scorecard_hours: Hours after interview before scorecard is overdue.
        offer_sent_days: Days after sending before offer follow-up.
        offer_draft_days: Days after drafting before offer is overdue.
        no_activity_days: Days of inactivity before flagging.
        client: Greenhouse API client (injected via Depends).
        now: Current timestamp (injectable for testing).

    Returns:
        Dict with total_items, sorted items list, and summary counts.
    """
    if now is None:
        now = datetime.now(tz=UTC)  # pragma: no cover

    applications = await client.get_applications(job_id=job_id, status="active")

    stages_cache: dict[int, list[dict[str, Any]]] = {}
    candidate_cache: dict[int, dict[str, Any]] = {}

    stuck_items = await _detect_stuck_applications(
        client,
        applications=applications,
        days_stale=days_stale,
        now=now,
        stages_cache=stages_cache,
        candidate_cache=candidate_cache,
    )

    stuck_app_ids = {item["application_id"] for item in stuck_items}

    no_activity_items = await _detect_no_activity(
        client,
        applications=applications,
        no_activity_days=no_activity_days,
        now=now,
        stuck_app_ids=stuck_app_ids,
        stages_cache=stages_cache,
        candidate_cache=candidate_cache,
    )

    # Remove stuck items that were superseded by no-activity items
    stuck_items = [item for item in stuck_items if item["application_id"] in stuck_app_ids]

    missing_scorecard_items = await _detect_missing_scorecards(
        client,
        applications=applications,
        scorecard_hours=scorecard_hours,
        now=now,
        stages_cache=stages_cache,
        candidate_cache=candidate_cache,
    )

    pending_offer_items = await _detect_pending_offers(
        client,
        applications=applications,
        offer_sent_days=offer_sent_days,
        offer_draft_days=offer_draft_days,
        now=now,
        stages_cache=stages_cache,
        candidate_cache=candidate_cache,
    )

    all_items = stuck_items + missing_scorecard_items + pending_offer_items + no_activity_items
    all_items.sort(key=lambda x: x["priority_score"], reverse=True)

    return {
        "total_items": len(all_items),
        "items": all_items,
        "summary": {
            "missing_scorecards": len(missing_scorecard_items),
            "stuck_applications": len(stuck_items),
            "pending_offers": len(pending_offer_items),
            "no_activity": len(no_activity_items),
        },
    }
