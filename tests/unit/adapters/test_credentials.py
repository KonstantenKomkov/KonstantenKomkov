"""Tests for private credential loading."""

import pytest

from it_activity.adapters.credentials import EnvironmentGitHubTokenProvider
from it_activity.domain.configuration import ConfigurationError


def test_github_credential_is_loaded_from_environment() -> None:
    provider = EnvironmentGitHubTokenProvider(
        {"IT_ACTIVITY_GITHUB_READ_TOKEN": "fixture-credential"}
    )

    assert provider.load() == "fixture-credential"


def test_github_credential_error_does_not_echo_value() -> None:
    provider = EnvironmentGitHubTokenProvider(
        {"IT_ACTIVITY_GITHUB_READ_TOKEN": "private fixture credential"}
    )

    with pytest.raises(ConfigurationError) as captured:
        provider.load()

    assert "private fixture credential" not in str(captured.value)
