"""Public profile artifact contract."""

from dataclasses import dataclass

SUPPORTED_PERIODS = (7, 30, 365)
DEFAULT_OPEN_PERIOD = 30

README_PATH = "README.md"
USAGE_SVG_PATH = "generated/usage.svg"
INTRO_SOURCE_PATH = "about.md"

MAX_INTRO_CHARACTERS = 2000
_FORBIDDEN_INTRO_FRAGMENTS = ("<script", "javascript:", "<iframe", "<style")


class ProfileIntroError(ValueError):
    """A safe-to-display validation error for the owner-authored intro."""


@dataclass(frozen=True)
class ProfileIntro:
    """Owner-authored Markdown shown above the generated charts."""

    markdown: str

    def __post_init__(self) -> None:
        markdown = self.markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(markdown) > MAX_INTRO_CHARACTERS:
            raise ProfileIntroError("Текст описания профиля слишком длинный.")
        if any(character < " " and character != "\n" for character in markdown):
            raise ProfileIntroError("Текст описания профиля содержит управляющие символы.")
        folded = markdown.casefold()
        if any(fragment in folded for fragment in _FORBIDDEN_INTRO_FRAGMENTS):
            raise ProfileIntroError("Текст описания профиля содержит запрещённую разметку.")
        object.__setattr__(self, "markdown", markdown)

    @property
    def is_empty(self) -> bool:
        """Return whether there is nothing to render above the charts."""
        return not self.markdown

    @classmethod
    def empty(cls) -> "ProfileIntro":
        """Return the intro used when the owner published no description."""
        return cls(markdown="")


def _validate_period(period: int) -> None:
    if period not in SUPPORTED_PERIODS:
        raise ValueError("Unsupported profile period")


def commits_svg_path(period: int) -> str:
    """Return the fixed public path for a commit chart."""
    _validate_period(period)
    return f"generated/commits-{period}.svg"


def lines_svg_path(period: int) -> str:
    """Return the fixed public path for a line chart."""
    _validate_period(period)
    return f"generated/lines-{period}.svg"


PUBLIC_OUTPUT_PATHS = frozenset(
    {
        README_PATH,
        USAGE_SVG_PATH,
        *(commits_svg_path(period) for period in SUPPORTED_PERIODS),
        *(lines_svg_path(period) for period in SUPPORTED_PERIODS),
    }
)
