"""HVA -- fixed-topology baseline admissibility audit.

EVIDENCE ONLY. The contract-faithful S2 reading is not committed to the runtime;
these tests assert the audit artifacts, not runtime behaviour under that reading.
"""
from __future__ import annotations
import hashlib, json, pathlib, pytest
from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session

ROOT = pathlib.Path("results/rvt_fd24")
V4 = json.loads((ROOT / "headroom_requalification_v4.json").read_text())
SPECS = ROOT / "layout_execution_specifications"


def test_frozen_s2_declares_compact_as_its_initial_topology() -> None:
    contract = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())
    s2 = contract["policies"]["S2_ALWAYS_LINE"]
    assert s2["initial_topology"] == COMPACT
    assert "role targets" in s2["topology_behavior"]


def test_compact_validity_reproduces_the_compiled_record_exactly() -> None:
    """HVA-5, the strongest sanity check: 0 disagreements over 150 cells."""
    equivalence = V4["compact_historical_equivalence"]
    assert equivalence["cells_checked"] == 150
    assert equivalence["disagreements"] == 0
    for cell in V4["cells"]:
        spec = json.loads((SPECS / cell["split"] / f"{cell['layout_id']}.json").read_text())
        compiled = spec["nominal_initial_validity_by_team_size"][str(cell["team_size"])]["valid"]
        runtime_invalid = cell["compact"]["termination"] == "INITIALIZATION_INVALID"
        assert compiled != runtime_invalid, (cell["layout_id"], cell["team_size"])


def test_policy_initial_state_infeasible_is_not_needed() -> None:
    correction = V4["correction"]
    assert correction["policy_initial_state_infeasible_needed"] is False
    assert "never requests a LINE initial placement" in correction[
        "policy_initial_state_infeasible_reason"]


def test_every_remaining_invalid_cell_is_compiler_declared() -> None:
    inv = V4["invalid_or_ambiguous"]
    assert inv["unexplained"] == 0
    for cell in inv["cells"]:
        spec = json.loads((SPECS / cell["split"] / f"{cell['layout_id']}.json").read_text())
        assert spec["nominal_initial_validity_by_team_size"][
            str(cell["team_size"])]["valid"] is False


def test_no_headroom_is_initial_admissibility_driven() -> None:
    driven = V4["initial_admissibility_driven_headroom"]
    assert driven["count"] == 0
    assert set(driven["fixed_line_failure_causes"]) == {"COLLISION"}


def test_h2_headroom_is_nonzero_and_diverse() -> None:
    rr = V4["reconfiguration_required"]
    assert rr["train"] > 0 and rr["validation"] > 0
    assert len(rr["families"]) > 1
    assert len(rr["team_sizes"]) > 1
    assert rr["concentration_class"] == "A"
    assert V4["h2"]["falsifiable"] is True


def test_f5_wording_stays_conservative() -> None:
    f5 = V4["f5"]
    assert f5["reconfiguration_required_cells"] == 3
    assert sum(f5["categories"].values()) == 15
    assert "not required in the remaining" in f5["conclusion"]


def test_all_one_hundred_and_fifty_cells_remain_covered() -> None:
    assert len(V4["cells"]) == 150
    assert V4["evaluation_domain"]["team_sizes"] == [5, 6, 8, 12, 16]
    assert 24 not in {c["team_size"] for c in V4["cells"]}


def test_earlier_artifacts_are_preserved() -> None:
    for name in ("headroom_requalification_v2.json", "headroom_requalification_v3.json"):
        assert (ROOT / name).exists()


def test_v4_hash_is_reproducible() -> None:
    body = {k: v for k, v in V4.items() if k != "headroom_requalification_v4_sha256"}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == (
        V4["headroom_requalification_v4_sha256"])


def test_isolation_counters() -> None:
    assert V4["final_test_access_count"] == 0
    assert V4["study_a_n24_access_count"] == 0
    assert V4["dataset_rows_generated"] == 0
