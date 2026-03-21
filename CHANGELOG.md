# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] - 2026-03-21

### Added
- `hiring_velocity` tool -- weekly application bucketing, SMA trend analysis, offer acceptance rates, department aggregation when no scope is specified
- `search_talent` tool -- ranked candidate search with client-side name/tag/stage/source filtering and relevance scoring
- ADR 0008: Velocity metrics design (bucket sizing, trend algorithm, insufficient data handling)
- ADR 0009: Greenhouse search API capabilities and client-side filtering strategy
- Comprehensive README with full tool reference, MCP client configuration, and architecture overview
- CHANGELOG covering all releases
- Gherkin scenarios for documentation accuracy
- Version bump to 0.3.0
- Capstone demos for Milestone 3

## [0.2.0] - 2026-03-20

### Added
- `pipeline_health` tool -- per-stage candidate counts, staleness metrics, bottleneck detection with HIGH/MEDIUM/LOW severity
- `candidate_dossier` tool -- concurrent assembly of candidate profile, applications, scorecards, interviews, offers, and activity feed
- `needs_attention` tool -- priority-scored action items for stale applications, missing scorecards, pending offers, and inactive candidates
- Realistic test double (`FakeGreenhouseClient`) registered as a dioxide adapter for `Profile.TEST`
- Capstone demos for Milestones 1 and 2

## [0.1.0] - 2026-03-19

### Added
- Project scaffold with FastMCP server and dioxide DI container
- `GreenhousePort` protocol (hexagonal architecture port)
- Async Greenhouse Harvest API client with rate limiting, automatic pagination, and retry logic
- Exception hierarchy (`AuthenticationError`, `NotFoundError`, `RateLimitError`, `GreenhouseAPIError`)
- BDD infrastructure with Cucumber.js and TypeScript step definitions
- Full quality gate pipeline: ruff (lint + format), mypy --strict, pytest with 100% line + branch coverage, pytest-gremlins mutation testing
