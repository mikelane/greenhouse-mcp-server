# ADR 0004: FastMCP + DI Integration Pattern

## Status

Accepted

## Context

We need a clean pattern for wiring dependency injection into FastMCP tool handlers so that tools depend on protocols (ports), not concrete classes (adapters). This enables:

- Swapping implementations by environment (production vs test) without changing tool code
- Testing tools with in-memory fakes instead of mocks or live API calls
- Clean hexagonal architecture where the Greenhouse API client is a port

### Technology Versions Evaluated

- **FastMCP 3.1.1** (latest as of March 2026)
- **dioxide 2.0.1** (latest as of March 2026)

### How FastMCP Handles Dependencies

FastMCP provides two complementary mechanisms:

1. **Lifespan context manager**: An `@asynccontextmanager` passed to `FastMCP(lifespan=...)` that initializes shared resources at startup and cleans them up at shutdown. Tools access the yielded value via `ctx.request_context.lifespan_context`.

2. **`Depends()` system**: Inspired by FastAPI, tools declare `param: Type = Depends(factory_fn)` and FastMCP resolves them automatically. Dependency parameters are excluded from the MCP schema. Dependencies are cached per-request and support nesting, async functions, and async context managers for cleanup.

### How Dioxide Works

Dioxide is a Rust-backed DI framework for Python that enforces hexagonal architecture:

- **Ports**: Python `Protocol` classes defining interfaces
- **Adapters**: Concrete implementations registered with `@adapter.for_(Port, profile=Profile.PRODUCTION)`
- **Services**: Business logic decorated with `@service`, dependencies auto-injected via constructor type hints
- **Container**: `Container(profile=Profile.PRODUCTION)` resolves ports to their adapters
- **Profiles**: `Profile.PRODUCTION`, `Profile.TEST` (and custom) swap implementations without code changes
- **Scoped containers**: `container.create_scope()` returns an async context manager for request-scoped instances

## Options Considered

### Option 1: Global Container

Module-level container, tools call `container.resolve()` directly.

```python
from dioxide import Container, Profile

container = Container(profile=Profile.PRODUCTION)

@mcp.tool
async def candidate_dossier(candidate_id: int) -> dict:
    client = container.resolve(GreenhouseClientPort)
    return await client.get_candidate(candidate_id)
```

**Pros:**
- Simplest possible pattern, zero ceremony
- Works immediately, no FastMCP integration needed

**Cons:**
- No lifecycle management (container never cleaned up)
- Hard to swap profiles for testing -- must mutate module-level state
- Tools have a hidden dependency on the global container
- Cannot use dioxide's `Scope.REQUEST` since there is no scope boundary

### Option 2: Lifespan Context Only

Container created in lifespan, tools access it via `ctx.request_context.lifespan_context`.

```python
@asynccontextmanager
async def lifespan(mcp: FastMCP):
    container = Container(profile=Profile.PRODUCTION)
    yield {"container": container}

@mcp.tool
async def candidate_dossier(candidate_id: int, ctx: Context) -> dict:
    container = ctx.request_context.lifespan_context["container"]
    client = container.resolve(GreenhouseClientPort)
    return await client.get_candidate(candidate_id)
```

**Pros:**
- Container has proper lifecycle (created on startup, available for cleanup on shutdown)
- Standard FastMCP pattern, well-documented

**Cons:**
- Every tool must accept `ctx: Context` and dig into `lifespan_context["container"]` -- boilerplate
- Dict-based access is not type-safe (`["container"]` could be misspelled)
- Tool signatures are polluted with infrastructure concerns

### Option 3: Closure Injection (Server Factory)

A factory function creates the container and server. Tool functions are closures that capture resolved dependencies.

```python
def create_server(profile: Profile = Profile.PRODUCTION) -> FastMCP:
    container = Container(profile=profile)
    greeter = container.resolve(GreeterPort)

    mcp = FastMCP(name="MyServer")

    @mcp.tool
    async def greet_person(name: str) -> str:
        return greeter.greet(name)  # captured from enclosing scope

    return mcp
```

**Pros:**
- Tool signatures are perfectly clean -- no Context, no Depends
- Easy to test: call `create_server(Profile.TEST)` and get a fully-wired test server
- Dependencies resolved once at startup (singleton-like)

**Cons:**
- All tools must be defined inside the factory function -- poor code organization for 5+ tools
- Cannot use dioxide's `Scope.REQUEST` since dependencies are resolved at startup
- Adding a new tool requires modifying the factory function
- Tool modules cannot be split into separate files easily

### Option 4: Lifespan + Depends() (Recommended)

Container created in lifespan for lifecycle management. `Depends()` factory functions resolve from the container. Tools declare dependencies as typed parameters.

```python
@asynccontextmanager
async def lifespan(mcp: FastMCP):
    container = Container(profile=Profile.PRODUCTION)
    yield {"container": container}

def get_greenhouse_client() -> GreenhouseClientPort:
    ctx = get_context()
    container = ctx.request_context.lifespan_context["container"]
    return container.resolve(GreenhouseClientPort)

@mcp.tool
async def candidate_dossier(
    candidate_id: int,
    client: GreenhouseClientPort = Depends(get_greenhouse_client),
) -> dict:
    return await client.get_candidate(candidate_id)
```

**Pros:**
- Tool signatures are clean and typed -- `client: GreenhouseClientPort`
- Container has proper lifecycle management via lifespan
- `Depends()` parameters are automatically excluded from MCP schema
- Per-request caching: if multiple dependencies share a sub-dependency, it is resolved once
- Factory functions can be shared across tool modules
- Supports async context manager factories for cleanup (e.g., scoped containers)
- Testable: swap the lifespan to yield a test container

**Cons:**
- Slightly more ceremony than global container (factory functions needed)
- `get_context()` inside factory functions is implicit (uses contextvars internally)
- Dict-based access to lifespan context is not fully type-safe (mitigated by centralizing in one factory)

## Decision

**Option 4: Lifespan + Depends()** is the chosen pattern.

It combines the best of both FastMCP mechanisms: lifespan for container lifecycle, Depends() for clean injection. It keeps tool signatures focused on their domain (ports, not infrastructure) while maintaining proper resource management.

### Concrete Architecture

```
server.py (lifespan + server creation)
    |
    +-- creates Container(profile) in lifespan
    |
dependencies.py (Depends factories)
    |
    +-- get_greenhouse_client() -> GreenhouseClientPort
    +-- get_container() -> Container  (internal helper)
    |
tools/
    +-- pipeline.py     uses Depends(get_greenhouse_client)
    +-- candidate.py    uses Depends(get_greenhouse_client)
    +-- attention.py    uses Depends(get_greenhouse_client)
    +-- velocity.py     uses Depends(get_greenhouse_client)
    +-- search.py       uses Depends(get_greenhouse_client)
```

### Profile Selection

The container profile is determined by environment variable, following 12-Factor:

```python
import os
from dioxide import Container, Profile

def get_profile() -> str:
    return os.environ.get("GREENHOUSE_MCP_PROFILE", Profile.PRODUCTION)
```

### Request Scoping (Future)

If we need request-scoped dependencies (e.g., per-request audit context), dioxide's `create_scope()` returns an async context manager that integrates naturally with FastMCP's `Depends()`:

```python
@asynccontextmanager
async def get_scoped_container():
    ctx = get_context()
    container = ctx.request_context.lifespan_context["container"]
    async with container.create_scope() as scoped:
        yield scoped
```

## Example

Complete minimal working example of the chosen pattern:

```python
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Protocol

from dioxide import Container, Profile, adapter
from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.server.dependencies import get_context


# --- Port ---

class GreenhouseClientPort(Protocol):
    async def get_candidate(self, candidate_id: int) -> dict: ...
    async def list_applications(self, job_id: int | None = None) -> list[dict]: ...


# --- Production Adapter ---

@adapter.for_(GreenhouseClientPort, profile=Profile.PRODUCTION)
class HttpGreenhouseClient:
    async def get_candidate(self, candidate_id: int) -> dict:
        # Real httpx call to Greenhouse Harvest API
        ...

    async def list_applications(self, job_id: int | None = None) -> list[dict]:
        # Real httpx call with pagination
        ...


# --- Test Adapter ---

@adapter.for_(GreenhouseClientPort, profile=Profile.TEST)
class FakeGreenhouseClient:
    def __init__(self) -> None:
        self.candidates: dict[int, dict] = {}
        self.applications: list[dict] = []

    async def get_candidate(self, candidate_id: int) -> dict:
        return self.candidates.get(candidate_id, {"id": candidate_id, "name": "Unknown"})

    async def list_applications(self, job_id: int | None = None) -> list[dict]:
        if job_id is None:
            return self.applications
        return [a for a in self.applications if a.get("job_id") == job_id]


# --- Lifespan ---

@asynccontextmanager
async def lifespan(mcp: FastMCP):
    profile = os.environ.get("GREENHOUSE_MCP_PROFILE", Profile.PRODUCTION)
    container = Container(profile=profile)
    yield {"container": container}


# --- Dependency Factories ---

def get_greenhouse_client() -> GreenhouseClientPort:
    ctx = get_context()
    container: Container = ctx.request_context.lifespan_context["container"]
    return container.resolve(GreenhouseClientPort)


# --- Server + Tools ---

mcp = FastMCP(name="greenhouse-mcp", lifespan=lifespan)


@mcp.tool
async def candidate_dossier(
    candidate_id: int,
    client: GreenhouseClientPort = Depends(get_greenhouse_client),
) -> dict:
    """Get a complete candidate dossier."""
    candidate = await client.get_candidate(candidate_id)
    applications = await client.list_applications()
    candidate_apps = [
        a for a in applications
        if a.get("candidate_id") == candidate_id
    ]
    return {
        "candidate": candidate,
        "applications": candidate_apps,
        "application_count": len(candidate_apps),
    }
```

### Testing with the Chosen Pattern

```python
import pytest
from dioxide import Container, Profile


@pytest.fixture
def test_container() -> Container:
    return Container(profile=Profile.TEST)


@pytest.fixture
def fake_client(test_container: Container) -> FakeGreenhouseClient:
    client = test_container.resolve(GreenhouseClientPort)
    # Pre-populate test data
    client.candidates[42] = {"id": 42, "name": "Jane Doe"}
    client.applications = [
        {"id": 1, "job_id": 100, "stage": "Interview", "candidate_id": 42},
    ]
    return client


async def test_candidate_dossier_returns_applications(fake_client):
    """candidate_dossier returns matching applications for a candidate."""
    candidate = await fake_client.get_candidate(42)
    assert candidate["name"] == "Jane Doe"

    apps = await fake_client.list_applications()
    assert len(apps) == 1
    assert apps[0]["candidate_id"] == 42
```

No mocks needed. The test adapter is a real object with real behavior. dioxide's profile system swaps it in automatically.

## Consequences

### Positive

- **Tools are decoupled from infrastructure.** They depend on `GreenhouseClientPort`, never on `HttpGreenhouseClient`. Swapping to a different API client (or a cached wrapper) requires zero tool changes.
- **Testing is straightforward.** Create a `Container(profile=Profile.TEST)`, resolve the port, get a fake. No `unittest.mock` needed for the happy path.
- **Container lifecycle is managed.** Lifespan creates it on startup, cleanup runs on shutdown. No dangling connections.
- **Tool signatures are clean.** `Depends()` parameters are hidden from the MCP schema. Clients see `candidate_id: int`, not infrastructure details.
- **Profile selection via env var.** Follows 12-Factor. `GREENHOUSE_MCP_PROFILE=test` gives you the fake client everywhere.

### Negative

- **Two systems to understand.** Developers need to know both FastMCP's `Depends()` and dioxide's container/adapter model. Mitigated by the fact that both are well-documented and the integration surface is small (one factory function per port).
- **`get_context()` is implicit.** The dependency factory uses FastMCP's contextvars to find the current context. This works but is not obvious to newcomers. Mitigated by centralizing all factories in a single `dependencies.py` module.
- **Dict-based lifespan context.** `lifespan_context["container"]` is a string key, not a typed attribute. Mitigated by accessing it in exactly one place (`get_container()` helper).

### Risks

- **FastMCP `Depends()` API stability.** FastMCP 3.x is relatively new. The `Depends()` pattern is borrowed from FastAPI and is well-established, but the exact import paths may shift. Low risk.
- **dioxide `Container.resolve()` thread safety.** MCP servers may handle concurrent requests. dioxide's Rust core handles singleton caching, but we should verify thread safety under load. Medium risk; mitigated by the fact that MCP tools are typically async (single-threaded event loop).
