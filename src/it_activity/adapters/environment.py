"""Environment-backed configuration adapter."""

import os
from collections.abc import Mapping
from typing import Optional

from it_activity.domain.configuration import (
    DEFAULT_TIMEZONE,
    ConfigurationError,
    ProfileConfiguration,
)

GITHUB_LOGIN_VARIABLE = "IT_ACTIVITY_GITHUB_LOGIN"
AUTHOR_EMAILS_VARIABLE = "IT_ACTIVITY_AUTHOR_EMAILS"
TIMEZONE_VARIABLE = "IT_ACTIVITY_TIMEZONE"
EXCLUSIONS_VARIABLE = "IT_ACTIVITY_EXCLUDED_REPOSITORIES"


class EnvironmentConfigurationProvider:
    """Read profile settings from process environment variables."""

    def __init__(self, environ: Optional[Mapping[str, str]] = None) -> None:
        self._environ = os.environ if environ is None else environ

    def load(self) -> ProfileConfiguration:
        """Load and validate configuration without exposing raw values."""
        github_login = self._required(GITHUB_LOGIN_VARIABLE)
        author_emails = frozenset(self._split(self._required(AUTHOR_EMAILS_VARIABLE)))
        timezone = self._environ.get(TIMEZONE_VARIABLE, DEFAULT_TIMEZONE)
        exclusions = frozenset(self._split(self._environ.get(EXCLUSIONS_VARIABLE, "")))

        return ProfileConfiguration(
            github_login=github_login,
            author_emails=author_emails,
            timezone=timezone,
            excluded_repositories=exclusions,
        )

    def _required(self, variable: str) -> str:
        value = self._environ.get(variable, "").strip()
        if not value:
            raise ConfigurationError(f"Не задана переменная окружения {variable}.")
        return value

    @staticmethod
    def _split(value: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in value.split(",") if item.strip())
