"""Task 4 — train / validation / test layouts must never share geometry."""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.environment import SwarmFormationEnv
from rvt_swarm.layouts import (
    FAMILIES,
    SPLITS,
    Layout,
    all_layouts,
    build_layouts,
    get_layout,
    mode_feasibility_hypothesis,
)


def test_every_split_has_every_family() -> None:
    for split in SPLITS:
        fams = {lay.family for lay in build_layouts(split)}
        assert fams == set(FAMILIES), f"{split} is missing {set(FAMILIES) - fams}"


def test_geometry_hashes_are_unique_within_each_split() -> None:
    for split in SPLITS:
        hashes = [lay.geometry_hash() for lay in build_layouts(split)]
        dupes = [h for h, c in Counter(hashes).items() if c > 1]
        assert not dupes, f"{split} has duplicate geometry: {dupes}"


def test_no_geometry_hash_is_shared_across_splits() -> None:
    """The load-bearing test: identical geometry in two splits is leakage."""
    owner: dict[str, list[str]] = defaultdict(list)
    for split, lays in all_layouts().items():
        for lay in lays:
            owner[lay.geometry_hash()].append(lay.layout_id)
    shared = {h: ids for h, ids in owner.items()
              if len({i.split("_")[0] for i in ids}) > 1}
    assert not shared, f"geometry shared across splits: {shared}"


def test_no_shared_fixed_obstacle_coordinates_across_splits() -> None:
    """Stronger than hashing: no split may reuse another's exact obstacle set."""
    sets = {}
    for split, lays in all_layouts().items():
        sets[split] = {tuple(sorted(lay.obstacles)) for lay in lays}
    for a in SPLITS:
        for b in SPLITS:
            if a >= b:
                continue
            overlap = sets[a] & sets[b]
            assert not overlap, f"{a} and {b} share {len(overlap)} obstacle configuration(s)"


def test_layouts_differ_by_geometry_not_only_by_start_randomisation() -> None:
    """A split must not be another split's maps with a different random start."""
    for a in SPLITS:
        for b in SPLITS:
            if a >= b:
                continue
            for la in build_layouts(a):
                for lb in build_layouts(b):
                    if la.family != lb.family:
                        continue
                    same_obs = np.allclose(
                        np.sort(la.obstacle_array, axis=0),
                        np.sort(lb.obstacle_array, axis=0),
                    ) if la.obstacle_array.shape == lb.obstacle_array.shape else False
                    assert not same_obs, (
                        f"{la.layout_id} and {lb.layout_id} have identical obstacle geometry"
                    )


def test_layout_ids_encode_split_and_family() -> None:
    for split in SPLITS:
        for lay in build_layouts(split):
            assert lay.layout_id.startswith(f"{split}_{lay.family}_")
            assert get_layout(lay.layout_id).geometry_hash() == lay.geometry_hash()


def test_geometry_hash_is_sensitive_to_geometry() -> None:
    """Guard: a hash blind to coordinates would make the tests above vacuous."""
    lay = build_layouts("val")[0]
    moved = Layout(lay.layout_id, lay.family, lay.split,
                   tuple([(x + 0.01, y) for x, y in lay.obstacles]),
                   lay.goal, lay.start_center, lay.params)
    assert moved.geometry_hash() != lay.geometry_hash()

    goal_moved = Layout(lay.layout_id, lay.family, lay.split, lay.obstacles,
                        (lay.goal[0] + 0.01, lay.goal[1]), lay.start_center, lay.params)
    assert goal_moved.geometry_hash() != lay.geometry_hash()


def test_geometry_hash_is_order_invariant() -> None:
    """Reordering the same obstacles is the same geometry, and must hash the same."""
    lay = build_layouts("val")[1]
    shuffled = Layout(lay.layout_id, lay.family, lay.split,
                      tuple(reversed(lay.obstacles)), lay.goal, lay.start_center, lay.params)
    assert shuffled.geometry_hash() == lay.geometry_hash()


@pytest.mark.parametrize("split", SPLITS)
def test_layouts_are_loadable_and_produce_valid_initial_states(split: str) -> None:
    cfg = Config()
    for lay in build_layouts(split):
        obs = SwarmFormationEnv(cfg).reset(6, "cluttered", seed=1234, layout=lay)
        pos = obs["positions"]
        assert np.isfinite(pos).all()
        assert np.abs(pos).max() <= cfg.env.world_size * 0.5
        d = np.linalg.norm(pos[:, None] - pos[None, :], axis=-1)
        np.fill_diagonal(d, np.inf)
        assert d.min() >= cfg.env.min_rr_distance, f"{lay.layout_id} spawns in collision"
        ro = np.linalg.norm(pos[:, None] - obs["obstacles"][None, :], axis=-1)
        assert ro.min() >= cfg.env.min_ro_distance, f"{lay.layout_id} spawns inside an obstacle"


def test_feasibility_hypotheses_are_not_all_identical() -> None:
    """The families must at least *intend* different admissible modes."""
    hyps = {lay.family: tuple(sorted(mode_feasibility_hypothesis(lay).items()))
            for lay in build_layouts("val")}
    assert len(set(hyps.values())) > 1, "every family hypothesises the same admissible modes"
    assert hyps["line_corridor"] != hyps["split_around"]
