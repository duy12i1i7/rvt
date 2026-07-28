"""Task 2 — the final test split must never reach a model-selection code path.

Model-selection paths, traced in docs/DATA_SPLIT_AND_CHECKPOINT_PROTOCOL.md:

    train.py: should_run_rollout_validation -> rollout_validation_summary
              rollout_validation_score / rollout_validation_key  (early stopping,
              checkpoint ranking)
              maybe_record_rollout_candidate                     (top-k pool)
              recheck_rollout_candidates                         (top-k re-eval)

All of them consume `evaluate.rollout_validation_summary`, which is the single
chokepoint guarded here.
"""

from __future__ import annotations

import pytest

from rvt_swarm.config import Config
from rvt_swarm.evaluate import _setting_episode_seeds, rollout_validation_summary
from rvt_swarm.splits import (
    TEST,
    TEST_TEAM_SIZES,
    TRAIN,
    VALIDATION,
    VALIDATION_TEAM_SIZES,
    TestSetLeakageError,
    assert_no_test_seeds,
    assert_no_test_team_sizes,
    episode_seed,
    is_test_seed,
    seed_split,
    setting_episode_seeds,
)


# --------------------------------------------------------------------------
# Namespace disjointness
# --------------------------------------------------------------------------
def test_split_seed_namespaces_are_disjoint() -> None:
    seen = {}
    for split in (TRAIN, VALIDATION, TEST):
        for scenario_idx in range(4):
            for n_agents in (2, 5, 11, 16, 21, 24):
                for episode_idx in range(5):
                    for split_seed in (0, 1, 7):
                        s = episode_seed(
                            split, scenario_idx, n_agents, episode_idx, split_seed=split_seed
                        )
                        assert seed_split(s) == split
                        assert s not in seen or seen[s] == split, (
                            f"seed {s} is claimed by both {seen.get(s)} and {split}"
                        )
                        seen[s] = split


def test_validation_and_test_team_sizes_are_disjoint() -> None:
    assert not (set(VALIDATION_TEAM_SIZES) & set(TEST_TEAM_SIZES)), (
        "a validation episode could coincide with a test episode"
    )


def test_is_test_seed_identifies_the_test_namespace() -> None:
    assert is_test_seed(episode_seed(TEST, 0, 8, 0))
    assert not is_test_seed(episode_seed(VALIDATION, 0, 5, 0))
    assert not is_test_seed(episode_seed(TRAIN, 0, 8, 0))
    assert seed_split(42) is None, "legacy un-namespaced seeds belong to no split"


# --------------------------------------------------------------------------
# Guards reject leakage
# --------------------------------------------------------------------------
def test_assert_no_test_seeds_rejects_a_test_seed() -> None:
    seeds = setting_episode_seeds(TEST, 0, 8, 3)
    with pytest.raises(TestSetLeakageError, match="model-selection"):
        assert_no_test_seeds(seeds, context="unit test")


def test_assert_no_test_seeds_accepts_validation_seeds() -> None:
    assert_no_test_seeds(setting_episode_seeds(VALIDATION, 0, 5, 3), context="unit test")


def test_assert_no_test_team_sizes_rejects_the_test_sweep() -> None:
    with pytest.raises(TestSetLeakageError, match="final test sweep"):
        assert_no_test_team_sizes([8, 16, 24], context="unit test")


def test_assert_no_test_team_sizes_accepts_validation_sizes() -> None:
    assert_no_test_team_sizes(VALIDATION_TEAM_SIZES, context="unit test")


# --------------------------------------------------------------------------
# The real checkpoint-selection path
# --------------------------------------------------------------------------
def test_checkpoint_selection_rejects_test_team_sizes() -> None:
    """Configuring validation with the test sweep must fail loudly, not silently."""
    cfg = Config()
    cfg.train.rollout_val_team_sizes = [8, 16, 24]  # the pre-fix configuration
    with pytest.raises(TestSetLeakageError):
        rollout_validation_summary("adaptive_formation", cfg, model=None)


def test_checkpoint_selection_draws_only_validation_seeds() -> None:
    cfg = Config()
    for scenario_idx in range(len(cfg.train.rollout_val_scenarios)):
        for n_agents in cfg.train.rollout_val_team_sizes:
            seeds = _setting_episode_seeds(cfg, scenario_idx, n_agents, 4, split=VALIDATION)
            assert all(seed_split(s) == VALIDATION for s in seeds)
            assert_no_test_seeds(seeds, context="checkpoint selection")


def test_default_validation_configuration_is_leakage_free() -> None:
    """The shipped default must pass the guard it is protected by."""
    cfg = Config()
    assert set(cfg.train.rollout_val_team_sizes) == set(VALIDATION_TEAM_SIZES)
    assert not (set(cfg.train.rollout_val_team_sizes) & set(TEST_TEAM_SIZES))


def test_evaluation_defaults_to_the_test_split_and_selection_to_validation() -> None:
    cfg = Config()
    test_seeds = _setting_episode_seeds(cfg, 0, 8, 3, split=TEST)
    val_seeds = _setting_episode_seeds(cfg, 0, 5, 3, split=VALIDATION)
    assert all(seed_split(s) == TEST for s in test_seeds)
    assert all(seed_split(s) == VALIDATION for s in val_seeds)
    assert not set(test_seeds) & set(val_seeds)
