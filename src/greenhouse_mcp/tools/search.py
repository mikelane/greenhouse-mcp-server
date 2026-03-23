"""search_talent tool: find candidates matching criteria.

Composes candidate search with application enrichment to answer
"find candidates matching X" with ranked, contextual results.
See ADR 0009 for Greenhouse API search limitations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from greenhouse_mcp.ports import GreenhousePort

_EXACT_MATCH_BONUS = 50.0
_PARTIAL_MATCH_SCORE = 25.0
_RECENCY_MAX_SCORE = 25.0
_RECENCY_DECAY_DAYS = 30


def _matches_name(candidate: dict[str, Any], query: str) -> bool:
    """Check if a candidate's name contains the query substring (case-insensitive)."""
    query_lower = query.lower()
    first = candidate.get("first_name", "").lower()
    last = candidate.get("last_name", "").lower()
    full = candidate.get("name", "").lower()
    return query_lower in first or query_lower in last or query_lower in full


def _compute_name_score(candidate: dict[str, Any], query: str) -> float:
    """Score a candidate's name match quality.

    Exact match on first_name or last_name scores higher than partial substring.

    Args:
        candidate: Candidate dict with first_name, last_name, name fields.
        query: Search query string.

    Returns:
        Name relevance score (0-50).
    """
    query_lower = query.lower()
    first = candidate.get("first_name", "").lower()
    last = candidate.get("last_name", "").lower()

    if query_lower in (first, last):
        return _EXACT_MATCH_BONUS
    return _PARTIAL_MATCH_SCORE


def _compute_recency_score(applications: list[dict[str, Any]]) -> float:
    """Score based on most recent activity across applications.

    More recent activity yields a higher score, decaying over RECENCY_DECAY_DAYS.

    Args:
        applications: List of enriched application dicts.

    Returns:
        Recency score (0-25).
    """
    if not applications:
        return 0.0

    most_recent: datetime | None = None
    for app in applications:
        last_activity = app.get("last_activity_at", "")
        if not last_activity:
            continue
        try:
            ts = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
        except ValueError, AttributeError:
            continue
        # gremlin: pardon[equivalent]  # noqa: ERA001
        if most_recent is None or ts > most_recent:
            most_recent = ts

    if most_recent is None:
        return 0.0

    now = datetime.now(tz=UTC)
    days_ago = max(0.0, (now - most_recent).total_seconds() / 86400)
    return max(0.0, _RECENCY_MAX_SCORE * (1.0 - days_ago / _RECENCY_DECAY_DAYS))


def _has_matching_stage(applications: list[dict[str, Any]], stage: str) -> bool:
    """Check if any application is in the given stage (case-insensitive)."""
    stage_lower = stage.lower()
    return any(app.get("stage", "").lower() == stage_lower for app in applications)


def _has_matching_source(applications: list[dict[str, Any]], source: str) -> bool:
    """Check if any application has the given source (case-insensitive)."""
    source_lower = source.lower()
    return any(app.get("source", "").lower() == source_lower for app in applications)


def _has_all_tags(candidate: dict[str, Any], tags: list[str]) -> bool:
    """Check if a candidate has all the specified tags (case-insensitive)."""
    candidate_tags = {t.lower() for t in candidate.get("tags", [])}
    return all(t.lower() in candidate_tags for t in tags)


def _enrich_application(app: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant fields from a raw application dict.

    Args:
        app: Raw application dict from the API.

    Returns:
        Enriched application dict with flattened fields.
    """
    source_obj = app.get("source")
    source_name = source_obj.get("public_name", "Unknown") if source_obj else "Unknown"
    stage_obj = app.get("current_stage")
    stage_name = stage_obj["name"] if stage_obj else "Unknown"
    jobs = app.get("jobs", [])
    job_name = jobs[0]["name"] if jobs else "Unknown"

    return {
        "application_id": app["id"],
        "job_name": job_name,
        "stage": stage_name,
        "status": app.get("status", "unknown"),
        "source": source_name,
        "applied_at": app.get("applied_at", ""),
        "last_activity_at": app.get("last_activity_at", ""),
    }


def _build_filters_applied(
    *,
    stage: str | None,
    source: str | None,
    tags: list[str] | None,
    created_after: str | None,
    job_id: int | None,
) -> dict[str, Any]:
    """Build the filters_applied dict for the response."""
    filters: dict[str, Any] = {}
    if stage is not None:
        filters["stage"] = stage
    if source is not None:
        filters["source"] = source
    if tags is not None:
        filters["tags"] = tags
    if created_after is not None:
        filters["created_after"] = created_after
    if job_id is not None:
        filters["job_id"] = job_id
    return filters


async def search_talent(  # noqa: PLR0913, C901
    *,
    query: str | None = None,
    job_id: int | None = None,
    stage: str | None = None,
    source: str | None = None,
    tags: list[str] | None = None,
    created_after: str | None = None,
    created_after_days: int | None = None,
    client: GreenhousePort,
) -> dict[str, Any]:
    """Find candidates matching search criteria with ranked results.

    Fetches candidates using available API filters, applies client-side
    filtering for name/tag matches, enriches with application data,
    and ranks by relevance.

    Args:
        query: Name substring to search for (case-insensitive).
        job_id: Filter to candidates with applications for this job.
        stage: Filter to candidates currently in this pipeline stage.
        source: Filter to candidates from this application source.
        tags: Filter to candidates with all of these tags.
        created_after: ISO 8601 lower bound for candidate creation date.
        created_after_days: Convenience alternative to created_after.
        client: Greenhouse API client (injected).

    Returns:
        Dict with total_results, results list, filters_applied, and message.
    """
    effective_created_after = created_after
    if created_after_days is not None and effective_created_after is None:
        cutoff = datetime.now(tz=UTC) - timedelta(days=created_after_days)
        effective_created_after = cutoff.isoformat()

    candidates = await client.get_candidates(
        job_id=job_id,
        created_after=effective_created_after,
    )

    all_applications = await client.get_applications()

    apps_by_candidate: dict[int, list[dict[str, Any]]] = {}
    for app in all_applications:
        cid = app.get("candidate_id")
        if cid is not None:
            apps_by_candidate.setdefault(cid, []).append(app)

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        cid = candidate["id"]

        if query is not None and not _matches_name(candidate, query):
            continue

        if tags is not None and not _has_all_tags(candidate, tags):
            continue

        raw_apps = apps_by_candidate.get(cid, [])
        enriched_apps = [_enrich_application(app) for app in raw_apps]

        if stage is not None and not _has_matching_stage(enriched_apps, stage):
            continue

        if source is not None and not _has_matching_source(enriched_apps, source):
            continue

        name_score = _compute_name_score(candidate, query) if query else 0.0
        recency_score = _compute_recency_score(enriched_apps) if query else 0.0
        relevance = name_score + recency_score

        results.append(
            {
                "candidate_id": cid,
                "name": candidate.get("name", ""),
                "email": candidate["email_addresses"][0]["value"] if candidate.get("email_addresses") else "",
                "tags": candidate.get("tags", []),
                "current_applications": enriched_apps,
                "relevance_score": relevance,
            }
        )

    results.sort(key=lambda r: r["relevance_score"], reverse=True)

    filters_applied = _build_filters_applied(
        stage=stage,
        source=source,
        tags=tags,
        created_after=effective_created_after,
        job_id=job_id,
    )

    message: str | None = None
    if not results:
        parts = []
        if query:
            parts.append(f'No candidates found matching "{query}"')
        else:
            parts.append("No candidates found")
        if filters_applied:
            filter_desc = ", ".join(f"{k}={v}" for k, v in filters_applied.items())
            parts.append(f"with filters: {filter_desc}")
        message = " ".join(parts)

    return {
        "query": query,
        "filters_applied": filters_applied,
        "total_results": len(results),
        "results": results,
        "message": message,
    }
