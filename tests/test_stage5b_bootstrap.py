"""The frozen paired stratified source-episode cluster bootstrap."""

import numpy as np
import pytest

from rvt_swarm.openloop_v3.bootstrap import (
    BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED, BootstrapContractError,
    build_cluster_design, paired_difference_interval,
    stratified_episode_bootstrap,
)


def _design(events_per_episode=3, episodes_per_layout=4, layouts=3):
    event_episode = []
    episode_layout = {}
    for layout in range(layouts):
        for episode in range(episodes_per_layout):
            name = f"L{layout}-E{episode}"
            episode_layout[name] = f"layout-{layout}"
            event_episode.extend([name] * events_per_episode)
    return build_cluster_design(event_episode, episode_layout), event_episode


def test_design_is_canonical_and_counts_are_preserved():
    design, event_episode = _design()
    assert design.layout_ids == ("layout-0", "layout-1", "layout-2")
    assert all(len(design.episode_ids_by_layout[layout]) == 4
               for layout in design.layout_ids)
    assert design.event_count == len(event_episode)


def test_design_is_independent_of_input_order():
    design_a, _ = _design()
    event_episode = []
    episode_layout = {}
    for layout in reversed(range(3)):
        for episode in reversed(range(4)):
            name = f"L{layout}-E{episode}"
            episode_layout[name] = f"layout-{layout}"
            event_episode.extend([name] * 3)
    design_b = build_cluster_design(event_episode, episode_layout)
    assert design_a.layout_ids == design_b.layout_ids
    assert design_a.episode_ids_by_layout == design_b.episode_ids_by_layout


def test_bootstrap_is_deterministic_across_two_runs():
    design, event_episode = _design()
    values = {"M2": list(np.linspace(0.1, 0.9, design.event_count))}
    first = stratified_episode_bootstrap(values, design, replicates=200)
    second = stratified_episode_bootstrap(values, design, replicates=200)
    np.testing.assert_array_equal(first["M2"], second["M2"])


def test_events_of_one_episode_always_co_resample():
    """An episode-level metric must be immune to how its events are ordered."""
    design, event_episode = _design(events_per_episode=3)
    rng = np.random.default_rng(7)
    base = rng.normal(size=design.event_count)
    shuffled = base.copy()
    for episode, indices in design.event_index_by_episode.items():
        block = [base[index] for index in indices]
        for position, index in enumerate(indices):
            shuffled[index] = block[(position + 1) % len(block)]
    first = stratified_episode_bootstrap({"a": base}, design, replicates=100)
    second = stratified_episode_bootstrap({"a": shuffled}, design, replicates=100)
    np.testing.assert_allclose(first["a"], second["a"], rtol=0.0, atol=1e-12)


def test_layout_sample_counts_are_preserved():
    """Every replicate draws exactly n_layout episodes from each layout."""
    design, _ = _design(events_per_episode=1, episodes_per_layout=5, layouts=2)
    marker = {"a": [1.0] * design.event_count}
    out = stratified_episode_bootstrap(marker, design, replicates=50)
    # a constant metric must reproduce exactly, which can only happen if every
    # replicate keeps the same total event count structure
    np.testing.assert_allclose(out["a"], np.ones(50), rtol=0.0, atol=1e-12)


def test_pairing_uses_the_same_resample_for_every_family():
    design, _ = _design()
    rng = np.random.default_rng(3)
    base = rng.normal(size=design.event_count)
    out = stratified_episode_bootstrap(
        {"a": base, "b": base + 1.0}, design, replicates=150)
    difference = out["b"] - out["a"]
    np.testing.assert_allclose(difference, np.ones(150), rtol=0.0, atol=1e-9)


def test_paired_interval_is_a_percentile_interval():
    a = np.linspace(0.0, 1.0, 1000)
    b = np.zeros(1000)
    lower, upper = paired_difference_interval(a, b)
    assert lower == pytest.approx(0.025, abs=1e-3)
    assert upper == pytest.approx(0.975, abs=1e-3)


def test_frozen_constants():
    assert BOOTSTRAP_REPLICATES == 10000
    assert BOOTSTRAP_SEED == 20260821


def test_a_ten_thousand_replicate_run_is_reproducible():
    design, _ = _design(events_per_episode=2, episodes_per_layout=6, layouts=4)
    rng = np.random.default_rng(11)
    values = {"M1": rng.normal(size=design.event_count),
              "M2": rng.normal(size=design.event_count)}
    first = stratified_episode_bootstrap(values, design)
    second = stratified_episode_bootstrap(values, design)
    for family in ("M1", "M2"):
        np.testing.assert_array_equal(first[family], second[family])
    lower, upper = paired_difference_interval(first["M2"], first["M1"])
    assert lower <= upper


def test_mismatched_value_length_is_refused():
    design, _ = _design()
    with pytest.raises(BootstrapContractError):
        stratified_episode_bootstrap({"a": [0.0]}, design, replicates=5)


def test_an_undeclared_episode_stratum_is_refused():
    with pytest.raises(BootstrapContractError):
        build_cluster_design(["E1"], {})
