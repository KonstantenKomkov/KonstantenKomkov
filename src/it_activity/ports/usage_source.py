"""Port for period-aware activity and repository manifests."""

from collections.abc import Sequence
from typing import Protocol

from it_activity.domain.activity import RepositoryReference
from it_activity.ports.activity_source import ActivitySource


class UsageSource(ActivitySource, Protocol):
    """Read activity and expose only bounded language and technology inputs."""

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        """Return only sanitized markers from the explicit manifest allowlist."""
