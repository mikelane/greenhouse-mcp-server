# Demo Narration: greenhouse-mcp-server — Complete Walkthrough

## Metadata

- Issue: #30
- Recording date: 2026-03-21

---

## Segments

<!-- SEGMENT: intro -->
This is greenhouse mcp server. Five tools that answer the five questions recruiters actually ask. Each tool composes multiple Greenhouse API calls into one response. No token waste. No coordination overhead. Let me show you.

<!-- SEGMENT: pipeline -->
First question: where are things stuck? Pipeline health fetches job stages and active applications, groups candidates by stage, and flags bottlenecks. Technical Interview has 5 candidates, 71 percent of the pipeline. Severity: high. The recruiter knows exactly where to focus.

<!-- SEGMENT: candidate -->
Second: tell me everything about Maria Chen. Candidate dossier fetches her profile, applications, scorecards, offers, and activity feed in parallel. Hired as Senior Software Engineer. Strong yes on the technical. Also has an active Product Manager application. One call, complete picture.

<!-- SEGMENT: attention -->
Third: what needs my attention? Needs attention scans for stale applications, missing scorecards, and pending offers. Eleven action items, priority-scored. Missing scorecards at the top. Pending offers flagged. Every item has a suggested action.

<!-- SEGMENT: velocity -->
Fourth: are we getting faster or slower? Hiring velocity buckets 90 days of applications into weekly counts. Trend: improving. Recent average up 67 percent. Offer acceptance rate: 75 percent. When data is thin, the tool warns you instead of guessing.

<!-- SEGMENT: search -->
Fifth: find senior engineers. Search talent finds candidates by name, stage, source, or tags. Results ranked by relevance. Exact name matches score higher. Each result includes current applications and recent activity. Client-side filtering handles what the API cannot.

<!-- SEGMENT: quality -->
Quality gates. Ruff for linting and formatting. Mypy strict for type safety. Pytest with 100 percent line and branch coverage. Mutation testing with zero surviving mutants. BDD scenarios in TypeScript, separate from the Python implementation.

<!-- SEGMENT: architecture -->
Hexagonal architecture. Tools depend on protocols, never on concrete classes. The dioxide container wires adapters by profile. Production gets the real HTTP client. Tests get the fake. Same interface, swappable at the boundary.

<!-- SEGMENT: closing -->
Five questions. Five tools. Each one worth three to five API calls. The server encodes domain expertise so the agent does not have to. That is the design philosophy. Tools answer questions. They do not mirror endpoints.
