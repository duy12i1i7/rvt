from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "rvt_swarm/phase8e"


def test_phase8e_does_not_import_legacy_environment_or_runtime() -> None:
    prohibited = {
        "rvt_swarm.environment",
        "rvt_swarm.decentralized.runtime",
        "rvt_swarm.decentralized.transition_runtime",
    }
    imported = set()
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="ascii"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    assert not (imported & prohibited)


def test_no_legacy_layout_attribute_or_hidden_default_origin_is_used() -> None:
    trees = [
        ast.parse(path.read_text(encoding="ascii"))
        for path in PACKAGE.glob("*.py")
    ]
    legacy_attributes = [
        node for tree in trees for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "start_center"
    ]
    legacy_keys = [
        node for tree in trees for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == "start_center"
    ]
    assert legacy_attributes == []
    assert legacy_keys == []
