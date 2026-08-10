"""Tests for environment configuration loading."""

import pytest

from it_activity.adapters.environment import EnvironmentConfigurationProvider
from it_activity.domain.configuration import ConfigurationError


def test_environment_provider_loads_required_and_optional_values() -> None:
    provider = EnvironmentConfigurationProvider(
        {
            "IT_ACTIVITY_GITHUB_LOGIN": "octocat",
            "IT_ACTIVITY_AUTHOR_EMAILS": "first@example.invalid, SECOND@example.invalid",
            "IT_ACTIVITY_TIMEZONE": "UTC",
            "IT_ACTIVITY_EXCLUDED_REPOSITORIES": "owner/one, owner/two",
            "IT_ACTIVITY_EXPECTED_REPOSITORIES": "owner/one, owner/private-two",
            "IT_ACTIVITY_ADDITIONAL_EXPECTED_REPOSITORIES": (
                "another-owner/private-three, owner/one"
            ),
        }
    )

    configuration = provider.load()

    assert configuration.author_emails == frozenset(
        {"first@example.invalid", "second@example.invalid"}
    )
    assert configuration.timezone == "UTC"
    assert configuration.excluded_repositories == frozenset({"owner/one", "owner/two"})
    assert configuration.expected_repositories == frozenset(
        {"owner/one", "owner/private-two", "another-owner/private-three"}
    )


def test_environment_provider_uses_default_timezone() -> None:
    configuration = EnvironmentConfigurationProvider(
        {
            "IT_ACTIVITY_GITHUB_LOGIN": "octocat",
            "IT_ACTIVITY_AUTHOR_EMAILS": "owner@example.invalid",
            "IT_ACTIVITY_EXPECTED_REPOSITORIES": "octocat/profile",
        }
    ).load()

    assert configuration.timezone == "Europe/Moscow"


def test_environment_provider_extends_expected_repositories_in_process() -> None:
    configuration = EnvironmentConfigurationProvider(
        {
            "IT_ACTIVITY_GITHUB_LOGIN": "octocat",
            "IT_ACTIVITY_AUTHOR_EMAILS": "owner@example.invalid",
            "IT_ACTIVITY_EXPECTED_REPOSITORIES": "octocat/profile",
        },
        additional_expected_repositories=(
            "fixture-org/local-private",
            "octocat/profile",
        ),
    ).load()

    assert configuration.expected_repositories == frozenset(
        {"octocat/profile", "fixture-org/local-private"}
    )


@pytest.mark.parametrize(
    "missing_variable",
    [
        "IT_ACTIVITY_GITHUB_LOGIN",
        "IT_ACTIVITY_AUTHOR_EMAILS",
        "IT_ACTIVITY_EXPECTED_REPOSITORIES",
    ],
)
def test_environment_provider_rejects_missing_required_value(missing_variable: str) -> None:
    environment = {
        "IT_ACTIVITY_GITHUB_LOGIN": "octocat",
        "IT_ACTIVITY_AUTHOR_EMAILS": "owner@example.invalid",
        "IT_ACTIVITY_EXPECTED_REPOSITORIES": "octocat/profile",
    }
    del environment[missing_variable]

    with pytest.raises(ConfigurationError, match=missing_variable):
        EnvironmentConfigurationProvider(environment).load()
