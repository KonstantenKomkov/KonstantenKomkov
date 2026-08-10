"""Use case for aggregating public-safe language and technology usage."""

from it_activity.domain.activity import RepositoryReference
from it_activity.domain.usage import (
    UsageDataError,
    UsageReport,
    build_usage_report,
    detect_technologies,
)
from it_activity.ports.configuration import ConfigurationProvider
from it_activity.ports.usage_source import UsageSource


class UsageCollectionError(RuntimeError):
    """A safe failure that prevents complete usage aggregation."""


class CollectUsage:
    """Aggregate Linguist languages and allowlisted technologies across repositories."""

    def __init__(
        self,
        configuration_provider: ConfigurationProvider,
        usage_source: UsageSource,
    ) -> None:
        self._configuration_provider = configuration_provider
        self._usage_source = usage_source

    def execute(self) -> UsageReport:
        """Return only allowlisted names, shares, and repository frequencies."""
        configuration = self._configuration_provider.load()
        repositories = self._validated_repositories(
            configuration.github_login,
            configuration.expected_repositories,
        )
        excluded = {name.casefold() for name in configuration.excluded_repositories}
        included = tuple(
            repository
            for repository in sorted(
                repositories,
                key=lambda item: (item.full_name.casefold(), item.repository_id),
            )
            if repository.full_name.casefold() not in excluded
        )
        language_bytes: dict[str, int] = {}
        technology_counts: dict[str, int] = {}

        for repository in included:
            if repository.empty:
                continue
            for language, byte_count in self._usage_source.get_language_bytes(repository).items():
                if (
                    not isinstance(language, str)
                    or not isinstance(byte_count, int)
                    or isinstance(byte_count, bool)
                    or byte_count < 0
                ):
                    raise UsageCollectionError("GitHub вернул некорректную языковую статистику.")
                language_bytes[language] = language_bytes.get(language, 0) + byte_count
            try:
                technologies = detect_technologies(
                    self._usage_source.list_manifest_markers(repository)
                )
            except UsageDataError as error:
                raise UsageCollectionError(str(error)) from None
            for technology in technologies:
                technology_counts[technology] = technology_counts.get(technology, 0) + 1

        try:
            return build_usage_report(language_bytes, technology_counts, len(included))
        except UsageDataError as error:
            raise UsageCollectionError(str(error)) from None

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
                raise UsageCollectionError("GitHub вернул повторяющийся репозиторий.")
            repository_ids.add(repository.repository_id)
            full_names.add(normalized_name)
        expected = {repository.casefold() for repository in expected_repositories}
        if not expected.issubset(full_names):
            raise UsageCollectionError(
                "GitHub не предоставил доступ ко всем ожидаемым репозиториям."
            )
        return repositories
