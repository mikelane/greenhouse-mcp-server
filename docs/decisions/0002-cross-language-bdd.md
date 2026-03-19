# ADR 0002: Cross-Language BDD with cucumber-js and Python

## Status
Accepted

## Context
We want BDD step definitions in TypeScript to prevent importing Python internals, enforcing true black-box behavioral testing. We need to verify that cucumber-js can reliably start a Python process, communicate with it over HTTP, and assert on responses.

## Findings

### Process Management
- Python server started via `spawn("python3", [script, "--port", "0"])` — port 0 lets the OS assign a free port
- Server prints `PORT=<N>` to stdout on startup; the TypeScript World class parses this to discover the port
- SIGTERM for graceful shutdown, SIGKILL fallback after 3-second timeout
- Before/After hooks in Cucumber handle lifecycle automatically per scenario

### Port Management
- Port 0 eliminates race conditions entirely — no need to find/reserve a free port
- Server reports the actual bound port via stdout, World class reads it
- Health check polling (`waitForReady`) with 10 retries at 100ms intervals confirms the server is accepting connections before steps run

### Startup Timing
- Python stdlib `http.server` starts in ~50ms
- Health check polling adds 100-200ms worst case
- 5-second timeout catches genuine failures without slowing the happy path

### CI Requirements
- CI environment needs both Node.js and Python runtimes
- No native extensions required — pure Python server, pure TypeScript steps
- `npm ci` in `bdd/` plus `python3` available is sufficient

### Error Clarity
- Cucumber's native assertion formatting shows expected vs actual clearly
- Python stderr is forwarded to console for debugging server-side issues
- Startup failures produce specific error messages (timeout, early exit with code/signal)

### Prototype Structure
```
bdd/
├── package.json          # @cucumber/cucumber, ts-node, typescript
├── tsconfig.json
├── cucumber.cjs          # requireModule: ts-node/register, paths: ../features/
└── steps/
    ├── support/world.ts  # ServerWorld: process mgmt, HTTP client, Before/After hooks
    └── health.steps.ts   # Given/When/Then step definitions
features/
└── health.feature        # Gherkin scenarios
test_server.py            # Trivial Python HTTP server for validation
```

## Decision
Use cucumber-js with TypeScript step definitions. The prototype validates the pattern:
- Process management via Node's `child_process.spawn` is reliable
- Port discovery via stdout is race-condition-free
- Health check polling handles startup timing
- Clean shutdown via SIGTERM works correctly

## Consequences
- CI workflows need both Node.js and Python
- Feature files live in `features/` (shared), step definitions in `bdd/steps/` (TypeScript)
- The `bdd/` directory is a separate npm project with its own `package.json`
- No Python imports possible from TypeScript — black-box testing is structurally enforced
- Each scenario gets a fresh server instance (Before/After hooks), ensuring test isolation
