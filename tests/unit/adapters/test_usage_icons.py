"""Tests for the pinned offline usage icon catalog."""

from it_activity.adapters.usage_icons import (
    SIMPLE_ICONS_INTEGRITY,
    SIMPLE_ICONS_VERSION,
    language_icon,
    technology_icon,
)


def test_supported_branded_icon_mappings_are_available() -> None:
    language_names = (
        "Python",
        "Dart",
        "C++",
        "Objective-C++",
        "HTML",
        "JavaScript",
        "Shell",
        "PHP",
        "C",
        "CSS",
        "CMake",
        "Makefile",
        "Astro",
        "Swift",
        "Blade",
        "Scala",
        "Ruby",
        "Objective-C",
        "Kotlin",
        "PowerShell",
        "Awk",
        "Metal",
        "TypeScript",
        "Dockerfile",
        "Java",
        "Batchfile",
        "Mako",
        "Smarty",
    )
    technology_names = (
        "Dart pub",
        "Gradle",
        "Make",
        "Python",
        "Docker",
        "Node.js",
        "Composer",
        "CMake",
    )

    assert all(language_icon(name) is not None for name in language_names)
    assert all(technology_icon(name) is not None for name in technology_names)
    assert SIMPLE_ICONS_VERSION == "16.28.0"
    assert SIMPLE_ICONS_INTEGRITY.startswith("sha512-")


def test_unmapped_allowlisted_usage_uses_renderer_fallback() -> None:
    assert language_icon("1C Enterprise") is None
    assert technology_icon("Ansible") is None
