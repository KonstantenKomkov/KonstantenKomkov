"""Tests for reading the owner-authored profile intro from the filesystem."""

from pathlib import Path

import pytest

from it_activity.adapters.profile_intro import FilesystemProfileIntroSource
from it_activity.ports.intro import ProfileIntroSourceError


def test_missing_file_yields_empty_intro(tmp_path: Path) -> None:
    intro = FilesystemProfileIntroSource(tmp_path).load()

    assert intro.is_empty


def test_existing_file_is_read_and_normalised(tmp_path: Path) -> None:
    (tmp_path / "about.md").write_text("## Hello\r\n\r\nA few words.\n\n", encoding="utf-8")

    intro = FilesystemProfileIntroSource(tmp_path).load()

    assert intro.markdown == "## Hello\n\nA few words."


def test_symlinked_source_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text("Some text.\n", encoding="utf-8")
    (tmp_path / "about.md").symlink_to(tmp_path / "target.md")

    with pytest.raises(ProfileIntroSourceError):
        FilesystemProfileIntroSource(tmp_path).load()


def test_oversized_source_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "about.md").write_text("a" * 20_000, encoding="utf-8")

    with pytest.raises(ProfileIntroSourceError):
        FilesystemProfileIntroSource(tmp_path).load()


def test_forbidden_markup_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "about.md").write_text("<script>alert(1)</script>\n", encoding="utf-8")

    with pytest.raises(ProfileIntroSourceError):
        FilesystemProfileIntroSource(tmp_path).load()
