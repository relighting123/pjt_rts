"""import 레이어 규칙 검증."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PREFIXES = {
    "src/simulation/domain": ("envs", "agents", "src.training", "src.db", "gymnasium"),
    "src/simulation/kernel": ("agents", "src.training", "gymnasium", "stable_baselines3", "sb3_contrib"),
}


def _imports_in_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_domain_has_no_forbidden_imports():
    domain_dir = ROOT / "src" / "simulation" / "domain"
    for py in domain_dir.glob("*.py"):
        if py.name == "__init__.py":
            continue
        imports = _imports_in_file(py)
        for forbidden in FORBIDDEN_PREFIXES["src/simulation/domain"]:
            for imp in imports:
                assert not imp.startswith(forbidden), f"{py}: forbidden import {imp}"


def test_kernel_has_no_forbidden_imports():
    kernel_dir = ROOT / "src" / "simulation" / "kernel"
    for py in kernel_dir.glob("*.py"):
        if py.name == "__init__.py":
            continue
        imports = _imports_in_file(py)
        for forbidden in FORBIDDEN_PREFIXES["src/simulation/kernel"]:
            for imp in imports:
                assert not imp.startswith(forbidden), f"{py}: forbidden import {imp}"
