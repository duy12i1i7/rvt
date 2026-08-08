"""S2ME -- fixed-LINE baseline mechanical initialization."""
from __future__ import annotations
import hashlib, json, math, pathlib, pytest
from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run

ROOT = pathlib.Path("results/rvt_fd24")
S2C = json.loads((ROOT / "s2_fixed_line_mechanical_initialization_v1.json").read_text())
V5 = json.loads((ROOT / "headroom_requalification_v5.json").read_text())


@pytest.mark.parametrize("layout,split,N", [
    ("train-f1-00", "train", 6), ("train-f5-00", "train", 12),
    ("validation-f9-00", "validation", 5), ("train-f4-00", "train", 8)])
def test_s1_and_s2_share_byte_identical_initial_physical_state(layout, split, N) -> None:
    a = build_session(layout, split=split, policy_id=P.S1, team_size=N)
    b = build_session(layout, split=split, policy_id=P.S2, team_size=N)
    assert [r.position for r in a.robots] == [r.position for r in b.robots]
    assert [r.velocity for r in a.robots] == [r.velocity for r in b.robots]
    assert [r.acceleration for r in a.robots] == [r.acceleration for r in b.robots]
    assert a.mission_origin == b.mission_origin and a.goal_center == b.goal_center
    assert a.initial_topology == b.initial_topology == COMPACT
    assert a.robots[0].committed_topology == b.robots[0].committed_topology == COMPACT


def test_s2_never_spawns_at_line_poses() -> None:
    """Defect 11 regression."""
    session = build_session("train-f4-00", policy_id=P.S2, team_size=16)
    span = max(r.position[0] for r in session.robots) - min(
        r.position[0] for r in session.robots)
    assert span < (16 - 1) * 0.9 / 2.0


def test_s1_creates_no_epoch_of_any_kind() -> None:
    session = run(build_session("train-f1-00", policy_id=P.S1), steps=60)
    assert session.topology_selection_epoch_count == 0
    assert session.mechanical_transition_epoch_count == 0


def test_s2_creates_a_mechanical_epoch_but_no_selection_epoch() -> None:
    session = run(build_session("train-f1-00", policy_id=P.S2), steps=60)
    assert session.topology_selection_epoch_count == 0
    assert session.mechanical_transition_epoch_count == 1


def test_s2_records_its_forced_initialization_auditably() -> None:
    session = run(build_session("train-f1-00", policy_id=P.S2), steps=20)
    forced = session.source_policy.forced_initialization
    assert forced["target_topology"] == LINE
    assert forced["event_type"] == "externally_forced_diagnostic"
    assert forced["selection_performed"] is False


def test_no_topology_selection_occurs_anywhere_in_s2() -> None:
    semantics = S2C["selection_semantics"]
    assert semantics["learned_model"] is False
    assert semantics["candidate_comparison"] is False
    assert semantics["score_consulted"] is False
    assert semantics["geometry_oracle"] is False
    assert semantics["target_predetermined"] is True


def test_s2_uses_the_full_qualified_transition_stack() -> None:
    forced = S2C["forced_initialization"]
    for element in ("mission staging", "robot-local readiness certificate",
                    "generic_role_space_profile", "local safety projection",
                    "Metric V3 tube and dwell"):
        assert element in forced["stack"]
    assert forced["free_teleport"] is False
    assert forced["unmanaged_direct_convergence"] is False
    assert forced["duplicate_transition_implementation"] is False


def test_s2_actually_runs_the_lifecycle_and_establishes_line() -> None:
    session = build_session("train-f1-00", policy_id=P.S2)
    states = set()
    for _ in range(500):
        session.step()
        states.update(r.protocol_node.state for r in session.robots)
        if session.termination is not None:
            break
    for phase in ("CANDIDATE_SCORE_AGREEMENT", "ALL_READY_AGREEMENT",
                  "TOPOLOGY_CONFIRMATION", "TRANSITION_EXECUTION", "TARGET_DWELL"):
        assert phase in states, phase
    assert sorted({r.committed_topology for r in session.robots}) == [LINE]
    assert session.metric_v3_dwell[LINE] > 0.0


def test_open_field_regression_clears_the_frozen_clearance() -> None:
    """S2ME-13: 0.3635 m unmanaged -> >= 0.4000 m managed, without retuning."""
    session = build_session("train-f1-00", policy_id=P.S2)
    minimum = float("inf")
    for _ in range(500):
        session.step()
        minimum = min(minimum, min(
            math.dist(a.position, b.position)
            for i, a in enumerate(session.robots) for b in session.robots[i + 1:]))
        if session.termination is not None:
            break
    required = float(session.runtime_config.derived.robot_robot_required_clearance_meters)
    assert minimum >= required, f"{minimum:.4f} < {required}"
    assert session.termination.cause == "GOAL_COMPLETE"
    assert S2C["open_field_regression"]["unmanaged_direct_convergence_min_separation_meters"] < required


def test_s2_failure_is_policy_failure_not_generation_invalidity() -> None:
    taxonomy = S2C["failure_taxonomy"]
    assert "fixed LINE policy failure" in taxonomy["forced_conversion_failure"]
    for cell in V5["cells"]:
        line = cell["line"]
        if not line["success"] and line["termination"] not in (
                "INITIALIZATION_INVALID", "NUMERICAL_INVALID", "EXECUTOR_EXCEPTION"):
            assert line["disposition"] == "VALID_TASK_NEGATIVE", cell["layout_id"]


# -- v5 headroom --------------------------------------------------------------
def test_v5_covers_all_one_hundred_and_fifty_cells() -> None:
    assert len(V5["cells"]) == 150
    assert V5["status"] == "PROVISIONAL_PRE_D12", (
        "v5 predates the defect 12 repair and must not be presented as "
        "authoritative; a post-repair v6 supersedes it")
    assert V5["evaluation_domain"]["team_sizes"] == [5, 6, 8, 12, 16]


def test_v5_supersedes_the_non_authoritative_artifacts() -> None:
    assert any("evidence only" in s for s in V5["supersedes"])
    for name in ("headroom_requalification_v3.json", "headroom_requalification_v4.json"):
        assert (ROOT / name).exists()


def test_h2_headroom_remains_nonzero_in_both_splits() -> None:
    rr = V5["reconfiguration_required"]
    assert rr["train"] > 0 and rr["validation"] > 0
    assert V5["h2"]["falsifiable"] is True


def test_the_initial_conversion_dependence_is_quantified_and_disclosed() -> None:
    rr = V5["reconfiguration_required"]
    assert rr["initial_conversion_driven"] + rr["later_task_driven"] + rr["mixed"] == (
        rr["train"] + rr["validation"])
    assert "materially weakens" in V5["h2"]["major_limitation"]


def test_f5_wording_is_not_strengthened() -> None:
    assert V5["f5"]["necessity_claim_restored"] is False
    assert "opportunities" in V5["f5"]["wording"]


def test_artifact_hashes_are_reproducible() -> None:
    for doc, key in ((V5, "headroom_requalification_v5_sha256"),
                     (S2C, "s2_fixed_line_mechanical_initialization_sha256")):
        body = {k: v for k, v in doc.items() if k != key}
        assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == doc[key]


def test_isolation_counters() -> None:
    assert V5["final_test_access_count"] == 0
    assert V5["study_a_n24_access_count"] == 0
    assert V5["dataset_rows_generated"] == 0
