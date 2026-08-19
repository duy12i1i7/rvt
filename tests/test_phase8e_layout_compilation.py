from __future__ import annotations

import copy
import json
from pathlib import Path

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase8.splits import load_nonfinal_split_manifest
from rvt_swarm.phase8e.compiler import compile_layout_record, compile_nonfinal_split
from rvt_swarm.phase8e.protocol import build_executable_protocol
from rvt_swarm.phase9c_rb.binding import load_execution_specification


ROOT = Path(__file__).resolve().parents[1]


def test_all_nonfinal_layouts_compile_with_zero_category_d() -> None:
    protocol = build_executable_protocol(ROOT)
    train = compile_nonfinal_split(ROOT, "train", protocol)
    validation = compile_nonfinal_split(ROOT, "validation", protocol)
    assert (len(train), len(validation)) == (20, 10)
    assert all(item["category_d_count"] == 0 for item in train + validation)
    assert all(verify_canonical_hash(item, "layout_execution_specification_sha256") for item in train + validation)


def _physical_compiler_projection(document):
    projection = copy.deepcopy(document)
    projection.pop("layout_execution_specification_sha256")
    projection["mission_frame"].pop("heading_radians")
    return projection


def test_persisted_layout_specs_are_exact_and_compiler_preserves_physics() -> None:
    protocol = build_executable_protocol(ROOT)
    for split, expected_count in (("train", 20), ("validation", 10)):
        compiled = compile_nonfinal_split(ROOT, split, protocol)
        # compile_nonfinal_split enumerates the frozen split manifest, so the
        # persisted set is narrowed to the same V2-era layouts. Phase 9G-V3X-Q
        # added thirty V3 specifications alongside them, additively.
        manifest = json.loads((
            ROOT / f"results/rvt_fd24/splits/{split}_layouts.json"
        ).read_text(encoding="ascii"))
        v2_era = {str(record["layout_id"]) for record in manifest["layout_records"]}
        paths = [path for path in sorted((
            ROOT / f"results/rvt_fd24/layout_execution_specifications/{split}"
        ).glob("*.json")) if path.stem in v2_era]
        persisted = tuple(
            load_execution_specification(
                ROOT / "results/rvt_fd24", split, path.stem
            )
            for path in paths
        )
        assert len(persisted) == expected_count
        assert tuple(map(_physical_compiler_projection, persisted)) == tuple(
            map(_physical_compiler_projection, compiled)
        )
        hashes = [item["layout_execution_specification_sha256"] for item in persisted]
        assert len(hashes) == len(set(hashes))


def test_compilation_is_order_independent_and_ignores_headroom_metadata() -> None:
    protocol = build_executable_protocol(ROOT)
    manifest = load_nonfinal_split_manifest(
        ROOT / "results/rvt_fd24/splits/train_layouts.json"
    )
    records = manifest["layout_records"]
    forward = {
        record["layout_id"]: compile_layout_record(record, "train", protocol)
        for record in records
    }
    reverse = {
        record["layout_id"]: compile_layout_record(record, "train", protocol)
        for record in reversed(records)
    }
    assert forward == reverse
    changed = copy.deepcopy(records[0])
    changed["diagnostic_headroom_by_team_size"] = [[5, "PROHIBITED_TEST_VALUE"]]
    assert compile_layout_record(changed, "train", protocol) == forward[records[0]["layout_id"]]


def test_nominal_invalid_team_size_is_recorded_not_repaired() -> None:
    record = json.loads((
        ROOT / "results/rvt_fd24/layout_execution_specifications/train/train-f2-00.json"
    ).read_text(encoding="ascii"))
    assert record["mission_frame"]["initial_topology_origin_meters"] == record["mission_frame"]["mission_origin_meters"]
    assert record["nominal_initial_validity_by_team_size"]["24"]["valid"] is False
    assert record["nominal_initial_validity_by_team_size"]["6"]["valid"] is True
