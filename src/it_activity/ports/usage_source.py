"""Port for period-aware GitHub Linguist data and repository manifests."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Protocol

from it_activity.domain.activity import CommitMetadata, RepositoryReference


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

    def get_language_bytes(self, repository: RepositoryReference) -> Mapping[str, int]:
        """Return GitHub Linguist byte counts for one repository."""

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        """Return only sanitized markers from the explicit manifest allowlist."""
