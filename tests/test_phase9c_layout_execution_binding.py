"""RB-A.1 / RB-A.2 -- compiled layout to runtime binding, and the legacy question."""

from __future__ import annotations

import ast
import json
import pathlib
import shutil

import pytest

from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.binding import (
    ADMITTED_CANDIDATES, ADMITTED_INITIAL_TOPOLOGIES, BindingError,
    build_binding, load_execution_specification,
)
from rvt_swarm.topology_registry import COMPACT, LINE

ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
POLICIES = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())

#: Phase 9G-V3X-Q added thirty ADDITIVE V3 execution specifications into
#: the same directories. Narrowing to the V2-era layout set -- defined by
#: the frozen split manifests -- keeps this assertion at its original
#: force over the historical layouts instead of loosening it.
def _v2_era_layout_ids(split):
    manifest = json.loads(
        (ROOT / "splits" / f"{split}_layouts.json").read_text(encoding="ascii"))
    return {str(record["layout_id"]) for record in manifest["layout_records"]}


LAYOUTS = [(split, path.stem)
           for split in ("train", "validation")
           for path in sorted((ROOT / "layout_execution_specifications" / split).glob("*.json"))
           if path.stem in _v2_era_layout_ids(split)]


def _build(split, layout_id, team_size=6, policy=P.S1):
    return build_binding(
        load_execution_specification(ROOT, split, layout_id), team_size=team_size,
        source_policy=policy, protocol=PROTOCOL, target_contract=TARGET,
        source_policy_contracts=POLICIES)


# -- RB-G1: every layout binds without a new scientific choice ---------------
@pytest.mark.parametrize("split,layout_id", LAYOUTS)
def test_every_compiled_layout_binds(split, layout_id) -> None:
    binding = _build(split, layout_id)
    assert binding.layout_id == layout_id
    assert binding.split == split
    assert binding.validity in ("RUNTIME_BINDING_VALID", "NOMINAL_INITIAL_STATE_INVALID")


def test_all_thirty_layouts_are_covered() -> None:
    assert len(LAYOUTS) == 30


@pytest.mark.parametrize("team_size", [5, 6, 8, 12, 16, 24])
def test_every_qualified_team_size_binds(team_size) -> None:
    binding = _build("train", "train-f1-00", team_size=team_size)
    assert binding.team_size == team_size
    assert len(binding.nominal_positions) == team_size


def test_binding_hashes_are_deterministic_and_layout_specific() -> None:
    first = _build("train", "train-f2-00").binding_sha256()
    again = _build("train", "train-f2-00").binding_sha256()
    other = _build("train", "train-f3-00").binding_sha256()
    assert first == again
    assert first != other


def test_binding_carries_every_required_provenance_hash() -> None:
    binding = _build("train", "train-f2-00")
    assert binding.executable_protocol_hash == PROTOCOL["protocol_hash"]
    assert binding.config_hashes["target_v4_execution_contract_sha256"] == (
        TARGET["target_v4_execution_contract_sha256"])
    assert binding.config_hashes["source_policy_contract_sha256"] == (
        POLICIES["source_policy_contract_sha256"])
    assert binding.config_hashes["phase8_protocol_sha256"] == PROTOCOL["phase8_protocol_hash"]


def test_initial_topology_is_compact_and_keep_is_not_admitted() -> None:
    assert ADMITTED_INITIAL_TOPOLOGIES == (COMPACT,)
    assert ADMITTED_CANDIDATES == (COMPACT, LINE)
    for split, layout_id in LAYOUTS:
        assert _build(split, layout_id).initialization["initial_topology_id"] == COMPACT


def test_nominal_initial_invalidity_is_retained_not_repaired() -> None:
    """F2 at N=24 is nominally invalid; the binding records it, it does not move
    the origin to make it fit."""
    binding = _build("train", "train-f2-00", team_size=24)
    assert binding.validity == "NOMINAL_INITIAL_STATE_INVALID"
    assert binding.initialization["nominal_validity"]["valid"] is False
    assert binding.initialization["nominal_validity"]["reasons"]


# -- the adapter refuses rather than defaulting ------------------------------
def test_binding_rejects_a_mismatched_protocol_hash() -> None:
    spec = load_execution_specification(ROOT, "train", "train-f2-00")
    spec["executable_protocol_sha256"] = "0" * 64
    with pytest.raises(BindingError):
        build_binding(spec, team_size=6, source_policy=P.S1, protocol=PROTOCOL,
                      target_contract=TARGET, source_policy_contracts=POLICIES)


def test_loader_rejects_a_modified_compiled_artifact(tmp_path) -> None:
    source = ROOT / "layout_execution_specifications/train/train-f2-01.json"
    target = tmp_path / "layout_execution_specifications/train/train-f2-01.json"
    target.parent.mkdir(parents=True)
    shutil.copyfile(source, target)
    specification = json.loads(target.read_text(encoding="ascii"))
    specification["mission_frame"]["heading_radians"] = 0.0
    target.write_text(json.dumps(specification), encoding="ascii")
    with pytest.raises(BindingError, match="hash mismatch"):
        load_execution_specification(tmp_path, "train", "train-f2-01")


def test_binding_rejects_a_mismatched_target_contract_hash() -> None:
    spec = load_execution_specification(ROOT, "train", "train-f2-00")
    spec["target_v4_contract_sha256"] = "0" * 64
    with pytest.raises(BindingError):
        build_binding(spec, team_size=6, source_policy=P.S1, protocol=PROTOCOL,
                      target_contract=TARGET, source_policy_contracts=POLICIES)


def test_binding_rejects_unresolved_category_d() -> None:
    spec = load_execution_specification(ROOT, "train", "train-f2-00")
    spec["category_d_count"] = 1
    with pytest.raises(BindingError):
        build_binding(spec, team_size=6, source_policy=P.S1, protocol=PROTOCOL,
                      target_contract=TARGET, source_policy_contracts=POLICIES)


def test_binding_rejects_an_unqualified_team_size() -> None:
    with pytest.raises(BindingError):
        _build("train", "train-f2-00", team_size=7)


def test_binding_rejects_an_undeclared_source_policy() -> None:
    with pytest.raises(BindingError):
        _build("train", "train-f2-00", policy="S9_INVENTED")


# -- RB-G15: final-test isolation --------------------------------------------
def test_final_test_split_cannot_be_loaded_at_runtime() -> None:
    with pytest.raises(BindingError):
        load_execution_specification(ROOT, "final_test", "anything")


def test_no_final_test_specification_directory_exists() -> None:
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
