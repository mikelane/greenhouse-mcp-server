# ADR 0007: Staleness Thresholds and Priority Scoring

## Status

Accepted

## Context

The `needs_attention` tool surfaces items a recruiter or hiring manager should act on.
Three questions drive the design:

1. **What counts as "stale"?** Which categories of inaction do we detect?
2. **How long is too long?** What default thresholds make sense for each category?
3. **How do we rank items?** When a recruiter has 30 action items, which come first?

The Greenhouse Harvest API gives us the raw data (see ADR 0003 for endpoint shapes). The
hard part is turning API fields into "needs attention" signals with defaults that work
across different company sizes and hiring velocities.

## Staleness Categories

Five categories of items need attention. Each maps to specific API fields and has its own
detection mechanism.

### Category 1: Applications Stuck in Stage

**What it means:** A candidate has been sitting in the same pipeline stage too long
with no activity. The most common cause of candidate drop-off.

**Detection method:**

```
now - application.last_activity_at > threshold
AND application.status == "active"
AND application.current_stage is not null
```

**API fields used:**
- `application.last_activity_at` (ISO 8601 UTC timestamp)
- `application.status` (must be `"active"` -- rejected/hired applications are resolved)
- `application.current_stage.id` and `application.current_stage.name`

**Why `last_activity_at` and not stage entry time:** The Greenhouse API does not expose a
"entered current stage at" timestamp on the application object. `last_activity_at` is the
closest proxy. It updates on any activity (stage change, email, note, scorecard submission),
so it slightly under-reports true time-in-stage when activity happened without a stage
transition. Good enough -- if there has been activity, the application is not truly stuck.

**Port method:** `get_applications(status="active")` to fetch candidates, then
client-side filtering on `last_activity_at`.

### Category 2: Missing Scorecards

**What it means:** An interview has been completed but one or more interviewers have not
submitted their scorecard. This blocks the debrief and slows decision-making.

**Detection method:**

```
scorecard.submitted_at is null
AND scheduled_interview.end.date_time < now - threshold
AND scheduled_interview.status in ("awaiting_feedback", "complete")
```

**API fields used:**
- `scorecard.submitted_at` (null when not yet submitted)
- `scorecard.interviewed_at` (when the interview occurred)
- `scorecard.interviewer` (who owes the scorecard)
- `scorecard.interview` (string name of the interview step)
- `scorecard.application_id` (to link back to the candidate)
- `scheduled_interview.end.date_time` (when the interview ended)
- `scheduled_interview.interviewers[].scorecard_id` (null means no scorecard submitted)

**Two detection paths:**

1. **Via scorecards endpoint:** `GET /applications/{id}/scorecards` returns all scorecards
   for an application, including unsubmitted ones (`submitted_at: null`). Compare
   `interviewed_at` to `now` to determine age.

2. **Via scheduled interviews endpoint:** `GET /applications/{id}/scheduled_interviews`
   with `status` in `awaiting_feedback` or `complete`. Each interviewer object has a
   `scorecard_id` field -- when null, that interviewer has not submitted. The `end.date_time`
   gives the exact interview end time.

Path 2 is more precise because it tells us exactly which interviewers are missing scorecards
and uses the interview end time rather than the scorecard creation time. However, path 1
requires fewer API calls when scanning across many applications.

**Recommended approach:** Use path 1 (scorecards endpoint) for the initial scan across all
active applications, since `get_scorecards(application_id)` is already in our port. Fall back
to path 2 only if we need interviewer-level detail for a specific application.

**Port methods:** `get_scorecards(application_id)` for detection,
`get_scheduled_interviews(application_id=id)` for interviewer-level detail.

### Category 3: Offers Pending Approval

**What it means:** An offer has been created (or sent) but remains in `unresolved` status
beyond a reasonable timeframe. This could mean the candidate hasn't responded, the approval
chain is stuck, or the offer was forgotten.

**Detection method:**

```
offer.status == "unresolved"
AND (now - offer.sent_at > threshold  OR  now - offer.created_at > threshold)
```

**API fields used:**
- `offer.status` (must be `"unresolved"`)
- `offer.sent_at` (date `YYYY-MM-DD`, present only after the offer is sent to the candidate)
- `offer.created_at` (ISO 8601 timestamp, present from the moment the offer is drafted)
- `offer.application_id` (to link back to the candidate)
- `offer.candidate_id` (for grouping)

**Two sub-cases:**
1. **Offer sent but no response:** `sent_at` is present, status is `unresolved`. The clock
   starts at `sent_at`.
2. **Offer drafted but not sent:** `sent_at` is null, status is `unresolved`. The clock
   starts at `created_at`. This indicates an internal bottleneck (approval chain, comp
   review, etc.).

Sub-case 2 is more urgent -- the candidate doesn't even know an offer is coming, and
internal delays compound drop-off risk.

**Port method:** `get_offers(status="unresolved")` fetches all pending offers globally.
No need to iterate per-application.

### Category 4: Candidates With No Recent Activity

**What it means:** A candidate has active applications but zero activity for an extended
period. Broader than "stuck in stage" -- this catches cases where the candidate has
been ghosted.

**Detection method:**

```
now - application.last_activity_at > threshold
AND application.status == "active"
```

This overlaps with Category 1 but uses a longer threshold. Category 1 catches stage-level
staleness (7 days). Category 4 catches system-level neglect (14+ days). An application that
triggers Category 4 will always also trigger Category 1, so deduplicate by showing only the
higher-severity Category 4 item.

**Port method:** Same as Category 1. `get_applications(status="active")` with client-side
filtering on `last_activity_at`. Deduplicate against Category 1 results.

### Category 5: Interviews Scheduled But No Movement After

**What it means:** An application is in an interview-type stage and has completed all
scheduled interviews, but has not advanced to the next stage. The debrief may have happened
but nobody moved the candidate forward (or backward).

**Detection method:**

```
all scheduled_interviews for application have status in ("awaiting_feedback", "complete")
AND all scorecards for application have submitted_at is not null
AND application has not changed stage for > threshold days
AND application.status == "active"
```

This is the hardest category to detect because "has not changed stage" is not directly
exposed by the API. We approximate it using `last_activity_at` as a proxy -- if all
interviews are done, all scorecards are in, and there has been no activity, the application
is stuck in post-interview limbo.

**Port methods:** `get_applications(status="active")`, `get_scorecards(application_id)`,
`get_scheduled_interviews(application_id=id)`.

## Default Thresholds

Defaults should catch real problems without flooding the recruiter with false positives.
These come from industry benchmarks and Greenhouse's own recommendations.

### Threshold Table

| Category | Default | Rationale |
|----------|---------|-----------|
| Application in stage (Category 1) | 7 calendar days | Industry benchmark: candidates expect next steps within 3-5 business days. 7 calendar days (~5 business days) is the upper bound of acceptable. |
| Missing scorecard (Category 2) | 2 calendar days (48 hours) | Greenhouse sends reminders starting 1 hour after interview end, then daily for 10 business days. 48 hours means the interviewer has received at least 2 reminders. Memory degrades rapidly after 24 hours -- scorecards submitted after 48 hours are less accurate. |
| Offer pending -- sent (Category 3a) | 3 calendar days | Candidates typically respond to offers within 2-3 business days. After 3 calendar days without response, the recruiter should follow up. |
| Offer pending -- drafted not sent (Category 3b) | 2 calendar days | Internal process should not take more than 1-2 days. A drafted offer sitting for 48 hours suggests an approval bottleneck. |
| No activity (Category 4) | 14 calendar days | Doubles the stage-staleness threshold. At 14 days a candidate has likely moved on mentally. This is the "candidate is being ghosted" signal. |
| Post-interview limbo (Category 5) | 3 calendar days | After all interviews and scorecards are complete, the debrief and decision should happen within 1-2 business days. 3 calendar days is generous. |

### Per-Stage Threshold Overrides

A flat 7-day threshold for all stages is a good starting point, but different stages have
different natural cadences. The tool should accept optional per-stage overrides:

| Stage Type | Suggested Override | Rationale |
|------------|-------------------|-----------|
| Application Review | 3 days | Initial resume review should be fast. Candidates who applied recently are most engaged. |
| Phone Screen | 5 days | Scheduling a 30-minute call should not take a week. |
| Technical Interview | 7 days | Scheduling multiple interviewers takes longer. Keep at default. |
| Onsite / Final Round | 10 days | Complex scheduling with multiple panelists, possible travel. |
| Offer | 5 days | Covered separately by Category 3, but if an application is "in offer stage" without an offer object, something is wrong. |
| Reference Check | 7 days | External dependency (references may be slow to respond). |

**Implementation note:** Stage names vary across companies. We cannot hard-code stage names.
Instead, expose a `stage_thresholds` parameter on the `needs_attention` tool that maps
stage names (or stage IDs) to day counts. The flat 7-day default applies to any stage not
in the override map.

### Configurability

All thresholds are configurable via the `needs_attention` tool parameters:

```python
async def needs_attention(
    *,
    job_id: int | None = None,
    days_stale: int = 7,               # Category 1 default
    scorecard_hours: int = 48,          # Category 2 default
    offer_sent_days: int = 3,           # Category 3a default
    offer_draft_days: int = 2,          # Category 3b default
    no_activity_days: int = 14,         # Category 4 default
    post_interview_days: int = 3,       # Category 5 default
    stage_thresholds: dict[str, int] | None = None,  # Per-stage overrides
) -> NeedsAttentionResult:
    ...
```

These are tool parameters, not environment variables. Thresholds are operational decisions
made by the recruiter or hiring manager per query, not deployment-time configuration.

## Priority Scoring

When multiple items need attention, order matters. We use a composite score from three
factors.

### Priority Factors

**Factor 1: Category severity (weight: 40%)**

| Category | Severity | Score |
|----------|----------|-------|
| Missing scorecard (2) | Critical | 100 |
| Offer pending (3) | Critical | 95 |
| Post-interview limbo (5) | High | 80 |
| Application stuck in stage (1) | Medium | 60 |
| No activity (4) | Medium | 50 |

Missing scorecards rank highest because they block the entire decision pipeline -- no
debrief can happen until scorecards are in. Pending offers rank second because candidate
drop-off risk is highest at the offer stage (the candidate likely has competing offers).

**Factor 2: Days overdue (weight: 40%)**

```
overdue_score = min(100, (days_overdue / threshold) * 50)
```

An item 2x over threshold scores 100. Long-overdue items rise to the top regardless of
category.

**Factor 3: Stage proximity to hire (weight: 20%)**

Later-stage candidates represent more sunk cost (interview time, evaluator time). Losing a
candidate at the offer stage is more expensive than losing one at the application review
stage.

```
stage_score = (stage_index / total_stages) * 100
```

Where `stage_index` is the 0-based position of the application's current stage in the job's
stage list (ordered by `priority`). An application in the final stage scores 100; one in the
first stage scores ~0.

### Composite Score

```
priority = (severity * 0.4) + (overdue_score * 0.4) + (stage_score * 0.2)
```

Range: 0-100. Higher is more urgent.

### Tie-breaking

When two items have the same composite score, break ties by:
1. `last_activity_at` ascending (oldest activity first)
2. `candidate_id` ascending (deterministic ordering)

## Edge Cases

### Weekends and Holidays

**Decision: Use calendar days, not business days.**

Rationale:
- Business day calculation requires knowing the company's holiday calendar, which varies
  by country, office, and even team. The Greenhouse API does not expose holiday data.
- Calendar days are simpler to reason about and implement.
- The thresholds are already generous enough to account for weekends. A 7-calendar-day
  threshold is approximately 5 business days.
- If a company wants tighter thresholds that account for business days, they can adjust
  the thresholds downward (e.g., use 5 calendar days instead of 7).

**Mitigation for weekend noise:** The tool does not suppress items that became stale over
a weekend. The recruiter sees them on Monday morning, which is actually the right time to
act. Hiding them until Tuesday would lose a day.

### Applications in Offer Stage Without an Offer Object

If an application's `current_stage.name` matches common offer-stage patterns (e.g.,
contains "offer" case-insensitively) but no offer object exists for that application,
this is a data inconsistency worth flagging. The application was moved to the offer stage
but nobody created an offer in Greenhouse.

**Detection:**
```
application.current_stage.name matches /offer/i
AND get_offers(application_id=id) returns empty list
AND application.status == "active"
```

This is a bonus signal, not a separate category. Include it in Category 1 results with
a note indicating the discrepancy.

### Rejected and Hired Applications

**Decision: Exclude entirely.**

Applications with `status` in `("rejected", "hired", "converted")` are resolved. They
should never appear in the attention list. Filter them out at the query level using
`get_applications(status="active")`.

### Multiple Items for the Same Candidate

A single candidate can trigger multiple attention items (e.g., missing scorecard AND
stuck in stage). **Group by candidate, list separately within the group.**

The response structure nests items under the candidate:

```json
{
  "items": [
    {
      "candidate_id": 42,
      "candidate_name": "Jane Doe",
      "job_name": "Senior Engineer",
      "attention_items": [
        {"category": "missing_scorecard", "priority": 92, "detail": "..."},
        {"category": "stuck_in_stage", "priority": 71, "detail": "..."}
      ]
    }
  ]
}
```

Sort candidates by their highest-priority item. Within a candidate, sort items by priority
descending.

### Prospects vs. Candidates

Greenhouse distinguishes between candidates (applied to a job) and prospects (sourced but
not yet applied). The `application.prospect` boolean indicates which is which.

**Decision: Include both, but label them.** Stuck prospects may actually matter more --
they represent sourcing effort going to waste. Include an `is_prospect` field in the
response so the agent can filter or highlight as needed.

### Soft-Deleted Stages

Job stages with `active: false` are soft-deleted (see ADR 0003). Applications should not
be flagged as "stuck" in a deleted stage because the stage may no longer be relevant to
the pipeline.

**Decision: Exclude applications whose `current_stage.id` maps to an inactive stage.**
This requires a lookup against `get_job_stages(job_id)` to check the `active` flag.

### Rate Limit Considerations

The `needs_attention` tool is the most API-intensive tool in the suite. For a company with
1,000 active applications, detecting missing scorecards requires up to 1,000 calls to
`GET /applications/{id}/scorecards` (one per application).

**Mitigation strategies:**
1. **Filter first.** Only fetch scorecards for applications in interview stages. Use
   `current_stage.name` heuristics or the job stages endpoint to identify interview stages.
2. **Use `last_activity_after` parameter.** When fetching applications, pass
   `last_activity_after` as a cutoff (e.g., 30 days ago) to exclude old applications that
   are unlikely to be actionable.
3. **Batch by job.** If `job_id` is provided, scope all queries to that job.
4. **Accept eventual consistency.** The tool does not need real-time accuracy. Caching
   scorecard results for a few minutes is acceptable.

## Consequences

### Impact on `needs_attention` Tool Design

1. **Five detection loops.** The tool runs five independent detection passes (one per
   category), deduplicates overlapping results (Category 1 vs Category 4), computes
   priority scores, groups by candidate, and returns a sorted list.

2. **Configurable thresholds.** All thresholds are tool parameters with sensible defaults.
   No environment variables needed for threshold configuration.

3. **Priority scoring is composable.** Adding a fourth factor (e.g., role seniority) means
   adding one more term to the weighted sum -- no architectural changes.

4. **API call budget.** O(N) calls where N = active applications. A company with 1,000
   active apps will hit the rate limiter. The tool should report progress ("scanning 1,247
   active applications...") and back off gracefully.

5. **Response structure.** Grouped by candidate, sorted by priority, with category labels
   and human-readable detail strings. Presentable to the user without post-processing.

### Impact on `GreenhousePort`

No new port methods needed. `get_applications`, `get_scorecards`,
`get_scheduled_interviews`, `get_offers`, and `get_job_stages` cover everything.

One gap: `get_applications` should expose a `last_activity_after` filter to support the
rate limit mitigation strategy. The Greenhouse API already accepts this parameter -- we
just haven't wired it through our port yet.

**Recommended port change:**
```python
async def get_applications(
    self,
    *,
    job_id: int | None = None,
    status: str | None = None,
    created_after: str | None = None,
    last_activity_after: str | None = None,  # <-- add this
) -> list[dict[str, Any]]:
```

### Open Questions

1. **Should the tool accept a `max_results` parameter?** For companies with many stale items,
   returning all of them may overwhelm the agent's context window. A default limit (e.g., 25)
   with pagination would be more practical.

2. **Should we cache scorecard lookups?** If the tool is called repeatedly within a short
   window (e.g., an agent iterating through jobs), caching per-application scorecard data
   for 5 minutes would significantly reduce API calls.

3. **Should stage type detection be configurable?** The heuristic of matching stage names
   against patterns like `/interview/i` and `/offer/i` may not work for all companies. A
   configuration mapping stage names to stage types would be more robust but adds complexity.
