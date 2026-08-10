"""Static security contract for scheduled profile publication."""

import re
from pathlib import Path

from it_activity.domain.profile import PUBLIC_OUTPUT_PATHS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "update-profile.yml"


def workflow_text() -> str:
    """Read the repository-owned workflow as UTF-8 text."""
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def staged_paths(workflow: str) -> tuple[str, ...]:
    """Extract the explicit paths between git add and the no-change guard."""
    lines = workflow.splitlines()
    start = next(index for index, line in enumerate(lines) if "git add --" in line)
    paths: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("if git diff --cached"):
            break
        paths.append(stripped.removesuffix("\\").strip())
    return tuple(paths)


def test_update_workflow_is_scheduled_and_manually_dispatchable() -> None:
    workflow = workflow_text()

    assert "schedule:" in workflow
    assert re.search(r'^\s+- cron: "[^"\n]+"$', workflow, flags=re.MULTILINE)
    assert "workflow_dispatch:" in workflow
    assert "contents: write" in workflow
    assert "cancel-in-progress: false" in workflow


def test_update_workflow_separates_private_read_credential() -> None:
    workflow = workflow_text()

    assert "IT_ACTIVITY_GITHUB_READ_TOKEN: ${{ secrets.IT_ACTIVITY_GITHUB_READ_TOKEN }}" in workflow
    assert (
        "IT_ACTIVITY_EXPECTED_REPOSITORIES: "
        "${{ secrets.IT_ACTIVITY_EXPECTED_REPOSITORIES }}" in workflow
    )
    assert workflow.count("IT_ACTIVITY_GITHUB_READ_TOKEN:") == 1
    assert "upload-artifact" not in workflow
    assert "download-artifact" not in workflow
    assert "actions/cache" not in workflow


def test_update_workflow_pins_actions_and_stages_only_public_outputs() -> None:
    workflow = workflow_text()
    action_references = re.findall(r"^\s+uses: [^@\s]+@([^\s]+)", workflow, re.MULTILINE)

    assert action_references
    assert all(re.fullmatch(r"[0-9a-f]{40}", reference) for reference in action_references)
    assert "git add ." not in workflow
    assert frozenset(staged_paths(workflow)) == PUBLIC_OUTPUT_PATHS
    assert len(staged_paths(workflow)) == len(PUBLIC_OUTPUT_PATHS)
