"""Tests for annual usage aggregation across public and private repositories."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from it_activity.application.collect_usage import CollectUsage, UsageCollectionError
from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference
from it_activity.domain.configuration import ProfileConfiguration

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40
SHA_E = "e" * 40


class StaticConfigurationProvider:
    """Return a fixed profile configuration."""

    def __init__(self, configuration: ProfileConfiguration) -> None:
        self._configuration = configuration

    def load(self) -> ProfileConfiguration:
        return self._configuration


class FixedClock:
    """Return a deterministic instant."""

    def __init__(self, current: datetime) -> None:
        self._current = current

    def now(self) -> datetime:
        return self._current


class FakeUsageSource:
    """Expose in-memory history, file changes, and manifest markers."""

    def __init__(
        self,
        repositories: Sequence[RepositoryReference],
        commits: Mapping[int, Sequence[CommitMetadata]],
        markers: Mapping[int, Sequence[str]],
        changes: Mapping[tuple[int, str], Sequence[FileChange]] | None = None,
    ) -> None:
        self._repositories = repositories
        self._commits = commits
        self._markers = markers
        self._changes = {} if changes is None else changes
        self.history_calls: list[tuple[int, datetime, datetime]] = []
        self.manifest_calls: list[int] = []
        self.file_change_calls: list[tuple[int, str]] = []

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        assert owner_login == "octocat"
        return self._repositories

    def iter_commits(
        self,
        repository: RepositoryReference,
        since: datetime,
        until: datetime,
    ) -> Iterable[CommitMetadata]:
        self.history_calls.append((repository.repository_id, since, until))
        return self._commits.get(repository.repository_id, ())

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        key = (repository.repository_id, commit_sha)
        self.file_change_calls.append(key)
        return self._changes.get(key, ())

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        self.manifest_calls.append(repository.repository_id)
        return self._markers[repository.repository_id]


def metadata(
    sha: str,
    authored_at: datetime,
    email: str = "owner@example.invalid",
) -> CommitMetadata:
    return CommitMetadata(sha=sha, authored_at=authored_at, author_email=email)


def test_collect_usage_uses_repositories_with_owner_activity_during_last_year() -> None:
    now = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    configured_timezone = ZoneInfo("Europe/Moscow")
    first_day = now.astimezone(configured_timezone).date() - timedelta(days=364)
    cutoff = datetime.combine(first_day, time.min, configured_timezone).astimezone(timezone.utc)
    repositories = (
        RepositoryReference(1, "octocat/public-fixture", private=False),
        RepositoryReference(2, "fixture-org/private-fixture", private=True),
        RepositoryReference(3, "octocat/empty-fixture", private=True, empty=True),
        RepositoryReference(4, "octocat/excluded-fixture", private=True),
        RepositoryReference(5, "octocat/stale-fixture", private=True),
        RepositoryReference(6, "octocat/other-author-fixture", private=True),
    )
    source = FakeUsageSource(
        repositories,
        {
            1: (
                metadata(SHA_A, cutoff),
                metadata(SHA_C, cutoff - timedelta(seconds=1)),
            ),
            2: (metadata(SHA_B, now),),
            4: (metadata(SHA_D, now),),
            5: (metadata(SHA_C, cutoff - timedelta(seconds=1)),),
            6: (
                metadata(SHA_D, now, "other@example.invalid"),
                metadata(SHA_E, now + timedelta(seconds=1)),
            ),
        },
        {
            1: ("package.json", "Dockerfile"),
            2: ("package.json", "pyproject.toml"),
            4: ("Cargo.toml",),
            5: ("go.mod",),
            6: ("Gemfile",),
        },
        {
            (1, SHA_A): (FileChange("src/app.py", additions=3, deletions=1),),
            (2, SHA_B): (FileChange("service/worker.py", additions=1, deletions=0),),
        },
    )
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"OWNER@example.invalid"}),
        excluded_repositories=frozenset({"OCTOCAT/excluded-fixture"}),
        expected_repositories=frozenset(repository.full_name for repository in repositories),
    )

    report = CollectUsage(
        StaticConfigurationProvider(configuration),
        source,
        FixedClock(now),
    ).execute()

    assert [
        (item.name, item.share_basis_points, item.active_days) for item in report.languages
    ] == [("Python", 10_000, 2)]
    assert [
        (item.name, item.repository_count, item.repository_share_basis_points)
        for item in report.technologies
    ] == [
        ("Node.js", 2, 10_000),
        ("Docker", 1, 5000),
        ("Python", 1, 5000),
    ]
    assert [repository_id for repository_id, _, _ in source.history_calls] == [2, 6, 1, 5]
    assert all(since == cutoff and until == now for _, since, until in source.history_calls)
    assert source.manifest_calls == [2, 1]
    assert source.file_change_calls == [(2, SHA_B), (1, SHA_A)]
    assert "Private Fixture Language" not in repr(report)
    assert "private-fixture" not in repr(report)
    assert "package.json" not in repr(report)


def test_collect_usage_rejects_missing_expected_access_without_private_data() -> None:
    now = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    repositories = (RepositoryReference(1, "fixture-org/visible-private", private=True),)
    source = FakeUsageSource(repositories, {}, {})
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"owner@example.invalid"}),
        expected_repositories=frozenset(
            {"fixture-org/visible-private", "fixture-org/missing-private"}
        ),
    )

    with pytest.raises(UsageCollectionError) as captured:
        CollectUsage(
            StaticConfigurationProvider(configuration),
            source,
            FixedClock(now),
        ).execute()

    message = str(captured.value)
    assert "ожидаемым репозиториям" in message
    assert "fixture-org" not in message
    assert "visible-private" not in message
    assert "missing-private" not in message
    assert source.history_calls == []
    assert source.manifest_calls == []
    assert source.file_change_calls == []


def test_collect_usage_deduplicates_sha_and_language_days_globally() -> None:
    now = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    repositories = (
        RepositoryReference(1, "octocat/first-fixture", private=False),
        RepositoryReference(2, "octocat/second-fixture", private=True),
    )
    source = FakeUsageSource(
        repositories,
        {
            1: (metadata(SHA_A, now), metadata(SHA_B, now + timedelta(minutes=1))),
            2: (metadata(SHA_A, now),),
        },
        {1: (), 2: ()},
        {
            (1, SHA_A): (FileChange("src/first.py", additions=1, deletions=0),),
            (1, SHA_B): (FileChange("src/second.py", additions=1, deletions=0),),
        },
    )
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"owner@example.invalid"}),
        expected_repositories=frozenset(repository.full_name for repository in repositories),
    )

    report = CollectUsage(
        StaticConfigurationProvider(configuration),
        source,
        FixedClock(now + timedelta(minutes=2)),
    ).execute()

    assert [
        (item.name, item.share_basis_points, item.active_days) for item in report.languages
    ] == [("Python", 10_000, 1)]
    assert source.file_change_calls == [(1, SHA_A), (1, SHA_B)]


def test_collect_usage_rejects_conflicting_duplicate_sha_without_private_data() -> None:
    now = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    repositories = (
        RepositoryReference(1, "fixture-org/first-private", private=True),
        RepositoryReference(2, "fixture-org/second-private", private=True),
    )
    source = FakeUsageSource(
        repositories,
        {
            1: (metadata(SHA_A, now),),
            2: (metadata(SHA_A, now, "conflict@example.invalid"),),
        },
        {},
    )
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"owner@example.invalid"}),
        expected_repositories=frozenset(repository.full_name for repository in repositories),
    )

    with pytest.raises(UsageCollectionError) as captured:
        CollectUsage(
            StaticConfigurationProvider(configuration),
            source,
            FixedClock(now),
        ).execute()

    message = str(captured.value)
    assert "SHA" in message
    assert "fixture-org" not in message
    assert "example.invalid" not in message
    assert source.manifest_calls == []


def test_collect_usage_requires_timezone_aware_clock() -> None:
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"owner@example.invalid"}),
        expected_repositories=frozenset({"octocat/profile"}),
    )
    source = FakeUsageSource((), {}, {})

    with pytest.raises(UsageCollectionError, match="часового пояса"):
        CollectUsage(
            StaticConfigurationProvider(configuration),
            source,
            FixedClock(datetime(2026, 8, 10, 9, 0)),
        ).execute()

    assert source.history_calls == []
