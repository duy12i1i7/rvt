"""Qualification suite for the clean-room scientific engine.

Every negative fixture here corresponds to a way the pilot programme did fail, or
could have failed silently. Each must fail closed.
"""
from __future__ import annotations

import numpy as np
import pytest
import torch

from rvt_swarm.cleanroom.calibration_contract import (
    TEMPERATURE_SCALING_ACTIVATED, clean_room_calibration,
)
from rvt_swarm.cleanroom.family_statistic import (
    CLEAN_ROOM_SEEDS, FamilyStatisticContractError, family_nll,
    family_statistic_replicates,
)
from rvt_swarm.cleanroom.selection import (
    CLEAN_ROOM_BOOTSTRAP_REPLICATES, CLEAN_ROOM_BOOTSTRAP_SEED,
    DOWNSTREAM_REPRESENTATIVE_SEED, DeltaInterval, SelectionContractError,
    downstream_checkpoint, percentile_interval, select_family,
)
from rvt_swarm.cleanroom.universe import (
    UniverseContractError, assert_episode_universe, zero_yield_episodes,
)
from rvt_swarm.openloop_v3.bootstrap import build_cluster_design
from rvt_swarm.openloop_v3.calibration import CalibrationContractError


# --------------------------------------------------------------- universe ---

def _universe(n_declared=6, n_contributing=6):
    ids = [f"e{i}" for i in range(n_declared)]
    layout = {e: ("L0" if i < n_declared // 2 else "L1") for i, e in enumerate(ids)}
    events = [e for e in ids[:n_contributing] for _ in range(2)]
    return ids, layout, events


def test_universe_accepts_zero_yield_episodes():
    ids, layout, events = _universe(6, 4)
    universe = assert_episode_universe(ids, layout, events, expected_count=6)
    assert len(universe) == 6
    assert zero_yield_episodes(universe, events) == ("e4", "e5")


def test_universe_rejects_a_missing_declared_episode():
    ids, layout, events = _universe(6, 6)
    with pytest.raises(UniverseContractError):
        assert_episode_universe(ids[:-1], layout, events, expected_count=6)


def test_universe_rejects_an_extra_undeclared_episode():
    ids, layout, events = _universe(6, 6)
    with pytest.raises(UniverseContractError):
        assert_episode_universe(ids, layout, events + ["ghost"], expected_count=6)


def test_universe_rejects_a_duplicate_episode():
    ids, layout, events = _universe(6, 6)
    with pytest.raises(UniverseContractError):
        assert_episode_universe(ids + ["e0"], layout, events, expected_count=7)


def test_universe_rejects_a_count_mismatch():
    ids, layout, events = _universe(6, 6)
    with pytest.raises(UniverseContractError):
        assert_episode_universe(ids, layout, events, expected_count=300)


def test_universe_rejects_missing_layout_membership():
    ids, layout, events = _universe(6, 6)
    del layout["e0"]
    with pytest.raises(UniverseContractError):
        assert_episode_universe(ids, layout, events, expected_count=6)


# -------------------------------------------------------- family statistic ---

def _design(n_episodes=8, events_per=3):
    ids = [f"e{i}" for i in range(n_episodes)]
    layout = {e: ("L0" if i < n_episodes // 2 else "L1") for i, e in enumerate(ids)}
    event_episode = [e for e in ids for _ in range(events_per)]
    return build_cluster_design(event_episode, layout), len(event_episode)


def test_family_nll_is_the_unweighted_three_seed_mean():
    assert family_nll({11: 0.30, 29: 0.60, 47: 0.90}) == pytest.approx(0.60)


@pytest.mark.parametrize("bad", [
    {47: 0.5},                              # seed47 only
    {11: 0.4, 29: 0.5},                     # a missing seed
    {11: 0.4, 29: 0.5, 47: 0.6, 3: 0.7},    # an extra seed
    {1: 0.4, 2: 0.5, 3: 0.6},               # wrong seeds entirely
])
def test_family_nll_rejects_any_seed_set_other_than_the_frozen_three(bad):
    with pytest.raises(FamilyStatisticContractError):
        family_nll(bad)


def test_family_statistic_averages_seeds_inside_each_replicate():
    """The frozen order: resample once, score each seed, then average the three."""
    design, n = _design()
    rng = np.random.default_rng(5)
    per_seed = {s: list(rng.uniform(0.1, 0.9, size=n)) for s in CLEAN_ROOM_SEEDS}
    m0 = list(rng.uniform(0.1, 0.9, size=n))
    out = family_statistic_replicates(
        {"M1": per_seed}, {"M0": m0}, design,
        replicates=64, seed=CLEAN_ROOM_BOOTSTRAP_SEED)
    # Averaging the per-event NLLs first and bootstrapping once must give the
    # same replicate vector, because the resample is shared across seeds.
    pooled = [sum(per_seed[s][i] for s in CLEAN_ROOM_SEEDS) / 3.0 for i in range(n)]
    reference = family_statistic_replicates(
        {"M1": {s: pooled for s in CLEAN_ROOM_SEEDS}}, {"M0": m0}, design,
        replicates=64, seed=CLEAN_ROOM_BOOTSTRAP_SEED)
    assert np.allclose(out["M1"], reference["M1"])
    assert out["M1"].shape == (64,)


def test_family_statistic_is_not_the_best_seed():
    design, n = _design()
    per_seed = {11: [0.9] * n, 29: [0.9] * n, 47: [0.3] * n}
    out = family_statistic_replicates({"M1": per_seed}, {"M0": [0.5] * n}, design,
                                      replicates=16, seed=CLEAN_ROOM_BOOTSTRAP_SEED)
    assert np.allclose(out["M1"], 0.7)          # the mean
    assert not np.allclose(out["M1"], 0.3)      # not the best seed
    assert not np.allclose(out["M1"], 0.9)      # not the median seed


def test_family_statistic_rejects_a_missing_seed():
    design, n = _design()
    with pytest.raises(FamilyStatisticContractError):
        family_statistic_replicates({"M1": {11: [0.5] * n, 29: [0.5] * n}},
                                    {"M0": [0.5] * n}, design, replicates=8)


def test_family_statistic_rejects_ragged_event_counts():
    design, n = _design()
    per_seed = {11: [0.5] * n, 29: [0.5] * n, 47: [0.5] * (n - 1)}
    with pytest.raises(FamilyStatisticContractError):
        family_statistic_replicates({"M1": per_seed}, {"M0": [0.5] * n}, design, replicates=8)


def test_bootstrap_constants_are_the_frozen_clean_room_values():
    assert CLEAN_ROOM_BOOTSTRAP_REPLICATES == 10000
    assert CLEAN_ROOM_BOOTSTRAP_SEED == 20260901
    assert CLEAN_ROOM_SEEDS == (11, 29, 47)


# ---------------------------------------------------------------- selection ---

def _d(name, lower, upper, point=None):
    return DeltaInterval(name, point if point is not None else (lower + upper) / 2, lower, upper)


def test_case_1_neither_eligible_gives_m0():
    o = select_family(_d("d10", -0.1, 0.05), _d("d20", -0.1, 0.02), _d("d21", -0.1, 0.1))
    assert (o.winner, o.case, o.learnability_supported) == ("M0", 1, False)


def test_case_2_only_m1_eligible():
    o = select_family(_d("d10", -0.2, -0.05), _d("d20", -0.1, 0.02), _d("d21", -0.1, 0.1))
    assert (o.winner, o.case) == ("M1", 2)


def test_case_3_only_m2_eligible():
    o = select_family(_d("d10", -0.1, 0.02), _d("d20", -0.2, -0.05), _d("d21", -0.1, 0.1))
    assert (o.winner, o.case) == ("M2", 3)


def test_case_4_both_eligible_m2_wins_only_when_d21_excludes_zero():
    both = (_d("d10", -0.3, -0.2), _d("d20", -0.4, -0.3))
    assert select_family(*both, _d("d21", -0.09, -0.01)).winner == "M2"
    assert select_family(*both, _d("d21", -0.09, 0.0)).winner == "M1"   # zero is not < zero
    assert select_family(*both, _d("d21", -0.09, 0.01)).winner == "M1"  # parsimony


def test_eligibility_is_strict_at_exactly_zero():
    o = select_family(_d("d10", -0.2, 0.0), _d("d20", -0.2, 0.0), _d("d21", -0.1, -0.05))
    assert o.winner == "M0" and not o.m1_eligible and not o.m2_eligible


def test_selection_rejects_an_inverted_interval():
    with pytest.raises(SelectionContractError):
        select_family(_d("d10", 0.2, -0.2), _d("d20", -0.2, -0.1), _d("d21", -0.1, -0.05))


def test_downstream_representative_seed_is_fixed_and_not_data_derived():
    assert DOWNSTREAM_REPRESENTATIVE_SEED == 47
    winner = select_family(_d("d10", -0.3, -0.2), _d("d20", -0.4, -0.3), _d("d21", -0.09, -0.01))
    assert downstream_checkpoint(winner) == ("M2", 47)
    m0 = select_family(_d("d10", -0.1, 0.05), _d("d20", -0.1, 0.02), _d("d21", -0.1, 0.1))
    assert downstream_checkpoint(m0) is None


def test_percentile_interval_rejects_mismatched_replicate_counts():
    with pytest.raises(SelectionContractError):
        percentile_interval(np.zeros(10), np.zeros(9), 0.1, 0.2, "d")


# -------------------------------------------------------------- calibration ---

def _cal(logits):
    z = torch.tensor(logits, dtype=torch.float32)
    t = torch.full_like(z, 0.4)
    w = torch.full_like(z, 1.0 / len(logits))
    return z, t, w


def test_constant_predictor_is_declared_non_identifiable_without_catching():
    z, t, w = _cal([0.3] * 64)
    r = clean_room_calibration(z, t, w)
    assert r.identifiable is False and r.intercept is None and r.slope is None
    assert r.distinct_logits == 1
    assert r.expected_calibration_error >= 0.0     # the diagnostic still exists


def test_varying_predictor_is_identifiable():
    z, t, w = _cal(list(np.linspace(-2.0, 2.0, 64)))
    r = clean_room_calibration(z, t, w)
    assert r.identifiable is True
    assert r.intercept is not None and r.slope is not None and r.distinct_logits == 64


def test_a_genuine_contract_violation_hard_fails_and_is_not_relabelled():
    """The pilot's broad except would have filed this as 'not identifiable'."""
    z, _, w = _cal(list(np.linspace(-2.0, 2.0, 64)))
    bad_targets = torch.full_like(z, 5.0)          # outside [0, 1]
    with pytest.raises(CalibrationContractError):
        clean_room_calibration(z, bad_targets, w)


def test_negative_weights_hard_fail():
    z, t, w = _cal(list(np.linspace(-2.0, 2.0, 64)))
    with pytest.raises(CalibrationContractError):
        clean_room_calibration(z, t, -w)


def test_temperature_scaling_is_not_activated():
    assert TEMPERATURE_SCALING_ACTIVATED is False
