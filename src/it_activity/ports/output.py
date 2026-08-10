"""Port for publishing generated public files."""

from collections.abc import Mapping
from typing import Protocol


class PublicOutputError(RuntimeError):
    """A safe failure while writing public generated files."""


class PublicOutputWriter(Protocol):
    """Write the fixed public artifact set and report the number changed."""

    def write(self, artifacts: Mapping[str, str]) -> int:
        """Atomically replace changed files and return their count."""
