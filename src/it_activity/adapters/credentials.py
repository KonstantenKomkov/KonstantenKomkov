"""Environment-backed credential loading without value disclosure."""

import os
from collections.abc import Mapping

from it_activity.domain.configuration import ConfigurationError

GITHUB_READ_TOKEN_VARIABLE = "IT_ACTIVITY_GITHUB_READ_TOKEN"  # noqa: S105
GITHUB_ADDITIONAL_READ_TOKENS_VARIABLE = "IT_ACTIVITY_GITHUB_ADDITIONAL_READ_TOKENS"


class EnvironmentGitHubTokensProvider:
    """Read one or more private-repository credentials from process environment."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def load(self) -> tuple[str, ...]:
        """Return header-safe tokens without placing their values in an exception."""
        primary_token = self._environ.get(GITHUB_READ_TOKEN_VARIABLE, "")
        if not primary_token:
            raise ConfigurationError(
                f"Не задана переменная окружения {GITHUB_READ_TOKEN_VARIABLE}."
            )

        raw_additional_tokens = self._environ.get(
            GITHUB_ADDITIONAL_READ_TOKENS_VARIABLE,
            "",
        )
        additional_tokens = tuple(line for line in raw_additional_tokens.splitlines() if line)
        tokens = (primary_token, *additional_tokens)
        if any(
            token != token.strip() or any(character.isspace() for character in token)
            for token in tokens
        ):
            raise ConfigurationError("Некорректно задан токен чтения GitHub.")
        if len(set(tokens)) != len(tokens):
            raise ConfigurationError("Токены чтения GitHub не должны повторяться.")
        return tokens
