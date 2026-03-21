"""Tests for the candidate_dossier tool."""

from __future__ import annotations

from typing import Any

import pytest

from greenhouse_mcp.exceptions import NotFoundError
from greenhouse_mcp.tools.candidate import candidate_dossier


class FakeGreenhouseClient:
    """In-memory fake implementing the GreenhousePort interface for testing."""

    def __init__(self) -> None:
        self.candidates: dict[int, dict[str, Any]] = {}
        self.scorecards: dict[int, list[dict[str, Any]]] = {}
        self.scheduled_interviews: dict[int, list[dict[str, Any]]] = {}
        self.offers: dict[int, list[dict[str, Any]]] = {}
        self.activity_feeds: dict[int, dict[str, Any]] = {}

    async def get_candidate(self, candidate_id: int) -> dict[str, Any]:
        if candidate_id not in self.candidates:
            msg = f"Candidate {candidate_id} not found"
            raise NotFoundError(msg)
        return self.candidates[candidate_id]

    async def get_scorecards(self, application_id: int) -> list[dict[str, Any]]:
        return self.scorecards.get(application_id, [])

    async def get_scheduled_interviews(self, *, application_id: int | None = None) -> list[dict[str, Any]]:
        if application_id is None:
            return []
        return self.scheduled_interviews.get(application_id, [])

    async def get_offers(self, *, application_id: int | None = None, status: str | None = None) -> list[dict[str, Any]]:
        if application_id is None:
            return []
        result = self.offers.get(application_id, [])
        if status is not None:
            result = [o for o in result if o.get("status") == status]
        return result

    async def get_activity_feed(self, candidate_id: int) -> dict[str, Any]:
        return self.activity_feeds.get(candidate_id, {"notes": [], "emails": [], "activities": []})


def _make_candidate(  # noqa: PLR0913
    candidate_id: int = 42,
    *,
    first_name: str = "Jane",
    last_name: str = "Doe",
    applications: list[dict[str, Any]] | None = None,
    email_addresses: list[dict[str, str]] | None = None,
    phone_numbers: list[dict[str, str]] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Build a fake candidate dict with sensible defaults.

    Bare application stubs (dicts with only ``id`` and ``status``) are
    automatically enriched via ``_make_application`` so that downstream
    production code sees the same shape the real Greenhouse API returns.
    """
    enriched_apps: list[dict[str, Any]] = []
    if applications is not None:
        for stub in applications:
            if "jobs" not in stub and "current_stage" not in stub:
                enriched_apps.append(_make_application(app_id=stub["id"], status=stub.get("status", "active")))
            else:
                enriched_apps.append(stub)
    return {
        "id": candidate_id,
        "first_name": first_name,
        "last_name": last_name,
        "name": f"{first_name} {last_name}",
        "applications": enriched_apps,
        "email_addresses": (
            email_addresses if email_addresses is not None else [{"value": "jane@example.com", "type": "personal"}]
        ),
        "phone_numbers": (phone_numbers if phone_numbers is not None else [{"value": "+1-555-0100", "type": "mobile"}]),
        "tags": tags if tags is not None else [],
    }


def _make_application(  # noqa: PLR0913
    app_id: int = 100,
    *,
    status: str = "active",
    job_name: str = "Software Engineer",
    stage_name: str = "Phone Screen",
    applied_at: str = "2026-01-15T10:00:00Z",
    last_activity_at: str = "2026-03-10T14:30:00Z",
    source_name: str = "LinkedIn",
    recruiter_name: str = "Alex Johnson",
) -> dict[str, Any]:
    return {
        "id": app_id,
        "status": status,
        "jobs": [{"id": 200, "name": job_name}],
        "current_stage": {"id": 300, "name": stage_name},
        "applied_at": applied_at,
        "last_activity_at": last_activity_at,
        "source": {"id": 1, "public_name": source_name},
        "recruiter": {"id": 10, "name": recruiter_name},
    }


def _make_scorecard(
    scorecard_id: int = 111,
    *,
    interview: str = "Technical Screen",
    interviewer_name: str = "Pat Lee",
    overall_recommendation: str = "strong_yes",
    submitted_at: str | None = "2026-02-01T16:00:00Z",
) -> dict[str, Any]:
    return {
        "id": scorecard_id,
        "interview": interview,
        "interviewer": {"id": 20, "name": interviewer_name},
        "overall_recommendation": overall_recommendation,
        "submitted_at": submitted_at,
    }


def _make_interview(
    interview_id: int = 222,
    *,
    interview_name: str = "System Design",
    start: str = "2026-03-25T13:00:00Z",
    status: str = "scheduled",
    interviewers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": interview_id,
        "interview": {"id": 30, "name": interview_name},
        "start": {"date_time": start},
        "status": status,
        "interviewers": interviewers
        or [
            {"id": 40, "name": "Morgan Chen"},
            {"id": 41, "name": "Sam Patel"},
        ],
    }


def _make_offer(
    offer_id: int = 333,
    *,
    status: str = "unresolved",
    starts_at: str = "2026-04-01",
    sent_at: str | None = "2026-03-15",
) -> dict[str, Any]:
    return {
        "id": offer_id,
        "status": status,
        "starts_at": starts_at,
        "sent_at": sent_at,
    }


def _make_activity_feed(
    *,
    num_notes: int = 0,
    num_emails: int = 0,
    num_activities: int = 0,
) -> dict[str, Any]:
    notes = [
        {
            "id": i,
            "created_at": f"2026-03-{10 - i:02d}T14:30:00Z",
            "body": f"Note {i}",
            "user": {"id": 10, "name": "Alex Johnson"},
        }
        for i in range(num_notes)
    ]
    emails = [
        {
            "id": i,
            "created_at": f"2026-03-{10 - i:02d}T14:30:00Z",
            "subject": f"Email {i}",
            "body": f"Email body {i}",
            "to": "jane@example.com",
            "from": "recruiter@company.com",
            "user": {"id": 10, "name": "Alex Johnson"},
        }
        for i in range(num_emails)
    ]
    activities = [
        {
            "id": i,
            "created_at": f"2026-03-{10 - i:02d}T14:30:00Z",
            "subject": f"Activity {i}",
            "body": f"Activity body {i}",
        }
        for i in range(num_activities)
    ]
    return {"notes": notes, "emails": emails, "activities": activities}


def _build_fake_client(  # noqa: PLR0913
    *,
    candidate: dict[str, Any] | None = None,
    scorecards: dict[int, list[dict[str, Any]]] | None = None,
    interviews: dict[int, list[dict[str, Any]]] | None = None,
    offers: dict[int, list[dict[str, Any]]] | None = None,
    activity_feed: dict[str, Any] | None = None,
    candidate_id: int = 42,
) -> FakeGreenhouseClient:
    client = FakeGreenhouseClient()
    if candidate is not None:
        client.candidates[candidate_id] = candidate
    if scorecards is not None:
        client.scorecards = scorecards
    if interviews is not None:
        client.scheduled_interviews = interviews
    if offers is not None:
        client.offers = offers
    if activity_feed is not None:
        client.activity_feeds[candidate_id] = activity_feed
    return client


@pytest.mark.small
@pytest.mark.anyio
class DescribeCandidateDossier:
    """Assembles a complete candidate dossier from multiple API sources."""

    async def it_returns_summary_applications_and_activity_feed(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [_make_scorecard()]},
            interviews={100: [_make_interview()]},
            offers={100: []},
            activity_feed=_make_activity_feed(num_notes=1),
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert "summary" in result
        assert "applications" in result
        assert "activity_feed" in result

    async def it_assembles_data_from_multiple_applications(self) -> None:
        candidate = _make_candidate(
            applications=[
                {"id": 100, "status": "active"},
                {"id": 101, "status": "rejected"},
            ]
        )
        client = _build_fake_client(
            candidate=candidate,
            scorecards={
                100: [_make_scorecard(scorecard_id=111)],
                101: [_make_scorecard(scorecard_id=112, interview="Culture Fit")],
            },
            interviews={100: [_make_interview()], 101: []},
            offers={100: [], 101: []},
            activity_feed=_make_activity_feed(num_notes=2),
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert len(result["applications"]) == 2  # noqa: PLR2004


@pytest.mark.small
@pytest.mark.anyio
class DescribeSummary:
    """The summary section provides quick-glance candidate info."""

    async def it_includes_candidate_identity_fields(self) -> None:
        candidate = _make_candidate(
            first_name="Jane",
            last_name="Doe",
            email_addresses=[{"value": "jane@example.com", "type": "personal"}],
            phone_numbers=[{"value": "+1-555-0100", "type": "mobile"}],
            tags=["senior", "referral"],
        )
        client = _build_fake_client(candidate=candidate)

        result = await candidate_dossier(candidate_id=42, client=client)
        summary = result["summary"]

        assert summary["candidate_id"] == 42  # noqa: PLR2004
        assert summary["name"] == "Jane Doe"
        assert summary["email"] == "jane@example.com"
        assert summary["phone"] == "+1-555-0100"
        assert summary["tags"] == ["senior", "referral"]

    async def it_counts_total_and_active_applications(self) -> None:
        candidate = _make_candidate(
            applications=[
                {"id": 100, "status": "active"},
                {"id": 101, "status": "rejected"},
                {"id": 102, "status": "active"},
            ]
        )
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [], 101: [], 102: []},
            interviews={100: [], 101: [], 102: []},
            offers={100: [], 101: [], 102: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        summary = result["summary"]

        assert summary["application_count"] == 3  # noqa: PLR2004
        assert summary["active_application_count"] == 2  # noqa: PLR2004

    async def it_detects_pending_offers(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: [_make_offer(status="unresolved")]},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["has_pending_offers"] is True

    async def it_reports_no_pending_offers_when_all_resolved(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: [_make_offer(status="accepted")]},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["has_pending_offers"] is False

    async def it_derives_active_status_when_any_application_is_active(self) -> None:
        candidate = _make_candidate(
            applications=[
                {"id": 100, "status": "rejected"},
                {"id": 101, "status": "active"},
            ]
        )
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [], 101: []},
            interviews={100: [], 101: []},
            offers={100: [], 101: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["overall_status"] == "active"

    async def it_derives_hired_status_when_no_active_apps_but_hired_exists(self) -> None:
        candidate = _make_candidate(
            applications=[
                {"id": 100, "status": "rejected"},
                {"id": 101, "status": "hired"},
            ]
        )
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [], 101: []},
            interviews={100: [], 101: []},
            offers={100: [], 101: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["overall_status"] == "hired"

    async def it_derives_rejected_status_when_all_apps_rejected(self) -> None:
        candidate = _make_candidate(
            applications=[
                {"id": 100, "status": "rejected"},
                {"id": 101, "status": "rejected"},
            ]
        )
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [], 101: []},
            interviews={100: [], 101: []},
            offers={100: [], 101: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["overall_status"] == "rejected"

    async def it_derives_converted_status_when_converted_app_exists(self) -> None:
        candidate = _make_candidate(
            applications=[
                {"id": 100, "status": "converted"},
            ]
        )
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["overall_status"] == "converted"

    async def it_uses_first_email_or_none(self) -> None:
        candidate = _make_candidate(email_addresses=[])
        client = _build_fake_client(candidate=candidate)

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["email"] is None

    async def it_uses_first_phone_or_none(self) -> None:
        candidate = _make_candidate(phone_numbers=[])
        client = _build_fake_client(candidate=candidate)

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["phone"] is None


@pytest.mark.small
@pytest.mark.anyio
class DescribeApplicationDetail:
    """Each application includes grouped scorecards, interviews, and offers."""

    async def it_includes_job_name_from_application(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        app = result["applications"][0]

        assert app["job_name"] == "Software Engineer"

    async def it_includes_current_stage(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        app = result["applications"][0]

        assert app["current_stage"] == "Phone Screen"

    async def it_includes_source_and_recruiter(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        app = result["applications"][0]

        assert app["source"] == "LinkedIn"
        assert app["recruiter"] == "Alex Johnson"

    async def it_groups_scorecards_under_their_application(self) -> None:
        candidate = _make_candidate(
            applications=[
                {"id": 100, "status": "active"},
                {"id": 101, "status": "rejected"},
            ]
        )
        client = _build_fake_client(
            candidate=candidate,
            scorecards={
                100: [_make_scorecard(scorecard_id=111)],
                101: [
                    _make_scorecard(scorecard_id=112, interview="Culture Fit"),
                    _make_scorecard(scorecard_id=113, interview="Technical"),
                ],
            },
            interviews={100: [], 101: []},
            offers={100: [], 101: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert len(result["applications"][0]["scorecards"]) == 1
        assert len(result["applications"][1]["scorecards"]) == 2  # noqa: PLR2004

    async def it_extracts_scorecard_summary_fields(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [_make_scorecard()]},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        sc = result["applications"][0]["scorecards"][0]

        assert sc["id"] == 111  # noqa: PLR2004
        assert sc["interview"] == "Technical Screen"
        assert sc["interviewer"] == "Pat Lee"
        assert sc["overall_recommendation"] == "strong_yes"
        assert sc["submitted_at"] == "2026-02-01T16:00:00Z"

    async def it_marks_unsubmitted_scorecards_as_draft(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [_make_scorecard(submitted_at=None)]},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        sc = result["applications"][0]["scorecards"][0]

        assert sc["status"] == "draft"

    async def it_marks_submitted_scorecards_as_submitted(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [_make_scorecard(submitted_at="2026-02-01T16:00:00Z")]},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        sc = result["applications"][0]["scorecards"][0]

        assert sc["status"] == "submitted"

    async def it_extracts_interview_summary_fields(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: [_make_interview()]},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        iv = result["applications"][0]["scheduled_interviews"][0]

        assert iv["id"] == 222  # noqa: PLR2004
        assert iv["interview_name"] == "System Design"
        assert iv["start"] == "2026-03-25T13:00:00Z"
        assert iv["status"] == "scheduled"
        assert iv["interviewers"] == ["Morgan Chen", "Sam Patel"]

    async def it_includes_offers_in_application(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: [_make_offer()]},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        offer = result["applications"][0]["offers"][0]

        assert offer["id"] == 333  # noqa: PLR2004
        assert offer["status"] == "unresolved"
        assert offer["starts_at"] == "2026-04-01"
        assert offer["sent_at"] == "2026-03-15"

    async def it_handles_application_with_no_jobs_array(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        # Override the fake to return an application without jobs key
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        app = result["applications"][0]

        assert app["job_name"] == "Software Engineer"

    async def it_handles_application_with_no_source(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        # Modify app stub to have null source
        candidate["applications"][0]["source"] = None  # type: ignore[index]
        client = _build_fake_client(candidate=candidate)

        result = await candidate_dossier(candidate_id=42, client=client)
        app = result["applications"][0]

        assert app["source"] is None

    async def it_handles_application_with_no_recruiter(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        candidate["applications"][0]["recruiter"] = None  # type: ignore[index]
        client = _build_fake_client(candidate=candidate)

        result = await candidate_dossier(candidate_id=42, client=client)
        app = result["applications"][0]

        assert app["recruiter"] is None

    async def it_handles_application_with_no_current_stage(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        candidate["applications"][0]["current_stage"] = None  # type: ignore[index]
        client = _build_fake_client(candidate=candidate)

        result = await candidate_dossier(candidate_id=42, client=client)
        app = result["applications"][0]

        assert app["current_stage"] is None


@pytest.mark.small
@pytest.mark.anyio
class DescribeActivityFeed:
    """The activity feed is truncated with total counts."""

    async def it_truncates_notes_to_ten_most_recent(self) -> None:
        candidate = _make_candidate()
        client = _build_fake_client(
            candidate=candidate,
            activity_feed=_make_activity_feed(num_notes=15),
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        feed = result["activity_feed"]

        assert len(feed["recent_notes"]) == 10  # noqa: PLR2004
        assert feed["total_notes"] == 15  # noqa: PLR2004

    async def it_truncates_emails_to_ten_most_recent(self) -> None:
        candidate = _make_candidate()
        client = _build_fake_client(
            candidate=candidate,
            activity_feed=_make_activity_feed(num_emails=12),
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        feed = result["activity_feed"]

        assert len(feed["recent_emails"]) == 10  # noqa: PLR2004
        assert feed["total_emails"] == 12  # noqa: PLR2004

    async def it_includes_all_items_when_under_truncation_limit(self) -> None:
        candidate = _make_candidate()
        client = _build_fake_client(
            candidate=candidate,
            activity_feed=_make_activity_feed(num_notes=3, num_emails=2),
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        feed = result["activity_feed"]

        assert len(feed["recent_notes"]) == 3  # noqa: PLR2004
        assert feed["total_notes"] == 3  # noqa: PLR2004
        assert len(feed["recent_emails"]) == 2  # noqa: PLR2004
        assert feed["total_emails"] == 2  # noqa: PLR2004

    async def it_counts_total_activities(self) -> None:
        candidate = _make_candidate()
        client = _build_fake_client(
            candidate=candidate,
            activity_feed=_make_activity_feed(num_activities=5),
        )

        result = await candidate_dossier(candidate_id=42, client=client)
        feed = result["activity_feed"]

        assert feed["total_activities"] == 5  # noqa: PLR2004

    async def it_returns_empty_feed_for_candidate_with_no_activity(self) -> None:
        candidate = _make_candidate()
        client = _build_fake_client(candidate=candidate)

        result = await candidate_dossier(candidate_id=42, client=client)
        feed = result["activity_feed"]

        assert feed["recent_notes"] == []
        assert feed["recent_emails"] == []
        assert feed["total_notes"] == 0
        assert feed["total_emails"] == 0
        assert feed["total_activities"] == 0


@pytest.mark.small
@pytest.mark.anyio
class DescribeEdgeCases:
    """Edge cases for missing data and error conditions."""

    async def it_returns_empty_applications_for_candidate_with_none(self) -> None:
        candidate = _make_candidate(applications=[])
        client = _build_fake_client(candidate=candidate)

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["applications"] == []
        assert result["summary"]["application_count"] == 0
        assert result["summary"]["active_application_count"] == 0
        assert result["summary"]["overall_status"] == "no_applications"

    async def it_returns_error_dict_for_nonexistent_candidate(self) -> None:
        client = FakeGreenhouseClient()

        result = await candidate_dossier(candidate_id=99999, client=client)

        assert result["error"] is True
        assert "not found" in result["message"].lower()

    async def it_returns_false_for_has_pending_offers_with_no_offers(self) -> None:
        candidate = _make_candidate(applications=[{"id": 100, "status": "active"}])
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: []},
            interviews={100: []},
            offers={100: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert result["summary"]["has_pending_offers"] is False

    async def it_includes_all_applications_regardless_of_status(self) -> None:
        candidate = _make_candidate(
            applications=[
                {"id": 100, "status": "active"},
                {"id": 101, "status": "rejected"},
                {"id": 102, "status": "hired"},
            ]
        )
        client = _build_fake_client(
            candidate=candidate,
            scorecards={100: [], 101: [], 102: []},
            interviews={100: [], 101: [], 102: []},
            offers={100: [], 101: [], 102: []},
        )

        result = await candidate_dossier(candidate_id=42, client=client)

        assert len(result["applications"]) == 3  # noqa: PLR2004
