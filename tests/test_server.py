"""Tests for the FastMCP server shell."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from dioxide import Profile
from fastmcp import FastMCP

from greenhouse_mcp.server import lifespan, main, mcp


@pytest.mark.small
class DescribeServerInstance:
    """Server module-level FastMCP instance."""

    def it_is_a_fastmcp_instance(self) -> None:
        assert isinstance(mcp, FastMCP)

    def it_is_named_greenhouse_mcp(self) -> None:
        assert mcp.name == "greenhouse-mcp"


@pytest.mark.small
class DescribeLifespan:
    """Lifespan context manager initializes DI container."""

    @pytest.mark.anyio
    async def it_yields_container_in_context(self) -> None:
        mock_server = AsyncMock(spec=FastMCP)
        async with lifespan(mock_server) as context:
            assert "container" in context
            assert "api_token" in context

    @pytest.mark.anyio
    async def it_reads_api_token_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GREENHOUSE_API_TOKEN", "test-token-123")
        mock_server = AsyncMock(spec=FastMCP)
        async with lifespan(mock_server) as context:
            assert context["api_token"] == "test-token-123"  # noqa: S105

    @pytest.mark.anyio
    async def it_defaults_api_token_to_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GREENHOUSE_API_TOKEN", raising=False)
        mock_server = AsyncMock(spec=FastMCP)
        async with lifespan(mock_server) as context:
            assert context["api_token"] == ""

    @pytest.mark.anyio
    async def it_defaults_to_production_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GREENHOUSE_MCP_PROFILE", raising=False)
        mock_server = AsyncMock(spec=FastMCP)
        async with lifespan(mock_server) as context:
            assert context["container"].active_profile == Profile.PRODUCTION

    @pytest.mark.anyio
    async def it_reads_profile_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GREENHOUSE_MCP_PROFILE", "test")
        mock_server = AsyncMock(spec=FastMCP)
        async with lifespan(mock_server) as context:
            assert context["container"].active_profile == Profile.TEST


@pytest.mark.small
class DescribeMain:
    """CLI entry point."""

    def it_is_callable(self) -> None:
        assert callable(main)
