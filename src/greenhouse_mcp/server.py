"""FastMCP server for greenhouse-mcp.

Uses the Lifespan + Depends() pattern (ADR 0004) to wire
dioxide dependency injection into tool handlers.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

from greenhouse_mcp.container import create_container

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Initialize the dioxide container on startup."""
    api_token = os.environ.get("GREENHOUSE_API_TOKEN", "")
    profile = os.environ.get("GREENHOUSE_MCP_PROFILE", "production")
    container = create_container(profile=profile, api_token=api_token)
    yield {"container": container, "api_token": api_token}


mcp = FastMCP(name="greenhouse-mcp", lifespan=lifespan)


def main() -> None:
    """Entry point for the greenhouse-mcp CLI command."""
    mcp.run()  # pragma: no cover
