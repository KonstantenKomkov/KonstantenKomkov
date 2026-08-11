"""Port for period-aware GitHub Linguist data and repository manifests."""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Protocol

from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference


class UsageSource(Protocol):
    """Read activity and expose only bounded language and technology inputs."""

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        """Return every repository visible to the configured account."""

    def iter_commits(
        self,
        repository: RepositoryReference,
        since: datetime,
        until: datetime,
    ) -> Iterable[CommitMetadata]:
        """Yield commits used to select repositories active during the usage period."""

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        """Return a complete diff used to identify active language days."""

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        """Return only sanitized markers from the explicit manifest allowlist."""
