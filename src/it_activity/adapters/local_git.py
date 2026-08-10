"""Private-safe activity collection from explicitly configured local Git clones."""

import os
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import blake2b
from pathlib import Path
from urllib.parse import urlsplit

from it_activity.domain.activity import (
    ActivityDataError,
    CommitMetadata,
    FileChange,
    RepositoryReference,
)
from it_activity.domain.configuration import ConfigurationError, valid_repository_full_name
from it_activity.ports.activity_source import ActivitySourceError

LOCAL_REPOSITORIES_VARIABLE = "IT_ACTIVITY_LOCAL_REPOSITORIES"

_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40,64}$")
_SCP_REMOTE_PATTERN = re.compile(
    r"^git@(?P<host>[A-Za-z0-9.-]+):(?P<path>[^?#]+)$",
    re.IGNORECASE,
)
_REMOTE_HOST_PATTERN = re.compile(r"^(?![.-])(?=.{1,253}$)[A-Za-z0-9.-]+(?<![.-])$")
_REMOTE_PATH_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_GIT_COMMAND_TIMEOUT_SECONDS = 120


class EnvironmentLocalRepositoryPathsProvider:
    """Load optional absolute repository paths without revealing their values."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def load(self) -> tuple[Path, ...]:
        """Return one absolute path per non-empty line of the environment value."""
        raw_value = self._environ.get(LOCAL_REPOSITORIES_VARIABLE, "")
        if not raw_value.strip():
            return ()

        values = tuple(line.strip() for line in raw_value.splitlines() if line.strip())
        if not values:
            return ()
        paths = tuple(Path(value) for value in values)
        if any(
            "\0" in value or not path.is_absolute()
            for value, path in zip(values, paths, strict=True)
        ):
            raise ConfigurationError(
                f"Некорректно задана переменная окружения {LOCAL_REPOSITORIES_VARIABLE}."
            )
        if len(set(paths)) != len(paths):
            raise ConfigurationError(
                f"Переменная окружения {LOCAL_REPOSITORIES_VARIABLE} содержит повторы."
            )
        return paths


@dataclass(frozen=True, repr=False)
class _LocalRepository:
    """Resolved private location paired with its non-public domain reference."""

    path: Path
    reference: RepositoryReference


class LocalGitActivitySource:
    """Read local commit statistics without fetching or returning source content."""

    def __init__(self, repository_paths: Sequence[Path]) -> None:
        if not repository_paths:
            raise ValueError("At least one local repository path is required")
        executable = shutil.which("git")
        if executable is None:
            raise ActivitySourceError("Git недоступен для чтения локальных репозиториев.")
        self._git_executable = executable
        self._repositories = self._discover_repositories(repository_paths)
        self._repositories_by_id = {
            repository.reference.repository_id: repository for repository in self._repositories
        }

    @property
    def repository_names(self) -> frozenset[str]:
        """Return internal identities only for in-process completeness validation."""
        return frozenset(repository.reference.full_name for repository in self._repositories)

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        """Return all explicitly configured repositories in deterministic order."""
        del owner_login
        return tuple(repository.reference for repository in self._repositories)

    def iter_commits(
        self,
        repository: RepositoryReference,
        since: datetime,
        until: datetime,
    ) -> Iterable[CommitMetadata]:
        """Yield author metadata for commits reachable from every local reference."""
        if (
            since.tzinfo is None
            or since.utcoffset() is None
            or until.tzinfo is None
            or until.utcoffset() is None
            or since > until
        ):
            raise ActivitySourceError("Некорректно задан период локальной истории Git.")
        local_repository = self._repository_for(repository)
        output = self._run_git(
            local_repository.path,
            "log",
            "--branches",
            "--remotes",
            "--no-show-signature",
            "-z",
            "--format=%H%x00%at%x00%ae",
            f"--since={since.astimezone(timezone.utc).isoformat()}",
            f"--until={until.astimezone(timezone.utc).isoformat()}",
        )
        fields = output.split(b"\0")
        if fields and fields[-1] == b"":
            fields.pop()
        if len(fields) % 3 != 0:
            raise ActivitySourceError("Локальная история Git содержит некорректные данные.")

        commits: list[CommitMetadata] = []
        for offset in range(0, len(fields), 3):
            try:
                sha = fields[offset].decode("ascii")
                authored_at = datetime.fromtimestamp(
                    int(fields[offset + 1].decode("ascii")),
                    tz=timezone.utc,
                )
                author_email = fields[offset + 2].decode("utf-8")
                commits.append(
                    CommitMetadata(
                        sha=sha,
                        authored_at=authored_at,
                        author_email=author_email,
                    )
                )
            except (ActivityDataError, UnicodeDecodeError, ValueError, OverflowError):
                raise ActivitySourceError(
                    "Локальная история Git содержит некорректные данные."
                ) from None
        return tuple(commits)

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        """Return a first-parent numstat without invoking external diff programs."""
        if _SHA_PATTERN.fullmatch(commit_sha) is None:
            raise ActivitySourceError("Некорректно задан локальный Git-коммит.")
        local_repository = self._repository_for(repository)
        parent_fields = self._run_git(
            local_repository.path,
            "rev-list",
            "--parents",
            "--max-count=1",
            commit_sha,
            "--",
        ).split()
        if not parent_fields or parent_fields[0].decode("ascii", errors="ignore") != commit_sha:
            raise ActivitySourceError("Локальный Git-коммит недоступен.")

        if len(parent_fields) == 1:
            output = self._run_git(
                local_repository.path,
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--numstat",
                "-z",
                "--find-renames",
                "-l0",
                "--no-ext-diff",
                "--no-textconv",
                "-r",
                commit_sha,
                "--",
            )
        else:
            first_parent = parent_fields[1]
            if _SHA_PATTERN.fullmatch(first_parent.decode("ascii", errors="ignore")) is None:
                raise ActivitySourceError("Локальная история Git содержит некорректные данные.")
            output = self._run_git(
                local_repository.path,
                "diff",
                "--numstat",
                "-z",
                "--find-renames",
                "-l0",
                "--no-ext-diff",
                "--no-textconv",
                first_parent.decode("ascii"),
                commit_sha,
                "--",
            )
        return self._parse_numstat(output)

    def _discover_repositories(
        self,
        repository_paths: Sequence[Path],
    ) -> tuple[_LocalRepository, ...]:
        discovered: list[_LocalRepository] = []
        resolved_paths: set[Path] = set()
        names: set[str] = set()
        identifiers: set[int] = set()

        for configured_path in repository_paths:
            try:
                resolved_path = configured_path.resolve(strict=True)
            except (OSError, RuntimeError):
                raise ActivitySourceError(
                    "Один из локальных Git-репозиториев недоступен."
                ) from None
            if not resolved_path.is_dir() or resolved_path in resolved_paths:
                raise ActivitySourceError("Список локальных Git-репозиториев некорректен.")

            top_level = self._decode_single_line(
                self._run_git(resolved_path, "rev-parse", "--show-toplevel"),
                "Локальный путь не указывает на корень Git-репозитория.",
            )
            try:
                discovered_top_level = Path(top_level).resolve(strict=True)
            except (OSError, RuntimeError):
                raise ActivitySourceError(
                    "Локальный путь не указывает на корень Git-репозитория."
                ) from None
            if discovered_top_level != resolved_path:
                raise ActivitySourceError("Локальный путь не указывает на корень Git-репозитория.")

            shallow = self._decode_single_line(
                self._run_git(resolved_path, "rev-parse", "--is-shallow-repository"),
                "Не удалось проверить полноту локальной истории Git.",
            )
            if shallow not in {"true", "false"}:
                raise ActivitySourceError("Не удалось проверить полноту локальной истории Git.")
            if shallow == "true":
                raise ActivitySourceError("Локальная история Git является неполной.")
            if self._uses_partial_clone(resolved_path):
                raise ActivitySourceError("Локальная история Git является неполной.")

            remote = self._decode_single_line(
                self._run_git(resolved_path, "remote", "get-url", "origin"),
                "У локального репозитория нет безопасного Git origin.",
            )
            full_name = self._repository_name(remote)
            normalized_name = full_name.casefold()
            repository_id = self._repository_id(normalized_name)
            if normalized_name in names or repository_id in identifiers:
                raise ActivitySourceError("Список локальных Git-репозиториев содержит повторы.")

            empty = not bool(
                self._run_git(
                    resolved_path,
                    "rev-list",
                    "--branches",
                    "--remotes",
                    "--max-count=1",
                    "--",
                ).strip()
            )
            discovered.append(
                _LocalRepository(
                    path=resolved_path,
                    reference=RepositoryReference(
                        repository_id=repository_id,
                        full_name=full_name,
                        private=True,
                        empty=empty,
                    ),
                )
            )
            resolved_paths.add(resolved_path)
            names.add(normalized_name)
            identifiers.add(repository_id)

        return tuple(
            sorted(
                discovered,
                key=lambda item: (
                    item.reference.full_name.casefold(),
                    item.reference.repository_id,
                ),
            )
        )

    def _repository_for(self, repository: RepositoryReference) -> _LocalRepository:
        local_repository = self._repositories_by_id.get(repository.repository_id)
        if local_repository is None or local_repository.reference != repository:
            raise ActivitySourceError("Репозиторий отсутствует в проверенном локальном списке.")
        return local_repository

    def _uses_partial_clone(self, repository: Path) -> bool:
        records = self._run_git(repository, "config", "--local", "-z", "--list").split(b"\0")
        for record in records:
            if not record:
                continue
            raw_key, separator, raw_value = record.partition(b"\n")
            if not separator:
                raise ActivitySourceError("Не удалось проверить полноту локальной истории Git.")
            key = raw_key.lower()
            value = raw_value.strip().lower()
            if key == b"extensions.partialclone" or (
                key.startswith(b"remote.") and key.endswith(b".promisor") and value == b"true"
            ):
                return True
        return False

    def _run_git(self, repository: Path, *arguments: str) -> bytes:
        environment = {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_EXTERNAL_DIFF": "",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": os.environ.get("PATH", os.defpath),
        }
        try:
            result = subprocess.run(  # noqa: S603 - executable is resolved with shutil.which
                [self._git_executable, "--no-pager", *arguments],
                cwd=repository,
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
                timeout=_GIT_COMMAND_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ActivitySourceError("Не удалось прочитать локальный Git-репозиторий.") from None
        if result.returncode != 0:
            raise ActivitySourceError("Не удалось прочитать локальный Git-репозиторий.")
        return result.stdout

    @staticmethod
    def _decode_single_line(value: bytes, error_message: str) -> str:
        try:
            decoded = value.decode("utf-8").strip()
        except UnicodeDecodeError:
            raise ActivitySourceError(error_message) from None
        if not decoded or any(character in decoded for character in "\r\n\0"):
            raise ActivitySourceError(error_message)
        return decoded

    @staticmethod
    def _repository_name(remote: str) -> str:
        """Return a GitHub name or an opaque identity for another safe Git host."""
        if remote != remote.strip() or any(character in remote for character in "\r\n\0"):
            raise ActivitySourceError("У локального репозитория нет безопасного Git origin.")

        scp_match = _SCP_REMOTE_PATTERN.fullmatch(remote)
        if scp_match is not None:
            host = scp_match.group("host").casefold()
            raw_path = scp_match.group("path")
        else:
            try:
                parsed = urlsplit(remote)
                port = parsed.port
            except ValueError:
                raise ActivitySourceError(
                    "У локального репозитория нет безопасного Git origin."
                ) from None
            scheme = parsed.scheme.casefold()
            allowed_scheme = scheme in {"https", "ssh"}
            allowed_user = (scheme == "https" and parsed.username is None) or (
                scheme == "ssh" and parsed.username == "git"
            )
            allowed_port = (scheme == "https" and port in {None, 443}) or (
                scheme == "ssh" and port in {None, 22}
            )
            canonical_path = (
                parsed.path.startswith("/")
                and not parsed.path.endswith("/")
                and "//" not in parsed.path
            )
            if (
                not allowed_scheme
                or parsed.hostname is None
                or parsed.password is not None
                or not allowed_user
                or not allowed_port
                or parsed.query
                or parsed.fragment
                or not canonical_path
            ):
                raise ActivitySourceError("У локального репозитория нет безопасного Git origin.")
            host = parsed.hostname.casefold()
            raw_path = parsed.path.removeprefix("/")

        if (
            _REMOTE_HOST_PATTERN.fullmatch(host) is None
            or ".." in host
            or raw_path.startswith("/")
            or raw_path.endswith("/")
            or "//" in raw_path
        ):
            raise ActivitySourceError("У локального репозитория нет безопасного Git origin.")

        components = raw_path.split("/")
        if components and components[-1].casefold().endswith(".git"):
            components[-1] = components[-1][:-4]
        if len(components) < 2 or any(
            component in {".", ".."} or _REMOTE_PATH_COMPONENT_PATTERN.fullmatch(component) is None
            for component in components
        ):
            raise ActivitySourceError("У локального репозитория нет безопасного Git origin.")

        if host == "github.com":
            full_name = "/".join(components)
            if len(components) != 2 or not valid_repository_full_name(full_name):
                raise ActivitySourceError("У локального репозитория нет безопасного Git origin.")
            return full_name

        canonical_remote = f"{host}/{'/'.join(components)}"
        opaque_name = blake2b(canonical_remote.encode("utf-8"), digest_size=16).hexdigest()
        return f"local/{opaque_name}"

    @staticmethod
    def _repository_id(normalized_name: str) -> int:
        digest = blake2b(normalized_name.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, byteorder="big") or 1

    @staticmethod
    def _parse_numstat(output: bytes) -> tuple[FileChange, ...]:
        records = output.split(b"\0")
        if records and records[-1] == b"":
            records.pop()
        changes: list[FileChange] = []
        offset = 0
        while offset < len(records):
            record = records[offset]
            offset += 1
            components = record.split(b"\t", maxsplit=2)
            if len(components) != 3:
                raise ActivitySourceError("Локальный Git diff содержит некорректные данные.")
            raw_additions, raw_deletions, raw_path = components
            if not raw_path:
                if offset + 1 >= len(records):
                    raise ActivitySourceError("Локальный Git diff содержит некорректные данные.")
                raw_old_path = records[offset]
                raw_path = records[offset + 1]
                offset += 2
                LocalGitActivitySource._decode_git_path(raw_old_path)
            binary = raw_additions == b"-" or raw_deletions == b"-"
            try:
                additions = 0 if binary else int(raw_additions.decode("ascii"))
                deletions = 0 if binary else int(raw_deletions.decode("ascii"))
                path = LocalGitActivitySource._decode_git_path(raw_path)
                changes.append(
                    FileChange(
                        path=path,
                        additions=additions,
                        deletions=deletions,
                        binary=binary,
                    )
                )
            except (ActivityDataError, UnicodeDecodeError, ValueError):
                raise ActivitySourceError(
                    "Локальный Git diff содержит некорректные данные."
                ) from None
        return tuple(changes)

    @staticmethod
    def _decode_git_path(raw_path: bytes) -> str:
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError:
            raise ActivitySourceError("Локальный Git diff содержит некорректные данные.") from None
        if not path or any(character in path for character in "\r\n\0"):
            raise ActivitySourceError("Локальный Git diff содержит некорректные данные.")
        return path
