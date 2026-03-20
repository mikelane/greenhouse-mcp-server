"""Protocol definitions (ports) for hexagonal architecture.

Tools depend on these protocols, never on concrete adapter classes.
This enables swapping implementations by environment (production vs test)
without changing tool code.
"""

from __future__ import annotations

from typing import Any, Protocol


class GreenhousePort(Protocol):
    """Abstract interface for accessing the Greenhouse Harvest API.

    Each method corresponds to a logical API operation that tools need.
    Implementations handle auth, rate limiting, pagination, and retries.
    """

    async def get_jobs(
        self,
        *,
        status: str | None = None,
        department_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch jobs, optionally filtered by status or department.

        Args:
            status: Filter by job status (open, closed, draft).
            department_id: Filter by department ID.

        Returns:
            List of job objects.
        """
        ...

    async def get_job(self, job_id: int) -> dict[str, Any]:
        """Fetch a single job by ID.

        Args:
            job_id: The Greenhouse job ID.

        Returns:
            Job object.

        Raises:
            NotFoundError: If the job does not exist.
        """
        ...

    async def get_job_stages(self, job_id: int) -> list[dict[str, Any]]:
        """Fetch stages for a specific job.

        Args:
            job_id: The Greenhouse job ID.

        Returns:
            List of stage objects ordered by priority.
        """
        ...

    async def get_applications(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        created_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch applications, optionally filtered.

        Args:
            job_id: Filter by job ID.
            status: Filter by application status.
            created_after: ISO 8601 timestamp lower bound.

        Returns:
            List of application objects.
        """
        ...

    async def get_candidate(self, candidate_id: int) -> dict[str, Any]:
        """Fetch a single candidate by ID.

        Args:
            candidate_id: The Greenhouse candidate ID.

        Returns:
            Candidate object.

        Raises:
            NotFoundError: If the candidate does not exist.
        """
        ...

    async def get_candidates(
        self,
        *,
        job_id: int | None = None,
        email: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch candidates, optionally filtered.

        Args:
            job_id: Filter by job ID.
            email: Filter by email address.

        Returns:
            List of candidate objects.
        """
        ...

    async def get_scorecards(self, application_id: int) -> list[dict[str, Any]]:
        """Fetch scorecards for a specific application.

        Args:
            application_id: The Greenhouse application ID.

        Returns:
            List of scorecard objects.
        """
        ...

    async def get_scheduled_interviews(
        self,
        *,
        application_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch scheduled interviews, optionally for a specific application.

        Args:
            application_id: Filter by application ID.

        Returns:
            List of scheduled interview objects.
        """
        ...

    async def get_offers(
        self,
        *,
        application_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch offers, optionally filtered.

        Args:
            application_id: Filter by application ID.
            status: Filter by offer status.

        Returns:
            List of offer objects.
        """
        ...

    async def get_activity_feed(self, candidate_id: int) -> dict[str, Any]:
        """Fetch the full activity feed for a candidate.

        Args:
            candidate_id: The Greenhouse candidate ID.

        Returns:
            Activity feed object with notes, emails, and activities.
        """
        ...
