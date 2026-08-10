"""Tests for the command-line entrypoint."""

import json

import pytest

from it_activity.entrypoints.cli import main


def test_empty_cli_scenario_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "validate-config" in captured.out
    assert "collect" in captured.out
    assert captured.err == ""


def test_validate_config_prints_safe_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("IT_ACTIVITY_GITHUB_LOGIN", "octocat")
    monkeypatch.setenv("IT_ACTIVITY_AUTHOR_EMAILS", "private-owner@example.invalid")
    monkeypatch.setenv("IT_ACTIVITY_EXCLUDED_REPOSITORIES", "private-owner/private-project")

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


def test_collect_requires_read_token_without_exposing_private_configuration(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("IT_ACTIVITY_GITHUB_LOGIN", "octocat")
    monkeypatch.setenv("IT_ACTIVITY_AUTHOR_EMAILS", "private-owner@example.invalid")
    monkeypatch.setenv("IT_ACTIVITY_EXCLUDED_REPOSITORIES", "private-owner/private-project")
    monkeypatch.delenv("IT_ACTIVITY_GITHUB_READ_TOKEN", raising=False)

    exit_code = main(["collect"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "IT_ACTIVITY_GITHUB_READ_TOKEN" in captured.err
    assert "private-owner@example.invalid" not in captured.err
    assert "private-owner/private-project" not in captured.err
