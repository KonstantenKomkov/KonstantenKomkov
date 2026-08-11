"""End-to-end aggregation and privacy checks using a temporary Git repository."""

import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from it_activity.adapters.filesystem import FilesystemPublicOutputWriter
from it_activity.adapters.local_git import LocalGitActivitySource
from it_activity.adapters.svg_renderer import SvgProfileRenderer
from it_activity.application.collect_activity import CollectActivity
from it_activity.application.collect_usage import CollectUsage
from it_activity.application.generate_profile import GenerateProfile
from it_activity.domain.activity import FileChange
from it_activity.domain.configuration import ProfileConfiguration
from it_activity.domain.profile import PUBLIC_OUTPUT_PATHS
from it_activity.ports.activity_source import ActivitySourceError

PRIVATE_REPOSITORY_NAME = "fixture-org/private-project"
PRIVATE_REPOSITORY_URL = "git@github.com:fixture-org/private-project.git"
PRIVATE_NON_GITHUB_URL = "git@gitlab.example.invalid:private-namespace/nested/private-project.git"
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
        "GIT_CONFIG_GLOBAL": os.devnull,
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
    create_private_repository(repository)

    configuration = ProfileConfiguration(
        github_login="octocat",
        author_emails=frozenset({PRIVATE_EMAIL}),
        expected_repositories=frozenset({PRIVATE_REPOSITORY_NAME}),
        timezone="Europe/Moscow",
    )
    configuration_provider = StaticConfigurationProvider(configuration)
    activity_source = LocalGitActivitySource((repository,))
    clock = FixedClock(datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc))
    activity_provider = CollectActivity(
        configuration_provider,
        activity_source,
        clock,
    )
    usage_provider = CollectUsage(configuration_provider, activity_source, clock)

    return LocalProfileFixture(repository, output, activity_provider, usage_provider)


def test_local_git_activity_aggregation(local_profile_fixture: LocalProfileFixture) -> None:
    activity = local_profile_fixture.activity_provider.execute()

    assert activity.totals(365).commits == 2
    assert activity.totals(365).added_lines == 5
    assert activity.totals(365).deleted_lines == 1
    assert next(day for day in activity.days if day.day.isoformat() == "2026-08-08").commits == 1
    assert activity.days[-1].day.isoformat() == "2026-08-10"
    assert activity.days[-1].commits == 1


def test_local_git_usage_aggregation(local_profile_fixture: LocalProfileFixture) -> None:
    usage = local_profile_fixture.usage_provider.execute()

    assert [(item.name, item.share_basis_points, item.active_days) for item in usage.languages] == [
        ("Python", 6667, 2),
        ("TypeScript", 3333, 1),
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


def test_local_git_activity_rejects_unsafe_origin_without_exposing_private_values(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "private-unsafe-origin"
    repository.mkdir()
    run_git(repository, "init", "--quiet", "--initial-branch=main")
    private_remote = (
        "https://private-user:private-password@example.invalid/fixture-org/private-project.git"
    )
    run_git(repository, "remote", "add", "origin", private_remote)

    with pytest.raises(ActivitySourceError) as captured:
        LocalGitActivitySource((repository,))

    message = str(captured.value)
    assert "безопасного Git origin" in message
    assert str(repository) not in message
    assert private_remote not in message
    assert "private-password" not in message


def test_local_git_activity_uses_an_opaque_identity_for_another_safe_git_host(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "private-non-github-repository"
    repository.mkdir()
    run_git(repository, "init", "--quiet", "--initial-branch=main")
    run_git(repository, "remote", "add", "origin", PRIVATE_NON_GITHUB_URL)
    write_fixture(repository, PRIVATE_PATH, f"{PRIVATE_SOURCE}\n")
    authored_at = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)
    commit_fixture(repository, PRIVATE_MESSAGE, PRIVATE_EMAIL, authored_at)
    source = LocalGitActivitySource((repository,))

    reference = source.list_repositories("octocat")[0]
    commits = tuple(
        source.iter_commits(
            reference,
            datetime(2026, 8, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
    )

    assert reference.full_name.startswith("local/")
    assert "gitlab" not in reference.full_name
    assert "private" not in reference.full_name
    assert [(commit.authored_at, commit.author_email) for commit in commits] == [
        (authored_at, PRIVATE_EMAIL)
    ]


def test_local_git_activity_rejects_missing_path_without_exposing_it(tmp_path: Path) -> None:
    missing_path = tmp_path / "private-missing-repository"

    with pytest.raises(ActivitySourceError) as captured:
        LocalGitActivitySource((missing_path,))

    message = str(captured.value)
    assert "недоступен" in message
    assert str(missing_path) not in message
    assert "private-missing-repository" not in message


def test_local_git_activity_uses_rename_detection_instead_of_counting_line_churn(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "private-rename-repository"
    repository.mkdir()
    run_git(repository, "init", "--quiet", "--initial-branch=main")
    run_git(repository, "remote", "add", "origin", PRIVATE_REPOSITORY_URL)
    old_path = "src/private_old_name.py"
    new_path = "src/private_new_name.py"
    write_fixture(repository, old_path, "PRIVATE_RENAME_VALUE = 1\n")
    commit_fixture(
        repository,
        "private rename base",
        PRIVATE_EMAIL,
        datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
    )
    (repository / old_path).rename(repository / new_path)
    commit_fixture(
        repository,
        "private pure rename",
        PRIVATE_EMAIL,
        datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc),
    )
    rename_sha = run_git(repository, "rev-parse", "HEAD").strip()
    source = LocalGitActivitySource((repository,))
    reference = source.list_repositories("octocat")[0]

    changes = source.get_file_changes(reference, rename_sha)

    assert changes == (FileChange(path=new_path, additions=0, deletions=0, binary=False),)


def test_local_git_activity_rejects_shallow_history_without_exposing_private_values(
    tmp_path: Path,
) -> None:
    source_repository = tmp_path / "private-full-source"
    source_repository.mkdir()
    run_git(source_repository, "init", "--quiet", "--initial-branch=main")
    write_fixture(source_repository, PRIVATE_PATH, f"{PRIVATE_SOURCE}\n")
    commit_fixture(
        source_repository,
        PRIVATE_MESSAGE,
        PRIVATE_EMAIL,
        datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
    )
    shallow_repository = tmp_path / "private-shallow-clone"
    run_git(
        tmp_path,
        "clone",
        "--quiet",
        "--depth=1",
        source_repository.as_uri(),
        str(shallow_repository),
    )

    with pytest.raises(ActivitySourceError) as captured:
        LocalGitActivitySource((shallow_repository,))

    message = str(captured.value)
    assert "неполной" in message
    assert str(source_repository) not in message
    assert str(shallow_repository) not in message
    assert PRIVATE_REPOSITORY_NAME not in message


def test_local_git_activity_rejects_partial_clone_configuration_without_network(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "private-partial-repository"
    repository.mkdir()
    run_git(repository, "init", "--quiet", "--initial-branch=main")
    run_git(repository, "remote", "add", "origin", PRIVATE_REPOSITORY_URL)
    run_git(repository, "config", "--local", "remote.origin.promisor", "true")

    with pytest.raises(ActivitySourceError) as captured:
        LocalGitActivitySource((repository,))

    message = str(captured.value)
    assert "неполной" in message
    assert str(repository) not in message
    assert PRIVATE_REPOSITORY_URL not in message
