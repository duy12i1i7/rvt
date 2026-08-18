"""EVENT_EQUAL_REPLICA_NORMALIZED_BRIER_V3.

``Brier_robot = (1/R) * SUM_r (p - Y_r)^2``

Because every ``Y_r`` is 0 or 1, ``Y_r^2 = Y_r`` and the sum collapses to

``p^2 - 2*p*(k/R) + k/R``

which is what this module computes. The tempting shortcut ``(p - k/R)^2`` is a
*different quantity*: it scores the prediction against the observed frequency
instead of against the replicas, and it is smaller whenever the replicas
disagree. At ``p = 0.5, k = 1, R = 3`` the correct value is 0.25 and the
shortcut gives 0.02777..., so a model could look eleven times better on exactly
the stochastic-boundary events V3 exists to learn. :func:`brier_robot` is the
only public entry point and the shortcut is not implemented anywhere.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import torch

RECOVERABILITY_BRIER_METRIC_V3_SHA256 = (
    "0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04")
EVENT_EQUAL_REPLICA_NORMALIZED_BRIER_V3 = "EVENT_EQUAL_REPLICA_NORMALIZED_BRIER_V3"

#: The frozen contract forbids a raw row mean over the split.
RAW_ROW_MEAN_PERMITTED = False


class V3MetricContractError(ValueError):
    """A metric-contract violation that must fail closed."""


def _check(k: int, R: int) -> float:                           # noqa: N803
    if not isinstance(R, int) or isinstance(R, bool) or R < 1:
        raise V3MetricContractError("R must be a positive integer")
    if not isinstance(k, int) or isinstance(k, bool) or not 0 <= k <= R:
        raise V3MetricContractError("the observation requires integer 0 <= k <= R")
    return float(k) / float(R)


def brier_robot(
    probability: torch.Tensor, *, k: int, R: int,              # noqa: N803
) -> torch.Tensor:
    """Replica-normalized Brier for one robot-local prediction.

    Equivalent to averaging ``(p - Y_r)^2`` over the R actual replica outcomes.
    """
    fraction = _check(k, R)
    p = probability
    return p * p - 2.0 * p * fraction + fraction


def brier_from_replica_outcomes(
    probability: torch.Tensor, outcomes: Sequence[int],
) -> torch.Tensor:
    """The definition, evaluated replica by replica.

    Kept so a test can confirm the closed form agrees with the literal
    ``(1/R) SUM_r (p - Y_r)^2`` on every ``(k, R)`` pattern.
    """
    if not outcomes:
        raise V3MetricContractError("Brier requires at least one replica outcome")
    for value in outcomes:
        if value not in (0, 1):
            raise V3MetricContractError(
                "every replica outcome must be a valid Y in {0, 1}; an invalid "
                "replica has no outcome and its candidate publishes no rows")
    total = None
    for value in outcomes:
        term = (probability - float(value)) ** 2
        total = term if total is None else total + term
    return total / float(len(outcomes))


def brier_candidate(
    probabilities: torch.Tensor, *, k: int, R: int,            # noqa: N803
) -> torch.Tensor:
    """Mean over the N robot rows of one candidate."""
    if probabilities.numel() == 0:
        raise V3MetricContractError("a candidate must carry at least one robot row")
    return brier_robot(probabilities, k=k, R=R).mean()


def brier_event(
    *, compact_probabilities: torch.Tensor, compact_k: int, compact_R: int,  # noqa: N803
    line_probabilities: torch.Tensor, line_k: int, line_R: int,              # noqa: N803
) -> torch.Tensor:
    """The two candidates at weight 0.5 each; the event carries weight 1."""
    if compact_probabilities.numel() != line_probabilities.numel():
        raise V3MetricContractError(
            "a decision event must carry the same N robot rows per candidate")
    return 0.5 * brier_candidate(compact_probabilities, k=compact_k, R=compact_R) \
        + 0.5 * brier_candidate(line_probabilities, k=line_k, R=line_R)


def brier_split(events: Sequence[Mapping[str, object]]) -> torch.Tensor:
    """Unweighted mean over decision events. Never a row mean."""
    if not events:
        raise V3MetricContractError("a split Brier requires at least one event")
    terms = [
        brier_event(
            compact_probabilities=event["compact_probabilities"],
            compact_k=int(event["compact_k"]), compact_R=int(event["compact_R"]),
            line_probabilities=event["line_probabilities"],
            line_k=int(event["line_k"]), line_R=int(event["line_R"]))
        for event in events
    ]
    return torch.stack(terms).mean()
