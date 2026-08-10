"""Executable checks for Clean Architecture dependency direction."""

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "it_activity"

ALLOWED_INTERNAL_DEPENDENCIES = {
    "domain": frozenset(),
    "ports": frozenset({"domain"}),
    "application": frozenset({"domain", "ports"}),
    "adapters": frozenset({"domain", "ports"}),
    "entrypoints": frozenset({"adapters", "application", "domain", "ports"}),
}


def internal_imports(source_file: Path) -> set[str]:
    """Return first-level package names imported from this project."""
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    imports: set[str] = set()
    for node in ast.walk(tree):
        modules: Iterable[str]
        if isinstance(node, ast.Import):
            modules = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules = (node.module,)
        else:
            continue
        for module in modules:
            prefix = "it_activity."
            if module.startswith(prefix):
                imports.add(module.removeprefix(prefix).split(".", maxsplit=1)[0])
    return imports


@pytest.mark.parametrize("layer", sorted(ALLOWED_INTERNAL_DEPENDENCIES))
def test_layer_imports_only_allowed_dependencies(layer: str) -> None:
    allowed = ALLOWED_INTERNAL_DEPENDENCIES[layer]
    for source_file in (PACKAGE_ROOT / layer).rglob("*.py"):
        forbidden = internal_imports(source_file) - allowed - {layer}
        assert not forbidden, f"{source_file.relative_to(PROJECT_ROOT)} imports {sorted(forbidden)}"
