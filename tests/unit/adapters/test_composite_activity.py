"""Tests for combining API and local repository activity."""

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

import pytest

from it_activity.adapters.composite_activity import CompositeActivitySource
from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference
from it_activity.ports.activity_source import ActivitySourceError

SHA = "a" * 40


class StubActivitySource:
    """Return deterministic activity and record repository routing."""

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
        del since, until
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
        del commit_sha
        self.operation_calls.append(("changes", repository.repository_id))
        return (FileChange(path="lib/main.dart", additions=2, deletions=1),)


def test_composite_activity_unions_sources_and_routes_unique_repositories() -> None:
    api_repository = RepositoryReference(1, "owner/api", private=False)
    local_repository = RepositoryReference(9, "organization/local", private=True)
    api = StubActivitySource((api_repository,))
    local = StubActivitySource((local_repository,))
    source = CompositeActivitySource((api, local))

    repositories = source.list_repositories("octocat")

    assert repositories == (local_repository, api_repository)
    since = datetime(2026, 8, 1, tzinfo=timezone.utc)
    until = datetime(2026, 8, 11, tzinfo=timezone.utc)
    assert next(iter(source.iter_commits(local_repository, since, until))).sha == SHA
    assert source.get_file_changes(local_repository, SHA)[0].additions == 2
    assert api.operation_calls == []
    assert local.operation_calls == [("commits", 9), ("changes", 9)]


def test_composite_activity_prefers_api_for_a_repository_also_configured_locally() -> None:
    api_repository = RepositoryReference(1, "organization/shared", private=True)
    local_repository = RepositoryReference(9, "ORGANIZATION/SHARED", private=True)
    api = StubActivitySource((api_repository,))
    local = StubActivitySource((local_repository,))
    source = CompositeActivitySource((api, local))

    repositories = source.list_repositories("octocat")
    source.get_file_changes(repositories[0], SHA)

    assert repositories == (api_repository,)
    assert api.operation_calls == [("changes", 1)]
    assert local.operation_calls == []


def test_composite_activity_rejects_identifier_collision_without_private_names() -> None:
    first = RepositoryReference(1, "private-owner/first-project", private=True)
    second = RepositoryReference(1, "private-owner/second-project", private=True)
    source = CompositeActivitySource((StubActivitySource((first,)), StubActivitySource((second,))))

    with pytest.raises(ActivitySourceError) as captured:
        source.list_repositories("octocat")

    message = str(captured.value)
    assert "противоречивые" in message
    assert "private-owner" not in message
    assert "first-project" not in message
    assert "second-project" not in message


def test_composite_activity_rejects_unverified_repository_without_private_names() -> None:
    known = RepositoryReference(1, "private-owner/known-project", private=True)
    unknown = RepositoryReference(2, "private-owner/unknown-project", private=True)
    source = CompositeActivitySource((StubActivitySource((known,)),))
    source.list_repositories("octocat")

    with pytest.raises(ActivitySourceError) as captured:
        source.get_file_changes(unknown, SHA)

    message = str(captured.value)
    assert "проверенном списке" in message
    assert "private-owner" not in message
    assert "unknown-project" not in message


def test_composite_activity_rejects_different_account_after_discovery() -> None:
    source = CompositeActivitySource((StubActivitySource(()),))
    source.list_repositories("octocat")

    with pytest.raises(ActivitySourceError, match="другого аккаунта"):
        source.list_repositories("different-private-user")


def test_composite_activity_requires_a_source() -> None:
    with pytest.raises(ValueError, match="At least one"):
        CompositeActivitySource(())
