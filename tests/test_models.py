"""Tests for Greenhouse API Pydantic models and enums."""

import pytest

from greenhouse_mcp.models import (
    ApplicationStatus,
    InterviewerResponseStatus,
    InterviewStatus,
    JobStatus,
    OfferStatus,
    OverallRecommendation,
)


@pytest.mark.small
class DescribeJobStatus:
    def it_has_open_value(self) -> None:
        assert JobStatus.OPEN == "open"

    def it_has_closed_value(self) -> None:
        assert JobStatus.CLOSED == "closed"

    def it_has_draft_value(self) -> None:
        assert JobStatus.DRAFT == "draft"


@pytest.mark.small
class DescribeApplicationStatus:
    def it_has_active_value(self) -> None:
        assert ApplicationStatus.ACTIVE == "active"

    def it_has_rejected_value(self) -> None:
        assert ApplicationStatus.REJECTED == "rejected"

    def it_has_hired_value(self) -> None:
        assert ApplicationStatus.HIRED == "hired"

    def it_has_converted_value(self) -> None:
        assert ApplicationStatus.CONVERTED == "converted"


@pytest.mark.small
class DescribeOfferStatus:
    def it_has_unresolved_value(self) -> None:
        assert OfferStatus.UNRESOLVED == "unresolved"

    def it_has_accepted_value(self) -> None:
        assert OfferStatus.ACCEPTED == "accepted"

    def it_has_rejected_value(self) -> None:
        assert OfferStatus.REJECTED == "rejected"

    def it_has_deprecated_value(self) -> None:
        assert OfferStatus.DEPRECATED == "deprecated"


@pytest.mark.small
class DescribeOverallRecommendation:
    def it_has_definitely_not_value(self) -> None:
        assert OverallRecommendation.DEFINITELY_NOT == "definitely_not"

    def it_has_no_value(self) -> None:
        assert OverallRecommendation.NO == "no"

    def it_has_yes_value(self) -> None:
        assert OverallRecommendation.YES == "yes"

    def it_has_strong_yes_value(self) -> None:
        assert OverallRecommendation.STRONG_YES == "strong_yes"

    def it_has_no_decision_value(self) -> None:
        assert OverallRecommendation.NO_DECISION == "no_decision"


@pytest.mark.small
class DescribeInterviewStatus:
    def it_has_scheduled_value(self) -> None:
        assert InterviewStatus.SCHEDULED == "scheduled"

    def it_has_awaiting_feedback_value(self) -> None:
        assert InterviewStatus.AWAITING_FEEDBACK == "awaiting_feedback"

    def it_has_complete_value(self) -> None:
        assert InterviewStatus.COMPLETE == "complete"


@pytest.mark.small
class DescribeInterviewerResponseStatus:
    def it_has_needs_action_value(self) -> None:
        assert InterviewerResponseStatus.NEEDS_ACTION == "needs_action"

    def it_has_declined_value(self) -> None:
        assert InterviewerResponseStatus.DECLINED == "declined"

    def it_has_tentative_value(self) -> None:
        assert InterviewerResponseStatus.TENTATIVE == "tentative"

    def it_has_accepted_value(self) -> None:
        assert InterviewerResponseStatus.ACCEPTED == "accepted"
