from dataclasses import replace

from rvt_swarm.phase8.targets import (
    COUNTERFACTUAL_ROLLOUT_SCHEMA_VERSION,
    RECOVERABILITY_TARGET_SCHEMA_VERSION,
    CounterfactualRolloutTrace,
    TaskRecoveryConditions,
    evaluate_candidate_recoverability,
    joint_outcome_category,
)
from rvt_swarm.topology_registry import COMPACT, LINE


def _trace(candidate, conditions, event="event-1"):
    return CounterfactualRolloutTrace(
        COUNTERFACTUAL_ROLLOUT_SCHEMA_VERSION,
        "episode-1",
        event,
        candidate,
        0,
        "a" * 64,
        "b" * 64,
        42,
        "c" * 64,
        "d" * 64,
        90.0,
        conditions,
        None,
        600,
    )


def _success():
    return TaskRecoveryConditions(*(True for _ in range(10)))


def test_recoverability_requires_every_task_level_condition():
    positive = evaluate_candidate_recoverability((_trace(COMPACT, _success()),))
    assert positive.schema_version == RECOVERABILITY_TARGET_SCHEMA_VERSION
    assert positive.label == 1
    for field in TaskRecoveryConditions.__dataclass_fields__:
        failed = replace(_success(), **{field: False})
        target = evaluate_candidate_recoverability((_trace(COMPACT, failed),))
        assert target.label == 0, field


def test_numerical_failure_is_invalid_and_not_positive():
    conditions = replace(_success(), numerically_valid=False)
    target = evaluate_candidate_recoverability((_trace(LINE, conditions),))
    assert target.label == 0
    assert target.invalid


def test_joint_outcome_preserves_all_four_categories():
    positive_compact = evaluate_candidate_recoverability((_trace(COMPACT, _success()),))
    negative_compact = evaluate_candidate_recoverability((_trace(COMPACT, replace(_success(), downstream_goal_complete=False)),))
    positive_line = evaluate_candidate_recoverability((_trace(LINE, _success()),))
    negative_line = evaluate_candidate_recoverability((_trace(LINE, replace(_success(), downstream_goal_complete=False)),))
    assert joint_outcome_category(positive_compact, negative_line) == "COMPACT_ONLY_SUCCESS"
    assert joint_outcome_category(negative_compact, positive_line) == "LINE_ONLY_SUCCESS"
    assert joint_outcome_category(positive_compact, positive_line) == "BOTH_SUCCESS"
    assert joint_outcome_category(negative_compact, negative_line) == "BOTH_FAIL"
