"""Deterministic source-file classification for line activity."""

from enum import Enum
from pathlib import PurePosixPath

from it_activity.domain.activity import FileChange


class FileCategory(Enum):
    """Internal reason for including or excluding a changed file."""

    SOURCE = "source"
    BINARY = "binary"
    GENERATED = "generated"
    VENDORED = "vendored"
    LOCK = "lock"
    DOCUMENTATION = "documentation"
    OTHER = "other"


_SOURCE_EXTENSIONS = frozenset(
    {
        ".asm",
        ".bash",
        ".bat",
        ".c",
        ".cc",
        ".cjs",
        ".clj",
        ".cljc",
        ".cljs",
        ".cmd",
        ".coffee",
        ".cpp",
        ".cs",
        ".css",
        ".cxx",
        ".dart",
        ".el",
        ".erl",
        ".ex",
        ".exs",
        ".fish",
        ".fs",
        ".fsx",
        ".go",
        ".graphql",
        ".groovy",
        ".gql",
        ".h",
        ".hh",
        ".hcl",
        ".hlsl",
        ".hpp",
        ".hs",
        ".html",
        ".htm",
        ".java",
        ".jl",
        ".js",
        ".jsx",
        ".kt",
        ".kts",
        ".less",
        ".lhs",
        ".lisp",
        ".lua",
        ".m",
        ".mm",
        ".mjs",
        ".ml",
        ".mli",
        ".nim",
        ".pas",
        ".php",
        ".pl",
        ".pm",
        ".ps1",
        ".py",
        ".pyi",
        ".pyx",
        ".r",
        ".rb",
        ".rs",
        ".sass",
        ".scala",
        ".scss",
        ".sh",
        ".sol",
        ".sql",
        ".svelte",
        ".swift",
        ".tcl",
        ".tf",
        ".tsx",
        ".ts",
        ".vb",
        ".vbs",
        ".vue",
        ".zig",
        ".zsh",
    }
)

_SOURCE_FILENAMES = frozenset(
    {
        ".bashrc",
        ".zshrc",
        "cmakelists.txt",
        "dockerfile",
        "jenkinsfile",
        "makefile",
        "procfile",
        "rakefile",
        "vagrantfile",
    }
)

_BINARY_EXTENSIONS = frozenset(
    {
        ".7z",
        ".a",
        ".avi",
        ".bin",
        ".bmp",
        ".class",
        ".dll",
        ".dylib",
        ".eot",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jar",
        ".jpeg",
        ".jpg",
        ".mov",
        ".mp3",
        ".mp4",
        ".o",
        ".otf",
        ".pdf",
        ".png",
        ".pyc",
        ".so",
        ".tar",
        ".ttf",
        ".wav",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".zip",
    }
)

_DOCUMENTATION_EXTENSIONS = frozenset({".adoc", ".markdown", ".md", ".rst"})
_DOCUMENTATION_DIRECTORIES = frozenset({"doc", "docs", "documentation"})
_VENDORED_DIRECTORIES = frozenset(
    {"deps", "external", "node_modules", "third_party", "vendor", "vendors"}
)
_GENERATED_DIRECTORIES = frozenset(
    {".next", "build", "coverage", "dist", "gen", "generated", "out", "target"}
)
_LOCK_FILENAMES = frozenset(
    {
        "cargo.lock",
        "composer.lock",
        "gemfile.lock",
        "gradle.lockfile",
        "package-lock.json",
        "packages.lock.json",
        "pipfile.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "yarn.lock",
    }
)

_GENERATED_FILENAME_MARKERS = (
    ".designer.",
    ".generated.",
    ".g.cs",
    ".min.",
    ".pb.cc",
    ".pb.go",
    ".pb.h",
    ".pb.kt",
    ".pb.swift",
    "_generated.",
    "_pb2.py",
)


def classify_file(change: FileChange) -> FileCategory:
    """Classify a private path without reading or exposing file contents."""
    path = PurePosixPath(change.path)
    parts = tuple(part.casefold() for part in path.parts)
    filename = path.name.casefold()
    suffix = path.suffix.casefold()
    directories = frozenset(parts[:-1])

    if change.binary or suffix in _BINARY_EXTENSIONS:
        return FileCategory.BINARY
    if directories & _VENDORED_DIRECTORIES:
        return FileCategory.VENDORED
    if directories & _GENERATED_DIRECTORIES or any(
        marker in filename for marker in _GENERATED_FILENAME_MARKERS
    ):
        return FileCategory.GENERATED
    if filename in _LOCK_FILENAMES:
        return FileCategory.LOCK
    if directories & _DOCUMENTATION_DIRECTORIES or suffix in _DOCUMENTATION_EXTENSIONS:
        return FileCategory.DOCUMENTATION
    if filename in _SOURCE_FILENAMES or suffix in _SOURCE_EXTENSIONS:
        return FileCategory.SOURCE
    return FileCategory.OTHER
