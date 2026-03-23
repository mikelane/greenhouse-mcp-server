"""Tests for the search_talent tool."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from greenhouse_mcp.tools.search import _compute_recency_score, search_talent


def _iso_ago(*, days: int = 0, hours: int = 0) -> str:
    return (datetime.now(tz=UTC) - timedelta(days=days, hours=hours)).isoformat()


def _make_candidate(  # noqa: PLR0913
    *,
    cid: int,
    first_name: str,
    last_name: str,
    tags: list[str] | None = None,
    email: str | None = None,
    created_days_ago: int = 10,
    updated_days_ago: int = 1,
) -> dict[str, Any]:
    name = f"{first_name} {last_name}"
    return {
        "id": cid,
        "first_name": first_name,
        "last_name": last_name,
        "name": name,
        "email_addresses": [{"value": email or f"{first_name.lower()}@example.com", "type": "personal"}],
        "tags": tags or [],
        "applications": [{"id": cid * 10, "status": "active"}],
        "created_at": _iso_ago(days=created_days_ago),
        "updated_at": _iso_ago(days=updated_days_ago),
    }


def _make_application(  # noqa: PLR0913
    *,
    app_id: int,
    candidate_id: int,
    job_id: int = 100,
    job_name: str = "Engineer",
    stage_name: str = "Phone Screen",
    source_name: str = "LinkedIn",
    status: str = "active",
    applied_days_ago: int = 10,
    last_activity_days_ago: int = 1,
) -> dict[str, Any]:
    return {
        "id": app_id,
        "candidate_id": candidate_id,
        "status": status,
        "jobs": [{"id": job_id, "name": job_name}],
        "current_stage": {"id": app_id * 10, "name": stage_name},
        "source": {"public_name": source_name},
        "applied_at": _iso_ago(days=applied_days_ago),
        "last_activity_at": _iso_ago(days=last_activity_days_ago),
    }


class FakeGreenhouseClient:
    """In-memory fake satisfying GreenhousePort for search_talent tests."""

    def __init__(self) -> None:
        self.candidates: list[dict[str, Any]] = []
        self.applications: list[dict[str, Any]] = []

    async def get_candidates(
        self,
        *,
        job_id: int | None = None,
        email: str | None = None,
        created_after: str | None = None,
        updated_after: str | None = None,
    ) -> list[dict[str, Any]]:
        result = list(self.candidates)
        if job_id is not None:
            result = [
                c
                for c in result
                if any(any(j["id"] == job_id for j in app.get("jobs", [])) for app in c.get("applications", []))
            ]
        if email is not None:
            result = [c for c in result if any(e["value"] == email for e in c.get("email_addresses", []))]
        if created_after is not None:
            cutoff = datetime.fromisoformat(created_after.replace("Z", "+00:00"))
            result = [c for c in result if datetime.fromisoformat(c["created_at"]) >= cutoff]
        if updated_after is not None:
            cutoff = datetime.fromisoformat(updated_after.replace("Z", "+00:00"))
            result = [c for c in result if datetime.fromisoformat(c["updated_at"]) >= cutoff]
        return result

    async def get_applications(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        created_after: str | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        result = list(self.applications)
        if job_id is not None:
            result = [a for a in result if any(j["id"] == job_id for j in a.get("jobs", []))]
        if status is not None:
            result = [a for a in result if a.get("status") == status]
        return result


# ---------------------------------------------------------------------------
# Basic behavior
# ---------------------------------------------------------------------------


class DescribeSearchTalent:
    @pytest.mark.anyio
    async def it_returns_empty_results_when_no_candidates_exist(self) -> None:
        client = FakeGreenhouseClient()
        result = await search_talent(client=client)

        assert result["total_results"] == 0
        assert result["results"] == []

    @pytest.mark.anyio
    async def it_returns_all_candidates_when_no_filters_applied(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
            _make_candidate(cid=2, first_name="Bob", last_name="Jones"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        result = await search_talent(client=client)

        assert result["total_results"] == 2  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_includes_query_in_response(self) -> None:
        client = FakeGreenhouseClient()
        result = await search_talent(query="alice", client=client)

        assert result["query"] == "alice"

    @pytest.mark.anyio
    async def it_includes_filters_applied_in_response(self) -> None:
        client = FakeGreenhouseClient()
        result = await search_talent(
            stage="Phone Screen",
            source="LinkedIn",
            tags=["senior"],
            client=client,
        )

        assert result["filters_applied"]["stage"] == "Phone Screen"
        assert result["filters_applied"]["source"] == "LinkedIn"
        assert result["filters_applied"]["tags"] == ["senior"]

    @pytest.mark.anyio
    async def it_returns_message_for_empty_results(self) -> None:
        client = FakeGreenhouseClient()
        result = await search_talent(query="nonexistent", client=client)

        assert result["total_results"] == 0
        assert result["message"] is not None
        assert "nonexistent" in result["message"].lower() or "no candidates" in result["message"].lower()

    @pytest.mark.anyio
    async def it_returns_none_message_when_results_exist(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
        ]

        result = await search_talent(client=client)

        assert result["message"] is None


# ---------------------------------------------------------------------------
# Name search (client-side filtering per ADR 0009)
# ---------------------------------------------------------------------------


class DescribeNameSearch:
    @pytest.mark.anyio
    async def it_matches_first_name_case_insensitively(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Maria", last_name="Chen"),
            _make_candidate(cid=2, first_name="James", last_name="Wilson"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        result = await search_talent(query="maria", client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1

    @pytest.mark.anyio
    async def it_matches_last_name_case_insensitively(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Maria", last_name="Chen"),
            _make_candidate(cid=2, first_name="James", last_name="Wilson"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        result = await search_talent(query="wilson", client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 2  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_matches_partial_name_substring(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Maria", last_name="Chen"),
            _make_candidate(cid=2, first_name="Marcus", last_name="Brown"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        result = await search_talent(query="mar", client=client)

        assert result["total_results"] == 2  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_matches_full_name(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Maria", last_name="Chen"),
            _make_candidate(cid=2, first_name="James", last_name="Wilson"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        result = await search_talent(query="maria chen", client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1

    @pytest.mark.anyio
    async def it_returns_empty_when_name_does_not_match(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Maria", last_name="Chen"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
        ]

        result = await search_talent(query="nonexistent", client=client)

        assert result["total_results"] == 0


# ---------------------------------------------------------------------------
# Stage filtering
# ---------------------------------------------------------------------------


class DescribeStageFilter:
    @pytest.mark.anyio
    async def it_filters_by_stage_name(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
            _make_candidate(cid=2, first_name="Bob", last_name="Jones"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, stage_name="Phone Screen"),
            _make_application(app_id=20, candidate_id=2, stage_name="Technical Interview"),
        ]

        result = await search_talent(stage="Phone Screen", client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1

    @pytest.mark.anyio
    async def it_matches_stage_case_insensitively(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, stage_name="Phone Screen"),
        ]

        result = await search_talent(stage="phone screen", client=client)

        assert result["total_results"] == 1

    @pytest.mark.anyio
    async def it_excludes_candidates_with_no_matching_stage(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, stage_name="Onsite"),
        ]

        result = await search_talent(stage="Phone Screen", client=client)

        assert result["total_results"] == 0


# ---------------------------------------------------------------------------
# Source filtering
# ---------------------------------------------------------------------------


class DescribeSourceFilter:
    @pytest.mark.anyio
    async def it_filters_by_source_name(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
            _make_candidate(cid=2, first_name="Bob", last_name="Jones"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, source_name="Referral"),
            _make_application(app_id=20, candidate_id=2, source_name="LinkedIn"),
        ]

        result = await search_talent(source="Referral", client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1

    @pytest.mark.anyio
    async def it_matches_source_case_insensitively(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, source_name="Referral"),
        ]

        result = await search_talent(source="referral", client=client)

        assert result["total_results"] == 1


# ---------------------------------------------------------------------------
# Tag filtering
# ---------------------------------------------------------------------------


class DescribeTagFilter:
    @pytest.mark.anyio
    async def it_filters_by_single_tag(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith", tags=["senior"]),
            _make_candidate(cid=2, first_name="Bob", last_name="Jones", tags=[]),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        result = await search_talent(tags=["senior"], client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1

    @pytest.mark.anyio
    async def it_requires_all_tags_to_match(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith", tags=["senior", "phd"]),
            _make_candidate(cid=2, first_name="Bob", last_name="Jones", tags=["senior"]),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        result = await search_talent(tags=["senior", "phd"], client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1

    @pytest.mark.anyio
    async def it_matches_tags_case_insensitively(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith", tags=["Senior"]),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
        ]

        result = await search_talent(tags=["senior"], client=client)

        assert result["total_results"] == 1


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------


class DescribeDateFilter:
    @pytest.mark.anyio
    async def it_passes_created_after_to_api(self) -> None:
        client = FakeGreenhouseClient()
        recent = _make_candidate(cid=1, first_name="Alice", last_name="Smith", created_days_ago=5)
        old = _make_candidate(cid=2, first_name="Bob", last_name="Jones", created_days_ago=60)
        client.candidates = [recent, old]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
        result = await search_talent(created_after=cutoff, client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1

    @pytest.mark.anyio
    async def it_converts_created_after_days_to_iso_timestamp(self) -> None:
        client = FakeGreenhouseClient()
        recent = _make_candidate(cid=1, first_name="Alice", last_name="Smith", created_days_ago=5)
        old = _make_candidate(cid=2, first_name="Bob", last_name="Jones", created_days_ago=60)
        client.candidates = [recent, old]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
            _make_application(app_id=20, candidate_id=2),
        ]

        result = await search_talent(created_after_days=30, client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1


# ---------------------------------------------------------------------------
# Application enrichment
# ---------------------------------------------------------------------------


class DescribeApplicationEnrichment:
    @pytest.mark.anyio
    async def it_includes_application_details_for_each_candidate(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            _make_application(
                app_id=10,
                candidate_id=1,
                job_name="Senior Engineer",
                stage_name="Technical Interview",
                source_name="Referral",
            ),
        ]

        result = await search_talent(client=client)

        apps = result["results"][0]["current_applications"]
        assert len(apps) == 1
        assert apps[0]["application_id"] == 10  # noqa: PLR2004
        assert apps[0]["job_name"] == "Senior Engineer"
        assert apps[0]["stage"] == "Technical Interview"
        assert apps[0]["source"] == "Referral"

    @pytest.mark.anyio
    async def it_includes_multiple_applications_for_one_candidate(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, job_name="Engineer"),
            _make_application(app_id=11, candidate_id=1, job_name="Manager"),
        ]

        result = await search_talent(client=client)

        apps = result["results"][0]["current_applications"]
        assert len(apps) == 2  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_includes_email_in_result(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith", email="alice@test.com"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
        ]

        result = await search_talent(client=client)

        assert result["results"][0]["email"] == "alice@test.com"

    @pytest.mark.anyio
    async def it_includes_tags_in_result(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith", tags=["senior", "phd"]),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
        ]

        result = await search_talent(client=client)

        assert result["results"][0]["tags"] == ["senior", "phd"]

    @pytest.mark.anyio
    async def it_handles_candidate_with_no_applications(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = []

        result = await search_talent(client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["current_applications"] == []

    @pytest.mark.anyio
    async def it_handles_application_without_source(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            {
                "id": 10,
                "candidate_id": 1,
                "status": "active",
                "jobs": [{"id": 100, "name": "Engineer"}],
                "current_stage": {"id": 200, "name": "Phone Screen"},
                "source": None,
                "applied_at": _iso_ago(days=5),
                "last_activity_at": _iso_ago(days=1),
            },
        ]

        result = await search_talent(client=client)

        assert result["results"][0]["current_applications"][0]["source"] == "Unknown"

    @pytest.mark.anyio
    async def it_handles_application_without_current_stage(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            {
                "id": 10,
                "candidate_id": 1,
                "status": "active",
                "jobs": [{"id": 100, "name": "Engineer"}],
                "current_stage": None,
                "source": {"public_name": "LinkedIn"},
                "applied_at": _iso_ago(days=5),
                "last_activity_at": _iso_ago(days=1),
            },
        ]

        result = await search_talent(client=client)

        assert result["results"][0]["current_applications"][0]["stage"] == "Unknown"

    @pytest.mark.anyio
    async def it_handles_application_without_jobs(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            {
                "id": 10,
                "candidate_id": 1,
                "status": "active",
                "jobs": [],
                "current_stage": {"id": 200, "name": "Phone Screen"},
                "source": {"public_name": "LinkedIn"},
                "applied_at": _iso_ago(days=5),
                "last_activity_at": _iso_ago(days=1),
            },
        ]

        result = await search_talent(client=client)

        assert result["results"][0]["current_applications"][0]["job_name"] == "Unknown"

    @pytest.mark.anyio
    async def it_handles_candidate_without_email(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            {
                "id": 1,
                "first_name": "Alice",
                "last_name": "Smith",
                "name": "Alice Smith",
                "email_addresses": [],
                "tags": [],
                "applications": [{"id": 10, "status": "active"}],
                "created_at": _iso_ago(days=5),
                "updated_at": _iso_ago(days=1),
            },
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
        ]

        result = await search_talent(client=client)

        assert result["results"][0]["email"] == ""


# ---------------------------------------------------------------------------
# Recency score arithmetic (mutant killer: * vs /)
# ---------------------------------------------------------------------------


@pytest.mark.small
class DescribeRecencyScoreArithmetic:
    @pytest.mark.anyio
    async def it_computes_correct_recency_score_for_known_activity_age(self) -> None:
        """An app with activity 15 days ago scores exactly 12.5 (not 50.0 if * were /)."""
        fifteen_days_ago = (datetime.now(tz=UTC) - timedelta(days=15)).isoformat()
        apps: list[dict[str, Any]] = [{"last_activity_at": fifteen_days_ago}]
        score = _compute_recency_score(apps)
        assert score == pytest.approx(12.5, abs=0.5)


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------


class DescribeRelevanceScoring:
    @pytest.mark.anyio
    async def it_scores_exact_name_match_higher_than_partial(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Maria", last_name="Chen"),
            _make_candidate(cid=2, first_name="Marianne", last_name="Woods"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, last_activity_days_ago=1),
            _make_application(app_id=20, candidate_id=2, last_activity_days_ago=1),
        ]

        result = await search_talent(query="maria", client=client)

        scores = {r["candidate_id"]: r["relevance_score"] for r in result["results"]}
        assert scores[1] > scores[2]

    @pytest.mark.anyio
    async def it_scores_recent_activity_higher(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
            _make_candidate(cid=2, first_name="Alice", last_name="Jones"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, last_activity_days_ago=1),
            _make_application(app_id=20, candidate_id=2, last_activity_days_ago=30),
        ]

        result = await search_talent(query="alice", client=client)

        scores = {r["candidate_id"]: r["relevance_score"] for r in result["results"]}
        assert scores[1] > scores[2]

    @pytest.mark.anyio
    async def it_sorts_results_by_relevance_descending(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
            _make_candidate(cid=2, first_name="Alice", last_name="Jones"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, last_activity_days_ago=30),
            _make_application(app_id=20, candidate_id=2, last_activity_days_ago=1),
        ]

        result = await search_talent(query="alice", client=client)

        assert result["results"][0]["relevance_score"] >= result["results"][1]["relevance_score"]

    @pytest.mark.anyio
    async def it_assigns_zero_relevance_when_no_query(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1),
        ]

        result = await search_talent(client=client)

        assert result["results"][0]["relevance_score"] == 0.0


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------


class DescribeCombinedFilters:
    @pytest.mark.anyio
    async def it_combines_name_and_stage_filters(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
            _make_candidate(cid=2, first_name="Alice", last_name="Jones"),
            _make_candidate(cid=3, first_name="Bob", last_name="Brown"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, stage_name="Phone Screen"),
            _make_application(app_id=20, candidate_id=2, stage_name="Onsite"),
            _make_application(app_id=30, candidate_id=3, stage_name="Phone Screen"),
        ]

        result = await search_talent(query="alice", stage="Phone Screen", client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1

    @pytest.mark.anyio
    async def it_combines_stage_and_source_filters(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
            _make_candidate(cid=2, first_name="Bob", last_name="Jones"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, stage_name="Phone Screen", source_name="Referral"),
            _make_application(app_id=20, candidate_id=2, stage_name="Phone Screen", source_name="LinkedIn"),
        ]

        result = await search_talent(stage="Phone Screen", source="Referral", client=client)

        assert result["total_results"] == 1
        assert result["results"][0]["candidate_id"] == 1


# ---------------------------------------------------------------------------
# Stage filtering with candidate having no matching application
# ---------------------------------------------------------------------------


class DescribeStageFilterEdgeCases:
    @pytest.mark.anyio
    async def it_excludes_candidate_when_stage_filter_and_no_applications(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = []

        result = await search_talent(stage="Phone Screen", client=client)

        assert result["total_results"] == 0

    @pytest.mark.anyio
    async def it_excludes_candidate_when_source_filter_and_no_applications(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = []

        result = await search_talent(source="Referral", client=client)

        assert result["total_results"] == 0


# ---------------------------------------------------------------------------
# Recency scoring edge cases
# ---------------------------------------------------------------------------


class DescribeRecencyScoring:
    @pytest.mark.anyio
    async def it_returns_zero_for_empty_applications_list(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = []

        result = await search_talent(query="alice", client=client)

        assert result["total_results"] == 1
        # name_score (exact match on first_name) + recency_score (0.0 from empty apps)
        assert result["results"][0]["relevance_score"] == 50.0  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_skips_application_with_empty_last_activity_at(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            {
                "id": 10,
                "candidate_id": 1,
                "status": "active",
                "jobs": [{"id": 100, "name": "Engineer"}],
                "current_stage": {"id": 200, "name": "Phone Screen"},
                "source": {"public_name": "LinkedIn"},
                "applied_at": _iso_ago(days=5),
                "last_activity_at": "",
            },
        ]

        result = await search_talent(query="alice", client=client)

        assert result["total_results"] == 1
        # Only name_score, no recency since all timestamps are empty
        assert result["results"][0]["relevance_score"] == 50.0  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_skips_application_with_unparseable_last_activity_at(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            {
                "id": 10,
                "candidate_id": 1,
                "status": "active",
                "jobs": [{"id": 100, "name": "Engineer"}],
                "current_stage": {"id": 200, "name": "Phone Screen"},
                "source": {"public_name": "LinkedIn"},
                "applied_at": _iso_ago(days=5),
                "last_activity_at": "not-a-timestamp",
            },
        ]

        result = await search_talent(query="alice", client=client)

        assert result["total_results"] == 1
        # Only name_score, no recency since timestamp is unparseable
        assert result["results"][0]["relevance_score"] == 50.0  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_uses_most_recent_timestamp_across_multiple_applications(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        # Newer app first, older app second -- exercises the branch where
        # ts > most_recent is False (the older second app does not replace most_recent)
        client.applications = [
            _make_application(
                app_id=10,
                candidate_id=1,
                last_activity_days_ago=1,
            ),
            _make_application(
                app_id=11,
                candidate_id=1,
                last_activity_days_ago=20,
            ),
        ]

        result = await search_talent(query="alice", client=client)

        assert result["total_results"] == 1
        # Exact name match (50) + recency based on the more recent app (1 day ago)
        score = result["results"][0]["relevance_score"]
        # 1 day ago yields ~24.2 recency score (25 * (1 - 1/30))
        assert score > 70.0  # noqa: PLR2004

    @pytest.mark.anyio
    async def it_returns_zero_recency_when_all_timestamps_are_invalid(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            {
                "id": 10,
                "candidate_id": 1,
                "status": "active",
                "jobs": [{"id": 100, "name": "Engineer"}],
                "current_stage": {"id": 200, "name": "Phone Screen"},
                "source": {"public_name": "LinkedIn"},
                "applied_at": _iso_ago(days=5),
                "last_activity_at": "",
            },
            {
                "id": 11,
                "candidate_id": 1,
                "status": "active",
                "jobs": [{"id": 101, "name": "Manager"}],
                "current_stage": {"id": 201, "name": "Onsite"},
                "source": {"public_name": "Referral"},
                "applied_at": _iso_ago(days=3),
                "last_activity_at": "garbage-date",
            },
        ]

        result = await search_talent(query="alice", client=client)

        assert result["total_results"] == 1
        # Exact match on first_name (50.0) + zero recency
        assert result["results"][0]["relevance_score"] == 50.0  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Job ID filter
# ---------------------------------------------------------------------------


class DescribeJobIdFilter:
    @pytest.mark.anyio
    async def it_includes_job_id_in_filters_applied(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            _make_application(app_id=10, candidate_id=1, job_id=42),
        ]

        result = await search_talent(job_id=42, client=client)

        assert result["filters_applied"]["job_id"] == 42  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Application with missing candidate_id
# ---------------------------------------------------------------------------


class DescribeApplicationWithoutCandidateId:
    @pytest.mark.anyio
    async def it_skips_applications_without_candidate_id(self) -> None:
        client = FakeGreenhouseClient()
        client.candidates = [
            _make_candidate(cid=1, first_name="Alice", last_name="Smith"),
        ]
        client.applications = [
            {
                "id": 99,
                "candidate_id": None,
                "status": "active",
                "jobs": [{"id": 100, "name": "Engineer"}],
                "current_stage": {"id": 200, "name": "Phone Screen"},
                "source": {"public_name": "LinkedIn"},
                "applied_at": _iso_ago(days=5),
                "last_activity_at": _iso_ago(days=1),
            },
            _make_application(app_id=10, candidate_id=1),
        ]

        result = await search_talent(client=client)

        assert result["total_results"] == 1
        # The application with None candidate_id is not associated with any candidate
        apps = result["results"][0]["current_applications"]
        assert len(apps) == 1
        assert apps[0]["application_id"] == 10  # noqa: PLR2004
