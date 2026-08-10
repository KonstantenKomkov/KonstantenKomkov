"""Combine independently scoped GitHub credentials behind one source port."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Protocol

from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference
from it_activity.ports.activity_source import ActivitySource, ActivitySourceError
from it_activity.ports.usage_source import UsageSource


class _ProfileSource(ActivitySource, UsageSource, Protocol):
    """Complete input contract implemented by each credential-scoped source."""


class CompositeGitHubActivitySource:
    """Expose the deterministic union of repositories visible to several tokens."""

    def __init__(self, sources: Sequence[_ProfileSource]) -> None:
        if not sources:
            raise ValueError("At least one GitHub activity source is required")
        self._sources = tuple(sources)
        self._owner_login: str | None = None
        self._repositories: tuple[RepositoryReference, ...] | None = None
        self._repository_sources: dict[int, _ProfileSource] = {}
        self._repositories_by_id: dict[int, RepositoryReference] = {}

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        """Return a conflict-checked union without duplicate repositories."""
        normalized_owner = owner_login.casefold()
        if self._owner_login is not None:
            if normalized_owner != self._owner_login:
                raise ActivitySourceError("Источники GitHub настроены для другого аккаунта.")
            if self._repositories is None:
                raise ActivitySourceError("Не удалось собрать полный список репозиториев GitHub.")
            return self._repositories

        repositories_by_id: dict[int, RepositoryReference] = {}
        repository_ids_by_name: dict[str, int] = {}
        repository_sources: dict[int, _ProfileSource] = {}

        for source in self._sources:
            for repository in source.list_repositories(owner_login):
                normalized_name = repository.full_name.casefold()
                existing = repositories_by_id.get(repository.repository_id)
                existing_id = repository_ids_by_name.get(normalized_name)
                if (existing is not None and existing != repository) or (
                    existing_id is not None and existing_id != repository.repository_id
                ):
                    raise ActivitySourceError("GitHub вернул противоречивые данные репозиториев.")
                if existing is None:
                    repositories_by_id[repository.repository_id] = repository
                    repository_ids_by_name[normalized_name] = repository.repository_id
                    repository_sources[repository.repository_id] = source

        repositories = tuple(
            sorted(
                repositories_by_id.values(),
                key=lambda item: (item.full_name.casefold(), item.repository_id),
            )
        )
        self._owner_login = normalized_owner
        self._repositories = repositories
        self._repository_sources = repository_sources
        self._repositories_by_id = repositories_by_id
        return repositories

    def iter_commits(
        self,
        repository: RepositoryReference,
        since: datetime,
        until: datetime,
    ) -> Iterable[CommitMetadata]:
        """Read commits using a token that advertised access to the repository."""
        return self._source_for(repository).iter_commits(repository, since, until)

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        """Read a commit diff through the repository's selected source."""
        return self._source_for(repository).get_file_changes(repository, commit_sha)

    def get_language_bytes(self, repository: RepositoryReference) -> Mapping[str, int]:
        """Read Linguist data through the repository's selected source."""
        return self._source_for(repository).get_language_bytes(repository)

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        """Read allowlisted manifest markers through the selected source."""
        return self._source_for(repository).list_manifest_markers(repository)

    def _source_for(self, repository: RepositoryReference) -> _ProfileSource:
        expected = self._repositories_by_id.get(repository.repository_id)
        source = self._repository_sources.get(repository.repository_id)
        if expected is None or source is None or expected != repository:
            raise ActivitySourceError("Репозиторий отсутствует в проверенном списке GitHub.")
        return source
