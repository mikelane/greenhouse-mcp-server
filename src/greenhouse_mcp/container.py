"""Dioxide DI container configuration."""

from __future__ import annotations

from dioxide import Container, Profile


def create_container(
    *,
    profile: str = Profile.PRODUCTION,
    api_token: str = "",  # noqa: ARG001
) -> Container:
    """Create and configure the dioxide DI container.

    Args:
        profile: The dioxide profile (production or test).
        api_token: The Greenhouse API token.

    Returns:
        Configured Container instance.
    """
    return Container(profile=profile)
