"""Tests for the command-line entrypoint."""

import json
from pathlib import Path
from typing import cast

import pytest

from it_activity.adapters.composite_activity import CompositeActivitySource
from it_activity.adapters.composite_github import CompositeGitHubActivitySource
from it_activity.domain.activity import RepositoryReference
from it_activity.entrypoints import cli
from it_activity.entrypoints.cli import main


def test_empty_cli_scenario_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "validate-config" in captured.out
    assert "collect" in captured.out
    assert "usage" in captured.out
    assert "generate" in captured.out
    assert captured.err == ""


def test_validate_config_prints_safe_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("IT_ACTIVITY_GITHUB_LOGIN", "octocat")
    monkeypatch.setenv("IT_ACTIVITY_AUTHOR_EMAILS", "private-owner@example.invalid")
    monkeypatch.setenv("IT_ACTIVITY_EXCLUDED_REPOSITORIES", "private-owner/private-project")
    monkeypatch.setenv("IT_ACTIVITY_EXPECTED_REPOSITORIES", "private-owner/private-project")

    exit_code = main(["validate-config"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output == {
        "author_identity_count": 1,
        "exclusion_count": 1,
        "github_login": "octocat",
        "timezone": "Europe/Moscow",
    }
    assert "private-owner@example.invalid" not in captured.out
    assert "private-owner/private-project" not in captured.out
    assert captured.err == ""


def test_validate_config_reports_safe_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("IT_ACTIVITY_GITHUB_LOGIN", raising=False)
    monkeypatch.setenv("IT_ACTIVITY_AUTHOR_EMAILS", "private-owner@example.invalid")

    exit_code = main(["validate-config"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "IT_ACTIVITY_GITHUB_LOGIN" in captured.err
    assert "private-owner@example.invalid" not in captured.err


@pytest.mark.parametrize("command", ["collect", "usage", "generate"])
def test_collection_requires_read_token_without_exposing_private_configuration(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("IT_ACTIVITY_GITHUB_LOGIN", "octocat")
    monkeypatch.setenv("IT_ACTIVITY_AUTHOR_EMAILS", "private-owner@example.invalid")
    monkeypatch.setenv("IT_ACTIVITY_EXCLUDED_REPOSITORIES", "private-owner/private-project")
    monkeypatch.delenv("IT_ACTIVITY_GITHUB_READ_TOKEN", raising=False)

    exit_code = main([command])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "IT_ACTIVITY_GITHUB_READ_TOKEN" in captured.err
    assert "private-owner@example.invalid" not in captured.err
    assert "private-owner/private-project" not in captured.err


def test_activity_assembly_is_unchanged_without_local_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IT_ACTIVITY_LOCAL_REPOSITORIES", raising=False)
    github_source = cast(CompositeGitHubActivitySource, object())

    activity_source, _configuration_provider = cli._with_optional_local_activity(github_source)

    assert activity_source is github_source


def test_activity_assembly_adds_and_prefers_runtime_local_repositories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_path = Path("/private/fixture-local-clone")
    monkeypatch.setenv("IT_ACTIVITY_LOCAL_REPOSITORIES", str(local_path))
    monkeypatch.setenv("IT_ACTIVITY_GITHUB_LOGIN", "octocat")
    monkeypatch.setenv("IT_ACTIVITY_AUTHOR_EMAILS", "private-owner@example.invalid")
    monkeypatch.setenv("IT_ACTIVITY_EXPECTED_REPOSITORIES", "octocat/profile")

    local_repository = RepositoryReference(9, "fixture-org/private-local", private=True)
    api_repository = RepositoryReference(1, "FIXTURE-ORG/PRIVATE-LOCAL", private=True)

    class StubLocalGitActivitySource:
        repository_names = frozenset({"fixture-org/private-local"})

        def __init__(self, repository_paths: tuple[Path, ...]) -> None:
            assert repository_paths == (local_path,)

        def list_repositories(self, owner_login: str) -> tuple[RepositoryReference, ...]:
            assert owner_login == "octocat"
            return (local_repository,)

    class StubGitHubActivitySource:
        def list_repositories(self, owner_login: str) -> tuple[RepositoryReference, ...]:
            assert owner_login == "octocat"
            return (api_repository,)

    monkeypatch.setattr(cli, "LocalGitActivitySource", StubLocalGitActivitySource)
    github_source = cast(CompositeGitHubActivitySource, StubGitHubActivitySource())

    activity_source, configuration_provider = cli._with_optional_local_activity(github_source)

    assert isinstance(activity_source, CompositeActivitySource)
    assert activity_source.list_repositories("octocat") == (local_repository,)
    assert configuration_provider.load().expected_repositories == frozenset(
        {"octocat/profile", "fixture-org/private-local"}
    )
