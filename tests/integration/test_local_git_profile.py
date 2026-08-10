"""End-to-end aggregation and privacy checks using a temporary Git repository."""

import os
import shutil
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from it_activity.adapters.filesystem import FilesystemPublicOutputWriter
from it_activity.adapters.svg_renderer import SvgProfileRenderer
from it_activity.application.collect_activity import CollectActivity
from it_activity.application.collect_usage import CollectUsage
from it_activity.application.generate_profile import GenerateProfile
from it_activity.domain.activity import CommitMetadata, FileChange, RepositoryReference
from it_activity.domain.configuration import ProfileConfiguration
from it_activity.domain.profile import PUBLIC_OUTPUT_PATHS
from it_activity.domain.usage import allowlisted_manifest_marker

PRIVATE_REPOSITORY_NAME = "fixture-org/private-project"
PRIVATE_REPOSITORY_URL = "https://example.invalid/fixture-org/private-project.git"
PRIVATE_PATH = "src/private/customer_name.py"
PRIVATE_EMAIL = "private-owner@example.invalid"
PRIVATE_MESSAGE = "private fixture customer migration"
PRIVATE_FEATURE_MESSAGE = "private feature fixture message"
OTHER_PRIVATE_EMAIL = "other-private-author@example.invalid"
OTHER_PRIVATE_MESSAGE = "other private author message"
PRIVATE_DEPENDENCY = "private-customer-sdk"
PRIVATE_SOURCE = 'PRIVATE_CUSTOMER = "fixture-customer"'
PRIVATE_WEB_PATH = "web/private_component.ts"
OTHER_PRIVATE_PATH = "src/ignored_other_author.py"


def run_git(
    repository: Path,
    *arguments: str,
    environment: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> str:
    """Run Git without exposing fixture arguments or output on failure."""
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("Git is required for local repository integration tests.")
    safe_environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", os.defpath),
    }
    if environment is not None:
        safe_environment.update(environment)
    result = subprocess.run(  # noqa: S603 - fixed executable and controlled fixture arguments
        [executable, *arguments],
        cwd=repository,
        env=safe_environment,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError("Failed to prepare the local Git fixture.")
    return result.stdout


def write_fixture(repository: Path, relative_path: str, content: str) -> None:
    """Write one private test fixture below the temporary repository."""
    target = repository / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def commit_fixture(
    repository: Path,
    message: str,
    email: str,
    authored_at: datetime,
) -> None:
    """Commit the complete fixture worktree with deterministic private metadata."""
    timestamp = authored_at.astimezone(timezone.utc).isoformat()
    environment = {
        "GIT_AUTHOR_NAME": "Private Fixture Owner",
        "GIT_AUTHOR_EMAIL": email,
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_NAME": "Private Fixture Owner",
        "GIT_COMMITTER_EMAIL": email,
        "GIT_COMMITTER_DATE": timestamp,
    }
    run_git(repository, "add", "--all", environment=environment)
    run_git(
        repository,
        "commit",
        "--quiet",
        "--file=-",
        environment=environment,
        input_text=f"{message}\n",
    )


class StaticConfigurationProvider:
    """Return one validated private fixture configuration."""

    def __init__(self, configuration: ProfileConfiguration) -> None:
        self._configuration = configuration

    def load(self) -> ProfileConfiguration:
        return self._configuration


class FixedClock:
    """Return the deterministic aggregation instant."""

    def __init__(self, current: datetime) -> None:
        self._current = current

    def now(self) -> datetime:
        return self._current


class LocalGitSource:
    """Test-only adapter exposing a temporary Git repository through both source ports."""

    def __init__(self, repository: Path) -> None:
        self._repository = repository
        self._reference = RepositoryReference(
            repository_id=1,
            full_name=PRIVATE_REPOSITORY_NAME,
            private=True,
        )

    def list_repositories(self, owner_login: str) -> Sequence[RepositoryReference]:
        assert owner_login == "octocat"
        return (self._reference,)

    def iter_commits(
        self,
        repository: RepositoryReference,
        since: datetime,
        until: datetime,
    ) -> Iterable[CommitMetadata]:
        assert repository == self._reference
        refs = run_git(
            self._repository,
            "for-each-ref",
            "--format=%(refname)",
            "refs/heads",
        ).splitlines()
        for ref in refs:
            log = run_git(
                self._repository,
                "log",
                ref,
                f"--since={since.isoformat()}",
                f"--until={until.isoformat()}",
                "--format=%H%x09%aI%x09%ae",
            )
            for line in log.splitlines():
                sha, authored_at, author_email = line.split("\t", maxsplit=2)
                yield CommitMetadata(
                    sha=sha,
                    authored_at=datetime.fromisoformat(authored_at),
                    author_email=author_email,
                )

    def get_file_changes(
        self,
        repository: RepositoryReference,
        commit_sha: str,
    ) -> Sequence[FileChange]:
        assert repository == self._reference
        numstat = run_git(
            self._repository,
            "show",
            "--format=",
            "--numstat",
            commit_sha,
            "--",
        )
        changes: list[FileChange] = []
        for line in numstat.splitlines():
            additions, deletions, path = line.split("\t", maxsplit=2)
            binary = additions == "-" or deletions == "-"
            changes.append(
                FileChange(
                    path=path,
                    additions=0 if binary else int(additions),
                    deletions=0 if binary else int(deletions),
                    binary=binary,
                )
            )
        return tuple(changes)

    def get_language_bytes(self, repository: RepositoryReference) -> Mapping[str, int]:
        assert repository == self._reference
        return {"Python": 300, "Private Internal DSL": 100}

    def list_manifest_markers(self, repository: RepositoryReference) -> Sequence[str]:
        assert repository == self._reference
        paths = run_git(
            self._repository,
            "ls-tree",
            "-r",
            "--name-only",
            "HEAD",
        ).splitlines()
        return tuple(
            marker for path in paths if (marker := allowlisted_manifest_marker(path)) is not None
        )


def create_private_repository(repository: Path) -> None:
    """Create branches, duplicate SHAs, private metadata, and excluded files."""
    repository.mkdir()
    run_git(repository, "init", "--quiet", "--initial-branch=main")
    run_git(repository, "remote", "add", "origin", PRIVATE_REPOSITORY_URL)

    write_fixture(
        repository,
        PRIVATE_PATH,
        f"{PRIVATE_SOURCE}\ndef customer_value():\n    return 1\n",
    )
    write_fixture(repository, "README.md", "Private repository documentation\n")
    write_fixture(
        repository,
        "pyproject.toml",
        f'[project]\nname = "{PRIVATE_DEPENDENCY}"\n',
    )
    write_fixture(repository, "poetry.lock", f'name = "{PRIVATE_DEPENDENCY}"\n')
    write_fixture(repository, "generated/private_client.py", "GENERATED_PRIVATE = True\n")
    commit_fixture(
        repository,
        PRIVATE_MESSAGE,
        PRIVATE_EMAIL,
        datetime(2026, 8, 8, 20, 30, tzinfo=timezone.utc),
    )

    run_git(repository, "switch", "--quiet", "--create", "feature-private")
    write_fixture(
        repository,
        PRIVATE_PATH,
        f"{PRIVATE_SOURCE}\ndef customer_value():\n    return 2\n",
    )
    write_fixture(repository, PRIVATE_WEB_PATH, "export const privateValue = 1;\n")
    commit_fixture(
        repository,
        PRIVATE_FEATURE_MESSAGE,
        PRIVATE_EMAIL,
        datetime(2026, 8, 9, 22, 30, tzinfo=timezone.utc),
    )

    run_git(repository, "switch", "--quiet", "main")
    write_fixture(repository, OTHER_PRIVATE_PATH, "IGNORED_PRIVATE = True\n")
    commit_fixture(
        repository,
        OTHER_PRIVATE_MESSAGE,
        OTHER_PRIVATE_EMAIL,
        datetime(2026, 8, 9, 8, 0, tzinfo=timezone.utc),
    )


@dataclass(frozen=True)
class LocalProfileFixture:
    """Assembled test-only profile dependencies and filesystem locations."""

    repository: Path
    output: Path
    activity_provider: CollectActivity
    usage_provider: CollectUsage


@pytest.fixture
def local_profile_fixture(tmp_path: Path) -> LocalProfileFixture:
    """Create a fresh private repository and assemble both aggregation use cases."""
    repository = tmp_path / "private-worktree"
    output = tmp_path / "public-output"
    output.mkdir()
    try:
        create_private_repository(repository)
    except Exception as error:
        raise AssertionError("SAFE_PHASE:repository-fixture") from error

    try:
        configuration = ProfileConfiguration(
            github_login="octocat",
            author_emails=frozenset({PRIVATE_EMAIL}),
            expected_repositories=frozenset({PRIVATE_REPOSITORY_NAME}),
            timezone="Europe/Moscow",
        )
    except Exception as error:
        raise AssertionError("SAFE_PHASE:configuration") from error
    configuration_provider = StaticConfigurationProvider(configuration)
    source = LocalGitSource(repository)
    activity_provider = CollectActivity(
        configuration_provider,
        source,
        FixedClock(datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)),
    )
    usage_provider = CollectUsage(configuration_provider, source)

    return LocalProfileFixture(repository, output, activity_provider, usage_provider)


def test_local_git_activity_aggregation(local_profile_fixture: LocalProfileFixture) -> None:
    try:
        activity = local_profile_fixture.activity_provider.execute()
    except Exception as error:
        raise AssertionError("SAFE_PHASE:activity-execute") from error

    assert activity.totals(365).commits == 2, "SAFE_PHASE:commit-count"
    assert activity.totals(365).added_lines == 5, "SAFE_PHASE:added-lines"
    assert activity.totals(365).deleted_lines == 1, "SAFE_PHASE:deleted-lines"
    assert next(day for day in activity.days if day.day.isoformat() == "2026-08-08").commits == 1, (
        "SAFE_PHASE:first-day"
    )
    assert activity.days[-1].day.isoformat() == "2026-08-10", "SAFE_PHASE:last-day"
    assert activity.days[-1].commits == 1, "SAFE_PHASE:last-day-count"


def test_local_git_usage_aggregation(local_profile_fixture: LocalProfileFixture) -> None:
    usage = local_profile_fixture.usage_provider.execute()

    assert [(item.name, item.share_basis_points) for item in usage.languages] == [
        ("Python", 7500),
        ("Other", 2500),
    ]
    assert [(item.name, item.repository_count) for item in usage.technologies] == [("Python", 1)]


def test_local_git_public_output_never_contains_private_values(
    local_profile_fixture: LocalProfileFixture,
) -> None:
    result = GenerateProfile(
        local_profile_fixture.activity_provider,
        local_profile_fixture.usage_provider,
        SvgProfileRenderer(),
        FilesystemPublicOutputWriter(local_profile_fixture.output),
    ).execute()

    assert result.changed_file_count == len(PUBLIC_OUTPUT_PATHS)

    public_output = "\n".join(
        (local_profile_fixture.output / path).read_text(encoding="utf-8")
        for path in sorted(PUBLIC_OUTPUT_PATHS)
    )
    for private_value in (
        PRIVATE_REPOSITORY_NAME,
        PRIVATE_REPOSITORY_URL,
        PRIVATE_PATH,
        PRIVATE_EMAIL,
        PRIVATE_MESSAGE,
        PRIVATE_FEATURE_MESSAGE,
        OTHER_PRIVATE_EMAIL,
        OTHER_PRIVATE_MESSAGE,
        PRIVATE_DEPENDENCY,
        PRIVATE_SOURCE,
        PRIVATE_WEB_PATH,
        OTHER_PRIVATE_PATH,
        "Private Internal DSL",
        str(local_profile_fixture.repository),
    ):
        assert private_value not in public_output
