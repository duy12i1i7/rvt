"""RB-14 -- Target V4 runtime polarity, truth table and termination causes."""
from __future__ import annotations
import json, pathlib, pytest
from rvt_swarm.phase8e.target import (
    TargetV4ExecutionSummary, TargetV4PredicateValues, evaluate_target_v4)
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import (
    SAFETY_CAUSES, build_execution_summary, execute_candidate, snapshot)
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run

ROOT = pathlib.Path("results/rvt_fd24")
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())

SCIENTIFIC_NEGATIVE_CAUSES = [
    "COLLISION", "PERSISTENT_DEADLOCK", "PROTOCOL_ABORT", "PROTOCOL_TIMEOUT",
    "TRANSITION_ABORT", "TRANSITION_TIMEOUT", "SAFETY_INFEASIBLE",
    "SAFETY_SOLVER_FAILURE", "IRREVERSIBLE_PROGRESS_LOSS", "WORLD_BOUNDARY_EXIT",
    "COMMUNICATION_ASSUMPTION_VIOLATION", "HORIZON_COMPLETE",
]
GENERATION_INVALID_CAUSES = [
    "INITIALIZATION_INVALID", "GEOMETRY_INVALID", "NUMERICAL_INVALID",
    "SCHEDULE_INVALID", "EXECUTOR_EXCEPTION",
]


def _predicates(**overrides):
    values = {f: True for f in TargetV4PredicateValues.__dataclass_fields__}
    values.update(overrides)
    return TargetV4PredicateValues(**values)


def _summary(cause, *, predicates=None, initialization_valid=True, geometry_valid=True,
             schedule_conformant=True, executor_completed=True):
    return TargetV4ExecutionSummary(
        termination_cause=cause, predicates=predicates or _predicates(),
        initialization_valid=initialization_valid, geometry_valid=geometry_valid,
        schedule_conformant=schedule_conformant, executor_completed=executor_completed)


# -- the three-way partition -------------------------------------------------
def test_a_complete_success_is_a_recoverable_positive() -> None:
    result = evaluate_target_v4(_summary("GOAL_COMPLETE"))
    assert result.disposition == "RECOVERABLE_POSITIVE"
    assert result.label == 1


@pytest.mark.parametrize("cause", SCIENTIFIC_NEGATIVE_CAUSES)
def test_genuine_scientific_failures_stay_valid_task_negatives(cause) -> None:
    """The polarity check: a hard failure must never become generation-invalid."""
    result = evaluate_target_v4(_summary(cause, predicates=_predicates(
        downstream_goal_complete=False)))
    assert result.disposition == "VALID_TASK_NEGATIVE", cause
    assert result.label == 0


@pytest.mark.parametrize("cause", GENERATION_INVALID_CAUSES)
def test_only_frozen_invalid_execution_conditions_are_generation_invalid(cause) -> None:
    kwargs = {"INITIALIZATION_INVALID": {"initialization_valid": False},
              "GEOMETRY_INVALID": {"geometry_valid": False},
              "SCHEDULE_INVALID": {"schedule_conformant": False},
              "EXECUTOR_EXCEPTION": {"executor_completed": False},
              "NUMERICAL_INVALID": {"predicates": _predicates(numerically_valid=False)},
              }[cause]
    result = evaluate_target_v4(_summary(cause, **kwargs))
    assert result.disposition == "GENERATION_INVALID", cause
    assert result.label is None


@pytest.mark.parametrize("predicate", list(TargetV4PredicateValues.__dataclass_fields__))
def test_every_predicate_alone_decides_the_outcome(predicate) -> None:
    """Truth table: flipping any single predicate must change the disposition."""
    result = evaluate_target_v4(_summary("GOAL_COMPLETE",
                                         predicates=_predicates(**{predicate: False})))
    if predicate == "numerically_valid":
        assert result.disposition == "GENERATION_INVALID"
    else:
        assert result.disposition == "VALID_TASK_NEGATIVE"
        assert predicate in result.failed_predicates


def test_exactly_one_classification_is_returned() -> None:
    for cause in SCIENTIFIC_NEGATIVE_CAUSES + GENERATION_INVALID_CAUSES + ["GOAL_COMPLETE"]:
        result = evaluate_target_v4(_summary(cause))
        assert result.disposition in {"RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE",
                                      "GENERATION_INVALID"}


# -- safety cause separation --------------------------------------------------
def test_solver_failure_and_infeasibility_remain_distinct_causes() -> None:
    assert set(SAFETY_CAUSES) == {"SAFETY_INFEASIBLE", "SAFETY_SOLVER_FAILURE"}
    assert "SAFETY_INFEASIBLE" in TARGET["termination_causes"]
    assert "SAFETY_SOLVER_FAILURE" in TARGET["termination_causes"]
    a = evaluate_target_v4(_summary("SAFETY_INFEASIBLE", predicates=_predicates(
        safety_projection_resolved=False)))
    b = evaluate_target_v4(_summary("SAFETY_SOLVER_FAILURE", predicates=_predicates(
        safety_projection_resolved=False)))
    assert a.disposition == b.disposition          # same frozen disposition
    assert a.termination_cause != b.termination_cause   # but never merged


def test_raw_traces_count_the_two_safety_causes_separately() -> None:
    session = run(build_session("train-f2-00", policy_id=P.S0), steps=25)
    result = execute_candidate(snapshot(session), COMPACT, max_steps=60)
    assert hasattr(result, "safety_infeasible_robots")
    assert hasattr(result, "safety_solver_failure_robots")


# -- runtime summary wiring ---------------------------------------------------
def test_runtime_summary_uses_the_frozen_vocabulary() -> None:
    session = run(build_session("train-f2-00", policy_id=P.S1), steps=400)
    summary = build_execution_summary(session, COMPACT)
    assert summary.termination_cause in set(TARGET["termination_causes"])


def test_a_collision_episode_becomes_a_valid_task_negative_not_invalid() -> None:
    session = run(build_session("train-f2-00", policy_id=P.S1), steps=400)
    assert session.termination.cause == "COLLISION"
    result = evaluate_target_v4(build_execution_summary(session, COMPACT))
    assert result.disposition == "VALID_TASK_NEGATIVE"
    assert result.label == 0


def test_an_open_field_hold_candidate_can_be_positive() -> None:
    """Non-vacuity: the evaluator must be able to return a positive."""
    session = run(build_session("train-f1-00", policy_id=P.S1), steps=20)
    result = execute_candidate(snapshot(session), COMPACT, max_steps=400)
    assert result.disposition == "RECOVERABLE_POSITIVE"
    assert result.label == 1


def test_goal_predicate_uses_the_topology_origin_estimator() -> None:
    session = run(build_session("train-f1-00", policy_id=P.S1), steps=10)
    origin_compact = session.fitted_topology_origin(COMPACT)
    origin_line = session.fitted_topology_origin(LINE)
    assert origin_compact != origin_line, "the estimator must depend on the topology"
