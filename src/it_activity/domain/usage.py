"""Public language and technology usage values."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Optional

from it_activity.domain.linguist_languages import ALLOWED_LINGUIST_LANGUAGES

BASIS_POINTS = 10_000
OTHER_LANGUAGE = "Other"

ALLOWED_LANGUAGES = ALLOWED_LINGUIST_LANGUAGES

_EXACT_MANIFEST_TECHNOLOGIES: Mapping[str, frozenset[str]] = {
    ".terraform.lock.hcl": frozenset({"Terraform"}),
    "BUILD.bazel": frozenset({"Bazel"}),
    "CMakeLists.txt": frozenset({"CMake"}),
    "Cargo.toml": frozenset({"Cargo"}),
    "Chart.yaml": frozenset({"Helm"}),
    "Dockerfile": frozenset({"Docker"}),
    "Gemfile": frozenset({"Bundler"}),
    "MODULE.bazel": frozenset({"Bazel"}),
    "Makefile": frozenset({"Make"}),
    "Package.swift": frozenset({"Swift Package Manager"}),
    "Pipfile": frozenset({"Python"}),
    "WORKSPACE": frozenset({"Bazel"}),
    "ansible.cfg": frozenset({"Ansible"}),
    "build.gradle": frozenset({"Gradle"}),
    "build.gradle.kts": frozenset({"Gradle"}),
    "cabal.project": frozenset({"Cabal"}),
    "composer.json": frozenset({"Composer"}),
    "compose.yaml": frozenset({"Docker"}),
    "compose.yml": frozenset({"Docker"}),
    "conanfile.py": frozenset({"Conan"}),
    "conanfile.txt": frozenset({"Conan"}),
    "deno.json": frozenset({"Deno"}),
    "deno.jsonc": frozenset({"Deno"}),
    "deps.edn": frozenset({"Clojure CLI"}),
    "docker-compose.yaml": frozenset({"Docker"}),
    "docker-compose.yml": frozenset({"Docker"}),
    "flake.nix": frozenset({"Nix"}),
    "go.mod": frozenset({"Go"}),
    "meson.build": frozenset({"Meson"}),
    "mix.exs": frozenset({"Mix"}),
    "package.json": frozenset({"Node.js"}),
    "pom.xml": frozenset({"Maven"}),
    "project.clj": frozenset({"Leiningen"}),
    "pubspec.yaml": frozenset({"Dart pub"}),
    "pyproject.toml": frozenset({"Python"}),
    "requirements.txt": frozenset({"Python"}),
    "settings.gradle": frozenset({"Gradle"}),
    "settings.gradle.kts": frozenset({"Gradle"}),
    "setup.cfg": frozenset({"Python"}),
    "setup.py": frozenset({"Python"}),
    "stack.yaml": frozenset({"Stack"}),
    "vcpkg.json": frozenset({"vcpkg"}),
}

_PREFIX_MANIFEST_TECHNOLOGIES: Mapping[str, frozenset[str]] = {
    "Dockerfile.": frozenset({"Docker"}),
}

_SUFFIX_MANIFEST_TECHNOLOGIES: Mapping[str, frozenset[str]] = {
    ".cabal": frozenset({"Cabal"}),
    ".csproj": frozenset({".NET"}),
    ".fsproj": frozenset({".NET"}),
    ".sln": frozenset({".NET"}),
    ".vbproj": frozenset({".NET"}),
}

ALLOWED_TECHNOLOGIES = frozenset(
    technology
    for technologies in (
        *_EXACT_MANIFEST_TECHNOLOGIES.values(),
        *_PREFIX_MANIFEST_TECHNOLOGIES.values(),
        *_SUFFIX_MANIFEST_TECHNOLOGIES.values(),
    )
    for technology in technologies
)


class UsageDataError(ValueError):
    """A safe-to-display error for invalid public usage data."""


@dataclass(frozen=True)
class LanguageUsage:
    """Public aggregate share for one allowlisted language."""

    name: str
    share_basis_points: int

    def __post_init__(self) -> None:
        if self.name not in ALLOWED_LANGUAGES | {OTHER_LANGUAGE}:
            raise UsageDataError("Язык отсутствует в публичном allowlist.")
        if (
            not isinstance(self.share_basis_points, int)
            or isinstance(self.share_basis_points, bool)
            or not 0 < self.share_basis_points <= BASIS_POINTS
        ):
            raise UsageDataError("Некорректно задана доля языка.")


@dataclass(frozen=True)
class TechnologyUsage:
    """Public repository frequency for one allowlisted technology."""

    name: str
    repository_count: int
    repository_share_basis_points: int

    def __post_init__(self) -> None:
        if self.name not in ALLOWED_TECHNOLOGIES:
            raise UsageDataError("Технология отсутствует в публичном allowlist.")
        if (
            not isinstance(self.repository_count, int)
            or isinstance(self.repository_count, bool)
            or not isinstance(self.repository_share_basis_points, int)
            or isinstance(self.repository_share_basis_points, bool)
            or self.repository_count <= 0
            or not 0 < self.repository_share_basis_points <= BASIS_POINTS
        ):
            raise UsageDataError("Некорректно задана частота технологии.")


@dataclass(frozen=True)
class UsageReport:
    """Public-only language and technology aggregates."""

    languages: tuple[LanguageUsage, ...]
    technologies: tuple[TechnologyUsage, ...]


def allowlisted_manifest_marker(path: str) -> Optional[str]:
    """Reduce a private path to an allowlisted public manifest marker."""
    if not path or any(character in path for character in "\r\n\0"):
        return None
    filename = PurePosixPath(path).name
    if filename in _EXACT_MANIFEST_TECHNOLOGIES:
        return filename
    for prefix in sorted(_PREFIX_MANIFEST_TECHNOLOGIES):
        if filename.startswith(prefix) and len(filename) > len(prefix):
            return prefix
    for suffix in sorted(_SUFFIX_MANIFEST_TECHNOLOGIES):
        if filename.endswith(suffix) and len(filename) > len(suffix):
            return suffix
    return None


def detect_technologies(manifest_markers: Sequence[str]) -> frozenset[str]:
    """Return only allowlisted technology names for sanitized manifest markers."""
    technologies: set[str] = set()
    for marker in manifest_markers:
        if marker in _EXACT_MANIFEST_TECHNOLOGIES:
            technologies.update(_EXACT_MANIFEST_TECHNOLOGIES[marker])
        elif marker in _PREFIX_MANIFEST_TECHNOLOGIES:
            technologies.update(_PREFIX_MANIFEST_TECHNOLOGIES[marker])
        elif marker in _SUFFIX_MANIFEST_TECHNOLOGIES:
            technologies.update(_SUFFIX_MANIFEST_TECHNOLOGIES[marker])
        else:
            raise UsageDataError("Получен манифест вне публичного allowlist.")
    return frozenset(technologies)


def build_usage_report(
    language_bytes: Mapping[str, int],
    technology_repository_counts: Mapping[str, int],
    repository_count: int,
) -> UsageReport:
    """Build deterministic safe aggregates without exposing raw language names."""
    if (
        not isinstance(repository_count, int)
        or isinstance(repository_count, bool)
        or repository_count < 0
    ):
        raise UsageDataError("Некорректно задано число репозиториев.")

    safe_language_bytes: dict[str, int] = {}
    for language, byte_count in language_bytes.items():
        if (
            not isinstance(language, str)
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise UsageDataError("GitHub вернул некорректную языковую статистику.")
        if byte_count == 0:
            continue
        safe_language = language if language in ALLOWED_LANGUAGES else OTHER_LANGUAGE
        safe_language_bytes[safe_language] = safe_language_bytes.get(safe_language, 0) + byte_count

    language_shares = _allocate_basis_points(safe_language_bytes)
    languages = tuple(
        LanguageUsage(name=name, share_basis_points=language_shares[name])
        for name, _ in sorted(
            safe_language_bytes.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )

    technologies: list[TechnologyUsage] = []
    for name, count in sorted(
        technology_repository_counts.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        if (
            name not in ALLOWED_TECHNOLOGIES
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count <= 0
            or count > repository_count
            or repository_count == 0
        ):
            raise UsageDataError("Некорректно задана агрегированная технология.")
        numerator = count * BASIS_POINTS
        share, remainder = divmod(numerator, repository_count)
        if remainder * 2 >= repository_count:
            share += 1
        technologies.append(
            TechnologyUsage(
                name=name,
                repository_count=count,
                repository_share_basis_points=share,
            )
        )

    return UsageReport(languages=languages, technologies=tuple(technologies))


def _allocate_basis_points(weights: Mapping[str, int]) -> Mapping[str, int]:
    total = sum(weights.values())
    if total == 0:
        return {}
    shares = {name: weight * BASIS_POINTS // total for name, weight in weights.items()}
    remainders = {name: weight * BASIS_POINTS % total for name, weight in weights.items()}
    remaining = BASIS_POINTS - sum(shares.values())
    for name in sorted(remainders, key=lambda item: (-remainders[item], item))[:remaining]:
        shares[name] += 1
    return shares
