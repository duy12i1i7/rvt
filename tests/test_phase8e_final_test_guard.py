from __future__ import annotations

import json
from pathlib import Path

import pytest

from rvt_swarm.phase8e.compiler import compile_nonfinal_split
from rvt_swarm.phase8e.protocol import build_executable_protocol


ROOT = Path(__file__).resolve().parents[1]


def test_phase8e_compiler_rejects_final_test_before_loading_a_manifest() -> None:
    protocol = build_executable_protocol(ROOT)
    with pytest.raises(PermissionError, match="sealed final-test"):
        compile_nonfinal_split(ROOT, "final_test", protocol)


def test_only_permitted_final_metadata_is_recorded() -> None:
    protocol = json.loads((
        ROOT / "results/rvt_fd24/executable_scientific_protocol_v1.json"
    ).read_text(encoding="ascii"))
    policy = protocol["final_test_access_policy"]
    assert policy["geometry_compilation"] == "prohibited"
    assert set(policy["permitted_metadata"]) == {
        "layout_count", "family_count", "manifest_sha256", "schema_compatibility"
    }
    assert policy["runtime_access_count"] == 0
    assert not (ROOT / "results/rvt_fd24/layout_execution_specifications/final_test").exists()
