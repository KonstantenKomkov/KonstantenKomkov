"""Tests for deterministic source-file classification."""

import pytest

from it_activity.domain.activity import FileChange
from it_activity.domain.source_files import FileCategory, classify_file


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
