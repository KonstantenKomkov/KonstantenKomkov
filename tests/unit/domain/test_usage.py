"""Tests for public-safe language and technology aggregation."""

from it_activity.domain.linguist_languages import (
    ALLOWED_LINGUIST_LANGUAGES,
    LINGUIST_LANGUAGES_COMMIT,
)
from it_activity.domain.usage import (
    OTHER_LANGUAGE,
    allowlisted_manifest_marker,
    build_usage_report,
    detect_technologies,
)


def test_manifest_paths_reduce_to_allowlisted_public_markers() -> None:
    markers = [
        allowlisted_manifest_marker("private/service/package.json"),
        allowlisted_manifest_marker("private/backend/service.csproj"),
        allowlisted_manifest_marker("private/docker/Dockerfile.production"),
        allowlisted_manifest_marker("private/unique-manifest.secret"),
    ]

    assert markers == ["package.json", ".csproj", "Dockerfile.", None]
    assert "private" not in repr(markers)
    assert "unique-manifest" not in repr(markers)


def test_detect_technologies_deduplicates_multiple_manifests() -> None:
    technologies = detect_technologies(
        ["package.json", "package.json", "pyproject.toml", "Dockerfile.", ".csproj"]
    )

    assert technologies == frozenset({"Node.js", "Python", "Docker", ".NET"})


def test_usage_report_aggregates_unknown_languages_as_other() -> None:
    report = build_usage_report(
        {
            "Python": 200,
            "TypeScript": 100,
            "Private Fixture Language": 100,
        },
        {},
        {"Node.js": 2, "Docker": 1},
        repository_count=3,
    )

    assert [(item.name, item.share_basis_points) for item in report.languages] == [
        ("Python", 5000),
        (OTHER_LANGUAGE, 2500),
        ("TypeScript", 2500),
    ]
    assert [
        (item.name, item.repository_count, item.repository_share_basis_points)
        for item in report.technologies
    ] == [("Node.js", 2, 6667), ("Docker", 1, 3333)]
    assert "Private Fixture Language" not in repr(report)


def test_language_basis_points_use_deterministic_largest_remainder() -> None:
    report = build_usage_report(
        {"Go": 1, "Python": 1, "Rust": 1},
        {},
        {},
        repository_count=1,
    )

    assert [(item.name, item.share_basis_points) for item in report.languages] == [
        ("Go", 3334),
        ("Python", 3333),
        ("Rust", 3333),
    ]
    assert sum(item.share_basis_points for item in report.languages) == 10_000


def test_tiny_positive_language_share_remains_visible() -> None:
    report = build_usage_report(
        {"Go": 1, "Python": 1_000_000_000, "Rust": 1},
        {},
        {},
        repository_count=1,
    )

    assert [(item.name, item.share_basis_points) for item in report.languages] == [
        ("Python", 9998),
        ("Go", 1),
        ("Rust", 1),
    ]
    assert sum(item.share_basis_points for item in report.languages) == 10_000


def test_full_pinned_linguist_allowlist_keeps_rare_public_language_name() -> None:
    report = build_usage_report(
        {"1C Enterprise": 10},
        {},
        {},
        repository_count=1,
    )

    assert [(item.name, item.share_basis_points) for item in report.languages] == [
        ("1C Enterprise", 10_000)
    ]
    assert len(ALLOWED_LINGUIST_LANGUAGES) == 825
    assert LINGUIST_LANGUAGES_COMMIT == "46e68a1dec7765b602ec9601693b10e0763436b1"


def test_language_score_blends_code_volume_and_active_days_equally() -> None:
    report = build_usage_report(
        {"Python": 900, "TypeScript": 100},
        {"Python": 1, "TypeScript": 9},
        {},
        repository_count=1,
    )

    assert [
        (item.name, item.share_basis_points, item.active_days) for item in report.languages
    ] == [
        ("Python", 5000, 1),
        ("TypeScript", 5000, 9),
    ]


def test_language_score_keeps_language_changed_but_absent_from_current_tree() -> None:
    report = build_usage_report(
        {"Python": 100},
        {"Python": 1, "TypeScript": 1},
        {},
        repository_count=1,
    )

    assert [
        (item.name, item.share_basis_points, item.active_days) for item in report.languages
    ] == [
        ("Python", 7500, 1),
        ("TypeScript", 2500, 1),
    ]
