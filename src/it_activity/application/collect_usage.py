"""Use case for aggregating public-safe language and technology usage."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from it_activity.domain.activity import MAX_HISTORY_DAYS, RepositoryReference
from it_activity.domain.source_files import source_language
from it_activity.domain.usage import (
    UsageDataError,
    UsageReport,
    build_usage_report,
    detect_technologies,
)
from it_activity.ports.clock import Clock
from it_activity.ports.configuration import ConfigurationProvider
from it_activity.ports.usage_source import UsageSource


class UsageCollectionError(RuntimeError):
    """A safe failure that prevents complete usage aggregation."""


class CollectUsage:
    """Aggregate usage across repositories active during the trailing year."""

    def __init__(
        self,
        configuration_provider: ConfigurationProvider,
        usage_source: UsageSource,
        clock: Clock,
    ) -> None:
        self._configuration_provider = configuration_provider
        self._usage_source = usage_source
        self._clock = clock

    def execute(self) -> UsageReport:
        """Return annual allowlisted names, shares, and repository frequencies."""
        configuration = self._configuration_provider.load()
        now = self._clock.now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise UsageCollectionError("Системные часы вернули дату без часового пояса.")

        configured_timezone = ZoneInfo(configuration.timezone)
        local_now = now.astimezone(configured_timezone)
        first_day = local_now.date() - timedelta(days=MAX_HISTORY_DAYS - 1)
        since = datetime.combine(first_day, time.min, configured_timezone).astimezone(timezone.utc)
        until = now.astimezone(timezone.utc)

        repositories = self._validated_repositories(
            configuration.github_login,
            configuration.expected_repositories,
        )
        excluded = {name.casefold() for name in configuration.excluded_repositories}
        candidates = tuple(
            repository
            for repository in sorted(
                repositories,
                key=lambda item: (item.full_name.casefold(), item.repository_id),
            )
            if repository.full_name.casefold() not in excluded
        )
        included, language_days = self._annual_repository_and_language_activity(
            candidates,
            configuration.author_emails,
            since,
            until,
            configured_timezone,
        )
        technology_counts: dict[str, int] = {}

        for repository in included:
            try:
                technologies = detect_technologies(
                    self._usage_source.list_manifest_markers(repository)
                )
            except UsageDataError as error:
                raise UsageCollectionError(str(error)) from None
            for technology in technologies:
                technology_counts[technology] = technology_counts.get(technology, 0) + 1

        try:
            return build_usage_report(
                {language: len(days) for language, days in language_days.items()},
                technology_counts,
                len(included),
            )
        except UsageDataError as error:
            raise UsageCollectionError(str(error)) from None

    def _annual_repository_and_language_activity(
        self,
        repositories: tuple[RepositoryReference, ...],
        author_emails: frozenset[str],
        since: datetime,
        until: datetime,
        configured_timezone: ZoneInfo,
    ) -> tuple[tuple[RepositoryReference, ...], dict[str, set[date]]]:
        active: list[RepositoryReference] = []
        seen_commits: dict[str, tuple[str, datetime]] = {}
        language_days: dict[str, set[date]] = {}

        for repository in repositories:
            if repository.empty:
                continue
            owner_activity = False
            for commit in self._usage_source.iter_commits(repository, since, until):
                identity = (commit.author_email, commit.authored_at)
                previous_identity = seen_commits.get(commit.sha)
                if previous_identity is not None:
                    if previous_identity != identity:
                        raise UsageCollectionError(
                            "Одинаковый SHA содержит противоречивые метаданные."
                        )
                    continue
                seen_commits[commit.sha] = identity

                authored_at = commit.authored_at.astimezone(timezone.utc)
                if authored_at < since or authored_at > until:
                    continue
                if commit.author_email in author_emails:
                    owner_activity = True
                    local_day = commit.authored_at.astimezone(configured_timezone).date()
                    commit_languages = {
                        language
                        for change in self._usage_source.get_file_changes(repository, commit.sha)
                        if change.additions + change.deletions > 0
                        if (language := source_language(change)) is not None
                    }
                    for language in commit_languages:
                        language_days.setdefault(language, set()).add(local_day)
            if owner_activity:
                active.append(repository)

        return tuple(active), language_days

    def _validated_repositories(
        self,
        owner_login: str,
        expected_repositories: frozenset[str],
    ) -> tuple[RepositoryReference, ...]:
        repositories = tuple(self._usage_source.list_repositories(owner_login))
        repository_ids: set[int] = set()
        full_names: set[str] = set()
        for repository in repositories:
            normalized_name = repository.full_name.casefold()
            if repository.repository_id in repository_ids or normalized_name in full_names:
                raise UsageCollectionError(
                    "Источники активности вернули повторяющийся репозиторий."
                )
            repository_ids.add(repository.repository_id)
            full_names.add(normalized_name)
        expected = {repository.casefold() for repository in expected_repositories}
        if not expected.issubset(full_names):
            raise UsageCollectionError(
                "Источники активности не предоставили доступ ко всем ожидаемым репозиториям."
            )
        return repositories
