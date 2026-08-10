"""Port for deterministic public profile rendering."""

from collections.abc import Mapping
from typing import Protocol

from it_activity.domain.activity import ActivityReport
from it_activity.domain.usage import UsageReport


class ProfileRenderingError(RuntimeError):
    """A safe failure while rendering public profile artifacts."""


class ProfileRenderer(Protocol):
    """Render the complete fixed set of public Markdown and SVG artifacts."""

    def render(
        self,
        activity: ActivityReport,
        usage: UsageReport,
    ) -> Mapping[str, str]:
        """Return deterministic UTF-8 text keyed by allowlisted relative path."""
