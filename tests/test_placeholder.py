"""Placeholder tests to verify package structure."""

import pytest

from greenhouse_mcp import __version__
from greenhouse_mcp.server import main


@pytest.mark.small
class DescribePackageImport:
    """Verify the greenhouse_mcp package is importable."""

    def it_exposes_a_version_string(self) -> None:
        """Package exposes a version string."""
        assert isinstance(__version__, str)


@pytest.mark.small
class DescribeServerEntrypoint:
    """Verify the server entrypoint exists and is callable."""

    def it_runs_without_error(self) -> None:
        """Server entrypoint runs without error."""
        main()
