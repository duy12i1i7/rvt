from dataclasses import replace

import pytest

from rvt_swarm.phase8.targets import (
    COUNTERFACTUAL_ROLLOUT_SCHEMA_VERSION,
    CounterfactualRolloutTrace,
    MatchedCounterfactualPair,
    TaskRecoveryConditions,
    evaluate_candidate_recoverability,
    verify_matched_counterfactual_pair,
)
from rvt_swarm.topology_registry import COMPACT, LINE


def _trace(candidate, replica=0, seed=17, success=True):
    conditions = TaskRecoveryConditions(*(success for _ in range(10)))
    return CounterfactualRolloutTrace(
        COUNTERFACTUAL_ROLLOUT_SCHEMA_VERSION,
        "ep", "event", candidate, replica,
        "a" * 64, "b" * 64, seed, "c" * 64, "d" * 64,
        120.0, conditions, None if success else "failed", 800,
    )


def test_candidate_counterfactuals_are_matched_on_state_seed_and_budget():
    pair = MatchedCounterfactualPair("event", (_trace(COMPACT),), (_trace(LINE),))
    assert verify_matched_counterfactual_pair(pair) == ()


def test_disturbance_or_budget_mismatch_is_explicit():
    mismatch = MatchedCounterfactualPair(
        "event", (_trace(COMPACT),), (_trace(LINE, seed=18),)
    )
    assert verify_matched_counterfactual_pair(mismatch) == ("unmatched_replica:0",)
    budget = MatchedCounterfactualPair(
        "event", (_trace(COMPACT),), (_trace(LINE), _trace(LINE, replica=1))
    )
    assert verify_matched_counterfactual_pair(budget) == ("candidate_rollout_budget_mismatch",)


def test_stochastic_aggregation_is_frozen_to_all_success_and_reports_instability():
    traces = (
        _trace(COMPACT, 0, success=True),
        _trace(COMPACT, 1, success=True),
        _trace(COMPACT, 2, success=False),
    )
    target = evaluate_candidate_recoverability(traces)
    assert target.aggregation == "all_success"
    assert target.label == 0
    assert target.unstable


def test_unpredeclared_replica_count_is_rejected():
    with pytest.raises(ValueError, match="replica count"):
        evaluate_candidate_recoverability((_trace(COMPACT), _trace(COMPACT, 1)))
