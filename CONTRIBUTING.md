# Contributing to greenhouse-mcp-server

Thank you for your interest in contributing!

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## Development Setup

    git clone https://github.com/mikelane/greenhouse-mcp-server
    cd greenhouse-mcp-server
    uv sync --dev

## Pull Request Workflow

1. File an issue first for non-trivial changes
2. Fork and branch: `git checkout -b issue-NNN-short-description`
3. Write tests before code (TDD)
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/)
5. Push and open a PR; fill in the template fully
6. One approval required to merge

## Commit Style

    type(scope): short imperative summary

    type: feat | fix | chore | docs | test | refactor | perf | ci

## Security Issues

**Do not open a public issue.** See [SECURITY.md](SECURITY.md).
