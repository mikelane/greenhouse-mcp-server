# greenhouse-mcp-server

An MCP server that gives AI agents workflow-oriented access to the [Greenhouse](https://www.greenhouse.io/) recruiting platform. Instead of mirroring the REST API endpoint-by-endpoint, each tool answers a question a recruiter or hiring manager actually asks.

[![Demo: Complete Walkthrough](https://img.youtube.com/vi/BfHNOBYvfR8/maxresdefault.jpg)](https://youtu.be/BfHNOBYvfR8)

> **2:26 narrated walkthrough** — all 5 tools, live quality gates, architecture overview

## Design Philosophy

Traditional API wrappers expose endpoints. This server exposes **workflows**. Each tool composes multiple Greenhouse Harvest API calls into a single response that answers a real question, saving the agent (and the user) from spending tokens coordinating across low-level operations.

A recruiter doesn't think "GET /applications, then GET /scorecards, then aggregate." They think "how's the pipeline looking?" -- and that's what the tool returns.

### Principles

1. **Tools answer questions, not mirror endpoints.** `pipeline_health` is not `GET /applications` -- it's "where are things stuck?"
2. **Compose aggressively.** Each tool is worth 3-5 raw API calls.
3. **Return structured, agent-friendly data.** Summaries first, details second. The agent never has to post-process.
4. **Read-only.** No write operations. Safe to use in any environment.

## Tools

| Tool | Question It Answers | Composes |
|------|-------------------|----------|
| `pipeline_health` | "Where are things stuck?" | Jobs + applications by stage + staleness metrics + bottleneck detection |
| `candidate_dossier` | "Tell me everything about this person." | Candidate + applications + scorecards + interviews + offers + activity feed |
| `needs_attention` | "What's falling through the cracks?" | Stale applications + missing scorecards + pending offers + inactive candidates |
| `hiring_velocity` | "Are we getting faster or slower?" | Weekly application buckets + SMA trend analysis + offer acceptance rates |
| `search_talent` | "Find candidates matching X." | Candidate search + name/tag/stage/source filtering + relevance ranking |

## Quick Start

```bash
# Clone and install
git clone https://github.com/mikelane/greenhouse-mcp-server.git
cd greenhouse-mcp-server
uv sync

# Set your Greenhouse Harvest API token
export GREENHOUSE_API_TOKEN="your-harvest-api-token"

# Run the server (stdio transport for local MCP clients)
uv run greenhouse-mcp
```

The server is ready when it begins listening on stdio. Connect an MCP client (see below) to start using the tools.

## MCP Client Configuration

### Claude Code

```bash
claude mcp add greenhouse-mcp -- uv run --directory /path/to/greenhouse-mcp-server greenhouse-mcp
```

### Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json` (macOS/Linux) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "greenhouse-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/greenhouse-mcp-server", "greenhouse-mcp"],
      "env": {
        "GREENHOUSE_API_TOKEN": "your-harvest-api-token"
      }
    }
  }
}
```

### SSE Transport (Remote / Shared Access)

```bash
uv run greenhouse-mcp --transport sse --port 8080
```

## Tool Reference

### `pipeline_health`

Analyzes hiring pipeline health with bottleneck detection. Groups active applications by stage, computes staleness, and flags stages where candidates are piling up.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `job_id` | `int \| None` | `None` | Specific job to analyze. Scans all open jobs when omitted. |
| `bottleneck_threshold` | `float` | `0.30` | Share of pipeline (0.0-1.0) to flag as bottleneck. |
| `staleness_days` | `int` | `7` | Days without activity before an application is considered stale. |

**Returns (single job):**

```
{
  "job_id": int,
  "job_name": str,
  "total_active": int,
  "stages": [
    {
      "stage_id": int,
      "stage_name": str,
      "count": int,
      "share": float,
      "avg_days_since_activity": float,
      "cold_count": int,
      "is_bottleneck": bool,
      "severity": "HIGH" | "MEDIUM" | "LOW" | null
    }
  ],
  "bottlenecks": [str]
}
```

**Returns (all jobs):**

```
{
  "jobs": [<single-job reports>],
  "jobs_needing_attention": [int]
}
```

**API calls composed:** `GET /jobs`, `GET /jobs/{id}/stages`, `GET /applications`

---

### `candidate_dossier`

Assembles a complete candidate picture from multiple API sources. Fetches the candidate record, then concurrently retrieves per-application scorecards, interviews, offers, and the activity feed.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `candidate_id` | `int` | *(required)* | The Greenhouse candidate ID. |

**Returns:**

```
{
  "summary": {
    "candidate_id": int,
    "name": str,
    "email": str | null,
    "phone": str | null,
    "tags": [str],
    "application_count": int,
    "active_application_count": int,
    "has_pending_offers": bool,
    "overall_status": "active" | "hired" | "converted" | "rejected" | "no_applications"
  },
  "applications": [
    {
      "application_id": int,
      "job_name": str,
      "status": str,
      "current_stage": str | null,
      "applied_at": str,
      "last_activity_at": str,
      "source": str | null,
      "recruiter": str | null,
      "scorecards": [...],
      "scheduled_interviews": [...],
      "offers": [...]
    }
  ],
  "activity_feed": {
    "recent_notes": [...],
    "recent_emails": [...],
    "total_notes": int,
    "total_emails": int,
    "total_activities": int
  }
}
```

**API calls composed:** `GET /candidates/{id}`, `GET /scorecards`, `GET /scheduled_interviews`, `GET /offers`, `GET /candidates/{id}/activity_feed`

---

### `needs_attention`

Surfaces items falling through the cracks. Detects four categories of issues and returns priority-scored action items sorted by urgency using a 3-factor composite: severity (40%) + days overdue (40%) + stage proximity to hire (20%).

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `job_id` | `int \| None` | `None` | Filter to a specific job. All jobs when omitted. |
| `days_stale` | `int` | `7` | Days before an application is considered stuck. |
| `scorecard_hours` | `int` | `48` | Hours after interview before a scorecard is overdue. |
| `offer_sent_days` | `int` | `3` | Days after sending before offer follow-up is needed. |
| `offer_draft_days` | `int` | `2` | Days after drafting before an unsent offer is overdue. |
| `no_activity_days` | `int` | `14` | Days of total inactivity before flagging. |

**Returns:**

```
{
  "total_items": int,
  "items": [
    {
      "type": "stuck_application" | "missing_scorecard" | "pending_offer" | "no_activity",
      "priority_score": float,
      "candidate_name": str,
      "candidate_id": int,
      "application_id": int,
      "job_name": str,
      "detail": str,
      "days_overdue": int,
      "suggested_action": str
    }
  ],
  "summary": {
    "missing_scorecards": int,
    "stuck_applications": int,
    "pending_offers": int,
    "no_activity": int
  }
}
```

**API calls composed:** `GET /applications`, `GET /candidates/{id}`, `GET /jobs/{id}/stages`, `GET /scorecards`, `GET /offers`

---

### `hiring_velocity`

Computes hiring velocity metrics over a time range. Buckets applications into weekly intervals, computes a simple moving average trend, and calculates offer acceptance rates. When no scope is specified, aggregates by department.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `job_id` | `int \| None` | `None` | Filter to a specific job. |
| `department_id` | `int \| None` | `None` | Filter to a specific department. |
| `days` | `int` | `90` | Number of days to look back. |
| `bucket_size_days` | `int` | `7` | Width of each time bucket in days. |
| `trend_window` | `int` | `4` | Number of buckets for the moving average window. |

**Returns (scoped to job or department):**

```
{
  "time_range": {"start": str, "end": str, "days": int},
  "total_applications": int,
  "weekly_buckets": [{"week_start": str, "count": int}],
  "trend": "improving" | "worsening" | "stable",
  "trend_details": {"recent_avg": float, "previous_avg": float, "change_pct": float},
  "offer_metrics": {
    "total_offers": int,
    "accepted": int,
    "rejected": int,
    "acceptance_rate_pct": float,
    "offer_scope": "organization-wide"
  },
  "insufficient_data": bool,
  "warning": str | null
}
```

**Returns (no scope -- department aggregation):**

```
{
  "departments": [{"department_id": int, "department_name": str, ...<metrics>}],
  "overall": {<metrics>}
}
```

**API calls composed:** `GET /applications`, `GET /jobs`, `GET /offers`

---

### `search_talent`

Finds candidates matching search criteria with ranked results. Fetches candidates using available API filters, applies client-side filtering for name/tag/stage/source matches, enriches with application data, and ranks by relevance score.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `query` | `str \| None` | `None` | Name substring to search for (case-insensitive). |
| `job_id` | `int \| None` | `None` | Filter to candidates with applications for this job. |
| `stage` | `str \| None` | `None` | Filter to candidates currently in this pipeline stage. |
| `source` | `str \| None` | `None` | Filter to candidates from this application source. |
| `tags` | `list[str] \| None` | `None` | Filter to candidates with all of these tags. |
| `created_after` | `str \| None` | `None` | ISO 8601 lower bound for candidate creation date. |
| `created_after_days` | `int \| None` | `None` | Convenience: look back N days instead of specifying a date. |

**Returns:**

```
{
  "query": str | null,
  "filters_applied": {<active filters>},
  "total_results": int,
  "results": [
    {
      "candidate_id": int,
      "name": str,
      "email": str,
      "tags": [str],
      "current_applications": [
        {
          "application_id": int,
          "job_name": str,
          "stage": str,
          "status": str,
          "source": str,
          "applied_at": str,
          "last_activity_at": str
        }
      ],
      "relevance_score": float
    }
  ],
  "message": str | null
}
```

**API calls composed:** `GET /candidates`, `GET /applications`

## Development

```bash
# Install all dependencies (including dev group)
uv sync

# Run tests (100% line + branch coverage required)
uv run pytest

# Mutation testing (100% -- no surviving mutants)
uv run pytest --gremlins --gremlin-workers auto --gremlin-cache

# Strict type checking
uv run mypy src

# Linting and formatting
uv run ruff check .
uv run ruff format --check .
```

All five gates must pass before merge. The test suite runs with `pytest-test-categories` in strict mode -- tests are small by default (no I/O, no network, no sleep, single-threaded) following Google's test size taxonomy.

## Architecture

This project uses **hexagonal architecture** (ports and adapters) with **dioxide** for dependency injection.

```
MCP Client  -->  FastMCP Server  -->  Tool Functions  -->  GreenhousePort (protocol)
                                                                  |
                                                          +-------+-------+
                                                          |               |
                                                  GreenhouseClient   FakeGreenhouseClient
                                                   (production)       (Profile.TEST)
```

- **Ports** (`ports.py`): `GreenhousePort` protocol defines the abstract interface. Tools depend on this, never on concrete classes.
- **Adapters**: `GreenhouseClient` implements the port for production (httpx, rate limiting, pagination). `FakeGreenhouseClient` implements it for tests and demos, registered via `dioxide.Profile.TEST`.
- **Container** (`container.py`): The dioxide `Container` resolves the correct adapter based on the active profile.
- **Tools** (`tools/`): Pure business logic. Each tool receives a `GreenhousePort` via dependency injection and orchestrates multiple API calls into a single structured response.

## Tech Stack

- **Python 3.14** -- bleeding edge, because this is a portfolio piece
- **[FastMCP](https://github.com/jlowin/fastmcp)** -- MCP server framework (stdio + SSE transports)
- **[httpx](https://www.python-httpx.org/)** -- async HTTP client for the Greenhouse Harvest API
- **[dioxide](https://github.com/mikelane/dioxide)** -- dependency injection container (port/adapter resolution by profile)
- **[Pydantic](https://docs.pydantic.dev/)** -- data validation and serialization
- **[pytest](https://docs.pytest.org/)** -- test framework with 100% coverage + mutation testing via pytest-gremlins
- **[mypy](https://mypy-lang.org/)** -- strict static type checking
- **[ruff](https://docs.astral.sh/ruff/)** -- linting and formatting (aggressive rule set)
- **[Cucumber.js](https://github.com/cucumber/cucumber-js)** + TypeScript -- BDD scenarios in a separate language to enforce black-box testing

## Greenhouse API

This server uses the [Greenhouse Harvest API](https://developers.greenhouse.io/harvest.html) (read-only operations only).

- **Auth**: Basic Auth over HTTPS (API token as username, blank password)
- **Rate limiting**: Per 10-second window, tracked via `X-RateLimit-Remaining` header
- **Pagination**: Link header pagination (RFC-5988), up to 500 results per page
- **Base URL**: `https://harvest.greenhouse.io/v1`

## License

MIT
