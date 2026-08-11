"""Snapshot and structural tests for deterministic public profile rendering."""

import hashlib
import xml.etree.ElementTree as element_tree
from datetime import date, timedelta

from it_activity.adapters.svg_renderer import SvgProfileRenderer
from it_activity.domain.activity import ActivityReport, DailyActivity
from it_activity.domain.profile import PUBLIC_OUTPUT_PATHS, README_PATH, USAGE_SVG_PATH
from it_activity.domain.usage import UsageReport, build_usage_report


def sample_activity_report() -> ActivityReport:
    first_day = date(2025, 8, 11)
    return ActivityReport(
        timezone="Europe/Moscow",
        days=tuple(
            DailyActivity(
                day=first_day + timedelta(days=offset),
                commits=offset % 5,
                added_lines=(offset * 7) % 41,
                deleted_lines=(offset * 3) % 23,
            )
            for offset in range(365)
        ),
    )


def sample_usage_report() -> UsageReport:
    return build_usage_report(
        {"Python": 600, "TypeScript": 300, "Cap'n Proto": 100},
        {"Node.js": 3, "Docker": 2, "Python": 1},
        repository_count=4,
    )


def test_renderer_returns_exact_deterministic_artifact_set() -> None:
    renderer = SvgProfileRenderer()
    activity = sample_activity_report()
    usage = sample_usage_report()

    first = renderer.render(activity, usage)
    second = renderer.render(activity, usage)

    assert set(first) == PUBLIC_OUTPUT_PATHS
    assert first == second


def test_all_svg_artifacts_are_well_formed_responsive_and_theme_aware() -> None:
    artifacts = SvgProfileRenderer().render(sample_activity_report(), sample_usage_report())

    for path, content in artifacts.items():
        if not path.endswith(".svg"):
            continue
        root = element_tree.fromstring(content)  # noqa: S314 - trusted renderer output
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.attrib["viewBox"].startswith("0 0 720 ")
        assert root.attrib["style"] == "max-width:100%;height:auto"
        assert "@media (prefers-color-scheme: dark)" in content
        assert "<script" not in content.casefold()
        assert "javascript:" not in content.casefold()


def test_daily_charts_show_numeric_per_day_scales() -> None:
    artifacts = SvgProfileRenderer().render(sample_activity_report(), sample_usage_report())
    commits_svg = artifacts["generated/commits-30.svg"]
    lines_svg = artifacts["generated/lines-30.svg"]

    assert "коммитов/день" in commits_svg
    assert "строк/день" in lines_svg
    assert "добавлено +" in lines_svg
    assert "удалено \N{MINUS SIGN}" in lines_svg
    for value in ("0", "1", "2", "3", "4"):
        assert f'text-anchor="end">{value}</text>' in commits_svg
    for value in ("0", "10", "20", "30", "40"):
        assert f'text-anchor="end">{value}</text>' in lines_svg


def test_usage_rows_embed_branded_and_generic_icons_without_external_assets() -> None:
    renderer = SvgProfileRenderer()
    activity = sample_activity_report()
    usage_svg = renderer.render(activity, sample_usage_report())[USAGE_SVG_PATH]
    fallback_svg = renderer.render(
        activity,
        build_usage_report(
            {"1C Enterprise": 1},
            {"Ansible": 1},
            repository_count=1,
        ),
    )[USAGE_SVG_PATH]

    for icon in ("python", "typescript", "nodedotjs", "docker", "generic-language"):
        assert f'data-icon="{icon}"' in usage_svg
    assert '<title id="title">Языки и технологии за 365 дней</title>' in usage_svg
    assert "Языки и технологии · 365 дней" in usage_svg
    assert 'data-icon="generic-technology"' in fallback_svg
    assert "<image" not in usage_svg.casefold()
    assert "href=" not in usage_svg.casefold()


def test_readme_uses_supported_details_and_opens_only_thirty_days() -> None:
    readme = SvgProfileRenderer().render(sample_activity_report(), sample_usage_report())[
        README_PATH
    ]

    assert readme.count("<details") == 3
    assert readme.count("<details open>") == 1
    assert "<details open>\n<summary><strong>Последние 30 дней" in readme
    assert "generated/commits-7.svg" in readme
    assert "generated/commits-30.svg" in readme
    assert "generated/commits-365.svg" in readme
    assert "generated/lines-7.svg" in readme
    assert "generated/lines-30.svg" in readme
    assert "generated/lines-365.svg" in readme
    assert "## Языки и технологии за 365 дней" in readme
    assert USAGE_SVG_PATH in readme
    assert "<script" not in readme.casefold()
    assert "javascript:" not in readme.casefold()


def test_zero_line_chart_displays_zero_scale() -> None:
    final_day = date(2026, 8, 10)
    activity = ActivityReport(
        timezone="Europe/Moscow",
        days=tuple(
            DailyActivity(final_day - timedelta(days=364 - offset)) for offset in range(365)
        ),
    )

    lines_svg = SvgProfileRenderer().render(
        activity,
        UsageReport(languages=(), technologies=()),
    )["generated/lines-30.svg"]

    assert "строк/день" in lines_svg
    assert 'font-size="10" x="46" y="213.5" text-anchor="end">0</text>' in lines_svg
    assert 'text-anchor="end">1</text>' not in lines_svg


def test_rendered_output_contains_no_private_fixture_values() -> None:
    artifacts = SvgProfileRenderer().render(sample_activity_report(), sample_usage_report())
    public_output = "\n".join(artifacts.values())

    for private_value in (
        "fixture-org/private-project",
        "https://github.com/fixture-org/private-project",
        "src/private/customer_name.py",
        "owner-private@example.invalid",
        "private fixture commit message",
    ):
        assert private_value not in public_output


def test_svg_snapshots_have_expected_hashes() -> None:
    artifacts = SvgProfileRenderer().render(sample_activity_report(), sample_usage_report())
    hashes = {
        path: hashlib.sha256(content.encode()).hexdigest()
        for path, content in sorted(artifacts.items())
    }

    assert hashes == {
        "README.md": "d8adf79c6c6c531e00249ace788ed507ac55d1fc5b0f2959643ccb08c65ac077",
        "generated/commits-30.svg": (
            "b59ec6b2297e5eb2f1ac226d73dd92a39bd648c73e34690bbee29d494001b0b3"
        ),
        "generated/commits-365.svg": (
            "f6e872089d15a6116d9099ffeda15c9d9bea308931012c4553208778c5f0d3e0"
        ),
        "generated/commits-7.svg": (
            "083fcb1488ccee355b4256777ad965c7f16ee106f465ddd3ea537590554da9ff"
        ),
        "generated/lines-30.svg": (
            "a26b5ed2086f3284bfe4a64f163efe03fcc8074c72218f3186ea80abac186bf4"
        ),
        "generated/lines-365.svg": (
            "505d7e5ef6ecccd0b128c0496ebf60f38bfcbf0222324c51d20b1bbc376068c5"
        ),
        "generated/lines-7.svg": (
            "422ad7e750d81139af299e5749004b4e84452d72cb8de96734257b739687c368"
        ),
        "generated/usage.svg": "4958a6da97f6a3d65a05b17af893888b5fcb56a5367aa39cc9197a48b67bc6a1",
    }
