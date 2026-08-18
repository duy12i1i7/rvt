"""FROZEN_EVENT_EQUAL_WEIGHT_V3 -- the grouped Bernoulli recoverability loss.

``L_candidate = -[k log p + (R - k) log(1 - p)] / R``

The division by R is mandatory and is the whole point: without it an R = 3
candidate would contribute three times the gradient of an R = 1 candidate, and
since F8 and F9 are the only multi-replica families that would silently
up-weight exactly the two stochastic families.

Implemented as ``BCEWithLogits(z, k/R)``, which is algebraically the same
expression and is evaluated by torch in a log-sum-exp-stable way, so no
clamping of ``p`` away from 0 and 1 is needed. At R = 1 the soft target is
exactly 0 or 1 and the term reduces to the ordinary BCE of the frozen loss
contract, which is what keeps deterministic-family semantics unchanged.

Aggregation order (frozen): robot rows -> mean over the N robots -> mean over
the two candidates -> the complete decision event carries weight 1.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

import torch
import torch.nn.functional as F

RECOVERABILITY_TRAINING_LOSS_V3_SHA256 = (
    "fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11")
FROZEN_EVENT_EQUAL_WEIGHT_V3 = "FROZEN_EVENT_EQUAL_WEIGHT_V3"

#: Frozen: no class weighting, no focal term, no oversampling, no
#: stochastic-family reweighting.
CLASS_WEIGHTING = "NONE"
POSITIVE_CLASS_WEIGHT = "NONE"
STOCHASTIC_FAMILY_REWEIGHTING = "NONE"


class V3LossContractError(ValueError):
    """A loss-contract violation that must fail closed."""


def _soft_target(k: int, R: int) -> float:                     # noqa: N803
    if not isinstance(R, int) or isinstance(R, bool) or R < 1:
        raise V3LossContractError("R must be a positive integer")
    if not isinstance(k, int) or isinstance(k, bool) or not 0 <= k <= R:
        raise V3LossContractError("the observation requires integer 0 <= k <= R")
    return float(k) / float(R)


def grouped_bernoulli_nll(
    logits: torch.Tensor, *, k: int, R: int,                   # noqa: N803
    replica_mask: Optional[Sequence[bool]] = None,
) -> torch.Tensor:
    """Per-row normalized grouped Bernoulli NLL for one candidate observation.

    ``replica_mask`` exists only to be refused: the frozen contract forbids
    masking individual replicas inside a published ``(k, R)``, and an interface
    that silently accepted one would make that impossible to enforce.
    """
    if replica_mask is not None:
        raise V3LossContractError(
            "per-replica masking inside a published (k, R) is forbidden; a "
            "candidate with an invalid required replica publishes no rows")
    if logits.ndim != 1:
        raise V3LossContractError("recoverability logits must be one-dimensional")
    target = torch.full_like(logits, _soft_target(k, R))
    return F.binary_cross_entropy_with_logits(logits, target, reduction="none")


def candidate_loss(
    logits: torch.Tensor, *, k: int, R: int,                   # noqa: N803
) -> torch.Tensor:
    """Step 1 and 2: per-row term, then the mean over the N robot rows."""
    if logits.numel() == 0:
        raise V3LossContractError("a candidate must carry at least one robot row")
    return grouped_bernoulli_nll(logits, k=k, R=R).mean()


def event_loss(
    *, compact_logits: torch.Tensor, compact_k: int, compact_R: int,   # noqa: N803
    line_logits: torch.Tensor, line_k: int, line_R: int,               # noqa: N803
) -> torch.Tensor:
    """Step 3 and 4: the two candidates at weight 0.5, the event at weight 1."""
    if compact_logits.numel() != line_logits.numel():
        raise V3LossContractError(
            "a decision event must carry the same N robot rows per candidate")
    compact_term = candidate_loss(compact_logits, k=compact_k, R=compact_R)
    line_term = candidate_loss(line_logits, k=line_k, R=line_R)
    return 0.5 * compact_term + 0.5 * line_term


def dataset_loss(events: Sequence[Mapping[str, object]]) -> torch.Tensor:
    """Step 5: the unweighted mean over decision events.

    Every complete event contributes exactly 1, whatever its team size or
    replica count.
    """
    if not events:
        raise V3LossContractError("a V3 loss requires at least one decision event")
    terms = [
        event_loss(
            compact_logits=event["compact_logits"],
            compact_k=int(event["compact_k"]), compact_R=int(event["compact_R"]),
            line_logits=event["line_logits"],
            line_k=int(event["line_k"]), line_R=int(event["line_R"]))
        for event in events
    ]
    return torch.stack(terms).mean()


def reference_candidate_loss(p: float, *, k: int, R: int) -> float:  # noqa: N803
    """The frozen formula written out, for cross-checking the stable path.

    Not used in training: it exists so a test can compare the stable
    implementation against ``-[k log p + (R-k) log(1-p)] / R`` directly.
    """
    import math
    if not 0.0 < p < 1.0:
        raise V3LossContractError("the reference form requires p in (0, 1)")
    target = _soft_target(k, R)
    del target
    return -(k * math.log(p) + (R - k) * math.log1p(-p)) / R
