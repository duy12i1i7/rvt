"""Strictly separated train / validation / final-test splits and seed roles.

Two independent guarantees are enforced here.

**Split separation.** Each split owns a disjoint seed namespace, so an episode
seed uniquely identifies which split it came from. Validation additionally uses
team sizes that the final test sweep never contains, so a validation episode can
never coincide with a test episode even by accident.

**Seed-role separation.** Model initialisation, training-data generation,
validation episodes, final-test episodes, counterfactual rollouts and environment
noise each draw from their own seed. Changing one must not perturb the others;
`tests/test_seed_independence.py` proves this with episode signatures.

Known limitation, stated plainly: the three splits draw from the *same four
scenario generators*. Only the layout instances (and, for validation, the team
sizes) differ. Unseen scenario *families* are a separate generalization axis and
are deliberately not addressed here — see PART 8 / E4 of the audit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


TRAIN = "train"
VALIDATION = "validation"
TEST = "test"
SPLITS: Tuple[str, ...] = (TRAIN, VALIDATION, TEST)

# Each split owns [BASE, BASE + SPAN). Namespaces cannot overlap.
SPLIT_SEED_BASE: Dict[str, int] = {
    TRAIN: 10_000_000,
    VALIDATION: 20_000_000,
    TEST: 30_000_000,
}
SPLIT_SEED_SPAN = 10_000_000

# Final test sweep: the team sizes the paper reports.
TEST_TEAM_SIZES: Tuple[int, ...] = (2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24)
# Validation uses odd team sizes, which the test sweep never contains. This makes
# validation and test episodes disjoint in team size as well as in seed.
VALIDATION_TEAM_SIZES: Tuple[int, ...] = (5, 11, 21)
# Training samples the same size distribution as the test sweep. That is
# in-distribution by design and is not leakage: no test episode, seed, or metric
# is consulted during training or checkpoint selection.
TRAIN_TEAM_SIZES: Tuple[int, ...] = TEST_TEAM_SIZES

ALL_SCENARIOS: Tuple[str, ...] = (
    "open_field",
    "cluttered",
    "narrow_passage",
    "dynamic_obstacles",
)


class TestSetLeakageError(RuntimeError):
    """Raised when final-test episodes reach a model-selection code path."""

    # Stops pytest trying to collect this as a test class because of its name.
    __test__ = False


@dataclass(frozen=True)
class SplitSpec:
    name: str
    scenarios: Tuple[str, ...]
    team_sizes: Tuple[int, ...]

    @property
    def seed_base(self) -> int:
        return SPLIT_SEED_BASE[self.name]


TRAIN_SPLIT = SplitSpec(TRAIN, ALL_SCENARIOS, TRAIN_TEAM_SIZES)
VALIDATION_SPLIT = SplitSpec(VALIDATION, ALL_SCENARIOS, VALIDATION_TEAM_SIZES)
TEST_SPLIT = SplitSpec(TEST, ALL_SCENARIOS, TEST_TEAM_SIZES)

SPLIT_SPECS: Dict[str, SplitSpec] = {
    TRAIN: TRAIN_SPLIT,
    VALIDATION: VALIDATION_SPLIT,
    TEST: TEST_SPLIT,
}


# ---------------------------------------------------------------------------
# Seed construction
# ---------------------------------------------------------------------------
def episode_seed(
    split: str,
    scenario_idx: int,
    n_agents: int,
    episode_idx: int,
    split_seed: int = 0,
) -> int:
    """Deterministic episode seed inside `split`'s namespace.

    `split_seed` re-draws the whole episode set for that split (e.g. a different
    `final_test_seed` yields a different, still method-independent, test set).
    """
    if split not in SPLIT_SEED_BASE:
        raise ValueError(f"unknown split {split!r}")
    offset = (
        (int(split_seed) % 100) * 100_000
        + 10_000 * int(scenario_idx)
        + 100 * int(n_agents)
        + int(episode_idx)
    )
    if not 0 <= offset < SPLIT_SEED_SPAN:
        raise ValueError(f"episode offset {offset} escapes the {split!r} namespace")
    return SPLIT_SEED_BASE[split] + offset


def setting_episode_seeds(
    split: str,
    scenario_idx: int,
    n_agents: int,
    n_episodes: int,
    split_seed: int = 0,
) -> List[int]:
    return [
        episode_seed(split, scenario_idx, n_agents, idx, split_seed=split_seed)
        for idx in range(n_episodes)
    ]


def seed_split(seed: int) -> Optional[str]:
    """Which split a seed belongs to, or None if it is outside every namespace."""
    for name, base in SPLIT_SEED_BASE.items():
        if base <= int(seed) < base + SPLIT_SEED_SPAN:
            return name
    return None


def is_test_seed(seed: int) -> bool:
    return seed_split(seed) == TEST


# ---------------------------------------------------------------------------
# Leakage guards
# ---------------------------------------------------------------------------
def assert_no_test_seeds(seeds: Iterable[int], context: str) -> None:
    """Raise if any final-test episode seed reaches a model-selection path."""
    offenders = [int(s) for s in seeds if is_test_seed(s)]
    if offenders:
        raise TestSetLeakageError(
            f"{context}: {len(offenders)} final-test episode seed(s) reached a "
            f"model-selection code path (first: {offenders[0]}). The final test "
            f"split must never influence early stopping, checkpoint ranking, "
            f"top-k re-evaluation, hyperparameter choice, or architecture choice."
        )


def assert_no_test_team_sizes(team_sizes: Iterable[int], context: str) -> None:
    """Raise if a model-selection path is configured with final-test team sizes."""
    offenders = sorted({int(n) for n in team_sizes} & set(TEST_TEAM_SIZES))
    if offenders:
        raise TestSetLeakageError(
            f"{context}: team sizes {offenders} belong to the final test sweep "
            f"{list(TEST_TEAM_SIZES)}. Validation must use "
            f"{list(VALIDATION_TEAM_SIZES)}."
        )


def assert_validation_config(scenarios: Sequence[str], team_sizes: Sequence[int], context: str) -> None:
    """Full guard for a checkpoint-selection configuration."""
    assert_no_test_team_sizes(team_sizes, context)
    unknown = [s for s in scenarios if s not in ALL_SCENARIOS]
    if unknown:
        raise ValueError(f"{context}: unknown scenario(s) {unknown}")


# ---------------------------------------------------------------------------
# Episode signatures (used to prove that episode sets match across methods/seeds)
# ---------------------------------------------------------------------------
def episode_signature(obs: Dict) -> str:
    """Stable hash of everything that defines an episode's initial conditions.

    Covers initial states, goal, obstacles and obstacle motion. Two runs with the
    same signature received the same episode.
    """
    hasher = hashlib.sha256()
    for key in ("positions", "velocities", "goal", "obstacles", "obstacle_velocities"):
        value = obs.get(key)
        if value is None:
            hasher.update(b"<none>")
            continue
        arr = np.ascontiguousarray(np.asarray(value, dtype=np.float64).round(9))
        hasher.update(key.encode())
        hasher.update(str(arr.shape).encode())
        hasher.update(arr.tobytes())
    return hasher.hexdigest()[:32]


def split_episode_signatures(
    cfg,
    split: str,
    episodes_per_setting: int = 2,
    split_seed: int = 0,
) -> Dict[str, str]:
    """Signature of every episode in a split, keyed by `scenario/N/index`.

    Imported lazily to keep this module free of an environment dependency at
    import time.
    """
    from .environment import SwarmFormationEnv

    spec = SPLIT_SPECS[split]
    signatures: Dict[str, str] = {}
    for scenario_idx, scenario in enumerate(spec.scenarios):
        for n_agents in spec.team_sizes:
            for episode_idx in range(episodes_per_setting):
                seed = episode_seed(
                    split, scenario_idx, n_agents, episode_idx, split_seed=split_seed
                )
                obs = SwarmFormationEnv(cfg).reset(n_agents, scenario, seed=seed)
                signatures[f"{scenario}/{n_agents}/{episode_idx}"] = episode_signature(obs)
    return signatures
