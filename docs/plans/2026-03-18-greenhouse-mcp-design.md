# Greenhouse MCP Server — Design Document

**Date:** 2026-03-18
**Status:** Approved

## Problem

Recruiters and hiring managers think in workflows: "where are things stuck?", "tell me about this candidate", "what needs my attention?" But Greenhouse's Harvest API is organized around resources — jobs, applications, candidates, scorecards. Bridging that gap today means the AI agent spends tokens coordinating 3-5 API calls per question, with pagination, rate limiting, and data assembly logic scattered across every conversation.

## Solution

An MCP server where each tool encodes a recruiting workflow. One tool call = one answer. The server handles Greenhouse API orchestration internally so the agent doesn't have to.

## Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Python version | 3.14 | Portfolio piece — demonstrates comfort with bleeding edge |
| MCP framework | FastMCP | Official Python MCP SDK, good ergonomics |
| HTTP client | httpx | Async-native, first-class HTTP/2, timeout/retry control |
| DI framework | dioxide | Strict Dependency Inversion Principle from day one. All dependencies flow through protocols, not concrete classes |
| Type checking | mypy --strict | No `Any` leakage, no untyped defs |
| Linting | ruff (aggressive rules) | Fast, replaces flake8+isort+pyupgrade+bandit |
| Test runner | pytest | With pytest-test-categories (strict mode, Google test sizes) and pytest-gremlins (mutation testing) |
| BDD framework | cucumber-js (TypeScript) | Separate language from production code prevents importing internals. True black-box behavioral testing |
| Coverage target | 100% line + branch + mutation | Non-negotiable for portfolio quality |

## Architecture

### Dependency Inversion

All tool implementations depend on **protocols** (abstract interfaces), never concrete classes. The dioxide container wires concrete adapters at startup.

```
Tool (depends on) → GreenhousePort (protocol)
                          ↑
              GreenhouseClient (implements)
```

This means:
- Tests inject fakes through the same protocol boundary
- No `unittest.mock.patch` on internal module paths
- Swapping the HTTP client doesn't touch any tool code

### Data Flow

```
Agent → MCP Protocol → FastMCP Server → Tool Function → GreenhousePort → httpx → Harvest API
                                              ↓
                                    Pydantic Models (validated)
                                              ↓
                                    Structured Response (summaries first, details second)
```

### Tool Design

Each tool:
1. Accepts a focused question as input (job_id, candidate_id, filters)
2. Orchestrates 3-5 Greenhouse API calls through the port
3. Assembles, aggregates, and summarizes
4. Returns structured data the agent can use directly

## Milestones and Epics

### Milestone 1: Foundation (v0.1)

**Goal:** Project builds, lints, type-checks. BDD infrastructure works end-to-end. Greenhouse client connects. MCP server starts.

**Epic 1: Project Scaffold & CI Pipeline**
- Spike: Validate Python 3.14 compatibility with all dependencies
- BDD: Project builds, all quality gates run green
- Implementation: pyproject.toml, ruff config, mypy config, pytest config, CI workflows, coverage ratchet
- Capstone: Narrated demo of CI pipeline

**Epic 2: Cross-Language BDD Infrastructure**
- Spike: Prove cucumber-js (TypeScript) can drive a Python process
- BDD: A trivial feature file runs step definitions against Python
- Implementation: TS project, cucumber config, step definition helpers
- Capstone: Narrated demo of Gherkin → TypeScript → Python round-trip

**Epic 3: Greenhouse API Client**
- Spike: Study Harvest API auth, rate-limit, pagination patterns
- BDD: Client authenticates, handles rate limits, paginates, retries transient failures
- Implementation: Async httpx client behind a dioxide-managed protocol
- Capstone: Narrated demo of client handling auth, rate limits, pagination

**Epic 4: MCP Server Shell**
- Spike: FastMCP + dioxide integration pattern
- BDD: Server starts via stdio, responds to list_tools
- Implementation: FastMCP server with dioxide container
- Capstone: Narrated demo of MCP server responding to protocol messages

### Milestone 2: Core Recruiting Tools (v0.2)

**Goal:** The three highest-impact tools are live.

**Epic 5: pipeline_health**
- Spike: Greenhouse stage model, bottleneck definition
- BDD: Given staged applications → counts, time-in-stage, bottleneck flags
- Implementation: Tool orchestration, stage analysis
- Capstone: Narrated demo

**Epic 6: candidate_dossier**
- Spike: Candidate/application/scorecard/offer/activity relationships
- BDD: Given candidate ID → complete picture
- Implementation: Data assembly across endpoints
- Capstone: Narrated demo

**Epic 7: needs_attention**
- Spike: Staleness thresholds per lifecycle stage
- BDD: Given overdue items → prioritized action list
- Implementation: Staleness detection, priority scoring
- Capstone: Narrated demo

### Milestone 3: Analytics & Search (v0.3)

**Goal:** Remaining tools complete the feature set.

**Epic 8: hiring_velocity**
- Spike: Velocity/trend metrics from application timestamps
- BDD: Given applications over time → velocity with trend
- Implementation: Time-series analysis
- Capstone: Narrated demo

**Epic 9: search_talent**
- Spike: Greenhouse search/filter capabilities
- BDD: Given filter criteria → ranked results
- Implementation: Search orchestration
- Capstone: Narrated demo

### Milestone 4: Release (v1.0)

**Goal:** Production-ready, documented, installable.

**Epic 10: Documentation & Release**
- BDD: README accurate, examples work, install succeeds
- Implementation: Docs, examples, release workflow
- Capstone: Full walkthrough of all 5 tools

## Quality Gates

Every PR must pass:
- ruff check + format
- mypy --strict
- pytest (100% line + branch coverage)
- pytest-gremlins (100% mutation coverage)
- pytest-test-categories (strict mode — small tests only unless tagged)
- cucumber-js BDD scenarios (for relevant features)
- Coverage ratchet (can only go up)

Every epic must pass:
- Adversarial QA review of Gherkin scenarios
- TDD git history validation
- Narrated capstone demo (`.mp4`, no exceptions)
