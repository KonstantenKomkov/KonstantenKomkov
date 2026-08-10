"""Activity values and invariants."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from re import compile as compile_pattern

MAX_HISTORY_DAYS = 365

_SHA_PATTERN = compile_pattern(r"^[0-9a-fA-F]{40,64}$")


class ActivityDataError(ValueError):
    """A safe-to-display error for invalid activity data."""


@dataclass(frozen=True, repr=False)
class RepositoryReference:
    """Internal reference to a repository without a public representation."""

    repository_id: int
    full_name: str
    private: bool

    def __post_init__(self) -> None:
        components = self.full_name.split("/")
        has_control_character = any(character in self.full_name for character in "\r\n\0")
        if (
            not isinstance(self.repository_id, int)
            or isinstance(self.repository_id, bool)
            or self.repository_id <= 0
            or not isinstance(self.private, bool)
            or len(components) != 2
            or not all(components)
            or has_control_character
        ):
            raise ActivityDataError("Некорректно задан идентификатор репозитория.")


@dataclass(frozen=True, repr=False)
class CommitMetadata:
    """Private commit identity needed to select profile-owner activity."""

    sha: str
    authored_at: datetime
    author_email: str

    def __post_init__(self) -> None:
        sha = self.sha.casefold()
        email = self.author_email.strip().casefold()
        if _SHA_PATTERN.fullmatch(sha) is None:
            raise ActivityDataError("Некорректно задан SHA коммита.")
        if self.authored_at.tzinfo is None or self.authored_at.utcoffset() is None:
            raise ActivityDataError("Дата коммита должна содержать часовой пояс.")
        if any(character in email for character in "\r\n\0"):
            raise ActivityDataError("Некорректно задан email автора коммита.")
        object.__setattr__(self, "sha", sha)
        object.__setattr__(self, "authored_at", self.authored_at.astimezone(timezone.utc))
        object.__setattr__(self, "author_email", email)


@dataclass(frozen=True, repr=False)
class FileChange:
    """Private file-level line counts for one commit."""

    path: str
    additions: int
    deletions: int
    binary: bool = False

    def __post_init__(self) -> None:
        if not self.path or any(character in self.path for character in "\r\n\0"):
            raise ActivityDataError("Некорректно задан путь изменённого файла.")
        if (
            not isinstance(self.additions, int)
            or isinstance(self.additions, bool)
            or not isinstance(self.deletions, int)
            or isinstance(self.deletions, bool)
            or not isinstance(self.binary, bool)
            or self.additions < 0
            or self.deletions < 0
        ):
            raise ActivityDataError("Некорректно задана статистика изменённого файла.")


@dataclass(frozen=True)
class DailyActivity:
    """Public aggregate for one configured calendar day."""

    day: date
    commits: int = 0
    added_lines: int = 0
    deleted_lines: int = 0

    def __post_init__(self) -> None:
        values = (self.commits, self.added_lines, self.deleted_lines)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values
        ):
            raise ActivityDataError("Некорректно заданы дневные агрегаты.")


@dataclass(frozen=True)
class ActivityTotals:
    """Public totals for a trailing period."""

    commits: int
    added_lines: int
    deleted_lines: int


@dataclass(frozen=True)
class ActivityReport:
    """Consecutive public day aggregates in one configured timezone."""

    timezone: str
    days: tuple[DailyActivity, ...]

    def __post_init__(self) -> None:
        if not self.days or len(self.days) > MAX_HISTORY_DAYS:
            raise ActivityDataError("Отчёт должен содержать от 1 до 365 дней.")
        for previous, current in zip(self.days, self.days[1:]):
            if current.day != previous.day + timedelta(days=1):
                raise ActivityDataError("Дни отчёта должны идти подряд.")

    def trailing_days(self, period: int) -> tuple[DailyActivity, ...]:
        """Return a supported trailing subset of the report."""
        if period <= 0 or period > len(self.days):
            raise ActivityDataError("Запрошенный период выходит за границы отчёта.")
        return self.days[-period:]

    def totals(self, period: int) -> ActivityTotals:
        """Sum public activity for a supported trailing period."""
        days = self.trailing_days(period)
        return ActivityTotals(
            commits=sum(day.commits for day in days),
            added_lines=sum(day.added_lines for day in days),
            deleted_lines=sum(day.deleted_lines for day in days),
        )
