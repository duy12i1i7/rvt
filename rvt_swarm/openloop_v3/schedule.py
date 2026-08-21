"""Optimizer schedule and early stopping, exactly as frozen.

Deliberately independent of any model so it can be tested without touching a
dataset: the schedule is arithmetic, and arithmetic should be provable on its
own rather than inferred from a training curve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

WARMUP_STEPS = 2000
MAXIMUM_STEPS = 50000
EVALUATION_INTERVAL_STEPS = 1000
EARLY_STOPPING_PATIENCE = 8
EARLY_STOPPING_MIN_DELTA = 0.0
GRADIENT_NORM_CLIP = 1.0
EVENTS_PER_BATCH = 16
LEARNING_RATES: Tuple[float, ...] = (1e-4, 3e-4, 1e-3)
WEIGHT_DECAYS: Tuple[float, ...] = (0.0, 1e-4)


class ScheduleContractError(ValueError):
    """A schedule-contract violation that must fail closed."""


def hyperparameter_grid() -> Tuple[Tuple[float, float], ...]:
    """The frozen 3 x 2 grid, in the frozen tie order: LR major, decay minor."""
    return tuple((lr, decay) for lr in LEARNING_RATES for decay in WEIGHT_DECAYS)


def learning_rate_at(step: int, *, base_learning_rate: float,
                     warmup_steps: int = WARMUP_STEPS) -> float:
    """Linear warmup to the configured rate, then constant.

    ``step`` is 0-based, so the first optimizer step already receives a nonzero
    rate and step ``warmup_steps - 1`` receives exactly the base rate.
    """
    if step < 0:
        raise ScheduleContractError("optimizer step must be nonnegative")
    if base_learning_rate <= 0.0:
        raise ScheduleContractError("base learning rate must be positive")
    if warmup_steps < 0:
        raise ScheduleContractError("warmup must be nonnegative")
    if warmup_steps == 0 or step >= warmup_steps - 1:
        return float(base_learning_rate)
    return float(base_learning_rate) * float(step + 1) / float(warmup_steps)


def scheduled_evaluation_steps(maximum_steps: int = MAXIMUM_STEPS,
                               interval: int = EVALUATION_INTERVAL_STEPS,
                               ) -> Tuple[int, ...]:
    if interval < 1:
        raise ScheduleContractError("the evaluation interval must be positive")
    return tuple(range(interval, maximum_steps + 1, interval))


@dataclass
class EarlyStopping:
    """Strict improvement only, patience 8, earliest step on exact equality.

    ``min_delta`` is fixed at 0.0 by the frozen preregistration -- ruling R7
    withdrew the arbitrary 1e-4 the Stage-5A draft proposed. Because improvement
    is strict (``value < best``), an exactly equal value does not update the best
    step, which is what makes "choose the earlier checkpoint" automatic rather
    than a separate rule that could disagree.
    """

    patience: int = EARLY_STOPPING_PATIENCE
    min_delta: float = EARLY_STOPPING_MIN_DELTA
    best_value: Optional[float] = None
    best_step: Optional[int] = None
    evaluations_since_improvement: int = 0
    history: List[Tuple[int, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.patience < 1:
            raise ScheduleContractError("patience must be at least one evaluation")
        if self.min_delta != 0.0:
            raise ScheduleContractError(
                "the frozen protocol requires strict improvement, min_delta = 0.0")

    def update(self, step: int, value: float) -> bool:
        """Record one scheduled evaluation. Returns True when training must stop."""
        if self.history and step <= self.history[-1][0]:
            raise ScheduleContractError("scheduled evaluations must be increasing")
        self.history.append((int(step), float(value)))
        if self.best_value is None or float(value) < self.best_value:
            self.best_value = float(value)
            self.best_step = int(step)
            self.evaluations_since_improvement = 0
        else:
            self.evaluations_since_improvement += 1
        return self.evaluations_since_improvement >= self.patience

    @property
    def stopped_early(self) -> bool:
        return self.evaluations_since_improvement >= self.patience
