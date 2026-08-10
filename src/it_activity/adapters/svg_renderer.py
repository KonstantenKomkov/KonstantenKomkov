"""Deterministic responsive SVG and GitHub README rendering."""

from collections.abc import Mapping, Sequence
from html import escape

from it_activity.domain.activity import ActivityDataError, ActivityReport, DailyActivity
from it_activity.domain.profile import (
    DEFAULT_OPEN_PERIOD,
    README_PATH,
    SUPPORTED_PERIODS,
    USAGE_SVG_PATH,
    commits_svg_path,
    lines_svg_path,
)
from it_activity.domain.usage import LanguageUsage, TechnologyUsage, UsageReport
from it_activity.ports.rendering import ProfileRenderingError

CARD_WIDTH = 720
CHART_HEIGHT = 260
CHART_LEFT = 54.0
CHART_RIGHT = 696.0
CHART_TOP = 88.0
CHART_BOTTOM = 210.0

_SVG_STYLE = """
text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1f2328; }
.surface { fill: #ffffff; stroke: #d0d7de; }
.title { font-size: 21px; font-weight: 650; }
.metric { font-size: 14px; font-weight: 600; }
.label { font-size: 12px; }
.muted { fill: #656d76; }
.grid { stroke: #d8dee4; stroke-width: 1; }
.track { fill: #eaeef2; }
.commit-bar { fill: #2f81f7; }
.added-line { fill: none; stroke: #1a7f37; }
.deleted-line { fill: none; stroke: #cf222e; }
.added-marker { fill: #1a7f37; stroke: #1a7f37; }
.deleted-marker { fill: #cf222e; stroke: #cf222e; }
.added-text { fill: #1a7f37; }
.deleted-text { fill: #cf222e; }
.language { fill: #8250df; }
.technology { fill: #0969da; }
@media (prefers-color-scheme: dark) {
  text { fill: #f0f6fc; }
  .surface { fill: #0d1117; stroke: #30363d; }
  .muted { fill: #8b949e; }
  .grid { stroke: #30363d; }
  .track { fill: #21262d; }
  .commit-bar { fill: #58a6ff; }
  .added-line { stroke: #3fb950; }
  .deleted-line { stroke: #f85149; }
  .added-marker { fill: #3fb950; stroke: #3fb950; }
  .deleted-marker { fill: #f85149; stroke: #f85149; }
  .added-text { fill: #3fb950; }
  .deleted-text { fill: #f85149; }
  .language { fill: #a371f7; }
  .technology { fill: #58a6ff; }
}
""".strip()


class SvgProfileRenderer:
    """Render public aggregates without repository-level input or external assets."""

    def render(
        self,
        activity: ActivityReport,
        usage: UsageReport,
    ) -> Mapping[str, str]:
        """Return the complete fixed profile artifact set."""
        artifacts: dict[str, str] = {README_PATH: self._render_readme()}
        try:
            for period in SUPPORTED_PERIODS:
                days = activity.trailing_days(period)
                artifacts[commits_svg_path(period)] = self._render_commits(days, period)
                artifacts[lines_svg_path(period)] = self._render_lines(days, period)
        except ActivityDataError:
            raise ProfileRenderingError("Недостаточно данных для всех периодов профиля.") from None
        artifacts[USAGE_SVG_PATH] = self._render_usage(usage)
        return artifacts

    def _render_commits(self, days: Sequence[DailyActivity], period: int) -> str:
        total = sum(day.commits for day in days)
        maximum = max((day.commits for day in days), default=0)
        scale_maximum = max(maximum, 1)
        chart_width = CHART_RIGHT - CHART_LEFT
        chart_height = CHART_BOTTOM - CHART_TOP
        slot_width = chart_width / len(days)
        bar_width = max(0.8, slot_width * 0.72)
        elements = self._svg_header(
            title=f"Коммиты за {period} дней",
            description=f"Всего {total} коммитов за выбранный период.",
            height=CHART_HEIGHT,
        )
        elements.extend(
            [
                '<text class="title" x="28" y="38">Коммиты</text>',
                (
                    f'<text class="metric" x="28" y="64">'
                    f"{escape(self._format_count(total))} за {period} дней</text>"
                ),
                (
                    f'<text class="label muted" x="{self._number(CHART_RIGHT)}" y="80" '
                    f'text-anchor="end">макс. {maximum}</text>'
                ),
                self._grid_line(CHART_TOP),
                self._grid_line(CHART_BOTTOM),
            ]
        )
        for index, day in enumerate(days):
            raw_height = day.commits / scale_maximum * chart_height
            height = 0.0 if day.commits == 0 else max(1.0, raw_height)
            x = CHART_LEFT + index * slot_width + (slot_width - bar_width) / 2
            y = CHART_BOTTOM - height
            elements.append(
                f'<rect class="commit-bar" x="{self._number(x)}" y="{self._number(y)}" '
                f'width="{self._number(bar_width)}" height="{self._number(height)}" rx="1">'
                f"<title>{escape(day.day.isoformat())}: {day.commits}</title></rect>"
            )
        elements.extend(self._date_axis(days))
        elements.append("</svg>")
        return "\n".join(elements) + "\n"

    def _render_lines(self, days: Sequence[DailyActivity], period: int) -> str:
        added_total = sum(day.added_lines for day in days)
        deleted_total = sum(day.deleted_lines for day in days)
        maximum = max(
            max((day.added_lines for day in days), default=0),
            max((day.deleted_lines for day in days), default=0),
        )
        scale_maximum = max(maximum, 1)
        added_points = self._line_points(days, scale_maximum, "added_lines")
        deleted_points = self._line_points(days, scale_maximum, "deleted_lines")
        elements = self._svg_header(
            title=f"Строки кода за {period} дней",
            description=(f"Добавлено {added_total}, удалено {deleted_total} строк исходного кода."),
            height=CHART_HEIGHT,
        )
        elements.extend(
            [
                '<text class="title" x="28" y="38">Строки кода</text>',
                (
                    f'<text class="metric added-text" x="28" y="64">+'
                    f"{escape(self._format_count(added_total))}</text>"
                ),
                (
                    f'<text class="metric deleted-text" x="150" y="64">−'
                    f"{escape(self._format_count(deleted_total))}</text>"
                ),
                (
                    f'<text class="label muted" x="{self._number(CHART_RIGHT)}" y="80" '
                    f'text-anchor="end">макс. {maximum}</text>'
                ),
                self._grid_line(CHART_TOP),
                self._grid_line(CHART_BOTTOM),
                (
                    f'<polyline class="added-line" points="{added_points}" '
                    'stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" '
                    'vector-effect="non-scaling-stroke" />'
                ),
                (
                    f'<polyline class="deleted-line" points="{deleted_points}" '
                    'stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" '
                    'vector-effect="non-scaling-stroke" />'
                ),
            ]
        )
        if len(days) <= 30:
            elements.extend(self._line_markers(days, scale_maximum, "added_lines", "added-marker"))
            elements.extend(
                self._line_markers(days, scale_maximum, "deleted_lines", "deleted-marker")
            )
        elements.extend(self._date_axis(days))
        elements.append("</svg>")
        return "\n".join(elements) + "\n"

    def _render_usage(self, usage: UsageReport) -> str:
        row_count = max(len(usage.languages), len(usage.technologies), 1)
        height = max(180, 112 + row_count * 34)
        elements = self._svg_header(
            title="Языки и технологии",
            description="Агрегированные доли языков и частота технологий по репозиториям.",
            height=height,
        )
        elements.extend(
            [
                '<text class="title" x="28" y="38">Языки и технологии</text>',
                '<text class="metric" x="28" y="76">Языки</text>',
                '<text class="metric" x="382" y="76">Технологии</text>',
            ]
        )
        elements.extend(self._language_rows(usage.languages))
        elements.extend(self._technology_rows(usage.technologies))
        elements.append("</svg>")
        return "\n".join(elements) + "\n"

    def _language_rows(self, languages: Sequence[LanguageUsage]) -> list[str]:
        if not languages:
            return ['<text class="label muted" x="28" y="108">Нет данных</text>']
        elements: list[str] = []
        for index, language in enumerate(languages):
            y = 104 + index * 34
            label = self._short_label(language.name)
            bar_width = 320 * language.share_basis_points / 10_000
            elements.extend(
                [
                    (
                        f"<g><title>{escape(language.name)}</title>"
                        f'<text class="label" x="28" y="{y}">{escape(label)}</text>'
                        f'<text class="label muted" x="348" y="{y}" text-anchor="end">'
                        f"{self._format_percentage(language.share_basis_points)}</text></g>"
                    ),
                    f'<rect class="track" x="28" y="{y + 8}" width="320" height="5" rx="2.5" />',
                    (
                        f'<rect class="language" x="28" y="{y + 8}" '
                        f'width="{self._number(bar_width)}" height="5" rx="2.5" />'
                    ),
                ]
            )
        return elements

    def _technology_rows(self, technologies: Sequence[TechnologyUsage]) -> list[str]:
        if not technologies:
            return ['<text class="label muted" x="382" y="108">Нет данных</text>']
        elements: list[str] = []
        for index, technology in enumerate(technologies):
            y = 104 + index * 34
            label = self._short_label(technology.name)
            bar_width = 310 * technology.repository_share_basis_points / 10_000
            frequency = (
                f"{technology.repository_count} · "
                f"{self._format_percentage(technology.repository_share_basis_points)}"
            )
            elements.extend(
                [
                    (
                        f"<g><title>{escape(technology.name)}</title>"
                        f'<text class="label" x="382" y="{y}">{escape(label)}</text>'
                        f'<text class="label muted" x="692" y="{y}" text-anchor="end">'
                        f"{escape(frequency)}</text></g>"
                    ),
                    f'<rect class="track" x="382" y="{y + 8}" width="310" height="5" rx="2.5" />',
                    (
                        f'<rect class="technology" x="382" y="{y + 8}" '
                        f'width="{self._number(bar_width)}" height="5" rx="2.5" />'
                    ),
                ]
            )
        return elements

    def _svg_header(self, title: str, description: str, height: int) -> list[str]:
        return [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_WIDTH} {height}" '
                f'width="{CARD_WIDTH}" height="{height}" style="max-width:100%;height:auto" '
                'role="img" aria-labelledby="title description" '
                'preserveAspectRatio="xMidYMid meet">'
            ),
            f'<title id="title">{escape(title)}</title>',
            f'<desc id="description">{escape(description)}</desc>',
            f"<style>{_SVG_STYLE}</style>",
            (
                f'<rect class="surface" x="1" y="1" width="{CARD_WIDTH - 2}" '
                f'height="{height - 2}" rx="12" />'
            ),
        ]

    def _line_points(
        self,
        days: Sequence[DailyActivity],
        maximum: int,
        field: str,
    ) -> str:
        return " ".join(
            f"{self._number(x)},{self._number(y)}"
            for x, y in self._series_coordinates(days, maximum, field)
        )

    def _line_markers(
        self,
        days: Sequence[DailyActivity],
        maximum: int,
        field: str,
        css_class: str,
    ) -> list[str]:
        values = (getattr(day, field) for day in days)
        return [
            (
                f'<circle class="{css_class}" cx="{self._number(x)}" '
                f'cy="{self._number(y)}" r="2.4">'
                f"<title>{escape(day.day.isoformat())}: {value}</title></circle>"
            )
            for day, value, (x, y) in zip(
                days,
                values,
                self._series_coordinates(days, maximum, field),
                strict=True,
            )
        ]

    @staticmethod
    def _series_coordinates(
        days: Sequence[DailyActivity],
        maximum: int,
        field: str,
    ) -> list[tuple[float, float]]:
        chart_width = CHART_RIGHT - CHART_LEFT
        chart_height = CHART_BOTTOM - CHART_TOP
        denominator = max(len(days) - 1, 1)
        return [
            (
                CHART_LEFT + index * chart_width / denominator,
                CHART_BOTTOM - getattr(day, field) / maximum * chart_height,
            )
            for index, day in enumerate(days)
        ]

    @staticmethod
    def _grid_line(y: float) -> str:
        return (
            f'<line class="grid" x1="{SvgProfileRenderer._number(CHART_LEFT)}" '
            f'y1="{SvgProfileRenderer._number(y)}" '
            f'x2="{SvgProfileRenderer._number(CHART_RIGHT)}" '
            f'y2="{SvgProfileRenderer._number(y)}" />'
        )

    @staticmethod
    def _date_axis(days: Sequence[DailyActivity]) -> list[str]:
        first = SvgProfileRenderer._format_date(days[0])
        last = SvgProfileRenderer._format_date(days[-1])
        return [
            (
                f'<text class="label muted" x="{SvgProfileRenderer._number(CHART_LEFT)}" '
                f'y="238">{first}</text>'
            ),
            (
                f'<text class="label muted" x="{SvgProfileRenderer._number(CHART_RIGHT)}" '
                f'y="238" text-anchor="end">{last}</text>'
            ),
        ]

    @staticmethod
    def _render_readme() -> str:
        lines = ["<!-- Generated by it-activity. Do not edit manually. -->", ""]
        for period in SUPPORTED_PERIODS:
            open_attribute = " open" if period == DEFAULT_OPEN_PERIOD else ""
            lines.extend(
                [
                    f"<details{open_attribute}>",
                    f"<summary><strong>Последние {period} дней</strong></summary>",
                    "",
                    f"![Коммиты за {period} дней]({commits_svg_path(period)})",
                    "",
                    f"![Строки кода за {period} дней]({lines_svg_path(period)})",
                    "",
                    "</details>",
                    "",
                ]
            )
        lines.extend(
            [
                "## Языки и технологии",
                "",
                f"![Языки и технологии]({USAGE_SVG_PATH})",
            ]
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _short_label(value: str, maximum: int = 26) -> str:
        return value if len(value) <= maximum else f"{value[: maximum - 1]}…"

    @staticmethod
    def _format_count(value: int) -> str:
        return f"{value:,}".replace(",", " ")

    @staticmethod
    def _format_percentage(basis_points: int) -> str:
        whole, fraction = divmod(basis_points, 100)
        return f"{whole}.{fraction:02d}%"

    @staticmethod
    def _format_date(day: DailyActivity) -> str:
        return f"{day.day.day:02d}.{day.day.month:02d}.{day.day.year}"

    @staticmethod
    def _number(value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")
