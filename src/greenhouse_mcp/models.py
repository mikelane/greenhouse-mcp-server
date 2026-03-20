"""Pydantic models and enums for Greenhouse API responses.

Enums define the known value sets from the Greenhouse Harvest API.
Models use ``extra="ignore"`` to tolerate new fields Greenhouse may add.
"""

from enum import StrEnum


class JobStatus(StrEnum):
    """Greenhouse job status values."""

    OPEN = "open"
    CLOSED = "closed"
    DRAFT = "draft"


class ApplicationStatus(StrEnum):
    """Greenhouse application status values."""

    ACTIVE = "active"
    REJECTED = "rejected"
    HIRED = "hired"
    CONVERTED = "converted"


class OfferStatus(StrEnum):
    """Greenhouse offer status values."""

    UNRESOLVED = "unresolved"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class OverallRecommendation(StrEnum):
    """Scorecard overall recommendation values."""

    DEFINITELY_NOT = "definitely_not"
    NO = "no"
    YES = "yes"
    STRONG_YES = "strong_yes"
    NO_DECISION = "no_decision"


class InterviewStatus(StrEnum):
    """Scheduled interview status values."""

    SCHEDULED = "scheduled"
    AWAITING_FEEDBACK = "awaiting_feedback"
    COMPLETE = "complete"


class InterviewerResponseStatus(StrEnum):
    """Interviewer RSVP response status values."""

    NEEDS_ACTION = "needs_action"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    ACCEPTED = "accepted"
