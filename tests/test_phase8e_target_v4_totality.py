from __future__ import annotations

import json
import copy
from pathlib import Path

import pytest

from rvt_swarm.phase8e.protocol import validate_target_v4_execution_contract
from rvt_swarm.phase8e.target import (
    GENERATION_INVALID,
    RECOVERABLE_POSITIVE,
    TERMINATION_CAUSES,
    VALID_TASK_NEGATIVE,
    TargetV4ExecutionSummary,
    TargetV4PredicateValues,
    evaluate_target_v4,
)


ROOT = Path(__file__).resolve().parents[1]


def _predicates(value: bool = True) -> TargetV4PredicateValues:
    return TargetV4PredicateValues(*([value] * 10))


def _summary(cause: str, predicates: TargetV4PredicateValues) -> TargetV4ExecutionSummary:
    return TargetV4ExecutionSummary(
        cause,
        predicates,
        initialization_valid=True,
        geometry_valid=True,
        schedule_conformant=True,
        executor_completed=True,
    )


def test_target_contract_defines_exactly_ten_predicates() -> None:
    document = json.loads((
        ROOT / "results/rvt_fd24/target_v4_execution_contract_v1.json"
    ).read_text(encoding="ascii"))
    validate_target_v4_execution_contract(document)
    assert len(document["conditions"]) == 10


def test_positive_requires_goal_completion_and_all_predicates() -> None:
    positive = evaluate_target_v4(_summary("GOAL_COMPLETE", _predicates()))
    assert positive.disposition == RECOVERABLE_POSITIVE
    assert positive.label == 1
    horizon = evaluate_target_v4(_summary("HORIZON_COMPLETE", _predicates()))
    assert horizon.disposition == VALID_TASK_NEGATIVE
    assert horizon.label == 0


def test_every_termination_cause_has_exactly_one_disposition() -> None:
    results = {
        cause: evaluate_target_v4(_summary(cause, _predicates())).disposition
        for cause in TERMINATION_CAUSES
    }
    assert set(results) == set(TERMINATION_CAUSES)
    assert set(results.values()) <= {
        RECOVERABLE_POSITIVE, VALID_TASK_NEGATIVE, GENERATION_INVALID
    }
    assert results["NUMERICAL_INVALID"] == GENERATION_INVALID
    assert results["COMMUNICATION_ASSUMPTION_VIOLATION"] == VALID_TASK_NEGATIVE


def test_numerical_predicate_failure_is_generation_invalid() -> None:
    values = _predicates()
    invalid = TargetV4PredicateValues(**{
        **values.__dict__, "numerically_valid": False
    })
    result = evaluate_target_v4(_summary("HORIZON_COMPLETE", invalid))
    assert result.disposition == GENERATION_INVALID
    assert result.label is None


@pytest.mark.parametrize("mutation", ["unknown", "omitted"])
def test_target_predicate_fields_cannot_be_unknown_or_omitted(mutation: str) -> None:
    document = json.loads((
        ROOT / "results/rvt_fd24/target_v4_execution_contract_v1.json"
    ).read_text(encoding="ascii"))
    changed = copy.deepcopy(document)
    condition = changed["conditions"]["no_persistent_deadlock"]
    if mutation == "unknown":
        condition["simulator_default_window"] = True
    else:
        condition.pop("window_seconds")
    with pytest.raises(ValueError):
        validate_target_v4_execution_contract(changed)
