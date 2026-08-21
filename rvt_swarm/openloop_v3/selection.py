"""The frozen family-selection rule and the TRAIN-only seed designation.

Both are pure functions over already-computed summaries. The selection rule is
deliberately unable to see anything except the three NLL values and the three
paired intervals: a rule that could reach a second metric could be argued into
using it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

M0 = "M0"
M1 = "M1"
M2 = "M2"
FAMILIES: Tuple[str, ...] = (M0, M1, M2)


class SelectionContractError(ValueError):
    """A selection-contract violation that must fail closed."""


@dataclass(frozen=True)
class FamilySelection:
    winner: str
    m1_eligible: bool
    m2_eligible: bool
    case: int
    learnability_supported: bool
    rationale: str


def _upper(interval: Tuple[float, float]) -> float:
    lower, upper = float(interval[0]), float(interval[1])
    if upper < lower:
        raise SelectionContractError("a confidence interval must be ordered")
    return upper


def select_family(*, upper_ci_delta_10: float, upper_ci_delta_20: float,
                  upper_ci_delta_21: float) -> FamilySelection:
    """The frozen four-case rule.

    Eligibility is STRICT: an upper bound of exactly 0.0 does not qualify. A
    boundary that touches zero has not excluded the null, and treating it as if
    it had is precisely the slippage a preregistration exists to prevent.
    """
    for value in (upper_ci_delta_10, upper_ci_delta_20, upper_ci_delta_21):
        if value != value:                                       # NaN
            raise SelectionContractError("a confidence bound is not a number")
    m1_eligible = float(upper_ci_delta_10) < 0.0
    m2_eligible = float(upper_ci_delta_20) < 0.0
    if not m1_eligible and not m2_eligible:
        return FamilySelection(
            winner=M0, m1_eligible=False, m2_eligible=False, case=1,
            learnability_supported=False,
            rationale="neither learned family excluded zero against M0")
    if m1_eligible and not m2_eligible:
        return FamilySelection(
            winner=M1, m1_eligible=True, m2_eligible=False, case=2,
            learnability_supported=True,
            rationale="only M1 excluded zero against M0")
    if m2_eligible and not m1_eligible:
        return FamilySelection(
            winner=M2, m1_eligible=False, m2_eligible=True, case=3,
            learnability_supported=True,
            rationale="only M2 excluded zero against M0")
    if float(upper_ci_delta_21) < 0.0:
        return FamilySelection(
            winner=M2, m1_eligible=True, m2_eligible=True, case=4,
            learnability_supported=True,
            rationale="both eligible and M2 excluded zero against M1")
    return FamilySelection(
        winner=M1, m1_eligible=True, m2_eligible=True, case=4,
        learnability_supported=True,
        rationale="both eligible, M2 did not exclude zero against M1; parsimony")


def select_family_from_intervals(
    delta_10: Tuple[float, float], delta_20: Tuple[float, float],
    delta_21: Tuple[float, float]) -> FamilySelection:
    return select_family(upper_ci_delta_10=_upper(delta_10),
                         upper_ci_delta_20=_upper(delta_20),
                         upper_ci_delta_21=_upper(delta_21))


def designate_downstream_seed(cross_validation_nll: Mapping[int, float]) -> int:
    """The median TRAIN-only CV NLL seed; exact ties go to the lower seed.

    Median, not minimum: a minimum would reward whichever initialization happened
    to land well, which is the seed-shopping the frozen protocol forbids. The
    quantity is TRAIN-only, so VALIDATION never sees a seed decision.
    """
    if len(cross_validation_nll) != 3:
        raise SelectionContractError("the frozen protocol trains exactly three seeds")
    ordered = sorted((float(value), int(seed))
                     for seed, value in cross_validation_nll.items())
    return ordered[1][1]


def per_seed_cross_validation_nll(fold_values: Mapping[int, Sequence[float]],
                                  ) -> Mapping[int, float]:
    """Mean over folds A and B of the selected held-out NLL, per seed."""
    out = {}
    for seed, values in fold_values.items():
        items = [float(value) for value in values]
        if len(items) != 2:
            raise SelectionContractError("each seed contributes exactly two folds")
        out[int(seed)] = sum(items) / 2.0
    return out
