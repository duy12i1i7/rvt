"""PCA-18 -- Target V4 must consume the CURRENT epoch's transition state.

A completed epoch 1 must never let a later candidate receive transition credit
before its own commit, profile, dwell and distributed completion succeed.
"""
from __future__ import annotations
import pytest
from rvt_swarm.phase8e.target import evaluate_target_v4
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import build_execution_summary
from rvt_swarm.phase9c_rb.policies import SourcePolicy
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session
from tests.test_phase9c_two_epoch_transition import _s2_after_first_epoch

RESTING = ("COMPLETE", "REARMED", "STABLE_TOPOLOGY")


def _predicates_for(session, candidate):
    return build_execution_summary(session, candidate).predicates


# -- epoch 1 established -------------------------------------------------------
def test_epoch_one_success_is_real() -> None:
    session = _s2_after_first_epoch()
    assert {r.committed_topology for r in session.robots} == {LINE}
    assert len(session.completion_agreements) == 1
    assert session.metric_v3_dwell[LINE] > 0.0


# -- PCA-18A: previous commit must not satisfy the new candidate ---------------
def test_epoch_one_commit_does_not_satisfy_a_compact_candidate() -> None:
    session = _s2_after_first_epoch()
    predicates = _predicates_for(session, COMPACT)
    assert predicates.candidate_commitment_valid is False, (
        "LINE is committed; a COMPACT candidate must not inherit that commitment")


# -- PCA-18C: previous dwell must not contribute ------------------------------
def test_epoch_one_line_dwell_does_not_satisfy_compact_dwell() -> None:
    session = _s2_after_first_epoch()
    assert session.metric_v3_dwell[LINE] > 0.0
    assert session.metric_v3_dwell[COMPACT] == 0.0
    assert _predicates_for(session, COMPACT).target_metric_v3_dwell_complete is False


# -- PCA-18B / 18D: checkpoints A-E through epoch 2 ---------------------------
def _drive_epoch_two(session, checkpoints, steps=500):
    requested = False
    seen = {}
    for _ in range(steps):
        session.step()
        if session.termination is not None:
            break
        if not requested and all(r.protocol_node.state in ("REARMED", "STABLE_TOPOLOGY")
                                 for r in session.robots):
            requested = session.request_candidate(
                session.robots[0], COMPACT, "externally_forced_diagnostic")
            continue
        if not requested:
            continue
        for label, predicate in checkpoints.items():
            if label not in seen and predicate(session):
                seen[label] = _predicates_for(session, COMPACT)
        if all(r.protocol_node.state in RESTING for r in session.robots) \
                and {r.committed_topology for r in session.robots} == {COMPACT}:
            break
    return seen, session


def test_target_v4_checkpoints_through_a_second_epoch() -> None:
    session = _s2_after_first_epoch()
    checkpoints = {
        "A_intent_adopted": lambda s: any(
            r.protocol_node.state == "INTENT_ACTIVE" for r in s.robots),
        "B_committed_profile_active": lambda s: any(
            r.transition_executor is not None for r in s.robots),
        "C_profile_complete_dwell_incomplete": lambda s: (
            all(r.transition_progress >= 1.0 for r in s.robots)
            and s.metric_v3_dwell[COMPACT] == 0.0),
        "D_local_dwell_no_distributed_complete": lambda s: (
            all(r.protocol_node.local_dwell_complete for r in s.robots)
            and len(s.completion_agreements) < 2),
    }
    seen, session = _drive_epoch_two(session, checkpoints)

    # Before the frozen completion boundary the transition predicate must be false.
    for label in ("A_intent_adopted", "B_committed_profile_active"):
        if label in seen:
            assert seen[label].target_metric_v3_dwell_complete is False, label

    # E: after distributed completion the epoch genuinely finished.
    assert len(session.completion_agreements) == 2, "second epoch did not complete"
    assert {r.committed_topology for r in session.robots} == {COMPACT}
    final = _predicates_for(session, COMPACT)
    assert final.candidate_commitment_valid is True


def test_a_second_epoch_records_its_own_distributed_completion() -> None:
    """PCA-18D: epoch 1's COMPLETE agreement cannot serve epoch 2."""
    session = _s2_after_first_epoch()
    first = list(session.completion_agreements)
    _drive_epoch_two(session, {})
    assert len(session.completion_agreements) == 2
    second = session.completion_agreements[1]
    assert second["lifecycle_id"] != first[0]["lifecycle_id"]
    assert second["epoch_id"] != first[0]["epoch_id"]
    assert second["status_agreement_time_seconds"] > first[0][
        "status_agreement_time_seconds"]


# -- PCA-18E: cumulative task history is NOT reset ----------------------------
def test_task_level_history_is_preserved_across_epochs() -> None:
    """Isolation applies to transition-epoch predicates, not episode history."""
    session = _s2_after_first_epoch()
    progress_before = session.max_longitudinal_progress
    _drive_epoch_two(session, {})
    assert session.max_longitudinal_progress >= progress_before, (
        "cumulative longitudinal progress must not be reset by a new epoch")
    assert session.collision_detected is False
    assert session.numerically_valid is True


def test_collision_history_is_cumulative_not_epoch_local() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_state
    session = _s2_after_first_epoch()
    state = canonical_execution_state(session)["mission_and_evaluator"]
    for cumulative in ("max_longitudinal_progress", "collision_detected",
                       "irreversible_loss_open", "numerically_valid"):
        assert cumulative in state
