"""Tests for validated profile configuration."""

import pytest

from it_activity.domain.configuration import ConfigurationError, ProfileConfiguration


def test_configuration_normalizes_private_identifiers() -> None:
    configuration = ProfileConfiguration(
        github_login=" octocat ",
        author_emails=frozenset({" OWNER@EXAMPLE.INVALID ", "owner@example.invalid"}),
        timezone="Europe/Moscow",
        excluded_repositories=frozenset({" private-owner/private-project "}),
        expected_repositories=frozenset({" private-owner/expected--project "}),
    )

    assert configuration.github_login == "octocat"
    assert configuration.author_emails == frozenset({"owner@example.invalid"})
    assert configuration.excluded_repositories == frozenset({"private-owner/private-project"})
    assert configuration.expected_repositories == frozenset({"private-owner/expected--project"})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("github_login", "-invalid", "GitHub login"),
        ("author_emails", frozenset(), "авторского email"),
        ("author_emails", frozenset({"not-an-email"}), "авторских email"),
        ("expected_repositories", frozenset(), "ожидаемого репозитория"),
        ("timezone", "Invalid/PrivateTimezone", "часовой пояс"),
        ("excluded_repositories", frozenset({"private\nname"}), "список исключений"),
        (
            "expected_repositories",
            frozenset({"private owner/private project"}),
            "ожидаемых репозиториев",
        ),
    ],
)
def test_configuration_rejects_invalid_values(field: str, value: object, message: str) -> None:
    values: dict[str, object] = {
        "github_login": "octocat",
        "author_emails": frozenset({"owner@example.invalid"}),
        "timezone": "Europe/Moscow",
        "excluded_repositories": frozenset(),
        "expected_repositories": frozenset({"octocat/profile"}),
    }
    values[field] = value

    with pytest.raises(ConfigurationError, match=message):
        ProfileConfiguration(**values)  # type: ignore[arg-type]


def test_configuration_representation_does_not_expose_private_values() -> None:
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"owner@example.invalid"}),
        excluded_repositories=frozenset({"private-owner/private-project"}),
        expected_repositories=frozenset({"private-owner/expected--project"}),
    )

    representation = repr(configuration)

    assert "owner@example.invalid" not in representation
    assert "private-owner/private-project" not in representation
    assert "private-owner/expected--project" not in representation
