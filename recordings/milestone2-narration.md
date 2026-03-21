# Demo Narration: Milestone 2 Core Recruiting Tools

## Metadata

- Issues: #18, #41, #53
- Recording date: 2026-03-21

---

## Segments

<!-- SECTION: intro -->

<!-- SEGMENT: intro -->
Milestone 2 delivers three recruiting workflow tools. Each one answers a question a recruiter actually asks, composing multiple Greenhouse API calls into a single response.

<!-- SECTION: pipeline -->

<!-- SEGMENT: pipeline_intro -->
First, pipeline health. This tool answers where are things stuck for a given role. It groups applications by stage, calculates days since last activity, and flags bottleneck stages where candidates are piling up.

<!-- SEGMENT: pipeline_tests -->
44 tests cover the bottleneck detection algorithm. A stage is flagged when its share of the pipeline exceeds 30 percent. Severity is high when more than half those candidates have gone cold. Every boundary condition and arithmetic operator is verified by mutation testing.

<!-- SECTION: candidate -->

<!-- SEGMENT: candidate_intro -->
Next, candidate dossier. This answers tell me everything about this person. It fetches the candidate profile, then concurrently gathers scorecards, interviews, and offers for every application, plus the full activity feed. Summary first, details second.

<!-- SEGMENT: candidate_tests -->
34 tests verify the concurrent assembly logic. The fake client injects canned data through the same protocol interface the production client uses. No mocking of internals, no patching of import paths.

<!-- SECTION: attention -->

<!-- SEGMENT: attention_intro -->
Finally, needs attention. This answers what is falling through the cracks. It scans for stale applications, missing scorecards, and pending offers, then ranks them by a three factor priority score: category severity, days overdue, and stage proximity to hire.

<!-- SEGMENT: attention_tests -->
63 tests cover four staleness categories and the priority scoring formula. Every comparison operator, every arithmetic calculation, every threshold boundary is verified. Zero surviving mutants across all three tools.

<!-- SEGMENT: closing -->
Three tools, 141 tests, 100 percent mutation coverage. The foundation from Milestone 1 made this possible: dependency injection, protocol boundaries, and injectable fakes. Next up: velocity metrics and talent search.
