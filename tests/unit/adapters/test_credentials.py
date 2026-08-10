"""Tests for private credential loading."""

import pytest

from it_activity.adapters.credentials import EnvironmentGitHubTokensProvider
from it_activity.domain.configuration import ConfigurationError


def test_primary_github_credential_is_loaded_from_environment() -> None:
    provider = EnvironmentGitHubTokensProvider(
        {"IT_ACTIVITY_GITHUB_READ_TOKEN": "fixture-credential"}
    )

    assert provider.load() == ("fixture-credential",)


def test_additional_github_credentials_are_loaded_one_per_line() -> None:
    provider = EnvironmentGitHubTokensProvider(
        {
            "IT_ACTIVITY_GITHUB_READ_TOKEN": "primary-fixture-credential",
            "IT_ACTIVITY_GITHUB_ADDITIONAL_READ_TOKENS": (
                "organization-one-fixture-credential\norganization-two-fixture-credential"
            ),
        }
    )

    assert provider.load() == (
        "primary-fixture-credential",
        "organization-one-fixture-credential",
        "organization-two-fixture-credential",
    )


def test_github_credential_error_does_not_echo_value() -> None:
    provider = EnvironmentGitHubTokensProvider(
        {"IT_ACTIVITY_GITHUB_READ_TOKEN": "private fixture credential"}
    )

    with pytest.raises(ConfigurationError) as captured:
        provider.load()

    assert "private fixture credential" not in str(captured.value)


def test_additional_github_credential_error_does_not_echo_value() -> None:
    provider = EnvironmentGitHubTokensProvider(
        {
            "IT_ACTIVITY_GITHUB_READ_TOKEN": "primary-fixture-credential",
            "IT_ACTIVITY_GITHUB_ADDITIONAL_READ_TOKENS": "private fixture credential",
        }
    )

    with pytest.raises(ConfigurationError) as captured:
        provider.load()

    assert "private fixture credential" not in str(captured.value)


def test_github_credentials_must_be_unique_without_echoing_value() -> None:
    provider = EnvironmentGitHubTokensProvider(
        {
            "IT_ACTIVITY_GITHUB_READ_TOKEN": "duplicate-fixture-credential",
            "IT_ACTIVITY_GITHUB_ADDITIONAL_READ_TOKENS": "duplicate-fixture-credential",
        }
    )

    with pytest.raises(ConfigurationError) as captured:
        provider.load()

    assert "повторяться" in str(captured.value)
    assert "duplicate-fixture-credential" not in str(captured.value)
