"""Filesystem adapter for the owner-authored profile intro."""

from pathlib import Path

from it_activity.domain.profile import INTRO_SOURCE_PATH, ProfileIntro, ProfileIntroError
from it_activity.ports.intro import ProfileIntroSourceError

MAX_INTRO_SOURCE_BYTES = 16 * 1024


class FilesystemProfileIntroSource:
    """Read the intro from a single regular file below the repository root."""

    def __init__(self, root: Path, relative_path: str = INTRO_SOURCE_PATH) -> None:
        try:
            self._root = root.resolve(strict=True)
        except OSError:
            raise ProfileIntroSourceError(
                "Не удалось определить каталог описания профиля."
            ) from None
        self._relative_path = relative_path

    def load(self) -> ProfileIntro:
        """Return the validated intro, or an empty intro when the file is absent."""
        source = self._root / self._relative_path
        if source.is_symlink():
            raise ProfileIntroSourceError(
                "Файл описания профиля не может быть символической ссылкой."
            )
        try:
            if not source.is_file():
                return ProfileIntro.empty()
            if source.stat().st_size > MAX_INTRO_SOURCE_BYTES:
                raise ProfileIntroSourceError("Файл описания профиля имеет недопустимый размер.")
            content = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ProfileIntroSourceError("Не удалось прочитать описание профиля.") from None
        try:
            return ProfileIntro(markdown=content)
        except ProfileIntroError as error:
            raise ProfileIntroSourceError(str(error)) from None
