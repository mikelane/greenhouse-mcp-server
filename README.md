# greenhouse-mcp-server

An MCP server that gives AI agents workflow-oriented access to the [Greenhouse](https://www.greenhouse.io/) recruiting platform. Instead of mirroring the REST API endpoint-by-endpoint, each tool answers a question a recruiter or hiring manager actually asks.

## Design Philosophy

Traditional API wrappers expose endpoints. This server exposes **workflows**. Each tool composes multiple Greenhouse Harvest API calls into a single response that answers a real question, saving the agent (and the user) from spending tokens coordinating across low-level operations.

A recruiter doesn't think "GET /applications, then GET /scorecards, then aggregate." They think "how's the pipeline looking?" — and that's what the tool should return.

## Tools

| Tool | What It Answers | API Calls Composed |
|------|----------------|-------------------|
| `pipeline_health` | "Where are things stuck for this role?" | jobs + applications by stage + time-in-stage calculations + bottleneck detection |
| `candidate_dossier` | "Tell me everything about this person." | candidate + applications + scorecards + activity feed + current offers |
| `needs_attention` | "What's falling through the cracks?" | stale applications beyond SLA + missing scorecards + pending offers + unscheduled interviews |
| `hiring_velocity` | "Are we getting faster or slower?" | applications over time + stage duration trends + offer acceptance rates |
| `search_talent` | "Find candidates matching X." | candidate search + filtering by stage, source, date, tags + recent activity summary |

## Tech Stack

- **Python 3.12+**
- **FastMCP** — MCP server framework
- **httpx** — async HTTP client for Greenhouse API
- **uv** — package management

## Greenhouse API

This server uses the [Greenhouse Harvest API](https://developers.greenhouse.io/harvest.html) (read-only operations only).

- **Auth**: Basic Auth over HTTPS (API token as username, blank password)
- **Rate limiting**: Per 10-second window, tracked via `X-RateLimit-Remaining` header
- **Pagination**: Link header pagination (RFC-5988), up to 500 results per page

## Setup

```bash
git clone https://github.com/mikelane/greenhouse-mcp-server.git
cd greenhouse-mcp-server
uv sync
```

### Environment

```bash
export GREENHOUSE_API_TOKEN="your-harvest-api-token"
```

### Running

```bash
# stdio transport (for Claude Code / Claude Desktop)
uv run greenhouse-mcp

# SSE transport (for remote / shared access)
uv run greenhouse-mcp --transport sse --port 8080
```

## Development

```bash
# Tests
uv run pytest

# Type checking
uv run mypy src

# Linting
uv run ruff check .
uv run ruff format --check .
```

## Why This Exists

Most MCP servers wrap APIs 1:1. That works for simple services, but recruiting workflows span multiple resources. A single "how's the pipeline?" question touches jobs, applications, stages, and time calculations. Forcing an agent to coordinate those calls wastes tokens and introduces failure modes at every step.

This server encodes domain expertise into the tool boundary. The agent asks one question; the server does the orchestration.

## License

MIT