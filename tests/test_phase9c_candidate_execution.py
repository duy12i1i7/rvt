"""RB-13 -- counterfactual candidate executor, both cases and replicas."""
from __future__ import annotations
import pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import (
    execute_candidate, execute_candidate_pair, snapshot)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE
from tests.test_phase9c_publication_executor import build_session, run


def _snapshot(layout="train-f1-00", policy_id=P.S1, steps=15):
    return snapshot(run(build_session(layout, policy_id=policy_id), steps=steps))


def test_keep_is_rejected_as_a_candidate() -> None:
    with pytest.raises(ValueError):
        execute_candidate(_snapshot(), KEEP, max_steps=5)


def test_case_a_hold_candidate_creates_no_source_equals_target_lifecycle() -> None:
    snap = _snapshot()
    assert all(r.committed_topology == COMPACT for r in snap._session.robots)
    result = execute_candidate(snap, COMPACT, max_steps=120)
    assert result.created_lifecycle is False


def test_case_b_differing_candidate_opens_a_real_phase7_lifecycle() -> None:
    result = execute_candidate(_snapshot(), LINE, max_steps=120)
    assert result.created_lifecycle is True


def test_both_candidates_execute_beyond_step_zero() -> None:
    snap = _snapshot()
    for candidate in (COMPACT, LINE):
        assert execute_candidate(snap, candidate, max_steps=60).control_steps > 0


def test_candidate_execution_does_not_mutate_the_source_snapshot() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_hash
    snap = _snapshot()
    execute_candidate(snap, LINE, max_steps=80)
    assert canonical_execution_hash(snap._session) == snap.canonical_hash


def test_the_source_policy_stops_originating_inside_a_counterfactual() -> None:
    snap = _snapshot("train-f5-00", policy_id=P.S0, steps=5)
    result = execute_candidate(snap, COMPACT, max_steps=60)
    assert result.created_lifecycle is False


@pytest.mark.parametrize("family,expected", [("F8", 3), ("F9", 3), ("F1", 1), ("F5", 1)])
def test_replica_counts_and_individual_traces_are_preserved(family, expected) -> None:
    layout = {"F8": "train-f8-01", "F9": "train-f9-00",
              "F1": "train-f1-00", "F5": "train-f5-00"}[family]
    pair = execute_candidate_pair(_snapshot(layout, steps=12), family,
                                  matched_disturbance_seed=4242, max_steps=60)
    for candidate, result in pair.items():
        assert len(result.replicas) == expected
        assert [r.replica_index for r in result.replicas] == list(range(expected))
        for replica in result.replicas:
            assert replica.termination_cause


def test_all_success_aggregation_is_applied_only_after_every_replica_ran() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import CandidateReplicaResult, CandidateResult
    def replica(index, label):
        return CandidateReplicaResult(
            candidate_topology=COMPACT, replica_index=index,
            termination_cause="GOAL_COMPLETE",
            disposition="RECOVERABLE_POSITIVE" if label else "VALID_TASK_NEGATIVE",
            label=label, failed_predicates=(), control_steps=1,
            safety_infeasible_robots=0, safety_solver_failure_robots=0,
            created_lifecycle=False, initial_clone_hash="x", final_state_hash="y")
    assert CandidateResult(COMPACT, tuple(replica(i, 1) for i in range(3))).aggregate_label == 1
    mixed = CandidateResult(COMPACT, (replica(0, 1), replica(1, 0), replica(2, 1)))
    assert mixed.aggregate_label == 0, "one failing replica must fail the aggregate"
    assert [r.label for r in mixed.replicas] == [1, 0, 1], "individual traces preserved"


def test_a_generation_invalid_replica_voids_the_aggregate_label() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import CandidateReplicaResult, CandidateResult
    invalid = CandidateReplicaResult(
        candidate_topology=COMPACT, replica_index=0, termination_cause="NUMERICAL_INVALID",
        disposition="GENERATION_INVALID", label=None, failed_predicates=(),
        control_steps=1, safety_infeasible_robots=0, safety_solver_failure_robots=0,
        created_lifecycle=False, initial_clone_hash="x", final_state_hash="y")
    assert CandidateResult(COMPACT, (invalid,)).aggregate_label is None
