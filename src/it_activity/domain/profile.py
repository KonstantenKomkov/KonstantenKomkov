"""Public profile artifact contract."""

SUPPORTED_PERIODS = (7, 30, 365)
DEFAULT_OPEN_PERIOD = 30

README_PATH = "README.md"
USAGE_SVG_PATH = "generated/usage.svg"


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
