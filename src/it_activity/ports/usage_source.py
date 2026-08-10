"""Port for GitHub Linguist data and allowlisted repository manifests."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from it_activity.domain.activity import RepositoryReference


class UsageSource(Protocol):
    """Read private repository metadata and expose only bounded aggregate inputs."""

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        """Return every repository visible to the configured account."""

    def get_language_bytes(self, repository: RepositoryReference) -> Mapping[str, int]:
        """Return GitHub Linguist byte counts for one repository."""

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        """Return only sanitized markers from the explicit manifest allowlist."""
