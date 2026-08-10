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
    assert USAGE_SVG_PATH in readme
    assert "<script" not in readme.casefold()
    assert "javascript:" not in readme.casefold()


def test_zero_line_chart_displays_zero_maximum() -> None:
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

    assert "макс. 0" in lines_svg
    assert "макс. 1" not in lines_svg


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
        "README.md": "d47409a7afb7f379546aa2f0b629eccbb24b19554e4bdf41867f503a300700c0",
        "generated/commits-30.svg": (
            "007ee8a4587ba1fc372295b594f9d6d39e8ab3f6451c02513041967a22e882a3"
        ),
        "generated/commits-365.svg": (
            "484e37df9d9b09ae5f28239a313e903a6fa6f0ce64cc3e7f2583c9b6ee4736de"
        ),
        "generated/commits-7.svg": (
            "510d82ba105dee55cb2946f2018c317843de5cb96b588f448fbea1b5c9823c1b"
        ),
        "generated/lines-30.svg": (
            "31d8b33aa905b0d63c220dd331b4a15a1f9ff42ceff2084b6ddf050e0b072033"
        ),
        "generated/lines-365.svg": (
            "18d1a2ed54ea35fc79fe45a2b98fb788c9b2fc2777c11a96e5e1de4064fddfb3"
        ),
        "generated/lines-7.svg": (
            "0696f0600a4d62c69c3109b225d8f32e55a326cab4818e744e93d6e50e6e3bc8"
        ),
        "generated/usage.svg": "883512a094da3ad745c3c0fdd21558d9fa82928fede7f7c3c007d30e93eab61e",
    }
