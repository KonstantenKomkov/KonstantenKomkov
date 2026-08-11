"""Tests for deterministic source-file classification."""

import pytest

from it_activity.domain.activity import FileChange
from it_activity.domain.linguist_languages import ALLOWED_LINGUIST_LANGUAGES
from it_activity.domain.source_files import FileCategory, classify_file, source_language


@pytest.mark.parametrize(
    ("path", "binary", "expected"),
    [
        ("src/app.py", False, FileCategory.SOURCE),
        ("web/component.tsx", False, FileCategory.SOURCE),
        ("Dockerfile", False, FileCategory.SOURCE),
        ("CMakeLists.txt", False, FileCategory.SOURCE),
        ("src/app.py", True, FileCategory.BINARY),
        ("assets/logo.png", False, FileCategory.BINARY),
        ("vendor/library.py", False, FileCategory.VENDORED),
        ("node_modules/tool/index.js", False, FileCategory.VENDORED),
        ("generated/client.py", False, FileCategory.GENERATED),
        ("src/client.generated.ts", False, FileCategory.GENERATED),
        ("dist/app.js", False, FileCategory.GENERATED),
        ("package-lock.json", False, FileCategory.LOCK),
        ("Cargo.lock", False, FileCategory.LOCK),
        ("docs/example.py", False, FileCategory.DOCUMENTATION),
        ("README.md", False, FileCategory.DOCUMENTATION),
        ("config/settings.yaml", False, FileCategory.OTHER),
    ],
)
def test_classify_file(
    path: str,
    binary: bool,
    expected: FileCategory,
) -> None:
    change = FileChange(path=path, additions=1, deletions=1, binary=binary)

    assert classify_file(change) is expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/app.py", "Python"),
        ("web/component.tsx", "TypeScript"),
        ("ios/bridge.mm", "Objective-C++"),
        ("shaders/view.metal", "Metal"),
        ("Makefile", "Makefile"),
        ("Jenkinsfile", "Groovy"),
        ("generated/client.py", None),
        ("docs/example.js", None),
        ("assets/data.json", None),
    ],
)
def test_source_language_returns_only_allowlisted_public_names(
    path: str,
    expected: str | None,
) -> None:
    language = source_language(FileChange(path=path, additions=1, deletions=0))

    assert language == expected
    assert language is None or language in ALLOWED_LINGUIST_LANGUAGES
