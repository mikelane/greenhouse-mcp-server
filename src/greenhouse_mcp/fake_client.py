"""Realistic test double for the Greenhouse API client.

Pre-populated with rich recruiting data that tells a story:
- Senior SWE pipeline has a bottleneck at Technical Interview
- Product Manager pipeline is healthy
- Data Scientist pipeline has a few candidates in early stages
- Missing scorecards, pending offers, and stuck candidates create
  realistic needs_attention scenarios.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from greenhouse_mcp.exceptions import NotFoundError

# ---------------------------------------------------------------------------
# Time helpers -- all timestamps are relative to "now" so data stays fresh
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=UTC)


def _iso_ago(*, days: int = 0, hours: int = 0) -> str:
    """Return an ISO 8601 timestamp for a point in the past."""
    return (_NOW - timedelta(days=days, hours=hours)).isoformat()


def _date_ago(*, days: int = 0) -> str:
    """Return a YYYY-MM-DD date string for a point in the past."""
    return (_NOW - timedelta(days=days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

_JOBS: list[dict[str, Any]] = [
    {
        "id": 1001,
        "name": "Senior Software Engineer",
        "status": "open",
        "departments": [{"id": 100, "name": "Engineering"}],
        "offices": [{"id": 10, "name": "San Francisco"}],
        "created_at": _iso_ago(days=90),
        "updated_at": _iso_ago(days=1),
    },
    {
        "id": 1002,
        "name": "Product Manager",
        "status": "open",
        "departments": [{"id": 200, "name": "Product"}],
        "offices": [{"id": 10, "name": "San Francisco"}],
        "created_at": _iso_ago(days=60),
        "updated_at": _iso_ago(days=2),
    },
    {
        "id": 1003,
        "name": "Data Scientist",
        "status": "open",
        "departments": [{"id": 100, "name": "Engineering"}],
        "offices": [{"id": 20, "name": "New York"}],
        "created_at": _iso_ago(days=45),
        "updated_at": _iso_ago(days=3),
    },
]

# ---------------------------------------------------------------------------
# Job stages
# ---------------------------------------------------------------------------

_STAGES: dict[int, list[dict[str, Any]]] = {
    1001: [
        {"id": 2001, "name": "Application Review", "active": True, "priority": 0},
        {"id": 2002, "name": "Phone Screen", "active": True, "priority": 1},
        {"id": 2003, "name": "Technical Interview", "active": True, "priority": 2},
        {"id": 2004, "name": "Onsite", "active": True, "priority": 3},
    ],
    1002: [
        {"id": 2010, "name": "Resume Review", "active": True, "priority": 0},
        {"id": 2011, "name": "Hiring Manager Screen", "active": True, "priority": 1},
        {"id": 2012, "name": "Panel Interview", "active": True, "priority": 2},
    ],
    1003: [
        {"id": 2020, "name": "Application Review", "active": True, "priority": 0},
        {"id": 2021, "name": "Technical Assessment", "active": True, "priority": 1},
        {"id": 2022, "name": "Team Interview", "active": True, "priority": 2},
        {"id": 2023, "name": "Final Round", "active": True, "priority": 3},
    ],
}

# ---------------------------------------------------------------------------
# Candidates (15 total)
# ---------------------------------------------------------------------------

_CANDIDATES: list[dict[str, Any]] = [
    # --- Senior SWE candidates ---
    {
        "id": 101,
        "first_name": "Maria",
        "last_name": "Chen",
        "name": "Maria Chen",
        "email_addresses": [{"value": "maria.chen@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0101", "type": "mobile"}],
        "tags": ["strong-referral", "senior"],
        "applications": [
            {
                "id": 3001,
                "status": "hired",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2004, "name": "Onsite"},
                "applied_at": _iso_ago(days=60),
                "last_activity_at": _iso_ago(days=2),
                "source": {"public_name": "Referral"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 101,
            },
            {
                "id": 3002,
                "status": "active",
                "jobs": [{"id": 1002, "name": "Product Manager"}],
                "current_stage": {"id": 2011, "name": "Hiring Manager Screen"},
                "applied_at": _iso_ago(days=30),
                "last_activity_at": _iso_ago(days=3),
                "source": {"public_name": "Internal Transfer"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 101,
            },
        ],
    },
    {
        "id": 102,
        "first_name": "James",
        "last_name": "Wilson",
        "name": "James Wilson",
        "email_addresses": [{"value": "james.wilson@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0102", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3003,
                "status": "active",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2002, "name": "Phone Screen"},
                "applied_at": _iso_ago(days=20),
                "last_activity_at": _iso_ago(days=15),
                "source": {"public_name": "LinkedIn"},
                "recruiter": {"name": "Tom Davis"},
                "prospect": False,
                "candidate_id": 102,
            },
        ],
    },
    {
        "id": 103,
        "first_name": "Aisha",
        "last_name": "Patel",
        "name": "Aisha Patel",
        "email_addresses": [{"value": "aisha.patel@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0103", "type": "mobile"}],
        "tags": ["senior"],
        "applications": [
            {
                "id": 3004,
                "status": "active",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2003, "name": "Technical Interview"},
                "applied_at": _iso_ago(days=30),
                "last_activity_at": _iso_ago(days=14),
                "source": {"public_name": "Company Website"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 103,
            },
        ],
    },
    {
        "id": 104,
        "first_name": "Carlos",
        "last_name": "Rodriguez",
        "name": "Carlos Rodriguez",
        "email_addresses": [{"value": "carlos.rodriguez@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0104", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3005,
                "status": "active",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2003, "name": "Technical Interview"},
                "applied_at": _iso_ago(days=28),
                "last_activity_at": _iso_ago(days=13),
                "source": {"public_name": "Referral"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 104,
            },
        ],
    },
    {
        "id": 105,
        "first_name": "Priya",
        "last_name": "Sharma",
        "name": "Priya Sharma",
        "email_addresses": [{"value": "priya.sharma@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0105", "type": "mobile"}],
        "tags": ["top-school"],
        "applications": [
            {
                "id": 3006,
                "status": "active",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2003, "name": "Technical Interview"},
                "applied_at": _iso_ago(days=25),
                "last_activity_at": _iso_ago(days=12),
                "source": {"public_name": "University Recruiting"},
                "recruiter": {"name": "Tom Davis"},
                "prospect": False,
                "candidate_id": 105,
            },
        ],
    },
    {
        "id": 106,
        "first_name": "David",
        "last_name": "Kim",
        "name": "David Kim",
        "email_addresses": [{"value": "david.kim@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0106", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3007,
                "status": "active",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2003, "name": "Technical Interview"},
                "applied_at": _iso_ago(days=22),
                "last_activity_at": _iso_ago(days=12),
                "source": {"public_name": "LinkedIn"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 106,
            },
        ],
    },
    {
        "id": 107,
        "first_name": "Elena",
        "last_name": "Volkov",
        "name": "Elena Volkov",
        "email_addresses": [{"value": "elena.volkov@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0107", "type": "mobile"}],
        "tags": ["senior"],
        "applications": [
            {
                "id": 3008,
                "status": "active",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2003, "name": "Technical Interview"},
                "applied_at": _iso_ago(days=20),
                "last_activity_at": _iso_ago(days=13),
                "source": {"public_name": "Referral"},
                "recruiter": {"name": "Tom Davis"},
                "prospect": False,
                "candidate_id": 107,
            },
        ],
    },
    {
        "id": 108,
        "first_name": "Marcus",
        "last_name": "Brown",
        "name": "Marcus Brown",
        "email_addresses": [{"value": "marcus.brown@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0108", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3009,
                "status": "rejected",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2002, "name": "Phone Screen"},
                "applied_at": _iso_ago(days=45),
                "last_activity_at": _iso_ago(days=30),
                "source": {"public_name": "Indeed"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 108,
            },
        ],
    },
    {
        "id": 109,
        "first_name": "Sophie",
        "last_name": "Laurent",
        "name": "Sophie Laurent",
        "email_addresses": [{"value": "sophie.laurent@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0109", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3010,
                "status": "active",
                "jobs": [{"id": 1001, "name": "Senior Software Engineer"}],
                "current_stage": {"id": 2001, "name": "Application Review"},
                "applied_at": _iso_ago(days=3),
                "last_activity_at": _iso_ago(days=1),
                "source": {"public_name": "Company Website"},
                "recruiter": {"name": "Tom Davis"},
                "prospect": False,
                "candidate_id": 109,
            },
        ],
    },
    # --- Product Manager candidates ---
    {
        "id": 110,
        "first_name": "Rachel",
        "last_name": "Green",
        "name": "Rachel Green",
        "email_addresses": [{"value": "rachel.green@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0110", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3011,
                "status": "active",
                "jobs": [{"id": 1002, "name": "Product Manager"}],
                "current_stage": {"id": 2010, "name": "Resume Review"},
                "applied_at": _iso_ago(days=5),
                "last_activity_at": _iso_ago(days=2),
                "source": {"public_name": "LinkedIn"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 110,
            },
        ],
    },
    {
        "id": 111,
        "first_name": "Nathan",
        "last_name": "Park",
        "name": "Nathan Park",
        "email_addresses": [{"value": "nathan.park@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0111", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3012,
                "status": "active",
                "jobs": [{"id": 1002, "name": "Product Manager"}],
                "current_stage": {"id": 2012, "name": "Panel Interview"},
                "applied_at": _iso_ago(days=20),
                "last_activity_at": _iso_ago(days=3),
                "source": {"public_name": "Referral"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 111,
            },
        ],
    },
    {
        "id": 112,
        "first_name": "Lisa",
        "last_name": "Wang",
        "name": "Lisa Wang",
        "email_addresses": [{"value": "lisa.wang@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0112", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3013,
                "status": "active",
                "jobs": [{"id": 1002, "name": "Product Manager"}],
                "current_stage": {"id": 2011, "name": "Hiring Manager Screen"},
                "applied_at": _iso_ago(days=10),
                "last_activity_at": _iso_ago(days=4),
                "source": {"public_name": "Company Website"},
                "recruiter": {"name": "Tom Davis"},
                "prospect": False,
                "candidate_id": 112,
            },
        ],
    },
    # --- Data Scientist candidates ---
    {
        "id": 113,
        "first_name": "Omar",
        "last_name": "Hassan",
        "name": "Omar Hassan",
        "email_addresses": [{"value": "omar.hassan@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0113", "type": "mobile"}],
        "tags": ["phd"],
        "applications": [
            {
                "id": 3014,
                "status": "active",
                "jobs": [{"id": 1003, "name": "Data Scientist"}],
                "current_stage": {"id": 2021, "name": "Technical Assessment"},
                "applied_at": _iso_ago(days=15),
                "last_activity_at": _iso_ago(days=5),
                "source": {"public_name": "LinkedIn"},
                "recruiter": {"name": "Tom Davis"},
                "prospect": False,
                "candidate_id": 113,
            },
        ],
    },
    {
        "id": 114,
        "first_name": "Emily",
        "last_name": "Foster",
        "name": "Emily Foster",
        "email_addresses": [{"value": "emily.foster@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0114", "type": "mobile"}],
        "tags": [],
        "applications": [
            {
                "id": 3015,
                "status": "active",
                "jobs": [{"id": 1003, "name": "Data Scientist"}],
                "current_stage": {"id": 2020, "name": "Application Review"},
                "applied_at": _iso_ago(days=4),
                "last_activity_at": _iso_ago(days=2),
                "source": {"public_name": "University Recruiting"},
                "recruiter": {"name": "Sarah Johnson"},
                "prospect": False,
                "candidate_id": 114,
            },
        ],
    },
    {
        "id": 115,
        "first_name": "Alex",
        "last_name": "Tanaka",
        "name": "Alex Tanaka",
        "email_addresses": [{"value": "alex.tanaka@example.com", "type": "personal"}],
        "phone_numbers": [{"value": "+1-415-555-0115", "type": "mobile"}],
        "tags": ["senior", "phd"],
        "applications": [
            {
                "id": 3016,
                "status": "active",
                "jobs": [{"id": 1003, "name": "Data Scientist"}],
                "current_stage": {"id": 2022, "name": "Team Interview"},
                "applied_at": _iso_ago(days=25),
                "last_activity_at": _iso_ago(days=4),
                "source": {"public_name": "Referral"},
                "recruiter": {"name": "Tom Davis"},
                "prospect": False,
                "candidate_id": 115,
            },
        ],
    },
]

# Build lookup tables
_CANDIDATES_BY_ID: dict[int, dict[str, Any]] = {c["id"]: c for c in _CANDIDATES}

# Flatten all applications from all candidates
_ALL_APPLICATIONS: list[dict[str, Any]] = []
for _c in _CANDIDATES:
    _ALL_APPLICATIONS.extend(_c["applications"])

# ---------------------------------------------------------------------------
# Scorecards
# ---------------------------------------------------------------------------

_SCORECARDS: dict[int, list[dict[str, Any]]] = {
    # Maria Chen's SWE application -- strong scorecards
    3001: [
        {
            "id": 5001,
            "application_id": 3001,
            "interview": "Technical Interview",
            "interviewed_at": _iso_ago(days=10),
            "submitted_at": _iso_ago(days=9),
            "interviewer": {"id": 801, "name": "Alice Zhang"},
            "overall_recommendation": "strong_yes",
            "attributes": [
                {"name": "Problem Solving", "rating": "strong_yes"},
                {"name": "Communication", "rating": "yes"},
            ],
        },
        {
            "id": 5002,
            "application_id": 3001,
            "interview": "Onsite - System Design",
            "interviewed_at": _iso_ago(days=5),
            "submitted_at": _iso_ago(days=4),
            "interviewer": {"id": 802, "name": "Bob Martinez"},
            "overall_recommendation": "yes",
            "attributes": [
                {"name": "System Design", "rating": "yes"},
                {"name": "Architecture Knowledge", "rating": "strong_yes"},
            ],
        },
    ],
    # James Wilson's application -- interview done but NO scorecard submitted
    3003: [
        {
            "id": 5003,
            "application_id": 3003,
            "interview": "Phone Screen",
            "interviewed_at": _iso_ago(days=3),
            "submitted_at": None,
            "interviewer": {"id": 803, "name": "Carol White"},
            "overall_recommendation": "no_decision",
            "attributes": [],
        },
    ],
    # Aisha Patel's application -- one submitted, one missing
    3004: [
        {
            "id": 5004,
            "application_id": 3004,
            "interview": "Technical Interview - Coding",
            "interviewed_at": _iso_ago(days=5),
            "submitted_at": _iso_ago(days=4),
            "interviewer": {"id": 801, "name": "Alice Zhang"},
            "overall_recommendation": "yes",
            "attributes": [
                {"name": "Coding", "rating": "yes"},
                {"name": "Problem Solving", "rating": "yes"},
            ],
        },
        {
            "id": 5005,
            "application_id": 3004,
            "interview": "Technical Interview - Design",
            "interviewed_at": _iso_ago(days=4),
            "submitted_at": None,
            "interviewer": {"id": 804, "name": "Dan Lee"},
            "overall_recommendation": "no_decision",
            "attributes": [],
        },
    ],
    # Nathan Park's PM application -- submitted
    3012: [
        {
            "id": 5006,
            "application_id": 3012,
            "interview": "Panel Interview",
            "interviewed_at": _iso_ago(days=4),
            "submitted_at": _iso_ago(days=3),
            "interviewer": {"id": 805, "name": "Eva Nguyen"},
            "overall_recommendation": "yes",
            "attributes": [
                {"name": "Product Sense", "rating": "yes"},
                {"name": "Analytical Thinking", "rating": "strong_yes"},
            ],
        },
    ],
    # Carlos Rodriguez -- scorecard submitted with "no"
    3005: [
        {
            "id": 5007,
            "application_id": 3005,
            "interview": "Technical Interview",
            "interviewed_at": _iso_ago(days=8),
            "submitted_at": _iso_ago(days=7),
            "interviewer": {"id": 802, "name": "Bob Martinez"},
            "overall_recommendation": "no",
            "attributes": [
                {"name": "Problem Solving", "rating": "no"},
                {"name": "Communication", "rating": "yes"},
            ],
        },
    ],
    # Alex Tanaka -- submitted scorecards
    3016: [
        {
            "id": 5008,
            "application_id": 3016,
            "interview": "Team Interview",
            "interviewed_at": _iso_ago(days=5),
            "submitted_at": _iso_ago(days=4),
            "interviewer": {"id": 806, "name": "Frank Adams"},
            "overall_recommendation": "strong_yes",
            "attributes": [
                {"name": "ML Knowledge", "rating": "strong_yes"},
                {"name": "Communication", "rating": "yes"},
            ],
        },
        {
            "id": 5009,
            "application_id": 3016,
            "interview": "Team Interview - ML Deep Dive",
            "interviewed_at": _iso_ago(days=4),
            "submitted_at": None,
            "interviewer": {"id": 807, "name": "Grace Liu"},
            "overall_recommendation": "no_decision",
            "attributes": [],
        },
    ],
}

# ---------------------------------------------------------------------------
# Offers
# ---------------------------------------------------------------------------

_OFFERS: list[dict[str, Any]] = [
    # Maria Chen -- accepted offer for SWE
    {
        "id": 6001,
        "application_id": 3001,
        "candidate_id": 101,
        "job_id": 1001,
        "status": "accepted",
        "starts_at": _date_ago(days=-30),
        "sent_at": _date_ago(days=10),
        "created_at": _iso_ago(days=12),
    },
    # Nathan Park -- offer sent 5 days ago, no response (unresolved)
    {
        "id": 6002,
        "application_id": 3012,
        "candidate_id": 111,
        "job_id": 1002,
        "status": "unresolved",
        "starts_at": _date_ago(days=-45),
        "sent_at": _date_ago(days=5),
        "created_at": _iso_ago(days=7),
    },
    # Alex Tanaka -- offer drafted 3 days ago but not sent (unresolved)
    {
        "id": 6003,
        "application_id": 3016,
        "candidate_id": 115,
        "job_id": 1003,
        "status": "unresolved",
        "starts_at": None,
        "sent_at": None,
        "created_at": _iso_ago(days=3),
    },
]

# ---------------------------------------------------------------------------
# Scheduled interviews
# ---------------------------------------------------------------------------

_SCHEDULED_INTERVIEWS: list[dict[str, Any]] = [
    # Priya Sharma -- scheduled for tomorrow
    {
        "id": 7001,
        "application_id": 3006,
        "interview": {"id": 8001, "name": "Technical Interview"},
        "start": {"date_time": _iso_ago(days=-1)},
        "end": {"date_time": _iso_ago(days=-1, hours=-1)},
        "status": "scheduled",
        "interviewers": [
            {"id": 801, "name": "Alice Zhang"},
            {"id": 802, "name": "Bob Martinez"},
        ],
    },
    # David Kim -- interview completed 3 days ago, awaiting feedback
    {
        "id": 7002,
        "application_id": 3007,
        "interview": {"id": 8002, "name": "Technical Interview"},
        "start": {"date_time": _iso_ago(days=3)},
        "end": {"date_time": _iso_ago(days=3, hours=-1)},
        "status": "awaiting_feedback",
        "interviewers": [
            {"id": 803, "name": "Carol White"},
        ],
    },
    # Elena Volkov -- interview completed 3 days ago, awaiting feedback
    {
        "id": 7003,
        "application_id": 3008,
        "interview": {"id": 8003, "name": "Technical Interview"},
        "start": {"date_time": _iso_ago(days=3)},
        "end": {"date_time": _iso_ago(days=3, hours=-1)},
        "status": "awaiting_feedback",
        "interviewers": [
            {"id": 804, "name": "Dan Lee"},
        ],
    },
    # Omar Hassan -- completed assessment
    {
        "id": 7004,
        "application_id": 3014,
        "interview": {"id": 8004, "name": "Technical Assessment"},
        "start": {"date_time": _iso_ago(days=5)},
        "end": {"date_time": _iso_ago(days=5, hours=-2)},
        "status": "complete",
        "interviewers": [
            {"id": 806, "name": "Frank Adams"},
        ],
    },
    # Lisa Wang -- scheduled for next week
    {
        "id": 7005,
        "application_id": 3013,
        "interview": {"id": 8005, "name": "Hiring Manager Screen"},
        "start": {"date_time": _iso_ago(days=-5)},
        "end": {"date_time": _iso_ago(days=-5, hours=-1)},
        "status": "scheduled",
        "interviewers": [
            {"id": 805, "name": "Eva Nguyen"},
        ],
    },
]

# ---------------------------------------------------------------------------
# Activity feeds
# ---------------------------------------------------------------------------

_ACTIVITY_FEEDS: dict[int, dict[str, Any]] = {
    101: {
        "notes": [
            {
                "id": 9001,
                "body": "Maria had an outstanding onsite. Strong system design and excellent communication.",
                "user": {"name": "Alice Zhang"},
                "created_at": _iso_ago(days=5),
            },
            {
                "id": 9002,
                "body": "Offer extended. Very excited about this candidate joining the team.",
                "user": {"name": "Sarah Johnson"},
                "created_at": _iso_ago(days=10),
            },
            {
                "id": 9003,
                "body": "Maria accepted the offer! Start date confirmed.",
                "user": {"name": "Sarah Johnson"},
                "created_at": _iso_ago(days=2),
            },
        ],
        "emails": [
            {
                "id": 9101,
                "subject": "Interview Confirmation",
                "from": "recruiting@company.com",
                "to": "maria.chen@example.com",
                "created_at": _iso_ago(days=15),
            },
            {
                "id": 9102,
                "subject": "Offer Letter",
                "from": "recruiting@company.com",
                "to": "maria.chen@example.com",
                "created_at": _iso_ago(days=10),
            },
        ],
        "activities": [
            {"id": 9201, "body": "Application submitted", "created_at": _iso_ago(days=60)},
            {"id": 9202, "body": "Moved to Phone Screen", "created_at": _iso_ago(days=55)},
            {"id": 9203, "body": "Moved to Technical Interview", "created_at": _iso_ago(days=40)},
            {"id": 9204, "body": "Moved to Onsite", "created_at": _iso_ago(days=20)},
            {"id": 9205, "body": "Offer extended", "created_at": _iso_ago(days=10)},
            {"id": 9206, "body": "Offer accepted", "created_at": _iso_ago(days=2)},
        ],
    },
    102: {
        "notes": [
            {
                "id": 9004,
                "body": "James seems to have gone quiet after phone screen was scheduled. Need to follow up.",
                "user": {"name": "Tom Davis"},
                "created_at": _iso_ago(days=10),
            },
        ],
        "emails": [
            {
                "id": 9103,
                "subject": "Phone Screen Scheduling",
                "from": "recruiting@company.com",
                "to": "james.wilson@example.com",
                "created_at": _iso_ago(days=18),
            },
        ],
        "activities": [
            {"id": 9207, "body": "Application submitted", "created_at": _iso_ago(days=20)},
            {"id": 9208, "body": "Moved to Phone Screen", "created_at": _iso_ago(days=18)},
        ],
    },
    111: {
        "notes": [
            {
                "id": 9005,
                "body": "Nathan did very well in the panel interview. Strong product sense.",
                "user": {"name": "Eva Nguyen"},
                "created_at": _iso_ago(days=4),
            },
        ],
        "emails": [
            {
                "id": 9104,
                "subject": "Offer Discussion",
                "from": "recruiting@company.com",
                "to": "nathan.park@example.com",
                "created_at": _iso_ago(days=5),
            },
        ],
        "activities": [
            {"id": 9209, "body": "Application submitted", "created_at": _iso_ago(days=20)},
            {"id": 9210, "body": "Moved to Panel Interview", "created_at": _iso_ago(days=8)},
            {"id": 9211, "body": "Offer sent", "created_at": _iso_ago(days=5)},
        ],
    },
}


# ---------------------------------------------------------------------------
# FakeGreenhouseClient
# ---------------------------------------------------------------------------


class FakeGreenhouseClient:
    """Realistic test double implementing GreenhousePort with pre-populated data.

    Contains 3 jobs, 15 candidates, scorecards, offers, interviews, and
    activity feeds that tell a recruiting story with bottlenecks, missing
    scorecards, and pending offers.
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
        result = list(_JOBS)
        if status is not None:
            result = [j for j in result if j["status"] == status]
        if department_id is not None:
            result = [j for j in result if any(d["id"] == department_id for d in j.get("departments", []))]
        return result

    async def get_job(self, job_id: int) -> dict[str, Any]:
        """Fetch a single job by ID.

        Args:
            job_id: The Greenhouse job ID.

        Returns:
            Job object.

        Raises:
            NotFoundError: If the job does not exist.
        """
        for job in _JOBS:
            if job["id"] == job_id:
                return job
        msg = f"Job {job_id} not found"
        raise NotFoundError(msg)

    async def get_job_stages(self, job_id: int) -> list[dict[str, Any]]:
        """Fetch stages for a specific job.

        Args:
            job_id: The Greenhouse job ID.

        Returns:
            List of stage objects ordered by priority.
        """
        return list(_STAGES.get(job_id, []))

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
        result = list(_ALL_APPLICATIONS)
        if job_id is not None:
            result = [a for a in result if any(j["id"] == job_id for j in a.get("jobs", []))]
        if status is not None:
            result = [a for a in result if a["status"] == status]
        if created_after is not None:
            cutoff = datetime.fromisoformat(created_after.replace("Z", "+00:00"))
            result = [a for a in result if datetime.fromisoformat(a["applied_at"]) >= cutoff]
        return result

    async def get_candidate(self, candidate_id: int) -> dict[str, Any]:
        """Fetch a single candidate by ID.

        Args:
            candidate_id: The Greenhouse candidate ID.

        Returns:
            Candidate object.

        Raises:
            NotFoundError: If the candidate does not exist.
        """
        candidate = _CANDIDATES_BY_ID.get(candidate_id)
        if candidate is None:
            msg = f"Candidate {candidate_id} not found"
            raise NotFoundError(msg)
        return candidate

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
        result = list(_CANDIDATES)
        if job_id is not None:
            result = [
                c
                for c in result
                if any(any(j["id"] == job_id for j in app.get("jobs", [])) for app in c.get("applications", []))
            ]
        if email is not None:
            result = [c for c in result if any(e["value"] == email for e in c.get("email_addresses", []))]
        return result

    async def get_scorecards(self, application_id: int) -> list[dict[str, Any]]:
        """Fetch scorecards for a specific application.

        Args:
            application_id: The Greenhouse application ID.

        Returns:
            List of scorecard objects.
        """
        return list(_SCORECARDS.get(application_id, []))

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
        if application_id is not None:
            return [i for i in _SCHEDULED_INTERVIEWS if i["application_id"] == application_id]
        return list(_SCHEDULED_INTERVIEWS)

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
        result = list(_OFFERS)
        if application_id is not None:
            result = [o for o in result if o["application_id"] == application_id]
        if status is not None:
            result = [o for o in result if o["status"] == status]
        return result

    async def get_activity_feed(self, candidate_id: int) -> dict[str, Any]:
        """Fetch the full activity feed for a candidate.

        Args:
            candidate_id: The Greenhouse candidate ID.

        Returns:
            Activity feed object with notes, emails, and activities.
        """
        return _ACTIVITY_FEEDS.get(
            candidate_id,
            {"notes": [], "emails": [], "activities": []},
        )
