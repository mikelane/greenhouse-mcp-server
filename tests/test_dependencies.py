"""Tests for dependency factory functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from greenhouse_mcp.dependencies import get_api_token, get_container


@pytest.mark.small
class DescribeGetContainer:
    """Factory that resolves the dioxide container from lifespan context."""

    @patch("greenhouse_mcp.dependencies.get_context")
    def it_resolves_container_from_lifespan_context(self, mock_get_context: MagicMock) -> None:
        sentinel_container = object()
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {
            "container": sentinel_container,
        }
        mock_get_context.return_value = mock_ctx

        result = get_container()

        assert result is sentinel_container


@pytest.mark.small
class DescribeGetApiToken:
    """Factory that resolves the API token from lifespan context."""

    @patch("greenhouse_mcp.dependencies.get_context")
    def it_resolves_token_from_lifespan_context(self, mock_get_context: MagicMock) -> None:
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {
            "api_token": "my-token",
        }
        mock_get_context.return_value = mock_ctx

        result = get_api_token()

        assert result == "my-token"
