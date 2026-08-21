"""Hyperparameter scoring and the frozen refit-step rule.

Both are pure arithmetic over already-computed held-out numbers, so neither can
reach a dataset even by accident.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence, Tuple

from .schedule import (
    EVALUATION_INTERVAL_STEPS, MAXIMUM_STEPS, hyperparameter_grid,
)

REFIT_STEP_MINIMUM = 1000
REFIT_STEP_MAXIMUM = MAXIMUM_STEPS


class HyperparameterSelectionError(ValueError):
    """A hyperparameter-selection contract violation that must fail closed."""


def hyperparameter_score(held_out_nll: Sequence[float]) -> float:
    """Mean held-out TRAIN NLL over the 3 seeds x 2 folds."""
    values = [float(value) for value in held_out_nll]
    if not values:
        raise HyperparameterSelectionError("a configuration needs at least one run")
    if any(not math.isfinite(value) for value in values):
        raise HyperparameterSelectionError("held-out NLL must be finite")
    return sum(values) / float(len(values))


def choose_hyperparameters(
    scores: Mapping[Tuple[float, float], float],
) -> Tuple[float, float]:
    """Lowest score; exact ties broken by lower LR, then lower weight decay."""
    grid = hyperparameter_grid()
    if set(scores) != set(grid):
        raise HyperparameterSelectionError(
            "every frozen configuration must be scored exactly once")
    best = min(scores.values())
    # The grid is already emitted in the frozen tie order, so the first
    # configuration attaining the minimum IS the tie-broken winner. Encoding the
    # tie order in the enumeration rather than in a comparator keeps the two from
    # ever disagreeing.
    for configuration in grid:
        if scores[configuration] == best:
            return configuration
    raise HyperparameterSelectionError("no configuration attained the minimum")


def refit_step(step_fold_a: int, step_fold_b: int) -> int:
    """S*(f, s) = 1000 * ceil((s_A + s_B) / 2000), clamped to [1000, 50000].

    Ceiling, not rounding: the mean of two multiples of 1000 can land on a
    half-multiple, and every half-rounding convention is a choice that would have
    had to be argued. Ceiling needs no such argument and is deterministic.
    """
    for value in (step_fold_a, step_fold_b):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HyperparameterSelectionError("fold steps must be nonnegative integers")
        if value % EVALUATION_INTERVAL_STEPS:
            raise HyperparameterSelectionError(
                "a selected step must fall on a scheduled evaluation")
    raw = EVALUATION_INTERVAL_STEPS * math.ceil(
        (step_fold_a + step_fold_b) / (2 * EVALUATION_INTERVAL_STEPS))
    return max(REFIT_STEP_MINIMUM, min(REFIT_STEP_MAXIMUM, raw))
