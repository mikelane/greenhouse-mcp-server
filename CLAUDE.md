# CLAUDE.md

## Project Overview

An MCP server that provides workflow-oriented access to the Greenhouse recruiting platform's Harvest API. Each tool composes multiple API calls to answer a recruiter/hiring manager question in a single response.

This project exists as both a useful open-source tool AND a proof-of-concept portfolio piece for an Anthropic application (Software Engineer, People Products). The code quality, design philosophy, and documentation should reflect that dual purpose.

## Architecture

### MCP Server
- Built with FastMCP (Python)
- stdio transport for local use, SSE for remote
- Each tool is a self-contained workflow that orchestrates multiple Greenhouse API calls

### Greenhouse Client
- Async HTTP client (httpx) wrapping the Harvest API
- Basic Auth (API token as username, blank password)
- Rate-limit-aware: reads `X-RateLimit-Remaining` headers, backs off when needed
- Pagination handled automatically (Link header traversal)

### Tool Design Principles
1. **Tools answer questions, not mirror endpoints.** `pipeline_health` is not `GET /applications` — it's "where are things stuck?"
2. **Compose aggressively.** Each tool should be worth 3-5 raw API calls.
3. **Return structured, agent-friendly data.** Summaries first, details second. The agent shouldn't have to post-process.
4. **Read-only.** No write operations. Safe to use in any environment.

## Tools

### `pipeline_health`
- Input: job_id (optional — all jobs if omitted)
- Composes: jobs + applications grouped by stage + time-in-stage averages + identifies bottleneck stages
- Returns: per-stage candidate counts, average time in stage, flagged bottlenecks

### `candidate_dossier`
- Input: candidate_id
- Composes: candidate details + all applications + scorecards + activity feed + current offers
- Returns: complete candidate picture in one response

### `needs_attention`
- Input: optional filters (job_id, days_stale threshold)
- Composes: applications exceeding time-in-stage thresholds + interviews missing scorecards + offers pending approval
- Returns: prioritized action items

### `hiring_velocity`
- Input: job_id or department, time range
- Composes: applications over time + stage duration trends + offer acceptance rates
- Returns: velocity metrics with trend direction

### `search_talent`
- Input: query string, optional filters (stage, source, date range, tags)
- Composes: candidate search + application status + recent activity
- Returns: ranked candidate list with context

## Build & Test Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing

# Type checking
uv run mypy src

# Linting
uv run ruff check .
uv run ruff format --check .

# Run the server (stdio)
uv run greenhouse-mcp

# Run the server (SSE)
uv run greenhouse-mcp --transport sse --port 8080
```

## Code Standards

- Python 3.14 (bleeding edge — portfolio piece)
- Type hints on all public functions (`mypy --strict`)
- ruff for linting and formatting (aggressive rule set)
- pytest for testing, with mock Greenhouse API responses (no live API calls in tests)
- Google test size taxonomy enforced by `pytest-test-categories` in strict mode (small by default: no I/O, no network, no sleep, single-threaded)
- TDD: write the test first, watch it fail, write minimal code to pass
- 100% line AND branch coverage — no exceptions
- `pytest-gremlins` mutation testing at 100% — no surviving mutants
- `dioxide` for dependency injection — strict adherence to the Dependency Inversion Principle from day one
- Tests only test **behaviors** via the public API — never test implementation details
- BDD with Gherkin (cucumber-js / TypeScript) — separate language to enforce black-box testing
- Narrated `.mp4` capstone demo for every epic (ElevenLabs TTS, no exceptions)

## File Structure (target)

```
greenhouse-mcp-server/
├── src/
│   └── greenhouse_mcp/
│       ├── __init__.py
│       ├── server.py          # FastMCP server + tool registration
│       ├── container.py       # dioxide DI container
│       ├── ports.py           # Abstract interfaces (protocols)
│       ├── client.py          # Async Greenhouse API client (adapter)
│       ├── models.py          # Pydantic models for API responses
│       └── tools/
│           ├── __init__.py
│           ├── pipeline.py    # pipeline_health tool
│           ├── candidate.py   # candidate_dossier tool
│           ├── attention.py   # needs_attention tool
│           ├── velocity.py    # hiring_velocity tool
│           └── search.py      # search_talent tool
├── tests/                     # Python unit tests (small, hermetic)
│   ├── conftest.py            # Shared fixtures, mock API responses
│   ├── test_client.py
│   ├── test_pipeline.py
│   ├── test_candidate.py
│   ├── test_attention.py
│   ├── test_velocity.py
│   └── test_search.py
├── features/                  # Gherkin feature files
│   ├── pipeline_health.feature
│   ├── candidate_dossier.feature
│   ├── needs_attention.feature
│   ├── hiring_velocity.feature
│   └── search_talent.feature
├── bdd/                       # TypeScript cucumber step definitions
│   ├── package.json
│   ├── tsconfig.json
│   ├── cucumber.js
│   └── steps/
│       ├── support/
│       │   └── world.ts       # Cucumber World (HTTP client to Python server)
│       ├── pipeline.steps.ts
│       ├── candidate.steps.ts
│       ├── attention.steps.ts
│       ├── velocity.steps.ts
│       └── search.steps.ts
├── docs/
│   ├── decisions/             # ADRs from spikes and implementation
│   └── plans/                 # Design documents
├── scripts/                   # CI/quality gate scripts
├── pyproject.toml
├── CLAUDE.md
├── README.md
└── LICENSE
```

## Greenhouse Harvest API Reference

- Docs: https://developers.greenhouse.io/harvest.html
- Auth: Basic Auth (token as username, empty password)
- Base URL: https://harvest.greenhouse.io/v1
- Rate limit: per 10-second window, check X-RateLimit-Remaining header
- Pagination: Link header (RFC-5988), per_page up to 500

### Key Endpoints Used

| Endpoint | Used By |
|----------|---------|
| GET /jobs | pipeline_health, hiring_velocity |
| GET /jobs/{id}/stages | pipeline_health |
| GET /applications | pipeline_health, needs_attention, hiring_velocity |
| GET /candidates | search_talent |
| GET /candidates/{id} | candidate_dossier |
| GET /scorecards | candidate_dossier, needs_attention |
| GET /scheduled_interviews | needs_attention |
| GET /offers | candidate_dossier, needs_attention |
| GET /candidates/{id}/activity_feed | candidate_dossier |