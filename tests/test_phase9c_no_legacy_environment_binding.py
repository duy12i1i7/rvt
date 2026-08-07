"""RB-A.2 / RB-G2 -- no legacy publication-runtime dependency.

The distinction this file exists to make, and which a bare substring grep
cannot: `ScenarioLayout.start_center_meters` is an explicit **approved** Phase 8
scientific field and is used. The *legacy environment* `layout.start_center`
attribute is forbidden. The tests below discriminate the two with AST analysis
rather than text matching.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

PACKAGE = pathlib.Path("rvt_swarm/phase9c_rb")
MODULES = sorted(PACKAGE.glob("*.py"))

PROHIBITED_IMPORTS = {
    "rvt_swarm.environment",
    "rvt_swarm.decentralized.runtime",
    "rvt_swarm.decentralized.transition_runtime",
    "rvt_swarm.legacy_global_graph",
    "rvt_swarm.dataset",
}


def _trees():
    return [(path, ast.parse(path.read_text(encoding="ascii"))) for path in MODULES]


def test_publication_package_imports_no_legacy_runtime() -> None:
    for path, tree in _trees():
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.ImportFrom) and node.level and node.module is None:
                continue
        assert not (imported & PROHIBITED_IMPORTS), (path, imported & PROHIBITED_IMPORTS)


def test_no_legacy_start_center_attribute_access() -> None:
    """`layout.start_center` -- the forbidden legacy environment attribute."""
    for path, tree in _trees():
        offenders = [node for node in ast.walk(tree)
                     if isinstance(node, ast.Attribute) and node.attr == "start_center"]
        assert offenders == [], path


def test_no_bare_start_center_string_key() -> None:
    for path, tree in _trees():
        offenders = [node for node in ast.walk(tree)
                     if isinstance(node, ast.Constant) and node.value == "start_center"]
        assert offenders == [], path


def test_the_approved_scientific_field_is_the_one_actually_used() -> None:
    """Non-vacuity: the tests above must not pass because nothing is used."""
    source = "\n".join(path.read_text(encoding="ascii") for path in MODULES)
    assert "initial_topology_origin_meters" in source, (
        "the binding must consume the approved compiled mission-frame origin")


def test_the_guard_discriminates_rather_than_matching_a_substring() -> None:
    """A module using the legacy attribute is caught; the approved field is not."""
    legacy = ast.parse("origin = layout.start_center\n")
    approved = ast.parse("origin = frame['initial_topology_origin_meters']\n")
    legacy_hits = [n for n in ast.walk(legacy)
                   if isinstance(n, ast.Attribute) and n.attr == "start_center"]
    approved_hits = [n for n in ast.walk(approved)
                     if isinstance(n, ast.Attribute) and n.attr == "start_center"]
    assert len(legacy_hits) == 1
    assert approved_hits == []


def test_online_keep_is_absent_from_the_publication_package() -> None:
    from rvt_swarm.phase9c_rb.binding import ADMITTED_CANDIDATES, ADMITTED_INITIAL_TOPOLOGIES
    from rvt_swarm.topology_registry import KEEP
    assert KEEP not in ADMITTED_CANDIDATES
    assert KEEP not in ADMITTED_INITIAL_TOPOLOGIES
