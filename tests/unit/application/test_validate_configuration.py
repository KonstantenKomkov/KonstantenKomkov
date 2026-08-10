"""Tests for the public configuration-validation use case."""

from it_activity.application.validate_configuration import ValidateConfiguration
from it_activity.domain.configuration import ProfileConfiguration


class StubConfigurationProvider:
    """Return a fixed configuration without external access."""

    def load(self) -> ProfileConfiguration:
        return ProfileConfiguration(
            github_login="octocat",
            author_emails=frozenset({"first@example.invalid", "second@example.invalid"}),
            expected_repositories=frozenset({"private-owner/private-project"}),
            excluded_repositories=frozenset({"private-owner/private-project"}),
        )


def test_validate_configuration_returns_only_public_summary() -> None:
    summary = ValidateConfiguration(StubConfigurationProvider()).execute()

    assert summary.github_login == "octocat"
    assert summary.timezone == "Europe/Moscow"
    assert summary.author_identity_count == 2
    assert summary.exclusion_count == 1
    assert "example.invalid" not in repr(summary)
    assert "private-project" not in repr(summary)
