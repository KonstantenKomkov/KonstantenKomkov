"""Tests for combining independently scoped GitHub read credentials."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone

import pytest

from it_activity.adapters.composite_github import CompositeGitHubActivitySource
from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference
from it_activity.ports.activity_source import ActivitySourceError

SHA = "a" * 40


class StubProfileSource:
    """Return bounded fixtures and record which source handled each repository."""

    def __init__(self, repositories: Sequence[RepositoryReference]) -> None:
        self.repositories = tuple(repositories)
        self.list_calls: list[str] = []
        self.operation_calls: list[tuple[str, int]] = []

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        self.list_calls.append(owner_login)
        return self.repositories

    def iter_commits(
        self,
        repository: RepositoryReference,
        since: datetime,
        until: datetime,
    ) -> Iterable[CommitMetadata]:
        self.operation_calls.append(("commits", repository.repository_id))
        return (
            CommitMetadata(
                sha=SHA,
                authored_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
                author_email="owner@example.invalid",
            ),
        )

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        self.operation_calls.append(("changes", repository.repository_id))
        return (FileChange(path="lib/main.dart", additions=2, deletions=1),)

    def get_language_bytes(self, repository: RepositoryReference) -> Mapping[str, int]:
        self.operation_calls.append(("languages", repository.repository_id))
        return {"Dart": 10}

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        self.operation_calls.append(("manifests", repository.repository_id))
        return ("pubspec.yaml",)


def test_composite_source_unions_deduplicates_and_routes_repositories() -> None:
    shared = RepositoryReference(1, "owner/shared", private=False)
    primary_only = RepositoryReference(2, "owner/z-primary", private=True)
    additional_only = RepositoryReference(3, "organization/a-additional", private=True)
    primary = StubProfileSource((primary_only, shared))
    additional = StubProfileSource((shared, additional_only))
    source = CompositeGitHubActivitySource((primary, additional))

    repositories = source.list_repositories("octocat")
    cached_repositories = source.list_repositories("OCTOCAT")

    assert [repository.repository_id for repository in repositories] == [3, 1, 2]
    assert cached_repositories == repositories
    assert primary.list_calls == ["octocat"]
    assert additional.list_calls == ["octocat"]

    since = datetime(2026, 8, 1, tzinfo=timezone.utc)
    until = datetime(2026, 8, 11, tzinfo=timezone.utc)
    assert next(iter(source.iter_commits(additional_only, since, until))).sha == SHA
    assert source.get_file_changes(additional_only, SHA)[0].additions == 2
    assert source.get_language_bytes(additional_only) == {"Dart": 10}
    assert source.list_manifest_markers(additional_only) == ("pubspec.yaml",)
    assert primary.operation_calls == []
    assert additional.operation_calls == [
        ("commits", 3),
        ("changes", 3),
        ("languages", 3),
        ("manifests", 3),
    ]


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (
            RepositoryReference(1, "private-owner/first-project", private=True),
            RepositoryReference(1, "private-owner/second-project", private=True),
        ),
        (
            RepositoryReference(1, "private-owner/private-project", private=True),
            RepositoryReference(2, "PRIVATE-OWNER/PRIVATE-PROJECT", private=True),
        ),
        (
            RepositoryReference(
                1,
                "private-owner/private-project",
                private=True,
                default_branch="main",
            ),
            RepositoryReference(
                1,
                "private-owner/private-project",
                private=True,
                default_branch="develop",
            ),
        ),
    ],
)
def test_composite_source_rejects_conflicts_without_private_names(
    first: RepositoryReference,
    second: RepositoryReference,
) -> None:
    source = CompositeGitHubActivitySource(
        (StubProfileSource((first,)), StubProfileSource((second,)))
    )

    with pytest.raises(ActivitySourceError) as captured:
        source.list_repositories("octocat")

    message = str(captured.value)
    assert "противоречивые" in message
    assert "private-owner" not in message.casefold()
    assert "private-project" not in message.casefold()


def test_composite_source_rejects_an_unverified_repository_without_private_data() -> None:
    known = RepositoryReference(1, "private-owner/known-project", private=True)
    unknown = RepositoryReference(2, "private-owner/unknown-project", private=True)
    source = CompositeGitHubActivitySource((StubProfileSource((known,)),))
    source.list_repositories("octocat")

    with pytest.raises(ActivitySourceError) as captured:
        source.get_language_bytes(unknown)

    message = str(captured.value)
    assert "проверенном списке" in message
    assert "private-owner" not in message
    assert "unknown-project" not in message


def test_composite_source_rejects_a_different_account_after_discovery() -> None:
    source = CompositeGitHubActivitySource((StubProfileSource(()),))
    source.list_repositories("octocat")

    with pytest.raises(ActivitySourceError, match="другого аккаунта"):
        source.list_repositories("different-private-user")


def test_composite_source_requires_at_least_one_credential_scoped_source() -> None:
    with pytest.raises(ValueError, match="At least one"):
        CompositeGitHubActivitySource(())
