"""Tests for aggregating usage across public and private repositories."""

from collections.abc import Mapping, Sequence

from it_activity.application.collect_usage import CollectUsage
from it_activity.domain.activity import RepositoryReference
from it_activity.domain.configuration import ProfileConfiguration


class StaticConfigurationProvider:
    """Return a fixed profile configuration."""

    def __init__(self, configuration: ProfileConfiguration) -> None:
        self._configuration = configuration

    def load(self) -> ProfileConfiguration:
        return self._configuration


class FakeUsageSource:
    """Expose only in-memory Linguist bytes and sanitized manifest markers."""

    def __init__(
        self,
        repositories: Sequence[RepositoryReference],
        languages: Mapping[int, Mapping[str, int]],
        markers: Mapping[int, Sequence[str]],
    ) -> None:
        self._repositories = repositories
        self._languages = languages
        self._markers = markers
        self.language_calls: list[int] = []
        self.manifest_calls: list[int] = []

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        assert owner_login == "octocat"
        return self._repositories

    def get_language_bytes(self, repository: RepositoryReference) -> Mapping[str, int]:
        self.language_calls.append(repository.repository_id)
        return self._languages[repository.repository_id]

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        self.manifest_calls.append(repository.repository_id)
        return self._markers[repository.repository_id]


def test_collect_usage_matches_manual_public_private_aggregate() -> None:
    repositories = (
        RepositoryReference(1, "octocat/public-fixture", private=False),
        RepositoryReference(2, "fixture-org/private-fixture", private=True),
        RepositoryReference(3, "octocat/empty-fixture", private=True, empty=True),
        RepositoryReference(4, "octocat/excluded-fixture", private=True),
    )
    source = FakeUsageSource(
        repositories,
        {
            1: {"Python": 100, "JavaScript": 100},
            2: {"Python": 100, "Private Fixture Language": 100},
            4: {"Rust": 999},
        },
        {
            1: ("package.json", "Dockerfile"),
            2: ("package.json", "pyproject.toml"),
            4: ("Cargo.toml",),
        },
    )
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"owner@example.invalid"}),
        excluded_repositories=frozenset({"OCTOCAT/excluded-fixture"}),
    )

    report = CollectUsage(StaticConfigurationProvider(configuration), source).execute()

    assert [(item.name, item.share_basis_points) for item in report.languages] == [
        ("Python", 5000),
        ("JavaScript", 2500),
        ("Other", 2500),
    ]
    assert [
        (item.name, item.repository_count, item.repository_share_basis_points)
        for item in report.technologies
    ] == [
        ("Node.js", 2, 6667),
        ("Docker", 1, 3333),
        ("Python", 1, 3333),
    ]
    assert source.language_calls == [2, 1]
    assert source.manifest_calls == [2, 1]
    assert "Private Fixture Language" not in repr(report)
    assert "private-fixture" not in repr(report)
    assert "package.json" not in repr(report)
