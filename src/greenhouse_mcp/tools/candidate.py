"""Candidate dossier tool -- assembles a complete candidate picture.

Answers "tell me everything about this person" by composing multiple
Greenhouse API calls into a single structured response with summary-first
design for agent consumption.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from greenhouse_mcp.exceptions import NotFoundError

if TYPE_CHECKING:
    from greenhouse_mcp.ports import GreenhousePort

_ACTIVITY_TRUNCATION_LIMIT = 10

_STATUS_PRIORITY = {
    "active": 0,
    "hired": 1,
    "converted": 2,
    "rejected": 3,
}


def _derive_overall_status(application_stubs: list[dict[str, Any]]) -> str:
    """Derive the candidate's overall status from their application statuses.

    Args:
        application_stubs: Application stub dicts with 'status' keys.

    Returns:
        The derived overall status string.
    """
    if not application_stubs:
        return "no_applications"

    statuses = [app.get("status", "rejected") for app in application_stubs]

    if "active" in statuses:
        return "active"
    if "hired" in statuses:
        return "hired"
    if "converted" in statuses:
        return "converted"
    return "rejected"


def _has_pending_offers(all_offers: list[list[dict[str, Any]]]) -> bool:
    """Check if any application has an unresolved offer.

    Args:
        all_offers: List of offer lists, one per application.

    Returns:
        True if any offer has status 'unresolved'.
    """
    return any(offer.get("status") == "unresolved" for offers in all_offers for offer in offers)


def _extract_email(candidate: dict[str, Any]) -> str | None:
    """Extract the first email address from a candidate dict.

    Args:
        candidate: The raw candidate dict from the API.

    Returns:
        The first email value, or None if no emails exist.
    """
    addresses = candidate.get("email_addresses", [])
    if addresses:
        return addresses[0].get("value")  # type: ignore[no-any-return]
    return None


def _extract_phone(candidate: dict[str, Any]) -> str | None:
    """Extract the first phone number from a candidate dict.

    Args:
        candidate: The raw candidate dict from the API.

    Returns:
        The first phone value, or None if no phones exist.
    """
    numbers = candidate.get("phone_numbers", [])
    if numbers:
        return numbers[0].get("value")  # type: ignore[no-any-return]
    return None


def _build_summary(
    candidate: dict[str, Any],
    application_stubs: list[dict[str, Any]],
    all_offers: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build the summary section of the dossier.

    Args:
        candidate: The raw candidate dict from the API.
        application_stubs: Application stub dicts embedded in the candidate.
        all_offers: List of offer lists, one per application.

    Returns:
        Summary dict with identity and derived fields.
    """
    active_count = sum(1 for app in application_stubs if app.get("status") == "active")

    return {
        "candidate_id": candidate["id"],
        "name": candidate.get("name", ""),
        "email": _extract_email(candidate),
        "phone": _extract_phone(candidate),
        "tags": candidate.get("tags", []),
        "application_count": len(application_stubs),
        "active_application_count": active_count,
        "has_pending_offers": _has_pending_offers(all_offers),
        "overall_status": _derive_overall_status(application_stubs),
    }


def _format_scorecard(raw: dict[str, Any]) -> dict[str, Any]:
    """Format a raw scorecard into the dossier's flattened shape.

    Args:
        raw: Raw scorecard dict from the API.

    Returns:
        Formatted scorecard dict.
    """
    interviewer = raw.get("interviewer") or {}
    return {
        "id": raw["id"],
        "interview": raw.get("interview", ""),
        "interviewer": interviewer.get("name", ""),
        "overall_recommendation": raw.get("overall_recommendation", ""),
        "submitted_at": raw.get("submitted_at"),
        "status": "submitted" if raw.get("submitted_at") is not None else "draft",
    }


def _format_interview(raw: dict[str, Any]) -> dict[str, Any]:
    """Format a raw scheduled interview into the dossier's flattened shape.

    Args:
        raw: Raw scheduled interview dict from the API.

    Returns:
        Formatted interview dict.
    """
    interview_info = raw.get("interview") or {}
    start_info = raw.get("start") or {}
    interviewers = raw.get("interviewers") or []

    return {
        "id": raw["id"],
        "interview_name": interview_info.get("name", ""),
        "start": start_info.get("date_time", ""),
        "status": raw.get("status", ""),
        "interviewers": [iv.get("name", "") for iv in interviewers],
    }


def _format_offer(raw: dict[str, Any]) -> dict[str, Any]:
    """Format a raw offer into the dossier's flattened shape.

    Args:
        raw: Raw offer dict from the API.

    Returns:
        Formatted offer dict.
    """
    return {
        "id": raw["id"],
        "status": raw.get("status", ""),
        "starts_at": raw.get("starts_at"),
        "sent_at": raw.get("sent_at"),
    }


def _build_application_detail(
    app_stub: dict[str, Any],
    scorecards: list[dict[str, Any]],
    interviews: list[dict[str, Any]],
    offers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a detailed application entry for the dossier.

    Args:
        app_stub: The application stub from the candidate response.
        scorecards: Raw scorecards for this application.
        interviews: Raw scheduled interviews for this application.
        offers: Raw offers for this application.

    Returns:
        Formatted application detail dict.
    """
    jobs = app_stub.get("jobs") or []
    job_name = jobs[0].get("name", "") if jobs else ""
    stage = app_stub.get("current_stage")
    stage_name = stage.get("name", "") if stage else None
    source = app_stub.get("source")
    source_name = source.get("public_name", "") if source else None
    recruiter = app_stub.get("recruiter")
    recruiter_name = recruiter.get("name", "") if recruiter else None

    return {
        "application_id": app_stub["id"],
        "job_name": job_name,
        "status": app_stub.get("status", ""),
        "current_stage": stage_name,
        "applied_at": app_stub.get("applied_at", ""),
        "last_activity_at": app_stub.get("last_activity_at", ""),
        "source": source_name,
        "recruiter": recruiter_name,
        "scorecards": [_format_scorecard(sc) for sc in scorecards],
        "scheduled_interviews": [_format_interview(iv) for iv in interviews],
        "offers": [_format_offer(o) for o in offers],
    }


def _build_activity_feed(raw_feed: dict[str, Any]) -> dict[str, Any]:
    """Build the truncated activity feed section.

    Args:
        raw_feed: Raw activity feed dict from the API.

    Returns:
        Truncated feed with recent items and total counts.
    """
    notes = raw_feed.get("notes", [])
    emails = raw_feed.get("emails", [])
    activities = raw_feed.get("activities", [])

    return {
        "recent_notes": notes[:_ACTIVITY_TRUNCATION_LIMIT],
        "recent_emails": emails[:_ACTIVITY_TRUNCATION_LIMIT],
        "total_notes": len(notes),
        "total_emails": len(emails),
        "total_activities": len(activities),
    }


async def _fetch_application_details(
    client: GreenhousePort,
    app_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch scorecards, interviews, and offers concurrently for one application.

    Args:
        client: The Greenhouse API client.
        app_id: The application ID.

    Returns:
        Tuple of (scorecards, interviews, offers).
    """
    scorecards, interviews, offers = await asyncio.gather(
        client.get_scorecards(app_id),
        client.get_scheduled_interviews(application_id=app_id),
        client.get_offers(application_id=app_id),
    )
    return scorecards, interviews, offers


async def candidate_dossier(
    candidate_id: int,
    client: GreenhousePort,
) -> dict[str, Any]:
    """Assemble a complete candidate dossier from multiple API sources.

    Fetches candidate details, then concurrently fetches per-application
    sub-resources (scorecards, interviews, offers) and the activity feed.

    Args:
        candidate_id: The Greenhouse candidate ID.
        client: The Greenhouse API client (injected via DI).

    Returns:
        Structured dossier dict with summary, applications, and activity feed.
        On candidate not found, returns an error dict.
    """
    try:
        candidate = await client.get_candidate(candidate_id)
    except NotFoundError:
        return {
            "error": True,
            "message": f"Candidate {candidate_id} not found",
        }

    application_stubs = candidate.get("applications", [])
    application_ids = [app["id"] for app in application_stubs]

    # Fetch all sub-resources concurrently
    app_detail_coros = [_fetch_application_details(client, app_id) for app_id in application_ids]
    activity_feed_coro = client.get_activity_feed(candidate_id)

    results = await asyncio.gather(*app_detail_coros, activity_feed_coro)

    # Unpack: all but last are app detail tuples, last is activity feed
    app_details = results[:-1]
    raw_activity_feed: dict[str, Any] = results[-1]  # type: ignore[assignment]

    # Build application detail entries and collect all offers for summary
    all_offers: list[list[dict[str, Any]]] = []
    applications: list[dict[str, Any]] = []

    for app_stub, details in zip(application_stubs, app_details, strict=True):  # pragma: no mutate
        scorecards, interviews, offers = details
        all_offers.append(offers)  # type: ignore[arg-type]
        applications.append(
            _build_application_detail(app_stub, scorecards, interviews, offers)  # type: ignore[arg-type]
        )

    return {
        "summary": _build_summary(candidate, application_stubs, all_offers),
        "applications": applications,
        "activity_feed": _build_activity_feed(raw_activity_feed),
    }
