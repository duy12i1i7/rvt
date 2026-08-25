"""The clean-room family statistic.

The frozen definition, for a learned family f over the three clean-room training
seeds {11, 29, 47} evaluated on SELECT-R:

    FamilyNLL(f) = ( NLL(f,11) + NLL(f,29) + NLL(f,47) ) / 3

It is a mean of per-seed event-equal NLLs. It is NOT the best seed, the median
seed, seed 47 alone, an ensemble of probabilities, an average of logits, or a
checkpoint average. Inside every bootstrap replicate the order is fixed and is
not open to interpretation by any caller:

    resample source episodes ONCE (paired across every seed and family)
        -> compute the event-equal NLL for each seed on that resample
        -> average the three per-seed NLLs
        -> that replicate's family statistic

Because the resample is shared, seed averaging inside a replicate is an
elementwise mean of the per-seed replicate vectors. That identity is what lets
this module reuse the qualified bootstrap engine rather than restating its draw
order, and it is asserted by the qualification suite.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from rvt_swarm.openloop_v3.bootstrap import (
    BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED, ClusterDesign,
    stratified_episode_bootstrap,
)

CLEAN_ROOM_SEEDS: tuple[int, ...] = (11, 29, 47)


class FamilyStatisticContractError(ValueError):
    """A family-statistic violation that must fail closed."""


def _key(family: str, seed: int) -> str:
    return f"{family}|seed{seed}"


def family_nll(per_seed_nll: Mapping[int, float]) -> float:
    """The point family statistic: the unweighted mean over exactly the three seeds."""
    _require_exact_seeds(per_seed_nll)
    return float(sum(float(per_seed_nll[s]) for s in CLEAN_ROOM_SEEDS) / len(CLEAN_ROOM_SEEDS))


def _require_exact_seeds(mapping: Mapping[int, object]) -> None:
    present = tuple(sorted(int(s) for s in mapping))
    if present != tuple(sorted(CLEAN_ROOM_SEEDS)):
        raise FamilyStatisticContractError(
            f"the family statistic requires exactly seeds {list(CLEAN_ROOM_SEEDS)}; got {list(present)}")


def family_statistic_replicates(
    per_seed_per_event_nll: Mapping[str, Mapping[int, Sequence[float]]],
    constant_per_event_nll: Mapping[str, Sequence[float]],
    design: ClusterDesign,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> Mapping[str, np.ndarray]:
    """Return, per family, the replicate distribution of the family statistic.

    ``per_seed_per_event_nll`` maps a learned family name to {seed: per-event NLL}.
    ``constant_per_event_nll`` maps a seedless family name (M0) to its per-event
    NLL. Every family and seed is bootstrapped in ONE paired call, so all of them
    share each replicate's resample indices.
    """
    if not per_seed_per_event_nll:
        raise FamilyStatisticContractError("no learned family was supplied")
    columns: dict[str, Sequence[float]] = {}
    lengths = set()
    for family, by_seed in per_seed_per_event_nll.items():
        _require_exact_seeds(by_seed)
        for s in CLEAN_ROOM_SEEDS:
            values = by_seed[s]
            lengths.add(len(values))
            columns[_key(family, s)] = values
    for family, values in constant_per_event_nll.items():
        lengths.add(len(values))
        columns[family] = values
    if len(lengths) != 1:
        raise FamilyStatisticContractError(
            f"every family and seed must score the same events; got lengths {sorted(lengths)}")

    drawn = stratified_episode_bootstrap(columns, design, replicates=replicates, seed=seed)

    out: dict[str, np.ndarray] = {}
    for family, by_seed in per_seed_per_event_nll.items():
        stack = np.stack([drawn[_key(family, s)] for s in CLEAN_ROOM_SEEDS], axis=0)
        if stack.shape[0] != len(CLEAN_ROOM_SEEDS):
            raise FamilyStatisticContractError("seed stack lost a seed")
        out[family] = stack.mean(axis=0)
    for family in constant_per_event_nll:
        out[family] = drawn[family]
    return out
