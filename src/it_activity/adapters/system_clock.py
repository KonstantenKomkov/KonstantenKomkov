"""System clock adapter."""

from datetime import datetime, timezone


class SystemClock:
    """Return one stable process-assembly instant in UTC."""

    def __init__(self) -> None:
        self._current = datetime.now(timezone.utc)

    def now(self) -> datetime:
        """Return the captured timezone-aware timestamp."""
        return self._current
