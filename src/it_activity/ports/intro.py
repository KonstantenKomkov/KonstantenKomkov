"""Port for reading the owner-authored profile intro."""

from typing import Protocol

from it_activity.domain.profile import ProfileIntro


class ProfileIntroSourceError(RuntimeError):
    """A safe failure while reading the owner-authored profile intro."""


class ProfileIntroSource(Protocol):
    """Provide the validated Markdown rendered above the generated charts."""

    def load(self) -> ProfileIntro:
        """Return the intro, or an empty intro when none is published."""
