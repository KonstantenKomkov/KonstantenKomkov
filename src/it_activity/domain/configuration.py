"""Configuration values that are independent from their external source."""

from dataclasses import dataclass, field
from re import compile as compile_pattern
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Europe/Moscow"

_GITHUB_LOGIN_PATTERN = compile_pattern(r"^(?!-)(?!.*--)[A-Za-z0-9-]{1,39}(?<!-)$")
_EMAIL_PATTERN = compile_pattern(r"^[^@\s]+@[^@\s]+$")
_REPOSITORY_NAME_PATTERN = compile_pattern(r"^[A-Za-z0-9._-]{1,100}$")


def valid_repository_full_name(value: str) -> bool:
    """Return whether a value is a canonical GitHub owner/repository name."""
    components = value.split("/")
    return (
        len(components) == 2
        and _GITHUB_LOGIN_PATTERN.fullmatch(components[0]) is not None
        and _REPOSITORY_NAME_PATTERN.fullmatch(components[1]) is not None
    )


class ConfigurationError(ValueError):
    """A safe-to-display configuration validation error."""


@dataclass(frozen=True, repr=False)
class ProfileConfiguration:
    """Validated owner configuration without credential data."""

    github_login: str
    author_emails: frozenset[str]
    expected_repositories: frozenset[str]
    timezone: str = DEFAULT_TIMEZONE
    excluded_repositories: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        login = self.github_login.strip()
        emails = frozenset(
            email.strip().casefold() for email in self.author_emails if email.strip()
        )
        timezone = self.timezone.strip()
        exclusions = frozenset(
            repository.strip() for repository in self.excluded_repositories if repository.strip()
        )
        expected = frozenset(
            repository.strip() for repository in self.expected_repositories if repository.strip()
        )

        if _GITHUB_LOGIN_PATTERN.fullmatch(login) is None:
            raise ConfigurationError("Некорректно задан GitHub login.")
        if not emails:
            raise ConfigurationError("Не задано ни одного авторского email.")
        if any(_EMAIL_PATTERN.fullmatch(email) is None for email in emails):
            raise ConfigurationError("Некорректно задан список авторских email.")
        if not expected:
            raise ConfigurationError("Не задано ни одного ожидаемого репозитория.")
        if any(not valid_repository_full_name(repository) for repository in exclusions):
            raise ConfigurationError("Некорректно задан список исключений.")
        if any(not valid_repository_full_name(repository) for repository in expected):
            raise ConfigurationError("Некорректно задан список ожидаемых репозиториев.")

        try:
            ZoneInfo(timezone)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise ConfigurationError("Некорректно задан часовой пояс.") from error

        object.__setattr__(self, "github_login", login)
        object.__setattr__(self, "author_emails", emails)
        object.__setattr__(self, "timezone", timezone)
        object.__setattr__(self, "excluded_repositories", exclusions)
        object.__setattr__(self, "expected_repositories", expected)
