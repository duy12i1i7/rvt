"""Total, specification-level Target V4 outcome classification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Tuple


RECOVERABLE_POSITIVE = "RECOVERABLE_POSITIVE"
VALID_TASK_NEGATIVE = "VALID_TASK_NEGATIVE"
GENERATION_INVALID = "GENERATION_INVALID"
TARGET_DISPOSITIONS: Tuple[str, ...] = (
    RECOVERABLE_POSITIVE,
    VALID_TASK_NEGATIVE,
    GENERATION_INVALID,
)

TERMINATION_CAUSES: Tuple[str, ...] = (
    "GOAL_COMPLETE",
    "HORIZON_COMPLETE",
    "COLLISION",
    "PERSISTENT_DEADLOCK",
    "PROTOCOL_ABORT",
    "PROTOCOL_TIMEOUT",
    "TRANSITION_ABORT",
    "TRANSITION_TIMEOUT",
    "SAFETY_INFEASIBLE",
    "SAFETY_SOLVER_FAILURE",
    "IRREVERSIBLE_PROGRESS_LOSS",
    "WORLD_BOUNDARY_EXIT",
    "COMMUNICATION_ASSUMPTION_VIOLATION",
    "INITIALIZATION_INVALID",
    "GEOMETRY_INVALID",
    "NUMERICAL_INVALID",
    "SCHEDULE_INVALID",
    "EXECUTOR_EXCEPTION",
)

_GENERATION_INVALID_CAUSES = frozenset({
    "INITIALIZATION_INVALID",
    "GEOMETRY_INVALID",
    "NUMERICAL_INVALID",
    "SCHEDULE_INVALID",
    "EXECUTOR_EXCEPTION",
})


@dataclass(frozen=True)
class TargetV4PredicateValues:
    collision_free_complete_horizon: bool
    no_persistent_deadlock: bool
    candidate_commitment_valid: bool
    transition_execution_valid: bool
    target_metric_v3_dwell_complete: bool
    downstream_goal_complete: bool
    protocol_resolved: bool
    safety_projection_resolved: bool
    numerically_valid: bool
    no_irreversible_progress_loss: bool

    def all_satisfied(self) -> bool:
        return all(asdict(self).values())


@dataclass(frozen=True)
class TargetV4ExecutionSummary:
    termination_cause: str
    predicates: TargetV4PredicateValues
    initialization_valid: bool
    geometry_valid: bool
    schedule_conformant: bool
    executor_completed: bool

    def __post_init__(self) -> None:
        if self.termination_cause not in TERMINATION_CAUSES:
            raise ValueError("unknown Target V4 termination cause")


@dataclass(frozen=True)
class TargetV4EvaluationResult:
    disposition: str
    label: int | None
    termination_cause: str
    failed_predicates: Tuple[str, ...]


def evaluate_target_v4(summary: TargetV4ExecutionSummary) -> TargetV4EvaluationResult:
    """Map every declared completed execution to exactly one disposition."""
    if not isinstance(summary, TargetV4ExecutionSummary):
        raise TypeError("Target V4 evaluator requires a typed execution summary")
    predicate_values: Dict[str, bool] = asdict(summary.predicates)
    failed = tuple(sorted(name for name, value in predicate_values.items() if not value))
    generation_valid = (
        summary.initialization_valid
        and summary.geometry_valid
        and summary.schedule_conformant
        and summary.executor_completed
        and summary.predicates.numerically_valid
        and summary.termination_cause not in _GENERATION_INVALID_CAUSES
    )
    if not generation_valid:
        return TargetV4EvaluationResult(
            GENERATION_INVALID, None, summary.termination_cause, failed
        )
    if (
        summary.termination_cause == "GOAL_COMPLETE"
        and summary.predicates.all_satisfied()
    ):
        return TargetV4EvaluationResult(
            RECOVERABLE_POSITIVE, 1, summary.termination_cause, ()
        )
    return TargetV4EvaluationResult(
        VALID_TASK_NEGATIVE, 0, summary.termination_cause, failed
    )
