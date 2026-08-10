"""Clock port used to make period boundaries deterministic."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Provide the current timezone-aware timestamp."""

    def now(self) -> datetime:
        """Return the current instant."""
