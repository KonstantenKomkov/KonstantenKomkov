"""Private-safe GitHub REST activity source."""

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Optional, cast
from urllib.parse import quote, urlencode, urlsplit

from it_activity.domain.activity import (
    ActivityDataError,
    CommitMetadata,
    FileChange,
    RepositoryReference,
)
from it_activity.domain.usage import allowlisted_manifest_marker
from it_activity.ports.activity_source import ActivitySourceError
from it_activity.ports.http import HttpClient, HttpTransportError

GITHUB_API_URL = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"
DEFAULT_PAGE_SIZE = 100
MAX_PAGES = 10_000
MAX_COMMIT_FILES = 3_000
MAX_TREE_REQUESTS = 100_000


class GitHubApiError(ActivitySourceError):
    """A redacted GitHub API failure."""


class GitHubRestActivitySource:
    """Collect repositories, every branch, commits, and complete file diffs."""

    def __init__(
        self,
        http_client: HttpClient,
        token: str,
        api_url: str = GITHUB_API_URL,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        normalized_api_url = api_url.rstrip("/")
        parsed_api_url = urlsplit(normalized_api_url)
        if (
            parsed_api_url.scheme != "https"
            or not parsed_api_url.netloc
            or parsed_api_url.username is not None
            or parsed_api_url.password is not None
            or parsed_api_url.query
            or parsed_api_url.fragment
        ):
            raise ValueError("GitHub API URL must be a credential-free HTTPS URL")
        if not token or token != token.strip() or any(character.isspace() for character in token):
            raise GitHubApiError("Некорректно задан токен чтения GitHub.")
        if page_size <= 0 or page_size > DEFAULT_PAGE_SIZE:
            raise ValueError("GitHub page size must be between 1 and 100")

        self._http_client = http_client
        self._token = token
        self._api_url = normalized_api_url
        self._api_origin = (parsed_api_url.scheme, parsed_api_url.netloc)
        self._page_size = page_size
        self._repository_cache: dict[str, tuple[RepositoryReference, ...]] = {}

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        """Return all repositories explicitly readable by the authenticated user."""
        cache_key = owner_login.casefold()
        cached = self._repository_cache.get(cache_key)
        if cached is not None:
            return cached
        authenticated_user = self._as_object(self._get_json("/user"))
        authenticated_login = self._required_string(authenticated_user, "login")
        if authenticated_login.casefold() != owner_login.casefold():
            raise GitHubApiError("Токен GitHub не принадлежит настроенному аккаунту.")

        values = self._get_paginated_array(
            "/user/repos",
            {
                "affiliation": "owner,collaborator,organization_member",
                "direction": "asc",
                "sort": "full_name",
                "visibility": "all",
            },
        )
        repositories: list[RepositoryReference] = []
        try:
            for value in values:
                item = self._as_object(value)
                repositories.append(
                    RepositoryReference(
                        repository_id=self._required_integer(item, "id"),
                        full_name=self._required_string(item, "full_name"),
                        private=self._required_boolean(item, "private"),
                        default_branch=self._required_string(item, "default_branch"),
                        empty=self._repository_is_empty(item),
                    )
                )
        except ActivityDataError:
            raise GitHubApiError("GitHub вернул некорректные данные репозитория.") from None
        result = tuple(repositories)
        self._repository_cache[cache_key] = result
        return result

    def get_language_bytes(self, repository: RepositoryReference) -> Mapping[str, int]:
        """Return byte counts calculated by GitHub Linguist for the default branch."""
        repository_path = quote(repository.full_name, safe="/")
        value = self._as_object(self._get_json(f"/repos/{repository_path}/languages"))
        language_bytes: dict[str, int] = {}
        for language, byte_count in value.items():
            if (
                not language
                or not isinstance(byte_count, int)
                or isinstance(byte_count, bool)
                or byte_count < 0
                or any(character in language for character in "\r\n\0")
            ):
                raise GitHubApiError("GitHub вернул некорректную языковую статистику.")
            language_bytes[language] = byte_count
        return language_bytes

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        """Traverse the default tree and return no private paths, only allowlisted markers."""
        repository_path = quote(repository.full_name, safe="/")
        default_ref = repository.default_branch
        recursive_tree = self._get_tree(repository_path, default_ref, recursive=True)
        if not self._required_boolean(recursive_tree, "truncated"):
            recursive_markers, _ = self._tree_markers_and_subtrees(recursive_tree)
            return tuple(sorted(recursive_markers))

        markers: set[str] = set()
        pending_refs = [default_ref]
        visited_refs: set[str] = set()
        request_count = 0
        while pending_refs:
            tree_ref = pending_refs.pop()
            if tree_ref in visited_refs:
                continue
            visited_refs.add(tree_ref)
            request_count += 1
            if request_count > MAX_TREE_REQUESTS:
                raise GitHubApiError("Дерево GitHub превысило допустимое число поддеревьев.")
            tree = self._get_tree(repository_path, tree_ref, recursive=False)
            if self._required_boolean(tree, "truncated"):
                raise GitHubApiError("GitHub вернул усечённое поддерево репозитория.")
            tree_markers, subtree_refs = self._tree_markers_and_subtrees(tree)
            markers.update(tree_markers)
            pending_refs.extend(subtree_refs)
        return tuple(sorted(markers))

    def iter_commits(
        self,
        repository: RepositoryReference,
        since: datetime,
        until: datetime,
    ) -> Iterable[CommitMetadata]:
        """Yield paginated commit metadata for every current repository branch."""
        if (
            since.tzinfo is None
            or since.utcoffset() is None
            or until.tzinfo is None
            or until.utcoffset() is None
            or since > until
        ):
            raise GitHubApiError("Некорректно задан период истории GitHub.")

        repository_path = quote(repository.full_name, safe="/")
        branch_values = self._get_paginated_array(f"/repos/{repository_path}/branches", {})
        branch_names: set[str] = set()
        for branch_value in branch_values:
            branch = self._as_object(branch_value)
            branch_name = self._required_string(branch, "name")
            if branch_name in branch_names:
                raise GitHubApiError("GitHub вернул повторяющуюся ветку.")
            branch_names.add(branch_name)

            commit_values = self._get_paginated_array(
                f"/repos/{repository_path}/commits",
                {
                    "sha": branch_name,
                    "since": self._format_timestamp(since),
                    "until": self._format_timestamp(until),
                },
            )
            for commit_value in commit_values:
                try:
                    yield self._parse_commit(commit_value)
                except ActivityDataError:
                    raise GitHubApiError("GitHub вернул некорректные данные коммита.") from None

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        """Return all file changes, failing if GitHub might have truncated them."""
        repository_path = quote(repository.full_name, safe="/")
        commit_path = quote(commit_sha, safe="")
        path = f"/repos/{repository_path}/commits/{commit_path}"
        changes: list[FileChange] = []
        seen_paths: set[str] = set()
        seen_pages: set[bytes] = set()
        expected_additions: Optional[int] = None
        expected_deletions: Optional[int] = None

        for page in range(1, MAX_PAGES + 1):
            value, page_digest = self._get_json_page(path, {}, page)
            if page_digest in seen_pages:
                raise GitHubApiError("GitHub повторил страницу файлов коммита.")
            seen_pages.add(page_digest)
            commit = self._as_object(value)
            response_sha = self._required_string(commit, "sha").casefold()
            if response_sha != commit_sha.casefold():
                raise GitHubApiError("GitHub вернул данные другого коммита.")

            if page == 1:
                stats = self._as_object(commit.get("stats"))
                expected_additions = self._required_integer(stats, "additions")
                expected_deletions = self._required_integer(stats, "deletions")

            file_values = self._as_array(commit.get("files"))
            if len(file_values) > self._page_size:
                raise GitHubApiError("GitHub превысил ожидаемый размер страницы файлов.")
            try:
                for file_value in file_values:
                    item = self._as_object(file_value)
                    file_path = self._required_string(item, "filename")
                    if file_path in seen_paths:
                        raise GitHubApiError("GitHub вернул повторяющийся файл коммита.")
                    seen_paths.add(file_path)
                    additions = self._required_integer(item, "additions")
                    deletions = self._required_integer(item, "deletions")
                    changes.append(
                        FileChange(
                            path=file_path,
                            additions=additions,
                            deletions=deletions,
                            binary=("patch" not in item and additions == 0 and deletions == 0),
                        )
                    )
            except ActivityDataError:
                raise GitHubApiError("GitHub вернул некорректные данные файла.") from None

            if len(changes) >= MAX_COMMIT_FILES:
                raise GitHubApiError("Diff коммита достиг лимита GitHub и может быть неполным.")
            if len(file_values) < self._page_size:
                break
        else:
            raise GitHubApiError("GitHub превысил допустимое число страниц файлов.")

        if expected_additions is None or expected_deletions is None:
            raise GitHubApiError("GitHub не вернул статистику коммита.")
        if (
            sum(change.additions for change in changes) != expected_additions
            or sum(change.deletions for change in changes) != expected_deletions
        ):
            raise GitHubApiError("Файловая статистика GitHub оказалась неполной.")
        return tuple(changes)

    def _get_paginated_array(
        self,
        path: str,
        parameters: Mapping[str, str],
    ) -> tuple[object, ...]:
        values: list[object] = []
        seen_pages: set[bytes] = set()
        for page in range(1, MAX_PAGES + 1):
            value, page_digest = self._get_json_page(path, parameters, page)
            if page_digest in seen_pages:
                raise GitHubApiError("GitHub повторил страницу пагинации.")
            seen_pages.add(page_digest)
            page_values = self._as_array(value)
            if len(page_values) > self._page_size:
                raise GitHubApiError("GitHub превысил ожидаемый размер страницы.")
            values.extend(page_values)
            if len(page_values) < self._page_size:
                return tuple(values)
        raise GitHubApiError("GitHub превысил допустимое число страниц.")

    def _get_json(self, path: str) -> object:
        value, _ = self._get_json_page(path, {}, None)
        return value

    def _get_tree(
        self,
        repository_path: str,
        tree_ref: str,
        recursive: bool,
    ) -> dict[str, object]:
        encoded_ref = quote(tree_ref, safe="")
        parameters = {"recursive": "1"} if recursive else {}
        value, _ = self._get_json_page(
            f"/repos/{repository_path}/git/trees/{encoded_ref}",
            parameters,
            None,
        )
        return self._as_object(value)

    def _tree_markers_and_subtrees(
        self,
        tree: Mapping[str, object],
    ) -> tuple[set[str], list[str]]:
        markers: set[str] = set()
        subtree_refs: list[str] = []
        for entry_value in self._as_array(tree.get("tree")):
            entry = self._as_object(entry_value)
            entry_type = self._required_string(entry, "type")
            path = self._required_string(entry, "path")
            if entry_type == "blob":
                marker = allowlisted_manifest_marker(path)
                if marker is not None:
                    markers.add(marker)
            elif entry_type == "tree":
                subtree_refs.append(self._required_string(entry, "sha"))
            elif entry_type != "commit":
                raise GitHubApiError("GitHub вернул неизвестный тип элемента дерева.")
        return markers, subtree_refs

    def _get_json_page(
        self,
        path: str,
        parameters: Mapping[str, str],
        page: Optional[int],
    ) -> tuple[object, bytes]:
        query = dict(parameters)
        if page is not None:
            query.update({"page": str(page), "per_page": str(self._page_size)})
        url = self._build_url(path, query)
        try:
            response = self._http_client.get(url, self._headers())
        except HttpTransportError:
            raise GitHubApiError("Не удалось получить полный ответ GitHub API.") from None
        if response.status != 200:
            raise GitHubApiError(f"GitHub API вернул ошибку HTTP {response.status}.")
        try:
            value: object = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GitHubApiError("GitHub API вернул некорректный JSON.") from None
        return value, hashlib.sha256(response.body).digest()

    def _build_url(self, path: str, parameters: Mapping[str, str]) -> str:
        if not path.startswith("/") or any(character in path for character in "\r\n\0"):
            raise GitHubApiError("Некорректно сформирован путь GitHub API.")
        url = f"{self._api_url}{path}"
        if parameters:
            url = f"{url}?{urlencode(sorted(parameters.items()))}"
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.netloc) != self._api_origin:
            raise GitHubApiError("GitHub API попытался изменить источник запроса.")
        return url

    def _headers(self) -> Mapping[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "it-activity/0.1",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

    @classmethod
    def _parse_commit(cls, value: object) -> CommitMetadata:
        item = cls._as_object(value)
        git_commit = cls._as_object(item.get("commit"))
        author = cls._as_object(git_commit.get("author"))
        return CommitMetadata(
            sha=cls._required_string(item, "sha"),
            authored_at=cls._parse_timestamp(cls._required_string(author, "date")),
            author_email=cls._required_string(author, "email", allow_empty=True),
        )

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            raise GitHubApiError("GitHub вернул некорректную дату коммита.") from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise GitHubApiError("GitHub вернул дату коммита без часового пояса.")
        return parsed

    @staticmethod
    def _as_object(value: object) -> dict[str, object]:
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise GitHubApiError("GitHub вернул объект в неожиданном формате.")
        return cast(dict[str, object], value)

    @staticmethod
    def _as_array(value: object) -> list[object]:
        if not isinstance(value, list):
            raise GitHubApiError("GitHub вернул список в неожиданном формате.")
        return cast(list[object], value)

    @staticmethod
    def _required_string(
        value: Mapping[str, object],
        key: str,
        allow_empty: bool = False,
    ) -> str:
        result = value.get(key)
        if not isinstance(result, str) or (not allow_empty and not result):
            raise GitHubApiError("В ответе GitHub отсутствует обязательная строка.")
        return result

    @staticmethod
    def _required_integer(value: Mapping[str, object], key: str) -> int:
        result = value.get(key)
        if not isinstance(result, int) or isinstance(result, bool) or result < 0:
            raise GitHubApiError("В ответе GitHub отсутствует обязательное число.")
        return result

    @staticmethod
    def _required_boolean(value: Mapping[str, object], key: str) -> bool:
        result = value.get(key)
        if not isinstance(result, bool):
            raise GitHubApiError("В ответе GitHub отсутствует обязательный флаг.")
        return result

    @staticmethod
    def _repository_is_empty(value: Mapping[str, object]) -> bool:
        if "pushed_at" not in value:
            raise GitHubApiError("В ответе GitHub отсутствует статус репозитория.")
        pushed_at = value["pushed_at"]
        if pushed_at is not None and not isinstance(pushed_at, str):
            raise GitHubApiError("GitHub вернул некорректный статус репозитория.")
        return pushed_at is None
