"""The single executable clean-room family-selection rule.

This is the only implementation of the rule. Orchestration calls it and reports
what it returns; no orchestration script may restate the eligibility tests, the
case analysis, or the parsimony tie-break.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

import numpy as np

from rvt_swarm.openloop_v3.bootstrap import CONFIDENCE_LEVEL

# Prospectively frozen clean-room constants. The seed is an arbitrary value fixed
# before any clean-room data exists; it is deliberately distinct from the pilot
# programme's 20260821 so that no clean-room interval inherits a pilot draw order.
CLEAN_ROOM_BOOTSTRAP_REPLICATES = 10000
CLEAN_ROOM_BOOTSTRAP_SEED = 20260901
CLEAN_ROOM_CONFIDENCE_LEVEL = CONFIDENCE_LEVEL  # 0.95, percentile method


class SelectionContractError(ValueError):
    """A family-selection violation that must fail closed."""


@dataclass(frozen=True)
class DeltaInterval:
    comparison: str
    point: float
    lower: float
    upper: float


@dataclass(frozen=True)
class SelectionOutcome:
    winner: str
    case: int
    m1_eligible: bool
    m2_eligible: bool
    rationale: str
    learnability_supported: bool


def percentile_interval(replicates_a: np.ndarray, replicates_b: np.ndarray,
                        point_a: float, point_b: float, comparison: str,
                        *, level: float = CLEAN_ROOM_CONFIDENCE_LEVEL) -> DeltaInterval:
    """Paired percentile interval of a - b, replicate by replicate."""
    if replicates_a.shape != replicates_b.shape:
        raise SelectionContractError("paired families must share a replicate count")
    if not 0.0 < level < 1.0:
        raise SelectionContractError("the confidence level must lie in (0, 1)")
    difference = np.asarray(replicates_a) - np.asarray(replicates_b)
    tail = (1.0 - level) / 2.0
    return DeltaInterval(
        comparison=comparison,
        point=float(point_a) - float(point_b),
        lower=float(np.percentile(difference, 100.0 * tail)),
        upper=float(np.percentile(difference, 100.0 * (1.0 - tail))))


def select_family(delta_10: DeltaInterval, delta_20: DeltaInterval,
                  delta_21: DeltaInterval) -> SelectionOutcome:
    """Apply the frozen rule to the three paired intervals.

    Eligibility is strict: a family qualifies only if the upper bound of its
    interval against M0 lies strictly below zero. When both qualify, M2 is taken
    over M1 only if the upper bound of delta_21 is strictly below zero; otherwise
    M1 wins by parsimony.
    """
    for name, d in (("delta_10", delta_10), ("delta_20", delta_20), ("delta_21", delta_21)):
        if d.lower > d.upper:
            raise SelectionContractError(f"{name} has an inverted interval")
    m1 = bool(delta_10.upper < 0.0)
    m2 = bool(delta_20.upper < 0.0)
    if not m1 and not m2:
        return SelectionOutcome("M0", 1, m1, m2,
                                "neither learned family excluded zero against M0", False)
    if m1 and not m2:
        return SelectionOutcome("M1", 2, m1, m2, "only M1 excluded zero against M0", True)
    if m2 and not m1:
        return SelectionOutcome("M2", 3, m1, m2, "only M2 excluded zero against M0", True)
    if delta_21.upper < 0.0:
        return SelectionOutcome("M2", 4, m1, m2,
                                "both eligible and M2 excluded zero against M1", True)
    return SelectionOutcome("M1", 4, m1, m2,
                            "both eligible and M2 did not exclude zero against M1; "
                            "M1 wins by parsimony", True)


# The downstream runtime representative is a methodological choice fixed before
# any clean-room data exists. It is never selected using SELECT-R: all three
# seeds participate in family selection, and this seed is only the predefined
# runtime representative of whichever family the rule returns.
DOWNSTREAM_REPRESENTATIVE_SEED = 47


def downstream_checkpoint(outcome: SelectionOutcome) -> Tuple[str, int] | None:
    """The (family, seed) carried into closed-loop work, or None if M0 wins."""
    if outcome.winner == "M0":
        return None
    return (outcome.winner, DOWNSTREAM_REPRESENTATIVE_SEED)
