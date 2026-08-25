"""The CL-DEV-R final-configuration selection rule, frozen before CL-DEV-R exists.

The method may be developed adaptively. The rule that picks the final
configuration may not. Every configuration is registered before it runs, every
result enters the append-only ledger, and the winner is whichever admissible
configuration the ordering below selects -- never a subjective choice made after
looking at plots.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

MAXIMUM_EVALUATED_CONFIGURATIONS = 40          # unchanged from V1
CONSECUTIVE_NON_IMPROVEMENTS_TO_STOP = 3       # unchanged from V1
NO_ADMISSIBLE_CONFIGURATION = "CLOSED_LOOP_DEVELOPMENT_NO_ADMISSIBLE_CONFIGURATION"


class DevelopmentSelectionError(ValueError):
    """A development-selection violation that must fail closed."""


@dataclass(frozen=True)
class ConfigurationRecord:
    ledger_index: int                 # position in the append-only hash-chained ledger
    registered_before_execution: bool
    run_completed: bool
    invalid_episode_fraction_acceptable: bool
    safety_gate_passes: bool          # the frozen H-CL2 rule vs B1, on CL-DEV-R
    delta_success_point: float        # primary development objective
    delta_success_ci_lower: float     # tie-break 1
    deadlock_rate: float              # tie-break 2, lower is better
    irreversible_collapse_rate: float # tie-break 3, lower is better
    minimum_clearance_m: float        # tie-break 4, higher is better
    topology_switches_per_episode: float  # tie-break 5, fewer is better


def is_admissible(c: ConfigurationRecord) -> bool:
    """Eligibility and the safety feasibility gate.

    A configuration that improves progress while failing the safety gate is
    INADMISSIBLE. That is not a trade-off to be weighed; it removes the
    configuration from consideration entirely.
    """
    return bool(c.registered_before_execution and c.run_completed
                and c.invalid_episode_fraction_acceptable and c.safety_gate_passes)


def _ordering_key(c: ConfigurationRecord) -> tuple:
    return (
        c.delta_success_point,          # 1. maximise the primary objective
        c.delta_success_ci_lower,       # 2. then the more certain of equals
        -c.deadlock_rate,               # 3. then fewer deadlocks
        -c.irreversible_collapse_rate,  # 4. then fewer collapses
        c.minimum_clearance_m,          # 5. then more clearance
        -c.topology_switches_per_episode,  # 6. then less switching churn
        -c.ledger_index,                # 7. then the earliest registered
    )


def select_final_configuration(ledger: Sequence[ConfigurationRecord]) -> ConfigurationRecord | str:
    """Return the frozen winner, or the no-admissible-configuration outcome."""
    if len(ledger) > MAXIMUM_EVALUATED_CONFIGURATIONS:
        raise DevelopmentSelectionError(
            f"the ledger holds {len(ledger)} configurations; the frozen budget is "
            f"{MAXIMUM_EVALUATED_CONFIGURATIONS}")
    indices = [c.ledger_index for c in ledger]
    if len(set(indices)) != len(indices):
        raise DevelopmentSelectionError("the ledger contains duplicate indices")
    unregistered = [c.ledger_index for c in ledger if not c.registered_before_execution]
    if unregistered:
        raise DevelopmentSelectionError(
            f"configurations were executed without prior registration: {unregistered}")
    admissible = [c for c in ledger if is_admissible(c)]
    if not admissible:
        return NO_ADMISSIBLE_CONFIGURATION
    return max(admissible, key=_ordering_key)


def should_stop(deltas_in_order: Sequence[float]) -> bool:
    """The frozen stopping procedure: budget exhausted, or a run of no improvement."""
    if len(deltas_in_order) >= MAXIMUM_EVALUATED_CONFIGURATIONS:
        return True
    if len(deltas_in_order) <= CONSECUTIVE_NON_IMPROVEMENTS_TO_STOP:
        return False
    best_before = max(deltas_in_order[:-CONSECUTIVE_NON_IMPROVEMENTS_TO_STOP])
    tail = deltas_in_order[-CONSECUTIVE_NON_IMPROVEMENTS_TO_STOP:]
    return all(d <= best_before for d in tail)
