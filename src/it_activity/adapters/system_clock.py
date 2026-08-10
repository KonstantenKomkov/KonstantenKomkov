"""System clock adapter."""

from datetime import datetime, timezone


class SystemClock:
    """Return the real current instant in UTC."""

    def now(self) -> datetime:
        """Return a timezone-aware timestamp."""
        return datetime.now(timezone.utc)
