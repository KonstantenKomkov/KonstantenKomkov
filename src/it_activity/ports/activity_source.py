"""Port for complete repository and commit activity collection."""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Protocol

from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference


class ActivitySourceError(RuntimeError):
    """A safe external-source failure that prevents complete aggregation."""


class ActivitySource(Protocol):
    """Read all repositories configured for one bounded activity source."""

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        """Return every public and private repository available to the source."""

    def iter_commits(
        self,
        repository: RepositoryReference,
        since: datetime,
        until: datetime,
    ) -> Iterable[CommitMetadata]:
        """Yield commits from every current branch within the requested bounds."""

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        """Return a complete file diff for one commit."""
