"""Dependency factories for FastMCP tool injection.

Each factory resolves a port from the dioxide container stored
in the FastMCP lifespan context. Tools use these via Depends().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.server.dependencies import get_context

if TYPE_CHECKING:
    from dioxide import Container


def get_container() -> Container:
    """Resolve the dioxide container from the lifespan context."""
    ctx = get_context()
    container: Container = ctx.request_context.lifespan_context["container"]  # type: ignore[union-attr]
    return container


def get_api_token() -> str:
    """Resolve the API token from the lifespan context."""
    ctx = get_context()
    token: str = ctx.request_context.lifespan_context["api_token"]  # type: ignore[union-attr]
    return token
