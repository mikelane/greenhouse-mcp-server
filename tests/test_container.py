"""Tests for the dioxide DI container configuration."""

from __future__ import annotations

import pytest
from dioxide import Container, Profile

from greenhouse_mcp.container import create_container


@pytest.mark.small
class DescribeCreateContainer:
    def it_returns_a_dioxide_container(self) -> None:
        result = create_container()

        assert isinstance(result, Container)

    def it_defaults_to_production_profile(self) -> None:
        result = create_container()

        assert result.active_profile == Profile.PRODUCTION

    def it_accepts_test_profile(self) -> None:
        result = create_container(profile=Profile.TEST)

        assert result.active_profile == Profile.TEST
