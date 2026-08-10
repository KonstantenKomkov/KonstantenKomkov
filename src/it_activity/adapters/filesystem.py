"""Allowlisted atomic filesystem output adapter."""

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from it_activity.domain.profile import PUBLIC_OUTPUT_PATHS
from it_activity.ports.output import PublicOutputError

MAX_PUBLIC_FILE_BYTES = 5 * 1024 * 1024


class FilesystemPublicOutputWriter:
    """Replace only changed allowlisted public files below one repository root."""

    def __init__(self, root: Path) -> None:
        try:
            self._root = root.resolve(strict=True)
        except OSError:
            raise PublicOutputError("Не удалось определить каталог публичного вывода.") from None
        if not self._root.is_dir():
            raise PublicOutputError("Каталог публичного вывода не существует.")

    def write(self, artifacts: Mapping[str, str]) -> int:
        """Stage every changed file, then atomically replace each destination."""
        if set(artifacts) != PUBLIC_OUTPUT_PATHS:
            raise PublicOutputError("Запрошена запись вне allowlist публичных файлов.")

        staged: list[tuple[Path, Path]] = []
        try:
            for relative_path in sorted(artifacts):
                target = self._target(relative_path)
                content = artifacts[relative_path].encode("utf-8")
                if not content or len(content) > MAX_PUBLIC_FILE_BYTES:
                    raise PublicOutputError("Публичный файл имеет недопустимый размер.")
                target.parent.mkdir(parents=True, exist_ok=True)
                self._validate_parent(target.parent)
                if target.exists() and target.read_bytes() == content:
                    continue
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=".it-activity-",
                    dir=target.parent,
                )
                temporary_path = Path(temporary_name)
                try:
                    with os.fdopen(descriptor, "wb") as temporary_file:
                        temporary_file.write(content)
                        temporary_file.flush()
                        os.fsync(temporary_file.fileno())
                except BaseException:
                    self._close_descriptor(descriptor)
                    temporary_path.unlink(missing_ok=True)
                    raise
                staged.append((temporary_path, target))

            for temporary_path, target in staged:
                os.replace(temporary_path, target)
            return len(staged)
        except PublicOutputError:
            self._cleanup(staged)
            raise
        except (OSError, UnicodeError):
            self._cleanup(staged)
            raise PublicOutputError("Не удалось записать полный публичный результат.") from None

    def _target(self, relative_path: str) -> Path:
        pure_path = PurePosixPath(relative_path)
        if (
            pure_path.is_absolute()
            or ".." in pure_path.parts
            or relative_path not in PUBLIC_OUTPUT_PATHS
        ):
            raise PublicOutputError("Запрошен небезопасный путь публичного файла.")
        target = self._root.joinpath(*pure_path.parts)
        if target.is_symlink():
            raise PublicOutputError("Публичный файл не может быть символической ссылкой.")
        return target

    def _validate_parent(self, parent: Path) -> None:
        resolved_parent = parent.resolve(strict=True)
        if resolved_parent != self._root and self._root not in resolved_parent.parents:
            raise PublicOutputError("Каталог публичного файла находится вне репозитория.")

    @staticmethod
    def _cleanup(staged: list[tuple[Path, Path]]) -> None:
        for temporary_path, _ in staged:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _close_descriptor(descriptor: int | None) -> None:
        if descriptor is None:
            return
        try:
            os.close(descriptor)
        except OSError:
            pass
