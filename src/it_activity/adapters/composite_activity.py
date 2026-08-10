"""Combine repository activity sources without exposing their private identities."""

from collections.abc import Iterable, Sequence
from datetime import datetime

from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference
from it_activity.ports.activity_source import ActivitySource, ActivitySourceError


class CompositeActivitySource:
    """Expose a deterministic, source-precedence union of repository histories."""

    def __init__(self, sources: Sequence[ActivitySource]) -> None:
        if not sources:
            raise ValueError("At least one activity source is required")
        self._sources = tuple(sources)
        self._owner_login: str | None = None
        self._repositories: tuple[RepositoryReference, ...] | None = None
        self._repository_sources: dict[int, ActivitySource] = {}
        self._repositories_by_id: dict[int, RepositoryReference] = {}

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        """Return a union where an earlier source wins for the same full name."""
        normalized_owner = owner_login.casefold()
        if self._owner_login is not None:
            if normalized_owner != self._owner_login:
                raise ActivitySourceError("Источники активности настроены для другого аккаунта.")
            if self._repositories is None:
                raise ActivitySourceError("Не удалось собрать полный список репозиториев.")
            return self._repositories

        repositories_by_id: dict[int, RepositoryReference] = {}
        repository_ids_by_name: dict[str, int] = {}
        repository_sources: dict[int, ActivitySource] = {}

        for source in self._sources:
            for repository in source.list_repositories(owner_login):
                normalized_name = repository.full_name.casefold()
                existing = repositories_by_id.get(repository.repository_id)
                existing_id = repository_ids_by_name.get(normalized_name)
                if existing is not None and existing.full_name.casefold() != normalized_name:
                    raise ActivitySourceError(
                        "Источники активности вернули противоречивые данные репозиториев."
                    )
                if existing_id is not None:
                    continue
                if existing is not None and existing != repository:
                    raise ActivitySourceError(
                        "Источники активности вернули противоречивые данные репозиториев."
                    )
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
        """Read commits from the selected source for a verified repository."""
        return self._source_for(repository).iter_commits(repository, since, until)

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        """Read a commit diff from the selected source for a verified repository."""
        return self._source_for(repository).get_file_changes(repository, commit_sha)

    def _source_for(self, repository: RepositoryReference) -> ActivitySource:
        expected = self._repositories_by_id.get(repository.repository_id)
        source = self._repository_sources.get(repository.repository_id)
        if expected is None or source is None or expected != repository:
            raise ActivitySourceError("Репозиторий отсутствует в проверенном списке источников.")
        return source
