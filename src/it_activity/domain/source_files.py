"""Deterministic source-file classification for line activity."""

from collections.abc import Mapping
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


_SOURCE_EXTENSION_LANGUAGES: Mapping[str, str] = {
    ".asm": "Assembly",
    ".astro": "Astro",
    ".bash": "Shell",
    ".bat": "Batchfile",
    ".c": "C",
    ".cc": "C++",
    ".cjs": "JavaScript",
    ".clj": "Clojure",
    ".cljc": "Clojure",
    ".cljs": "Clojure",
    ".cmd": "Batchfile",
    ".coffee": "CoffeeScript",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".cxx": "C++",
    ".dart": "Dart",
    ".el": "Emacs Lisp",
    ".erl": "Erlang",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".fish": "fish",
    ".fs": "F#",
    ".fsx": "F#",
    ".go": "Go",
    ".graphql": "GraphQL",
    ".groovy": "Groovy",
    ".gql": "GraphQL",
    ".h": "C",
    ".hh": "C++",
    ".hcl": "HCL",
    ".hlsl": "HLSL",
    ".hpp": "C++",
    ".hs": "Haskell",
    ".html": "HTML",
    ".htm": "HTML",
    ".java": "Java",
    ".jl": "Julia",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".less": "Less",
    ".lhs": "Literate Haskell",
    ".lisp": "Common Lisp",
    ".lua": "Lua",
    ".m": "Objective-C",
    ".mako": "Mako",
    ".metal": "Metal",
    ".mjs": "JavaScript",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".mm": "Objective-C++",
    ".nim": "Nim",
    ".pas": "Pascal",
    ".php": "PHP",
    ".pl": "Perl",
    ".pm": "Perl",
    ".ps1": "PowerShell",
    ".py": "Python",
    ".pyi": "Python",
    ".pyx": "Cython",
    ".r": "R",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".s": "Assembly",
    ".sass": "Sass",
    ".scala": "Scala",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".sol": "Solidity",
    ".sql": "SQL",
    ".svelte": "Svelte",
    ".swift": "Swift",
    ".tcl": "Tcl",
    ".tf": "HCL",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vb": "Visual Basic .NET",
    ".vbs": "VBScript",
    ".vue": "Vue",
    ".zig": "Zig",
    ".zsh": "Shell",
}

_SOURCE_FILENAME_LANGUAGES: Mapping[str, str] = {
    ".bashrc": "Shell",
    ".zshrc": "Shell",
    "cmakelists.txt": "CMake",
    "dockerfile": "Dockerfile",
    "jenkinsfile": "Groovy",
    "makefile": "Makefile",
    "procfile": "Procfile",
    "rakefile": "Ruby",
    "vagrantfile": "Ruby",
}

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
    if filename in _SOURCE_FILENAME_LANGUAGES or suffix in _SOURCE_EXTENSION_LANGUAGES:
        return FileCategory.SOURCE
    return FileCategory.OTHER


def source_language(change: FileChange) -> str | None:
    """Return a public Linguist language for an included source-file change."""
    if classify_file(change) is not FileCategory.SOURCE:
        return None
    path = PurePosixPath(change.path)
    filename = path.name.casefold()
    return _SOURCE_FILENAME_LANGUAGES.get(
        filename,
        _SOURCE_EXTENSION_LANGUAGES.get(path.suffix.casefold()),
    )
