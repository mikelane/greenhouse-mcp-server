"""Tests for the FakeGreenhouseClient test double."""

from __future__ import annotations

import pytest

from greenhouse_mcp.exceptions import NotFoundError
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.ports import GreenhousePort


@pytest.mark.small
class DescribeFakeGreenhouseClient:
    """Verify that FakeGreenhouseClient implements GreenhousePort faithfully."""

    def it_satisfies_the_greenhouse_port_protocol(self) -> None:
        client = FakeGreenhouseClient()
        port_methods = [
            name for name in dir(GreenhousePort) if not name.startswith("_") and callable(getattr(GreenhousePort, name))
        ]
        for method_name in port_methods:
            assert hasattr(client, method_name), f"Missing method: {method_name}"
            assert callable(getattr(client, method_name))

    @pytest.mark.anyio
    async def it_returns_all_jobs_when_no_filter(self) -> None:
        client = FakeGreenhouseClient()
        jobs = await client.get_jobs()
        assert len(jobs) == 3
        assert all("id" in j and "name" in j for j in jobs)

    @pytest.mark.anyio
    async def it_returns_jobs_matching_status_filter(self) -> None:
        client = FakeGreenhouseClient()
        open_jobs = await client.get_jobs(status="open")
        assert len(open_jobs) == 3
        assert all(j["status"] == "open" for j in open_jobs)

        closed_jobs = await client.get_jobs(status="closed")
        assert len(closed_jobs) == 0

    @pytest.mark.anyio
    async def it_returns_jobs_matching_department_id_filter(self) -> None:
        client = FakeGreenhouseClient()
        all_jobs = await client.get_jobs()
        dept_ids = {j["departments"][0]["id"] for j in all_jobs if j.get("departments")}
        first_dept = next(iter(dept_ids))
        filtered = await client.get_jobs(department_id=first_dept)
        assert len(filtered) >= 1
        assert all(any(d["id"] == first_dept for d in j.get("departments", [])) for j in filtered)

    @pytest.mark.anyio
    async def it_returns_a_single_job_by_id(self) -> None:
        client = FakeGreenhouseClient()
        job = await client.get_job(1001)
        assert job["id"] == 1001
        assert job["name"] == "Senior Software Engineer"

    @pytest.mark.anyio
    async def it_raises_not_found_for_unknown_job_id(self) -> None:
        client = FakeGreenhouseClient()
        with pytest.raises(NotFoundError):
            await client.get_job(9999)

    @pytest.mark.anyio
    async def it_returns_stages_for_a_job(self) -> None:
        client = FakeGreenhouseClient()
        stages = await client.get_job_stages(1001)
        assert len(stages) == 4
        assert stages[0]["name"] == "Application Review"

    @pytest.mark.anyio
    async def it_returns_empty_stages_for_unknown_job(self) -> None:
        client = FakeGreenhouseClient()
        stages = await client.get_job_stages(9999)
        assert stages == []

    @pytest.mark.anyio
    async def it_returns_all_applications_when_no_filter(self) -> None:
        client = FakeGreenhouseClient()
        apps = await client.get_applications()
        assert len(apps) > 0

    @pytest.mark.anyio
    async def it_returns_applications_matching_job_id_filter(self) -> None:
        client = FakeGreenhouseClient()
        apps = await client.get_applications(job_id=1001)
        assert len(apps) > 0
        assert all(any(j["id"] == 1001 for j in a.get("jobs", [])) for a in apps)

    @pytest.mark.anyio
    async def it_returns_applications_matching_status_filter(self) -> None:
        client = FakeGreenhouseClient()
        active_apps = await client.get_applications(status="active")
        assert len(active_apps) > 0
        assert all(a["status"] == "active" for a in active_apps)

    @pytest.mark.anyio
    async def it_returns_applications_matching_created_after_filter(self) -> None:
        client = FakeGreenhouseClient()
        all_apps = await client.get_applications()
        recent = await client.get_applications(created_after="2099-01-01T00:00:00Z")
        assert len(recent) == 0

        old = await client.get_applications(created_after="2000-01-01T00:00:00Z")
        assert len(old) == len(all_apps)

    @pytest.mark.anyio
    async def it_returns_applications_with_combined_filters(self) -> None:
        client = FakeGreenhouseClient()
        apps = await client.get_applications(job_id=1001, status="active")
        assert all(a["status"] == "active" for a in apps)
        assert all(any(j["id"] == 1001 for j in a.get("jobs", [])) for a in apps)

    @pytest.mark.anyio
    async def it_returns_candidate_by_id(self) -> None:
        client = FakeGreenhouseClient()
        candidate = await client.get_candidate(101)
        assert candidate["id"] == 101
        assert "first_name" in candidate
        assert "last_name" in candidate
        assert "email_addresses" in candidate
        assert "applications" in candidate

    @pytest.mark.anyio
    async def it_raises_not_found_for_unknown_candidate_id(self) -> None:
        client = FakeGreenhouseClient()
        with pytest.raises(NotFoundError):
            await client.get_candidate(9999)

    @pytest.mark.anyio
    async def it_returns_candidates_when_no_filter(self) -> None:
        client = FakeGreenhouseClient()
        candidates = await client.get_candidates()
        assert len(candidates) == 15

    @pytest.mark.anyio
    async def it_returns_candidates_matching_job_id_filter(self) -> None:
        client = FakeGreenhouseClient()
        candidates = await client.get_candidates(job_id=1001)
        assert len(candidates) > 0

    @pytest.mark.anyio
    async def it_returns_candidates_matching_email_filter(self) -> None:
        client = FakeGreenhouseClient()
        all_candidates = await client.get_candidates()
        first_email = all_candidates[0]["email_addresses"][0]["value"]
        filtered = await client.get_candidates(email=first_email)
        assert len(filtered) == 1
        assert filtered[0]["email_addresses"][0]["value"] == first_email

    @pytest.mark.anyio
    async def it_returns_empty_list_for_unmatched_email(self) -> None:
        client = FakeGreenhouseClient()
        filtered = await client.get_candidates(email="nonexistent@example.com")
        assert filtered == []

    @pytest.mark.anyio
    async def it_returns_scorecards_for_application(self) -> None:
        client = FakeGreenhouseClient()
        apps = await client.get_applications()
        app_with_scorecards = None
        for app in apps:
            scorecards = await client.get_scorecards(app["id"])
            if scorecards:
                app_with_scorecards = app
                break
        assert app_with_scorecards is not None
        scorecards = await client.get_scorecards(app_with_scorecards["id"])
        assert len(scorecards) > 0
        assert "overall_recommendation" in scorecards[0]

    @pytest.mark.anyio
    async def it_returns_empty_scorecards_for_unknown_application(self) -> None:
        client = FakeGreenhouseClient()
        scorecards = await client.get_scorecards(9999)
        assert scorecards == []

    @pytest.mark.anyio
    async def it_returns_scheduled_interviews_for_application(self) -> None:
        client = FakeGreenhouseClient()
        apps = await client.get_applications()
        found_interview = False
        for app in apps:
            interviews = await client.get_scheduled_interviews(application_id=app["id"])
            if interviews:
                found_interview = True
                assert "status" in interviews[0]
                break
        assert found_interview

    @pytest.mark.anyio
    async def it_returns_all_scheduled_interviews_when_no_filter(self) -> None:
        client = FakeGreenhouseClient()
        interviews = await client.get_scheduled_interviews()
        assert len(interviews) >= 4

    @pytest.mark.anyio
    async def it_returns_offers_for_application(self) -> None:
        client = FakeGreenhouseClient()
        apps = await client.get_applications()
        found_offer = False
        for app in apps:
            offers = await client.get_offers(application_id=app["id"])
            if offers:
                found_offer = True
                assert "status" in offers[0]
                break
        assert found_offer

    @pytest.mark.anyio
    async def it_returns_offers_matching_status_filter(self) -> None:
        client = FakeGreenhouseClient()
        unresolved = await client.get_offers(status="unresolved")
        assert len(unresolved) >= 1
        assert all(o["status"] == "unresolved" for o in unresolved)

    @pytest.mark.anyio
    async def it_returns_all_offers_when_no_filter(self) -> None:
        client = FakeGreenhouseClient()
        offers = await client.get_offers()
        assert len(offers) >= 3

    @pytest.mark.anyio
    async def it_returns_activity_feed_for_candidate(self) -> None:
        client = FakeGreenhouseClient()
        feed = await client.get_activity_feed(101)
        assert "notes" in feed
        assert "emails" in feed
        assert "activities" in feed
        assert len(feed["notes"]) > 0

    @pytest.mark.anyio
    async def it_returns_empty_activity_feed_for_unknown_candidate(self) -> None:
        client = FakeGreenhouseClient()
        feed = await client.get_activity_feed(9999)
        assert feed["notes"] == []
        assert feed["emails"] == []
        assert feed["activities"] == []


@pytest.mark.small
class DescribeFakeGreenhouseClientDataStory:
    """Verify the fake data tells the expected recruiting story."""

    @pytest.mark.anyio
    async def it_has_swe_bottleneck_at_technical_interview(self) -> None:
        client = FakeGreenhouseClient()
        apps = await client.get_applications(job_id=1001, status="active")
        stages = await client.get_job_stages(1001)
        tech_interview_stage = next(s for s in stages if s["name"] == "Technical Interview")
        stuck_in_tech = [a for a in apps if a.get("current_stage", {}).get("id") == tech_interview_stage["id"]]
        assert len(stuck_in_tech) >= 5

    @pytest.mark.anyio
    async def it_has_unsubmitted_scorecards(self) -> None:
        client = FakeGreenhouseClient()
        apps = await client.get_applications(status="active")
        unsubmitted_count = 0
        for app in apps:
            scorecards = await client.get_scorecards(app["id"])
            for sc in scorecards:
                if sc.get("submitted_at") is None:
                    unsubmitted_count += 1
        assert unsubmitted_count >= 2

    @pytest.mark.anyio
    async def it_has_unresolved_offers(self) -> None:
        client = FakeGreenhouseClient()
        unresolved = await client.get_offers(status="unresolved")
        assert len(unresolved) >= 2

    @pytest.mark.anyio
    async def it_has_accepted_offer(self) -> None:
        client = FakeGreenhouseClient()
        all_offers = await client.get_offers()
        accepted = [o for o in all_offers if o["status"] == "accepted"]
        assert len(accepted) >= 1

    @pytest.mark.anyio
    async def it_has_candidate_with_multiple_applications(self) -> None:
        client = FakeGreenhouseClient()
        candidate = await client.get_candidate(101)
        assert len(candidate["applications"]) >= 2

    @pytest.mark.anyio
    async def it_has_interviews_awaiting_feedback(self) -> None:
        client = FakeGreenhouseClient()
        interviews = await client.get_scheduled_interviews()
        awaiting = [i for i in interviews if i["status"] == "awaiting_feedback"]
        assert len(awaiting) >= 2
