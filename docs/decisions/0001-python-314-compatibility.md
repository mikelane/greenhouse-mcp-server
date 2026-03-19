# ADR 0001: Python 3.14 Compatibility

## Status
Accepted

## Context
This project targets Python 3.14 as a portfolio piece for an Anthropic application. We need to verify all required dependencies install and function correctly before committing to this version. The spike was time-boxed to answer one question: can Python 3.14 work with all required dependencies?

## Findings

All dependencies were tested on Python 3.14.3 (CPython, Clang 17.0.0, macOS ARM64).

| Package | Version Tested | Install | Import | CLI/Runtime | Notes |
|---------|---------------|---------|--------|-------------|-------|
| fastmcp | 3.1.1 | OK | OK | OK (server instantiation, tool registration) | No issues |
| httpx | 0.28.1 | OK | OK | OK | No issues |
| pydantic | 2.12.5 | OK | OK | OK (model creation, validation) | pydantic-core 2.41.5 compiled wheel available |
| dioxide | 2.0.1 | OK | OK | OK | Minor: `__version__` reports 1.0.1 (metadata mismatch in package, not a 3.14 issue) |
| pytest | 9.0.2 | OK | OK | OK (test collection, execution) | No issues |
| pytest-gremlins | 1.5.1 | OK | OK | OK (plugin loaded by pytest) | No issues |
| pytest-test-categories | 1.2.1 | OK | OK | OK (plugin loaded, size markers functional) | No issues |
| mypy | 1.19.1 | OK | OK | OK (type-checked Python 3.14 code, `--python-version 3.14` flag works) | Compiled: yes |
| ruff | 0.15.6 | OK | OK | OK (lint + format on Python 3.14 code) | No issues |

### Python 3.13 Comparison

For completeness, Python 3.13.12 was also tested. All packages resolve to identical versions and install without issues. There is no functional difference between 3.13 and 3.14 for this dependency set.

### Key Observations

1. **No build failures.** All packages with C extensions (pydantic-core, cryptography, cffi, caio, rpds-py, watchfiles) had precompiled wheels available for Python 3.14 on macOS ARM64.

2. **No version constraint issues.** Every package in the dependency tree declares compatibility with Python 3.14 (or has no upper bound that excludes it).

3. **Tooling fully supports 3.14.** mypy accepts `--python-version 3.14`, ruff handles 3.14 syntax, and pytest runs without compatibility warnings.

4. **PEP 649 (deferred evaluation of annotations)** is active in 3.14. Forward references in type annotations work without `from __future__ import annotations`. This is a benefit, not a risk -- it simplifies annotation patterns.

5. **Total dependency tree:** 86 packages resolved (74 in default group + 6 in test group + 6 in dev group). All installed in under 500ms, indicating mature wheel availability.

## Decision

Use Python 3.14 as the project's target Python version with `requires-python = ">=3.14"`.

Rationale:
- All dependencies work without workarounds
- Python 3.14 is the latest stable release and demonstrates currency as a portfolio piece
- PEP 649 (deferred annotations) aligns well with Pydantic's model system
- No fallback to 3.13 is needed -- there are zero compatibility issues to work around

## Consequences

- `pyproject.toml` will specify `requires-python = ">=3.14"`
- CI will test on Python 3.14 only (no matrix needed for a portfolio project)
- Contributors will need Python 3.14 installed (available via `uv python install 3.14`, Homebrew, or system package managers)
- If any dependency later drops 3.14 support (unlikely given it is current), we can pin that dependency's version
