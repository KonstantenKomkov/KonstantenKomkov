"""Use case for safely validating external configuration."""

from dataclasses import dataclass

from it_activity.ports.configuration import ConfigurationProvider


@dataclass(frozen=True)
class ConfigurationSummary:
    """Public-only summary suitable for logs and command output."""

    github_login: str
    timezone: str
    author_identity_count: int
    exclusion_count: int


class ValidateConfiguration:
    """Load configuration and expose only non-sensitive validation details."""

    def __init__(self, provider: ConfigurationProvider) -> None:
        self._provider = provider

    def execute(self) -> ConfigurationSummary:
        """Validate and return a public summary."""
        configuration = self._provider.load()
        return ConfigurationSummary(
            github_login=configuration.github_login,
            timezone=configuration.timezone,
            author_identity_count=len(configuration.author_emails),
            exclusion_count=len(configuration.excluded_repositories),
        )
