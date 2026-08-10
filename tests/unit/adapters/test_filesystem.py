"""Tests for allowlisted atomic public output writes."""

from pathlib import Path

import pytest

from it_activity.adapters.filesystem import FilesystemPublicOutputWriter
from it_activity.domain.profile import PUBLIC_OUTPUT_PATHS
from it_activity.ports.output import PublicOutputError


def artifacts(content: str = "generated\n") -> dict[str, str]:
    return {path: f"{path}: {content}" for path in PUBLIC_OUTPUT_PATHS}


def test_writer_writes_only_changes_and_is_idempotent(tmp_path: Path) -> None:
    writer = FilesystemPublicOutputWriter(tmp_path)
    initial = artifacts()

    assert writer.write(initial) == len(PUBLIC_OUTPUT_PATHS)
    assert writer.write(initial) == 0

    changed = dict(initial)
    changed["README.md"] = "updated\n"
    assert writer.write(changed) == 1
    assert (tmp_path / "README.md").read_text() == "updated\n"
    assert not tuple(tmp_path.rglob(".it-activity-*"))


def test_writer_rejects_incomplete_artifact_set_without_writing(tmp_path: Path) -> None:
    writer = FilesystemPublicOutputWriter(tmp_path)

    with pytest.raises(PublicOutputError, match="allowlist"):
        writer.write({"README.md": "incomplete\n"})

    assert not (tmp_path / "README.md").exists()


def test_writer_rejects_generated_directory_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "generated").symlink_to(outside, target_is_directory=True)
    writer = FilesystemPublicOutputWriter(root)

    with pytest.raises(PublicOutputError, match="вне репозитория"):
        writer.write(artifacts())

    assert not tuple(outside.iterdir())


def test_writer_rejects_matching_file_beneath_directory_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    expected = artifacts()
    (outside / "commits-7.svg").write_text(expected["generated/commits-7.svg"])
    (root / "generated").symlink_to(outside, target_is_directory=True)
    writer = FilesystemPublicOutputWriter(root)

    with pytest.raises(PublicOutputError, match="вне репозитория"):
        writer.write(expected)

    assert (outside / "commits-7.svg").read_text() == expected["generated/commits-7.svg"]
