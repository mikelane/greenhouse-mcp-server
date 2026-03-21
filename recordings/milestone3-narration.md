# Demo Narration: Milestone 3 Analytics and Search

## Metadata

- Issues: #27, #33
- Recording date: 2026-03-21

---

## Segments

<!-- SEGMENT: intro -->
Milestone 3 adds the final two tools to greenhouse mcp server. Analytics and search. The hiring velocity tool answers are we getting faster or slower at hiring. The search talent tool finds candidates matching any criteria.

<!-- SEGMENT: velocity_question -->
First: hiring velocity. Are we getting faster at hiring? The tool fetches 90 days of applications, groups them into weekly buckets, calculates a trend using a simple moving average, and reports offer acceptance rates.

<!-- SEGMENT: velocity_result -->
Thirteen weekly buckets. Trend is improving. Nine applications in the time range for Senior Software Engineer. Offer acceptance rate: 100 percent with one accepted and zero rejected. When the sample is small, the tool warns you.

<!-- SEGMENT: velocity_department -->
When no job is specified, velocity breaks down by department. Engineering has 12 applications. Product has 4. Both are trending upward. The overall summary aggregates everything.

<!-- SEGMENT: search_question -->
Next: search talent. Find me candidates matching a name, stage, source, or tag. The tool searches candidates, enriches them with application data, and ranks by relevance.

<!-- SEGMENT: search_name -->
Search for Maria. One result. Exact match on first name scores 50 points plus a recency bonus. Maria Chen has two applications: Senior Software Engineer where she was hired, and Product Manager at hiring manager screen. Tags include strong referral and senior.

<!-- SEGMENT: search_tags -->
Filter by tag: senior. Four candidates with that tag. Maria Chen, Aisha Patel, Elena Volkov, and Alex Tanaka. The tool handles all tag matching client side since the Greenhouse API does not support server side tag filtering.

<!-- SEGMENT: closing -->
Five tools. Five questions answered. Pipeline health, candidate dossier, needs attention, hiring velocity, and search talent. Every tool composes multiple API calls so the agent does not have to.
