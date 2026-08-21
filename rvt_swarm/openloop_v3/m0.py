"""M0 -- the frozen constant-probability baseline.

The frozen preregistration fixes M0 as the exact minimizer of the event-equal
grouped Bernoulli NLL over a constant predictor. That minimizer has a closed
form, so M0 needs no optimizer at all:

    p_hat = (1 / 2E) * SUM over events e and candidates c of k_{e,c} / R_{e,c}

Derivation. With a constant p the per-robot term no longer depends on the robot,
so step 2 of the frozen aggregation collapses and the dataset loss becomes a
weighted Bernoulli cross-entropy over the 2E candidate observations with equal
weights w = 1/(2E) and soft targets t = k/R. Setting the derivative of
SUM_j w_j [-t_j log p - (1 - t_j) log(1 - p)] to zero gives
p = SUM_j w_j t_j / SUM_j w_j, which is the plain mean of k/R.

The value therefore does not depend on N, on the order of candidates, or on the
order of events. This module is a pure function; it fits nothing by itself and
knows nothing about which dataset it is handed.
"""

from __future__ import annotations

from typing import Sequence


class M0ContractError(ValueError):
    """An M0 fitting-contract violation that must fail closed."""


def m0_constant_probability(groups: Sequence[object]) -> float:
    """The closed-form event-equal constant. Pure; no optimizer, no state."""
    if not groups:
        raise M0ContractError("M0 requires at least one decision event")
    total = 0.0
    observations = 0
    for group in groups:
        for candidate in (group.compact, group.line):        # type: ignore[attr-defined]
            replicas = int(candidate.R)
            successes = int(candidate.k)
            if replicas < 1:
                raise M0ContractError("R must be a positive integer")
            if not 0 <= successes <= replicas:
                raise M0ContractError("the observation requires integer 0 <= k <= R")
            total += float(successes) / float(replicas)
            observations += 1
    if observations != 2 * len(groups):
        raise M0ContractError("every decision event must carry exactly two candidates")
    return total / float(observations)
