# ADR 0006: Candidate Data Relationships and Fetch Strategy

## Status

Accepted

## Context

The `candidate_dossier` tool must assemble a complete picture of a candidate from
multiple Greenhouse API endpoints in a single MCP tool call. Before implementing
this tool, we need precise answers to:

1. How do Candidate, Application, Scorecard, Offer, Scheduled Interview, and
   Activity Feed resources relate to each other?
2. What is the most efficient fetch order, and where can we use concurrency?
3. How should the response be structured for agent consumption?
4. What edge cases must the implementation handle?

All findings are derived from ADR 0003 (Greenhouse API Patterns) and the existing
`GreenhousePort` / `GreenhouseClient` implementation.

## Relationship Map

```
Candidate (1)
├── applications[] (1:N)  — embedded as [{id, status}] in GET /candidates/{id}
│   ├── scorecards[] (1:N)    — GET /applications/{id}/scorecards
│   ├── scheduled_interviews[] (1:N) — GET /applications/{id}/scheduled_interviews
│   └── offers[] (1:N)        — GET /applications/{id}/offers
└── activity_feed (1:1)   — GET /candidates/{id}/activity_feed
        ├── notes[]
        ├── emails[]
        └── activities[]
```

### Key Observations

1. **Candidate embeds application stubs.** `GET /candidates/{id}` returns an
   `applications` array with `[{id, status}]` objects. These give us the
   application IDs we need without a separate list call.

2. **Sub-resources are scoped to Application, not Candidate.** Scorecards,
   scheduled interviews, and offers are fetched per-application via
   `/applications/{id}/scorecards`, `/applications/{id}/scheduled_interviews`,
   and `/applications/{id}/offers`. There is no `/candidates/{id}/scorecards`
   shortcut.

3. **Activity feed is scoped to Candidate.** `GET /candidates/{id}/activity_feed`
   returns all notes, emails, and activities across all applications. It is
   independent of any specific application.

4. **No cross-resource joins.** The API provides no way to fetch "all scorecards
   for a candidate" in one call. We must iterate over applications.

## Fetch Strategy

### Optimal Call Ordering

```
Step 1: GET /candidates/{candidate_id}
        → Extract application IDs from response.applications[].id
        → Extract candidate summary fields

Step 2 (concurrent via asyncio.gather):
  ├── For each application_id (concurrent per-application):
  │   ├── GET /applications/{app_id}/scorecards
  │   ├── GET /applications/{app_id}/scheduled_interviews
  │   └── GET /applications/{app_id}/offers
  └── GET /candidates/{candidate_id}/activity_feed
```

### Why This Order

- **Step 1 must complete first.** We need the application IDs from the candidate
  response before we can fetch sub-resources. There is no way to know application
  IDs without this call.

- **Step 2 is fully parallelizable.** The activity feed is independent of
  applications. Within each application, scorecards, interviews, and offers are
  independent of each other. All of these can run concurrently.

### Implementation Pattern

```python
async def candidate_dossier(candidate_id: int, client: GreenhousePort) -> dict:
    # Step 1: Fetch candidate (sequential, required for app IDs)
    candidate = await client.get_candidate(candidate_id)
    application_ids = [app["id"] for app in candidate.get("applications", [])]

    # Step 2: Fetch all sub-resources concurrently
    async def fetch_application_details(app_id: int) -> dict:
        scorecards, interviews, offers = await asyncio.gather(
            client.get_scorecards(app_id),
            client.get_scheduled_interviews(application_id=app_id),
            client.get_offers(application_id=app_id),
        )
        return {
            "application_id": app_id,
            "scorecards": scorecards,
            "scheduled_interviews": interviews,
            "offers": offers,
        }

    app_details_coros = [fetch_application_details(app_id) for app_id in application_ids]
    activity_feed_coro = client.get_activity_feed(candidate_id)

    # All sub-resource fetches + activity feed run concurrently
    *app_details_list, activity_feed = await asyncio.gather(
        *app_details_coros,
        activity_feed_coro,
    )

    return assemble_dossier(candidate, app_details_list, activity_feed)
```

### Expected API Call Count

| Scenario | API Calls | Formula |
|----------|-----------|---------|
| Candidate with 0 applications | 2 | 1 (candidate) + 1 (activity feed) |
| Candidate with 1 application | 5 | 1 + 3 (scorecards + interviews + offers) + 1 |
| Candidate with 3 applications | 11 | 1 + 3*3 + 1 |
| Candidate with N applications | 3N + 2 | 1 + 3N + 1 |

A typical candidate has 1-3 applications, so **5-11 API calls** is the expected
range. With full concurrency in Step 2, wall-clock time is dominated by the
slowest single sub-resource call, not the total count.

### Rate Limit Budget

Per ADR 0003, the rate limit window is ~50 requests per 10 seconds. A single
dossier fetch for a candidate with 3 applications uses 11 calls. That leaves
~39 calls in the window for other operations. Even a candidate with 10
applications (32 calls) stays within budget with margin.

For candidates with an unusually high number of applications (>15), we should
consider batching the per-application fetches with a concurrency semaphore
(e.g., `asyncio.Semaphore(10)`) to avoid exhausting the rate limit in a single
burst. This is a defensive measure; the typical case does not require it.

## Response Structure

The dossier follows the project's design principle: **summaries first, details
second**. An agent reading the response should get actionable context from the
first few fields without parsing nested arrays.

```json
{
  "summary": {
    "candidate_id": 12345,
    "name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "+1-555-0100",
    "tags": ["strong-referral", "senior"],
    "application_count": 2,
    "active_application_count": 1,
    "has_pending_offers": true,
    "overall_status": "active"
  },
  "applications": [
    {
      "application_id": 67890,
      "job_name": "Senior Engineer",
      "status": "active",
      "current_stage": "Onsite Interview",
      "applied_at": "2026-01-15T10:00:00Z",
      "last_activity_at": "2026-03-10T14:30:00Z",
      "source": "LinkedIn",
      "recruiter": "Alex Johnson",
      "scorecards": [
        {
          "id": 111,
          "interview": "Technical Screen",
          "interviewer": "Pat Lee",
          "overall_recommendation": "strong_yes",
          "submitted_at": "2026-02-01T16:00:00Z"
        }
      ],
      "scheduled_interviews": [
        {
          "id": 222,
          "interview_name": "Onsite: System Design",
          "start": "2026-03-25T13:00:00Z",
          "status": "scheduled",
          "interviewers": ["Morgan Chen", "Sam Patel"]
        }
      ],
      "offers": []
    }
  ],
  "activity_feed": {
    "recent_notes": [
      {
        "created_at": "2026-03-10T14:30:00Z",
        "user": "Alex Johnson",
        "body": "Candidate confirmed availability for onsite."
      }
    ],
    "recent_emails": [],
    "total_notes": 5,
    "total_emails": 12,
    "total_activities": 23
  }
}
```

### Field Selection Rationale

**Summary section** gives the agent enough to answer "who is this candidate and
where do they stand?" without reading further:
- `name`, `email`, `phone` -- contact basics
- `tags` -- recruiter-assigned labels (often encode referral source, seniority)
- `application_count` / `active_application_count` -- scope of engagement
- `has_pending_offers` -- critical flag for prioritization
- `overall_status` -- derived from application statuses (active if any app is
  active, otherwise the most recent terminal status)

**Applications section** groups sub-resources by application. Each application
includes flattened summaries of its scorecards, interviews, and offers rather
than raw API responses. This avoids the agent needing to cross-reference IDs.

**Activity feed section** includes recent notes/emails (most recent 5-10) with
total counts. The full activity feed can be very large for long-tenured
candidates; truncating with counts lets the agent decide whether to request more.

### Derived Fields

Several response fields require computation, not just pass-through:

| Field | Derivation |
|-------|------------|
| `overall_status` | If any application is `active`, status is `active`. Otherwise, use the most recent terminal status (`hired` > `rejected` > `converted`). |
| `has_pending_offers` | `True` if any application has an offer with `status == "unresolved"` |
| `active_application_count` | Count of applications where `status == "active"` |
| `job_name` | Extracted from the application's `jobs[0].name` (applications embed a jobs array) |
| `recruiter` | Extracted from application's `recruiter.name` |
| `source` | Extracted from application's `source.public_name` |

## Edge Cases

### Candidate with Zero Applications

Possible for prospects or manually-created candidate records. The response
should return an empty `applications` array and still fetch the activity feed.
The summary's `overall_status` should be `"no_applications"`.

### Application with No Scorecards

Common for early-stage applications (e.g., just applied, not yet screened). The
`scorecards` array is empty `[]`. No special handling needed -- this is the
normal empty-collection behavior from the API.

### Application with No Offers

The vast majority of applications never reach the offer stage. Empty `offers`
array is the default case, not an edge case.

### Unsubmitted Scorecards

Scorecards where `submitted_at` is `null` are in-progress. The dossier should
include them but flag them distinctly (e.g., `"status": "draft"` vs
`"status": "submitted"`). Recruiters need to know an interviewer started but
hasn't finished their feedback.

### Large Activity Feeds (No Pagination)

Per ADR 0003, `GET /candidates/{id}/activity_feed` has no pagination and dumps
the entire history. For candidates with years of activity, this could be a large
payload.

**Mitigation strategy:**
1. Set a generous HTTP read timeout on this specific call (30s vs the default).
2. Truncate the response: return only the N most recent items per category
   (notes, emails, activities) with total counts.
3. Document the truncation so agents know they're seeing a subset.

The truncation happens in the tool layer, not the client layer. The client
faithfully returns what the API gives; the tool shapes it for agent consumption.

### Deleted/Rejected Applications

**Include all applications regardless of status.** The dossier should give the
complete picture. Rejected applications contain valuable context:
- Rejection reason (why they were passed on before)
- Previous scorecards (what interviewers said)
- Historical timeline (how long ago, for which role)

Filter by status in the summary (`active_application_count`) but show everything
in the details.

### Candidate Not Found (404)

`GET /candidates/{id}` returns 404 for nonexistent IDs. The client raises
`NotFoundError` (per ADR 0003). The tool should catch this and return a clear
error message rather than letting the exception propagate to the MCP framework.

### Deleted Resources

Per ADR 0003, deleted resources return `{"message": "... has been deleted."}`
with a 200 status, not a 404. The tool should detect this pattern (response is
a dict with only a `message` key, no `id` field) and handle it gracefully --
either skip the deleted resource or include it with a `"deleted": true` flag.

## Consequences

### Impact on `candidate_dossier` Tool Design

1. **The tool needs `asyncio.gather` for concurrent sub-resource fetching.**
   Sequential fetching of 3N+2 calls would be unacceptably slow. The port
   interface already supports this -- all methods are `async`.

2. **The tool layer owns response shaping.** The client returns raw API dicts;
   the tool extracts, flattens, and summarizes. This keeps the client generic
   and the tool focused on the "complete candidate picture" use case.

3. **Activity feed truncation is a tool-layer concern.** The client returns
   the full feed; the tool truncates to recent items with counts.

4. **A concurrency semaphore is advisable for safety.** While typical candidates
   won't hit rate limits, a defensive `asyncio.Semaphore` prevents pathological
   cases from burning the entire rate limit budget.

### Impact on `GreenhousePort`

The existing port interface already has all the methods needed:
- `get_candidate(candidate_id)` -- Step 1
- `get_scorecards(application_id)` -- Step 2
- `get_scheduled_interviews(application_id=...)` -- Step 2
- `get_offers(application_id=...)` -- Step 2
- `get_activity_feed(candidate_id)` -- Step 2

No new port methods are required. The current interface was designed with this
use case in mind.

### Impact on Pydantic Models

The tool should define response models in `models.py` for the shaped output:
- `CandidateSummary` -- the summary section
- `ApplicationDetail` -- per-application with embedded scorecards/interviews/offers
- `ActivityFeedSummary` -- truncated feed with counts
- `CandidateDossier` -- the top-level response combining all three

These are *output* models (what the tool returns), not *input* models (what the
API returns). The client continues to return `dict[str, Any]`; the tool
constructs typed models from those dicts.

### Open Questions

1. **How many recent activity items to include?** Proposal: 10 most recent per
   category (notes, emails, activities). This is configurable via a tool
   parameter with a sensible default.

2. **Should the tool accept an `include_rejected` parameter?** The default
   includes all applications. A parameter could let callers filter to active-only
   for a cleaner view. Recommendation: include all by default, let the agent
   filter if needed.

3. **Should scorecard details include the full `attributes` and `questions`
   arrays?** These can be verbose. Proposal: include `overall_recommendation`
   and a count of attributes, with full details available via a separate tool
   or parameter flag.
