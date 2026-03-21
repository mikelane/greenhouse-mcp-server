# ADR 0008: Velocity Metrics Design

## Status

Accepted

## Context

The `hiring_velocity` tool answers "are we getting faster or slower at hiring?" — requiring
decisions on time bucketing, trend calculation, small-sample behavior, offer metrics, and
department-level aggregation.

## Decisions

### Time-series bucketing

**Context:** Recruiting operates on a weekly cadence (interview loops, debriefs, pipeline reviews).
**Decision:** Use weekly buckets (configurable via `bucket_size_days`, default 7).
**Consequence:** Monthly trends are still visible by setting `bucket_size_days=30`; weekly is the default because it surfaces week-over-week changes that monthly hides.

### Trend calculation

**Context:** Recruiters need a directional signal ("improving", "worsening", "stable"), not a statistical model.
**Decision:** Simple moving average over a configurable window (default 4 buckets). Compare the average of the most recent `trend_window` buckets to the preceding `trend_window` buckets. Classify as "improving" if recent > previous, "worsening" if recent < previous, "stable" if equal.
**Consequence:** SMA is transparent and interpretable — recruiters can verify the math. Linear regression would add complexity without proportional value for this domain.

### Small sample handling

**Context:** New jobs or short time ranges may have fewer than 5 applications, making trend calculations misleading.
**Decision:** When fewer than 5 applications exist in the time range, return all data but add `"insufficient_data": true` and a warning message. Never refuse to return data.
**Consequence:** Consumers always get a response; the flag lets agents decide whether to caveat the results or ask the user to expand the time range.

### Offer acceptance rate

**Context:** Unresolved offers have no outcome yet and would skew acceptance calculations.
**Decision:** Compute as `accepted / (accepted + rejected)` — ignore unresolved and deprecated offers. Report as a percentage.
**Consequence:** The denominator only includes decided offers, giving an accurate conversion rate. When no decided offers exist, report `acceptance_rate_pct` as `0.0` with a note.

### Department aggregation

**Context:** When no `job_id` is specified, users expect a department-level view.
**Decision:** When neither `job_id` nor `department_id` is specified, aggregate metrics by department using department info from job objects. Return both per-department breakdowns and an overall summary.
**Consequence:** Adds one `get_jobs` call to resolve department mappings. Jobs without departments are grouped under "Unassigned".
