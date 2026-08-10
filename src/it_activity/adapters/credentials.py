"""Environment-backed credential loading without value disclosure."""

import os
from collections.abc import Mapping

from it_activity.domain.configuration import ConfigurationError

GITHUB_READ_TOKEN_VARIABLE = "IT_ACTIVITY_GITHUB_READ_TOKEN"  # noqa: S105


class EnvironmentGitHubTokenProvider:
    """Read the private-repository credential from process environment."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def load(self) -> str:
        """Return a header-safe token without placing it in an exception."""
        token = self._environ.get(GITHUB_READ_TOKEN_VARIABLE, "")
        if not token:
            raise ConfigurationError(
                f"Не задана переменная окружения {GITHUB_READ_TOKEN_VARIABLE}."
            )
        if token != token.strip() or any(character.isspace() for character in token):
            raise ConfigurationError("Некорректно задан токен чтения GitHub.")
        return token
