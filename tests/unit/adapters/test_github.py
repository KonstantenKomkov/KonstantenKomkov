"""Contract tests for paginated private-safe GitHub REST collection."""

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest

from it_activity.adapters.github import GITHUB_API_VERSION, GitHubApiError, GitHubRestActivitySource
from it_activity.domain.activity import RepositoryReference
from it_activity.ports.http import HttpResponse

API_URL = "https://api.github.test"
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def response(
    value: object,
    status: int = 200,
    headers: Mapping[str, str] | None = None,
) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers={"content-type": "application/json", **(headers or {})},
        body=json.dumps(value).encode(),
    )


def url(path: str, **parameters: str) -> str:
    base = f"{API_URL}{path}"
    return base if not parameters else f"{base}?{urlencode(sorted(parameters.items()))}"


class StubHttpClient:
    """Return exact fixture responses and record credential handling."""

    def __init__(self, responses: Mapping[str, HttpResponse]) -> None:
        self._responses = responses
        self.requests: list[tuple[str, Mapping[str, str]]] = []

    def get(self, request_url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.requests.append((request_url, dict(headers)))
        return self._responses[request_url]


def repository_item(
    identifier: int,
    full_name: str,
    private: bool,
    default_branch: str = "main",
    pushed_at: object = "2026-08-01T00:00:00Z",
) -> dict[str, object]:
    return {
        "id": identifier,
        "full_name": full_name,
        "private": private,
        "default_branch": default_branch,
        "pushed_at": pushed_at,
    }


def commit_item(sha: str, email: str, date: str, message: str) -> dict[str, object]:
    return {
        "sha": sha,
        "commit": {
            "author": {"email": email, "date": date},
            "message": message,
        },
    }


def test_list_repositories_checks_identity_and_fetches_every_page() -> None:
    routes = {
        url("/user"): response({"login": "octocat"}),
        url(
            "/user/repos",
            affiliation="owner,collaborator,organization_member",
            direction="asc",
            page="1",
            per_page="2",
            sort="full_name",
            visibility="all",
        ): response(
            [
                repository_item(1, "octocat/public-fixture", False),
                repository_item(2, "fixture-org/private-fixture", True),
            ]
        ),
        url(
            "/user/repos",
            affiliation="owner,collaborator,organization_member",
            direction="asc",
            page="2",
            per_page="2",
            sort="full_name",
            visibility="all",
        ): response([repository_item(3, "fixture-org/collaborator-fixture", True)]),
    }
    http_client = StubHttpClient(routes)
    source = GitHubRestActivitySource(
        http_client,
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    repositories = source.list_repositories("OCTOCAT")
    cached_repositories = source.list_repositories("octocat")

    assert [(item.repository_id, item.private) for item in repositories] == [
        (1, False),
        (2, True),
        (3, True),
    ]
    assert cached_repositories == repositories
    assert len(http_client.requests) == 3
    assert all(item.default_branch == "main" and not item.empty for item in repositories)
    assert all("fixture-credential" not in request_url for request_url, _ in http_client.requests)
    assert all(
        headers["Authorization"] == "Bearer fixture-credential"
        for _, headers in http_client.requests
    )
    assert all(
        headers["X-GitHub-Api-Version"] == GITHUB_API_VERSION for _, headers in http_client.requests
    )
    assert "private-fixture" not in repr(repositories[1])


def test_iter_commits_fetches_every_branch_and_page_without_messages() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    since = datetime(2026, 8, 1, tzinfo=timezone.utc)
    until = datetime(2026, 8, 10, tzinfo=timezone.utc)
    common = {
        "since": "2026-08-01T00:00:00Z",
        "until": "2026-08-10T00:00:00Z",
        "per_page": "2",
    }
    routes = {
        url("/repos/fixture-org/private-fixture/branches", page="1", per_page="2"): response(
            [{"name": "main"}, {"name": "feature/private-fixture"}]
        ),
        url("/repos/fixture-org/private-fixture/branches", page="2", per_page="2"): response([]),
        url(
            "/repos/fixture-org/private-fixture/commits",
            page="1",
            sha="main",
            **common,
        ): response(
            [
                commit_item(
                    SHA_A,
                    "owner@example.invalid",
                    "2026-08-09T10:00:00Z",
                    "private fixture message A",
                ),
                commit_item(
                    SHA_B,
                    "other@example.invalid",
                    "2026-08-08T10:00:00+00:00",
                    "private fixture message B",
                ),
            ]
        ),
        url(
            "/repos/fixture-org/private-fixture/commits",
            page="2",
            sha="main",
            **common,
        ): response(
            [
                commit_item(
                    SHA_C,
                    "owner@example.invalid",
                    "2026-08-07T10:00:00Z",
                    "private fixture message C",
                )
            ]
        ),
        url(
            "/repos/fixture-org/private-fixture/commits",
            page="1",
            sha="feature/private-fixture",
            **common,
        ): response(
            [
                commit_item(
                    SHA_A,
                    "owner@example.invalid",
                    "2026-08-09T10:00:00Z",
                    "private fixture message A",
                )
            ]
        ),
    }
    source = GitHubRestActivitySource(
        StubHttpClient(routes),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    commits = tuple(source.iter_commits(repository, since, until))

    assert [commit.sha for commit in commits] == [SHA_A, SHA_B, SHA_C, SHA_A]
    assert commits[0].author_email == "owner@example.invalid"
    assert "private fixture message" not in repr(commits)
    assert "owner@example.invalid" not in repr(commits)


def test_get_file_changes_follows_link_header_and_accepts_file_counts() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    commit_path = f"/repos/fixture-org/private-fixture/commits/{SHA_A}"
    stats = {"additions": 15, "deletions": 3}
    routes = {
        url(commit_path, page="1", per_page="2"): response(
            {
                "sha": SHA_A,
                "stats": stats,
                "files": [
                    {
                        "filename": "src/private_name.py",
                        "additions": 10,
                        "deletions": 2,
                        "patch": "diff",
                    },
                    {"filename": "README.md", "additions": 5, "deletions": 1, "patch": "diff"},
                ],
            },
            headers={
                "Link": (
                    f'<{url(commit_path, page="2", per_page="2")}>; rel="next", '
                    f'<{url(commit_path, page="2", per_page="2")}>; rel="last"'
                )
            },
        ),
        url(commit_path, page="2", per_page="2"): response(
            {
                "sha": SHA_A,
                "stats": stats,
                "files": [{"filename": "assets/private.png", "additions": 0, "deletions": 0}],
            }
        ),
    }
    source = GitHubRestActivitySource(
        StubHttpClient(routes),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    changes = source.get_file_changes(repository, SHA_A)

    assert [(change.additions, change.deletions, change.binary) for change in changes] == [
        (10, 2, False),
        (5, 1, False),
        (0, 0, True),
    ]
    assert "private_name.py" not in repr(changes)
    assert "private.png" not in repr(changes)


def test_github_error_redacts_repository_sha_url_and_credential() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    request_url = url(
        f"/repos/fixture-org/private-fixture/commits/{SHA_A}",
        page="1",
        per_page="2",
    )
    source = GitHubRestActivitySource(
        StubHttpClient({request_url: response({"message": "private failure"}, status=404)}),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    with pytest.raises(GitHubApiError) as captured:
        source.get_file_changes(repository, SHA_A)

    message = str(captured.value)
    assert "HTTP 404" in message
    assert "private-fixture" not in message
    assert SHA_A not in message
    assert "fixture-credential" not in message


def test_github_rejects_credential_for_another_account() -> None:
    source = GitHubRestActivitySource(
        StubHttpClient({url("/user"): response({"login": "different-user"})}),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    with pytest.raises(GitHubApiError, match="настроенному аккаунту"):
        source.list_repositories("octocat")


def test_repository_pagination_failure_blocks_partial_result() -> None:
    first_page_url = url(
        "/user/repos",
        affiliation="owner,collaborator,organization_member",
        direction="asc",
        page="1",
        per_page="2",
        sort="full_name",
        visibility="all",
    )
    second_page_url = url(
        "/user/repos",
        affiliation="owner,collaborator,organization_member",
        direction="asc",
        page="2",
        per_page="2",
        sort="full_name",
        visibility="all",
    )
    source = GitHubRestActivitySource(
        StubHttpClient(
            {
                url("/user"): response({"login": "octocat"}),
                first_page_url: response(
                    [
                        repository_item(1, "fixture-org/private-one", True),
                        repository_item(2, "fixture-org/private-two", True),
                    ]
                ),
                second_page_url: response({"message": "private failure"}, status=503),
            }
        ),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    with pytest.raises(GitHubApiError, match="HTTP 503") as captured:
        source.list_repositories("octocat")

    assert "private-one" not in str(captured.value)
    assert "private-two" not in str(captured.value)


def test_file_totals_do_not_override_complete_github_pagination() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    commit_path = f"/repos/fixture-org/private-fixture/commits/{SHA_A}"
    source = GitHubRestActivitySource(
        StubHttpClient(
            {
                url(commit_path, page="1", per_page="2"): response(
                    {
                        "sha": SHA_A,
                        "stats": {"additions": 99, "deletions": 1},
                        "files": [
                            {
                                "filename": "src/private_name.py",
                                "additions": 1,
                                "deletions": 1,
                                "patch": "diff",
                            }
                        ],
                    }
                )
            }
        ),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    changes = source.get_file_changes(repository, SHA_A)

    assert [(change.additions, change.deletions) for change in changes] == [(1, 1)]
    assert "private_name.py" not in repr(changes)


def test_full_file_page_without_next_link_is_complete() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    commit_path = f"/repos/fixture-org/private-fixture/commits/{SHA_A}"
    first_page_url = url(commit_path, page="1", per_page="2")
    http_client = StubHttpClient(
        {
            first_page_url: response(
                {
                    "sha": SHA_A,
                    "files": [
                        {
                            "filename": "src/private_one.py",
                            "additions": 1,
                            "deletions": 0,
                            "patch": "diff",
                        },
                        {
                            "filename": "src/private_two.py",
                            "additions": 0,
                            "deletions": 1,
                            "patch": "diff",
                        },
                    ],
                }
            )
        }
    )
    source = GitHubRestActivitySource(
        http_client,
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    changes = source.get_file_changes(repository, SHA_A)

    assert [(change.additions, change.deletions) for change in changes] == [(1, 0), (0, 1)]
    assert [request_url for request_url, _ in http_client.requests] == [first_page_url]
    assert "private_one.py" not in repr(changes)
    assert "private_two.py" not in repr(changes)


def test_file_next_link_failure_blocks_partial_diff() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    commit_path = f"/repos/fixture-org/private-fixture/commits/{SHA_A}"
    second_page_url = url(commit_path, page="2", per_page="2")
    source = GitHubRestActivitySource(
        StubHttpClient(
            {
                url(commit_path, page="1", per_page="2"): response(
                    {
                        "sha": SHA_A,
                        "files": [
                            {
                                "filename": "src/private_name.py",
                                "additions": 1,
                                "deletions": 1,
                                "patch": "diff",
                            }
                        ],
                    },
                    headers={"link": f'<{second_page_url}>; rel="next"'},
                ),
                second_page_url: response({"message": "private failure"}, status=503),
            }
        ),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    with pytest.raises(GitHubApiError, match="HTTP 503") as captured:
        source.get_file_changes(repository, SHA_A)

    assert "private_name.py" not in str(captured.value)


def test_file_pagination_rejects_cross_origin_link_without_leaking_it() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    commit_path = f"/repos/fixture-org/private-fixture/commits/{SHA_A}"
    source = GitHubRestActivitySource(
        StubHttpClient(
            {
                url(commit_path, page="1", per_page="2"): response(
                    {
                        "sha": SHA_A,
                        "files": [
                            {
                                "filename": "src/private_name.py",
                                "additions": 1,
                                "deletions": 1,
                                "patch": "diff",
                            }
                        ],
                    },
                    headers={"link": '<https://private.example.invalid/page/2>; rel="next"'},
                )
            }
        ),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    with pytest.raises(GitHubApiError, match="некорректную пагинацию") as captured:
        source.get_file_changes(repository, SHA_A)

    message = str(captured.value)
    assert "private.example.invalid" not in message
    assert "private_name.py" not in message


def test_get_language_bytes_returns_linguist_counts_without_repository_details() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    source = GitHubRestActivitySource(
        StubHttpClient(
            {
                url("/repos/fixture-org/private-fixture/languages"): response(
                    {"Python": 120, "Private Fixture Language": 30}
                )
            }
        ),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    languages = source.get_language_bytes(repository)

    assert languages == {"Python": 120, "Private Fixture Language": 30}
    assert "private-fixture" not in repr(languages)


def test_manifest_tree_returns_only_allowlisted_markers() -> None:
    repository = RepositoryReference(1, "fixture-org/private-fixture", private=True)
    tree_url = url(
        "/repos/fixture-org/private-fixture/git/trees/main",
        recursive="1",
    )
    source = GitHubRestActivitySource(
        StubHttpClient(
            {
                tree_url: response(
                    {
                        "truncated": False,
                        "tree": [
                            {
                                "path": "private/service/package.json",
                                "type": "blob",
                                "sha": "1" * 40,
                            },
                            {
                                "path": "private/unique-name.secret",
                                "type": "blob",
                                "sha": "2" * 40,
                            },
                            {
                                "path": "private/backend/service.csproj",
                                "type": "blob",
                                "sha": "3" * 40,
                            },
                        ],
                    }
                )
            }
        ),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    markers = source.list_manifest_markers(repository)

    assert markers == (".csproj", "package.json")
    assert "private" not in repr(markers)
    assert "unique-name" not in repr(markers)


def test_truncated_manifest_tree_falls_back_to_complete_subtree_walk() -> None:
    subtree_sha = "1" * 40
    repository = RepositoryReference(
        1,
        "fixture-org/private-fixture",
        private=True,
        default_branch="feature/private",
    )
    tree_path = "/repos/fixture-org/private-fixture/git/trees/feature%2Fprivate"
    routes = {
        url(tree_path, recursive="1"): response({"truncated": True, "tree": []}),
        url(tree_path): response(
            {
                "truncated": False,
                "tree": [
                    {"path": "private-directory", "type": "tree", "sha": subtree_sha},
                    {"path": "Dockerfile", "type": "blob", "sha": "2" * 40},
                ],
            }
        ),
        url(f"/repos/fixture-org/private-fixture/git/trees/{subtree_sha}"): response(
            {
                "truncated": False,
                "tree": [
                    {"path": "pyproject.toml", "type": "blob", "sha": "3" * 40},
                    {"path": "private-dependency.json", "type": "blob", "sha": "4" * 40},
                ],
            }
        ),
    }
    source = GitHubRestActivitySource(
        StubHttpClient(routes),
        "fixture-credential",
        api_url=API_URL,
        page_size=2,
    )

    markers = source.list_manifest_markers(repository)

    assert markers == ("Dockerfile", "pyproject.toml")
    assert "private-directory" not in repr(markers)
    assert "private-dependency" not in repr(markers)
