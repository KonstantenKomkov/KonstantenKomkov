"""Use case for collecting globally deduplicated daily activity."""

from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from it_activity.domain.activity import (
    MAX_HISTORY_DAYS,
    ActivityDataError,
    ActivityReport,
    CommitMetadata,
    DailyActivity,
    RepositoryReference,
)
from it_activity.domain.source_files import FileCategory, classify_file
from it_activity.ports.activity_source import ActivitySource
from it_activity.ports.clock import Clock
from it_activity.ports.configuration import ConfigurationProvider


class CollectionError(RuntimeError):
    """A safe-to-display failure that prevents complete aggregation."""


class CollectActivity:
    """Aggregate owner-authored commits across every available repository."""

    def __init__(
        self,
        configuration_provider: ConfigurationProvider,
        activity_source: ActivitySource,
        clock: Clock,
    ) -> None:
        self._configuration_provider = configuration_provider
        self._activity_source = activity_source
        self._clock = clock

    def execute(self) -> ActivityReport:
        """Return exactly 365 configured calendar days of public aggregates."""
        configuration = self._configuration_provider.load()
        now = self._clock.now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise CollectionError("Системные часы вернули дату без часового пояса.")

        configured_timezone = ZoneInfo(configuration.timezone)
        local_now = now.astimezone(configured_timezone)
        first_day = local_now.date() - timedelta(days=MAX_HISTORY_DAYS - 1)
        since = datetime.combine(first_day, time.min, configured_timezone).astimezone(timezone.utc)
        until = now.astimezone(timezone.utc)
        daily = {
            first_day + timedelta(days=offset): DailyActivity(
                day=first_day + timedelta(days=offset)
            )
            for offset in range(MAX_HISTORY_DAYS)
        }

        repositories = self._validated_repositories(configuration.github_login)
        excluded = {name.casefold() for name in configuration.excluded_repositories}
        seen_commits: dict[str, tuple[str, datetime]] = {}

        for repository in sorted(
            repositories,
            key=lambda item: (item.full_name.casefold(), item.repository_id),
        ):
            if repository.full_name.casefold() in excluded:
                continue
            for commit in self._activity_source.iter_commits(repository, since, until):
                identity = (commit.author_email, commit.authored_at)
                previous_identity = seen_commits.get(commit.sha)
                if previous_identity is not None:
                    if previous_identity != identity:
                        raise CollectionError("Одинаковый SHA содержит противоречивые метаданные.")
                    continue
                seen_commits[commit.sha] = identity

                authored_at = commit.authored_at.astimezone(timezone.utc)
                if authored_at < since or authored_at > until:
                    continue
                if commit.author_email not in configuration.author_emails:
                    continue

                local_day = commit.authored_at.astimezone(configured_timezone).date()
                current = daily.get(local_day)
                if current is None:
                    continue
                added_lines, deleted_lines = self._source_line_counts(repository, commit)
                daily[local_day] = replace(
                    current,
                    commits=current.commits + 1,
                    added_lines=current.added_lines + added_lines,
                    deleted_lines=current.deleted_lines + deleted_lines,
                )

        return ActivityReport(
            timezone=configuration.timezone,
            days=tuple(daily[day] for day in sorted(daily)),
        )

    def _validated_repositories(self, owner_login: str) -> tuple[RepositoryReference, ...]:
        repositories = tuple(self._activity_source.list_repositories(owner_login))
        repository_ids: set[int] = set()
        full_names: set[str] = set()
        for repository in repositories:
            normalized_name = repository.full_name.casefold()
            if repository.repository_id in repository_ids or normalized_name in full_names:
                raise CollectionError("GitHub вернул повторяющийся репозиторий.")
            repository_ids.add(repository.repository_id)
            full_names.add(normalized_name)
        return repositories

    def _source_line_counts(
        self,
        repository: RepositoryReference,
        commit: CommitMetadata,
    ) -> tuple[int, int]:
        try:
            changes = self._activity_source.get_file_changes(repository, commit.sha)
        except ActivityDataError as error:
            raise CollectionError(str(error)) from None
        source_changes = [
            change for change in changes if classify_file(change) is FileCategory.SOURCE
        ]
        return (
            sum(change.additions for change in source_changes),
            sum(change.deletions for change in source_changes),
        )
