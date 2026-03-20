# Demo Narration: Milestone 1 Foundation

## Metadata

- Issues: #9, #28, #43, #51
- Recording date: 2026-03-20

---

## Segments

<!-- SECTION: scaffold -->

<!-- SEGMENT: intro -->
This is greenhouse mcp server, an MCP server that gives AI agents workflow-oriented access to the Greenhouse recruiting platform. Let me show you what we built for the foundation.

<!-- SEGMENT: uv_sync -->
First, the project scaffold. Python 3.14. We run uv sync, and 83 packages install, including dioxide for dependency injection, pytest gremlins for mutation testing, and pytest test categories for enforcing Google test sizes.

<!-- SEGMENT: ruff_check -->
Ruff with 30 rule categories enabled. Security, complexity, annotations, naming. All checks pass.

<!-- SEGMENT: mypy_strict -->
Mypy in strict mode. No any types, no untyped definitions, no escapes. Every function, every parameter, every return value is fully typed. Zero issues across all source files.

<!-- SEGMENT: pytest_run -->
Pytest with 100 percent line and branch coverage enforced as a gate. 123 tests, all classified as small, meaning no IO, no network, no sleep, single threaded. The test distribution report confirms it.

<!-- SECTION: bdd -->

<!-- SEGMENT: bdd_intro -->
Next, the cross-language BDD infrastructure. Step definitions are in TypeScript, not Python, so you physically cannot import production internals. Black box testing is structurally enforced.

<!-- SEGMENT: bdd_run -->
Cucumber JS starts a Python test server as a subprocess, discovers the port via standard out, polls the health endpoint until ready, then runs the Gherkin scenarios. Two scenarios, seven steps, all passing in about six seconds.

<!-- SECTION: client -->

<!-- SEGMENT: client_intro -->
The Greenhouse API client is the core of the system. It handles authentication, rate limiting, pagination, and retries behind a protocol interface for dependency injection.

<!-- SEGMENT: client_tests -->
123 tests cover auth, rate limiting, pagination, retries, and error handling. All through the public API, no mocking of internals. The client talks to httpx mock transports that simulate the real Greenhouse API.

<!-- SEGMENT: mutation -->
And the mutation testing score: 55 gremlins tested, 55 killed, zero survivors. 100 percent mutation coverage. Every boundary condition, every comparison operator, every backoff calculation is verified by at least one test that would fail if the code were mutated.

<!-- SECTION: server -->

<!-- SEGMENT: server_intro -->
Finally, the MCP server shell. FastMCP wired with dioxide dependency injection using the lifespan plus depends pattern from our architecture decision record.

<!-- SEGMENT: server_pattern -->
The lifespan context manager creates the dioxide container on startup. Depends factory functions resolve ports from that container. Tool handlers declare their dependencies as typed parameters, and FastMCP hides them from the MCP schema. Clean signatures, proper lifecycle, fully testable.

<!-- SEGMENT: closing -->
Thats the foundation. Every line covered, every mutant killed, every type checked. Next up: the recruiting workflow tools.
