# ADR 0005: Pipeline Bottleneck Definition

## Status

Accepted

## Context

The `pipeline_health` tool needs to answer "where are things stuck?" for a given job's hiring
pipeline. This requires three capabilities:

1. Grouping active applications by their current stage
2. Calculating how long each application has been in its current stage
3. Identifying which stages are bottlenecks

Before designing the tool, we need precise answers about what data the Greenhouse Harvest API
provides and what it does not -- because the naive assumption ("there's a `stage_entered_at`
timestamp") turns out to be wrong.

### What the API gives us

**Job stages** (`GET /v1/jobs/{id}/stages`):

| Field | Type | Purpose |
|-------|------|---------|
| `id` | integer | Unique stage identifier |
| `name` | string | Human-readable name (e.g., "Phone Screen", "Onsite") |
| `priority` | integer | Ordering key (lowest first) |
| `active` | boolean | `false` = soft-deleted stage |
| `job_id` | integer | Parent job |
| `interviews[]` | array | Interview steps configured for this stage |

Stages are job-specific. Two jobs may both have a stage called "Phone Screen" but they are
distinct stage objects with different IDs. The `priority` field defines display order.

**Applications** (`GET /v1/applications`):

| Field | Type | Purpose |
|-------|------|---------|
| `id` | integer | Unique application identifier |
| `current_stage` | `{id, name}` | Where the application is RIGHT NOW |
| `applied_at` | ISO 8601 | When the candidate applied |
| `last_activity_at` | ISO 8601 | When ANY activity last occurred |
| `rejected_at` | ISO 8601 or null | When rejected (if applicable) |
| `status` | enum | `active`, `rejected`, `hired`, `converted` |
| `jobs[{id, name}]` | array | Associated job(s) |

The critical gap: **there is no `stage_entered_at` or `moved_to_stage_at` field.** The API
tells us where an application is, but not when it arrived there.

**Activity feed** (`GET /v1/candidates/{id}/activity_feed`):

Returns `notes[]`, `emails[]`, and `activities[]` for a candidate. The `activities` array
contains system-generated events (including stage transitions) with `created_at` timestamps.
However:

- It is per-candidate, not per-application (a candidate may have multiple applications)
- It is not paginated -- returns ALL activity for the candidate's lifetime
- Activity entries do not have structured `from_stage` / `to_stage` fields; the stage
  transition information is embedded in the `body` text (human-readable, not machine-parseable)
- Fetching this for every application in a pipeline would burn through the rate limit fast

## Time-in-Stage Calculation

### Options evaluated

**Option A: Parse activity feed for stage transitions.**
For each active application, fetch the candidate's activity feed, find the most recent stage
transition activity, and extract the timestamp.

- Pro: Most accurate -- gives the actual moment the candidate moved into the stage.
- Con: Requires one API call per candidate (not per application -- slightly better if candidates
  have one application, but the activity feed is unbounded in size). A pipeline with 200 active
  applications means 200 additional API calls. At Greenhouse's rate limit (~50 per 10-second
  window), that is 40+ seconds of additional latency just for this one computation. The stage
  transition body text is not structured -- parsing "Candidate was moved from Phone Screen to
  Onsite" requires brittle string matching that breaks if Greenhouse changes the wording.
- **Verdict: Rejected.** Too expensive, too fragile.

**Option B: Use `last_activity_at` as a proxy.**
Treat `last_activity_at` as an approximation of "last time something meaningful happened."

- Pro: Zero additional API calls -- the field is already on the application object.
- Con: `last_activity_at` updates for ANY activity (notes, emails, scorecard submissions,
  interview scheduling, stage moves). A recruiter adding a note resets the clock. This would
  undercount time-in-stage for applications that have recent non-stage-transition activity.
- **Verdict: Rejected as the primary signal.** It answers "when was this application last
  touched?" but not "how long has it been in this stage?" Those are different questions.
  However, it is useful as a secondary staleness indicator (see below).

**Option C: Use `applied_at` plus stage ordering to estimate.**
If we know the stage order (via `priority`) and the application date, we could estimate
that earlier stages were traversed quickly and attribute remaining time to the current stage.

- Pro: No additional API calls.
- Con: Pure speculation. A candidate who applied 30 days ago and is in stage 3 of 5 could have
  spent 25 days in stage 1 and 2 days in stages 2-3, or 5 days spread evenly. There is no way
  to distinguish these cases from the available data.
- **Verdict: Rejected.** Guessing is worse than admitting uncertainty.

**Option D (Chosen): Snapshot-based time-in-stage with `last_activity_at` as a staleness signal.**

Accept the API's limitation and design around it:

1. **Snapshot approach**: Each call to `pipeline_health` captures the current state. The tool
   reports per-stage candidate counts and identifies bottlenecks by **count distribution** (where
   candidates are piling up), not by duration (how long they have been there).

2. **Staleness signal**: Use `last_activity_at` to flag applications that have not been touched
   recently. An application in "Phone Screen" with `last_activity_at` 14 days ago is likely
   stuck, even though we cannot prove it has been in Phone Screen for all 14 days. The staleness
   threshold is caller-configurable (default: 7 days).

3. **Duration as a bonus, not a guarantee**: Report `days_since_last_activity` per application
   as a secondary metric. Label it clearly as "days since last activity" not "days in stage" to
   avoid misleading the consumer.

This approach is honest about what the data supports. It avoids presenting fabricated precision
(fake "time in stage" numbers) while still surfacing actionable information (where candidates
are piling up and which ones have gone cold).

### Why this is the right trade-off for an MCP tool

The consumer of `pipeline_health` is an AI agent, not a BI dashboard. The agent needs to answer
questions like "what should I look at?" and "where should I focus?" -- not "what is the exact
p95 stage duration?" Count-based bottleneck detection plus staleness flags give the agent
enough signal to prioritize. If exact duration data is needed, the agent can call
`candidate_dossier` for specific candidates to drill into their activity timeline.

## Bottleneck Definition

### Options evaluated

**Option A: Average time exceeds 2x the median across all stages.**
Requires accurate time-in-stage data, which we do not have (see above).
**Verdict: Rejected** -- depends on data we cannot reliably compute.

**Option B: Stage with the highest absolute time-in-stage.**
Same dependency on time-in-stage data.
**Verdict: Rejected** -- same reason as Option A.

**Option C (Chosen): Count-based with configurable threshold.**
A stage is a bottleneck when it holds a disproportionate share of active applications.

Algorithm:

```
for each active stage:
    stage_share = stage_count / total_active_count

    if stage_share >= bottleneck_threshold:
        mark as bottleneck
```

Default `bottleneck_threshold`: **0.30** (30% of active pipeline in one stage).

Rationale for 30%: In a healthy pipeline with 4-6 stages, each stage should hold roughly
15-25% of active candidates. If one stage holds 30%+, candidates are accumulating there
faster than they are being moved forward. This is a strong signal that something is slowing
down at that stage -- interviews not being scheduled, feedback not being submitted, or a
capacity constraint.

The threshold is caller-configurable because "disproportionate" depends on context:
- A 3-stage pipeline might use 0.40 (40%)
- A 10-stage pipeline might use 0.20 (20%)
- A user who wants aggressive alerting might use 0.25

### Staleness-augmented bottleneck scoring

A stage with 30% of candidates where everyone was active yesterday is less concerning than
a stage with 30% of candidates where half have not been touched in two weeks. The tool
augments count-based bottleneck detection with a staleness dimension:

```
stale_fraction = count_of_stale_apps_in_stage / stage_count

bottleneck_severity:
    HIGH   = stage_share >= threshold AND stale_fraction >= 0.50
    MEDIUM = stage_share >= threshold AND stale_fraction < 0.50
    LOW    = stage_share < threshold AND stale_fraction >= 0.50
```

Where "stale" means `days_since_last_activity >= staleness_days` (default: 7).

- **HIGH**: Lots of candidates AND most of them are going cold. Immediate action needed.
- **MEDIUM**: Lots of candidates but they are being actively worked. May be capacity-constrained
  but not neglected.
- **LOW**: Few candidates but they have gone cold. Individual follow-up needed, not a systemic
  bottleneck.

## Edge Cases

### Jobs with no applications

Return an empty stage breakdown with zero counts. No stages are flagged as bottlenecks
(division by zero is avoided by checking `total_active_count > 0` before computing shares).
The tool returns a clear message: "No active applications for this job."

### Applications with no current_stage

Applications with `status` of `rejected`, `hired`, or `converted` may have `current_stage`
set to `null`. These are excluded from the active pipeline breakdown since they have exited
the funnel. They are counted separately in summary stats:

```
{
    "active": 45,
    "rejected": 12,
    "hired": 3,
    "total_processed": 60
}
```

This gives the agent context on pipeline throughput without polluting the bottleneck analysis.

### Soft-deleted stages (active: false)

Stages with `active: false` are filtered out of the stage list by default. However, an
application may still reference a deleted stage in its `current_stage` field (Greenhouse
soft-deletes stages but does not retroactively update applications). These applications are
grouped under a synthetic "Unknown/Deleted Stage" entry in the breakdown.

### Multiple jobs aggregation (no job_id filter)

When `job_id` is omitted, the tool aggregates across all open jobs. Each job gets its own
stage breakdown (stages are job-specific -- "Phone Screen" on Job A is a different stage
than "Phone Screen" on Job B). Bottleneck detection runs independently per job. The response
includes a top-level summary that identifies the jobs with the most severe bottlenecks.

```
{
    "jobs": [
        {"job_id": 101, "job_name": "SWE", "stages": [...], "bottlenecks": [...]},
        {"job_id": 102, "job_name": "PM", "stages": [...], "bottlenecks": [...]}
    ],
    "jobs_needing_attention": [101]  // jobs with HIGH severity bottlenecks
}
```

### Prospect applications

Applications where `prospect: true` are candidates sourced proactively, not applicants.
They follow a different lifecycle (prospect pools/stages vs. job stages). The `pipeline_health`
tool excludes prospects from the active pipeline count since they are not in the job's stage
funnel. They are counted separately if present.

## Consequences

### Impact on pipeline_health tool design

1. **Two API calls per job**: `get_job_stages(job_id)` + `get_applications(job_id=..., status="active")`.
   No activity feed calls needed. This keeps response time under 2 seconds for most pipelines.

2. **Stage ordering via priority**: Stages are sorted by `priority` (ascending) for display.
   This gives the agent a left-to-right funnel view.

3. **Configurable parameters**: The tool accepts `bottleneck_threshold` (default 0.30) and
   `staleness_days` (default 7) as optional inputs. The MCP schema exposes these with
   descriptions so the agent can adjust them.

4. **Response structure**: Summary first (total counts, bottleneck list), then per-stage
   detail. The agent can stop reading after the summary if the pipeline is healthy.

5. **No `GreenhousePort` changes needed**: The existing `get_job_stages()` and
   `get_applications()` methods provide all required data. No new API methods are needed.

### Future improvements

If Greenhouse ever adds a `stage_entered_at` field or a stage transition history endpoint,
the tool can switch from count-based to duration-based bottleneck detection without changing
its interface. The `bottleneck_severity` enum and the tool's input/output schema remain stable
either way.

An alternative future approach: use webhooks (if the deployment environment supports them) to
build a local stage transition log. This would enable accurate time-in-stage calculations
without polling the activity feed. This is out of scope for the MCP server (read-only, no
state) but could be a companion service.
