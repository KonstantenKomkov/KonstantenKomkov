"""Unit tests for private local Git path configuration."""

from pathlib import Path

import pytest

from it_activity.adapters.local_git import (
    EnvironmentLocalRepositoryPathsProvider,
    LocalGitActivitySource,
)
from it_activity.domain.configuration import ConfigurationError
from it_activity.ports.activity_source import ActivitySourceError


def test_local_path_provider_is_disabled_when_variable_is_absent() -> None:
    assert EnvironmentLocalRepositoryPathsProvider({}).load() == ()


def test_local_path_provider_loads_one_absolute_path_per_line() -> None:
    provider = EnvironmentLocalRepositoryPathsProvider(
        {"IT_ACTIVITY_LOCAL_REPOSITORIES": ("/private/fixture one\n\n/private/fixture-two\n")}
    )

    assert provider.load() == (
        Path("/private/fixture one"),
        Path("/private/fixture-two"),
    )


@pytest.mark.parametrize(
    "value",
    ["relative/private-repository", "/private/duplicate\n/private/duplicate"],
)
def test_local_path_provider_rejects_invalid_values_without_exposing_them(value: str) -> None:
    with pytest.raises(ConfigurationError) as captured:
        EnvironmentLocalRepositoryPathsProvider({"IT_ACTIVITY_LOCAL_REPOSITORIES": value}).load()

    message = str(captured.value)
    assert "IT_ACTIVITY_LOCAL_REPOSITORIES" in message
    assert value not in message
    assert "private-repository" not in message
    assert "duplicate" not in message


@pytest.mark.parametrize(
    ("remote", "expected"),
    [
        ("git@github.com:fixture-org/private-project.git", "fixture-org/private-project"),
        ("ssh://git@github.com/fixture-org/private-project", "fixture-org/private-project"),
        ("https://github.com/fixture-org/private-project.git", "fixture-org/private-project"),
    ],
)
def test_local_source_accepts_only_canonical_github_remote_forms(
    remote: str,
    expected: str,
) -> None:
    assert LocalGitActivitySource._github_repository_name(remote) == expected


@pytest.mark.parametrize(
    "remote",
    [
        "https://private-user:private-password@github.com/fixture-org/private-project.git",
        "ssh://git@github.com:443/fixture-org/private-project.git",
        "git@example.invalid:fixture-org/private-project.git",
        "file:///private/fixture-org/private-project.git",
        "https://github.com/fixture-org/private-project.git?private=value",
        "https://github.com/fixture-org/private-project.git/",
        "https://github.com//fixture-org/private-project.git",
    ],
)
def test_local_source_rejects_unsafe_remote_without_echoing_it(remote: str) -> None:
    with pytest.raises(ActivitySourceError) as captured:
        LocalGitActivitySource._github_repository_name(remote)

    message = str(captured.value)
    assert "безопасного GitHub origin" in message
    assert remote not in message
    assert "private-password" not in message
