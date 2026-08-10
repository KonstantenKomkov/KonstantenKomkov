"""Tests for complete, private-safe activity aggregation."""

from collections.abc import Iterable, Sequence
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from it_activity.application.collect_activity import CollectActivity, CollectionError
from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference
from it_activity.domain.configuration import ProfileConfiguration

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40
SHA_E = "e" * 40
SHA_F = "f" * 40


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


class FakeActivitySource:
    """Expose a complete in-memory public/private repository fixture."""

    def __init__(
        self,
        repositories: Sequence[RepositoryReference],
        commits: dict[int, tuple[CommitMetadata, ...]],
        changes: dict[str, tuple[FileChange, ...]],
    ) -> None:
        self._repositories = repositories
        self._commits = commits
        self._changes = changes
        self.history_calls: list[tuple[int, datetime, datetime]] = []
        self.change_calls: list[tuple[int, str]] = []

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
        self.change_calls.append((repository.repository_id, commit_sha))
        return self._changes[commit_sha]


def metadata(
    sha: str, authored_at: datetime, email: str = "owner@example.invalid"
) -> CommitMetadata:
    return CommitMetadata(sha=sha, authored_at=authored_at, author_email=email)


def test_collect_activity_matches_manual_public_private_aggregate() -> None:
    now = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    local_timezone = ZoneInfo("Europe/Moscow")
    first_day = now.astimezone(local_timezone).date() - timedelta(days=364)
    cutoff = datetime.combine(first_day, time.min, local_timezone).astimezone(timezone.utc)
    repositories = (
        RepositoryReference(1, "octocat/public-fixture", private=False),
        RepositoryReference(2, "fixture-org/private-fixture", private=True),
        RepositoryReference(3, "octocat/fork-fixture", private=False),
        RepositoryReference(4, "octocat/excluded-fixture", private=True),
    )
    owner_today = metadata(SHA_A, datetime(2026, 8, 9, 22, 30, tzinfo=timezone.utc))
    other_author = metadata(
        SHA_B,
        datetime(2026, 8, 9, 8, 0, tzinfo=timezone.utc),
        "other@example.invalid",
    )
    owner_at_cutoff = metadata(SHA_C, cutoff)
    owner_two_days_ago = metadata(
        SHA_D,
        datetime(2026, 8, 8, 20, 30, tzinfo=timezone.utc),
    )
    before_cutoff = metadata(SHA_E, cutoff - timedelta(seconds=1))
    future = metadata(SHA_F, now + timedelta(seconds=1))
    source = FakeActivitySource(
        repositories=repositories,
        commits={
            1: (owner_today, other_author, owner_at_cutoff, before_cutoff, future),
            2: (owner_today, owner_two_days_ago),
            3: (owner_today, owner_two_days_ago),
            4: (metadata("1" * 40, now),),
        },
        changes={
            SHA_A: (
                FileChange("src/app.py", 10, 2),
                FileChange("README.md", 100, 20),
                FileChange("package-lock.json", 200, 40),
                FileChange("vendor/library.py", 50, 5),
            ),
            SHA_C: (FileChange("generated/client.py", 30, 3),),
            SHA_D: (
                FileChange("web/component.ts", 7, 1),
                FileChange("src/binary.py", 8, 4, binary=True),
            ),
        },
    )
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"OWNER@example.invalid"}),
        excluded_repositories=frozenset({"OCTOCAT/excluded-fixture"}),
    )

    report = CollectActivity(
        StaticConfigurationProvider(configuration), source, FixedClock(now)
    ).execute()

    assert len(report.days) == 365
    assert report.days[0].day == first_day
    assert report.days[0].commits == 1
    assert report.days[0].added_lines == 0
    assert report.days[0].deleted_lines == 0
    today = report.days[-1]
    assert today.day == now.astimezone(local_timezone).date()
    assert today.commits == 1
    assert today.added_lines == 10
    assert today.deleted_lines == 2
    two_days_ago = next(day for day in report.days if day.day.isoformat() == "2026-08-08")
    assert two_days_ago.commits == 1
    assert two_days_ago.added_lines == 7
    assert two_days_ago.deleted_lines == 1
    assert report.totals(365).commits == 3
    assert report.totals(365).added_lines == 17
    assert report.totals(365).deleted_lines == 3

    assert {repository_id for repository_id, _, _ in source.history_calls} == {1, 2, 3}
    assert all(since == cutoff and until == now for _, since, until in source.history_calls)
    assert [sha for _, sha in source.change_calls].count(SHA_A) == 1
    assert [sha for _, sha in source.change_calls].count(SHA_D) == 1
    assert {sha for _, sha in source.change_calls} == {SHA_A, SHA_C, SHA_D}


def test_collect_activity_rejects_conflicting_duplicate_sha_without_private_data() -> None:
    now = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    repositories = (
        RepositoryReference(1, "fixture-org/first-private", private=True),
        RepositoryReference(2, "fixture-org/second-private", private=True),
    )
    source = FakeActivitySource(
        repositories,
        {
            1: (metadata(SHA_A, now, "owner@example.invalid"),),
            2: (metadata(SHA_A, now, "conflict@example.invalid"),),
        },
        {SHA_A: ()},
    )
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"owner@example.invalid"}),
    )

    with pytest.raises(CollectionError) as captured:
        CollectActivity(
            StaticConfigurationProvider(configuration), source, FixedClock(now)
        ).execute()

    message = str(captured.value)
    assert "SHA" in message
    assert "fixture-org" not in message
    assert "example.invalid" not in message


def test_collect_activity_requires_timezone_aware_clock() -> None:
    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({"owner@example.invalid"}),
    )
    source = FakeActivitySource((), {}, {})

    with pytest.raises(CollectionError, match="часового пояса"):
        CollectActivity(
            StaticConfigurationProvider(configuration),
            source,
            FixedClock(datetime(2026, 8, 10, 9, 0)),
        ).execute()
