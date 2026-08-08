"""SPEC-1/SPEC-2 -- the frozen residual candidate lattice.

The owner decision for Residual Expert V2 is the minimal symmetric full-factorial
lattice over the frozen residual-action bound:

    dx in {-bx, 0, +bx}   dy in {-by, 0, +by}

`bx` and `by` are never written here. They come from
`residual_action_limits(model_config, runtime_config)`, which derives them as
`residual_limit_fractions_of_maximum_acceleration * a_max`. Changing either
authoritative field changes the lattice, deterministically and with no other
edit.

This module enumerates candidates and nothing else. It performs no evaluation,
computes no utility, runs no rollout and never calls the frozen selector: the
V2 producer is not implemented, because the utility normalizers are not yet
specified. See `docs/PHASE8R_RESIDUAL_EXPERT_SPEC_V2.md`.
"""

from __future__ import annotations

import hashlib
import json
from typing import Sequence, Tuple

from ..fd24.configuration import FD24ModelConfig, residual_action_limits
from ..runtime_configuration import RuntimeConfig

RESIDUAL_CANDIDATE_LATTICE_SCHEMA_VERSION = "rvt-residual-candidate-lattice/v2"
RESIDUAL_EXPERT_V2_ID = "B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V2"
RESIDUAL_EXPERT_V1_ID = "B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1"

# Canonical ordering, x-major then y, each ascending: -b, 0, +b. The order is
# fixed by the owner decision, so it is written as multipliers rather than
# produced by an iteration whose order could later be changed silently.
CANONICAL_MULTIPLIERS: Tuple[Tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, +1),
    (0, -1), (0, 0), (0, +1),
    (+1, -1), (+1, 0), (+1, +1),
)

CANDIDATE_COUNT = len(CANONICAL_MULTIPLIERS)


def residual_candidate_lattice(
    model_config: FD24ModelConfig,
    runtime_config: RuntimeConfig,
) -> Tuple[Tuple[float, float], ...]:
    """The nine residual candidates in canonical order, world-frame m/s^2.

    Element four (index 4) is the exact zero residual, and it occurs exactly
    once: the multiplier table contains `(0, 0)` a single time and the two
    non-zero multipliers of each axis are distinct whenever the bound is
    non-zero.
    """
    limits = residual_action_limits(model_config, runtime_config)
    if len(limits) != 2:
        raise ValueError("the residual lattice requires a two-component bound")
    bx, by = float(limits[0]), float(limits[1])
    return tuple((sx * bx, sy * by) for sx, sy in CANONICAL_MULTIPLIERS)


def zero_residual_index() -> int:
    """Index of the single zero-residual candidate in canonical order."""
    return CANONICAL_MULTIPLIERS.index((0, 0))


def canonical_lattice_hash(candidates: Sequence[Sequence[float]]) -> str:
    """Order-sensitive canonical hash of a candidate set."""
    payload = json.dumps([[float(value) for value in candidate]
                          for candidate in candidates],
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
