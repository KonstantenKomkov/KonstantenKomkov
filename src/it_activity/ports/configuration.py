"""Port for loading profile configuration."""

from typing import Protocol

from it_activity.domain.configuration import ProfileConfiguration


class ConfigurationProvider(Protocol):
    """Load validated profile configuration from an external source."""

    def load(self) -> ProfileConfiguration:
        """Return validated configuration without logging private values."""
