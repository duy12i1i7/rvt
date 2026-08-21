"""Paired stratified cluster bootstrap over VALIDATION source episodes.

Up to K = 5 selected decision events come from ONE source trajectory. Resampling
events independently would treat those as independent draws and understate the
interval, so the resampling unit is the SOURCE EPISODE and every event of a
sampled episode moves with it.

Stratification is by VALIDATION layout, resampling each layout's episodes with
replacement while preserving that layout's episode count. The interval this
produces is uncertainty over episodes CONDITIONAL on the frozen validation
layouts; it is not a statement about unseen layouts.

Pairing: one replicate draws one set of episode indices and every family is
evaluated on that same resample, so differences are paired by construction.

This module never opens a dataset. It consumes a table of per-event metric
values that some other component computed, which is what lets it be qualified
against synthetic tables with VALIDATION still sealed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np

BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20260821
CONFIDENCE_LEVEL = 0.95


class BootstrapContractError(ValueError):
    """A bootstrap-contract violation that must fail closed."""


@dataclass(frozen=True)
class ClusterDesign:
    """Episode clusters and their layout strata, in the frozen canonical order."""

    layout_ids: Tuple[str, ...]
    episode_ids_by_layout: Mapping[str, Tuple[str, ...]]
    event_index_by_episode: Mapping[str, Tuple[int, ...]]
    event_count: int


def build_cluster_design(event_episode_ids: Sequence[str],
                         episode_layout_ids: Mapping[str, str]) -> ClusterDesign:
    """Canonicalize the design so the result cannot depend on input order."""
    if len(event_episode_ids) == 0:
        raise BootstrapContractError("the bootstrap requires at least one event")
    by_episode: Dict[str, List[int]] = {}
    for index, episode in enumerate(event_episode_ids):
        by_episode.setdefault(str(episode), []).append(index)
    missing = sorted(set(by_episode) - set(episode_layout_ids))
    if missing:
        raise BootstrapContractError(
            f"{len(missing)} episode(s) have no declared layout stratum")
    by_layout: Dict[str, List[str]] = {}
    for episode in sorted(episode_layout_ids):
        by_layout.setdefault(str(episode_layout_ids[episode]), []).append(str(episode))
    return ClusterDesign(
        layout_ids=tuple(sorted(by_layout)),
        episode_ids_by_layout={layout: tuple(sorted(items))
                               for layout, items in by_layout.items()},
        event_index_by_episode={episode: tuple(indices)
                                for episode, indices in by_episode.items()},
        event_count=len(event_episode_ids))


def _episode_sums(values: np.ndarray, design: ClusterDesign,
                  ) -> Tuple[np.ndarray, np.ndarray, Tuple[str, ...]]:
    """Per-episode sum and count, so a replicate is a cheap gather-and-divide."""
    episodes = tuple(
        episode for layout in design.layout_ids
        for episode in design.episode_ids_by_layout[layout])
    sums = np.zeros(len(episodes), dtype=np.float64)
    counts = np.zeros(len(episodes), dtype=np.float64)
    for position, episode in enumerate(episodes):
        indices = design.event_index_by_episode.get(episode, ())
        if indices:
            sums[position] = values[list(indices)].sum()
            counts[position] = float(len(indices))
    return sums, counts, episodes


def stratified_episode_bootstrap(
    per_event_values: Mapping[str, Sequence[float]],
    design: ClusterDesign, *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> Mapping[str, np.ndarray]:
    """Return, per family, the replicate distribution of the event-equal mean.

    Draw order is pinned: replicates in order, layouts in ascending layout_id,
    one ``rng.integers(0, n_layout, size=n_layout)`` call per layout. That fully
    determines every draw from the seed alone.
    """
    if replicates < 1:
        raise BootstrapContractError("at least one replicate is required")
    families = tuple(sorted(per_event_values))
    if not families:
        raise BootstrapContractError("at least one family is required")
    arrays = {}
    for family in families:
        values = np.asarray(per_event_values[family], dtype=np.float64)
        if values.shape != (design.event_count,):
            raise BootstrapContractError(
                f"family {family!r} supplies {values.shape} values for "
                f"{design.event_count} events")
        if not np.isfinite(values).all():
            raise BootstrapContractError("per-event metric values must be finite")
        arrays[family] = values

    prepared = {family: _episode_sums(arrays[family], design) for family in families}
    episodes = prepared[families[0]][2]
    position_of = {episode: index for index, episode in enumerate(episodes)}
    layout_positions = [
        np.array([position_of[episode]
                  for episode in design.episode_ids_by_layout[layout]],
                 dtype=np.int64)
        for layout in design.layout_ids
    ]

    rng = np.random.default_rng(seed)
    out = {family: np.empty(replicates, dtype=np.float64) for family in families}
    for replicate in range(replicates):
        drawn = []
        for positions in layout_positions:
            size = positions.shape[0]
            drawn.append(positions[rng.integers(0, size, size=size)])
        picked = np.concatenate(drawn) if drawn else np.empty(0, dtype=np.int64)
        for family in families:
            sums, counts, _ = prepared[family]
            total_count = counts[picked].sum()
            if total_count <= 0.0:
                raise BootstrapContractError(
                    "a bootstrap replicate produced zero decision events")
            out[family][replicate] = sums[picked].sum() / total_count
    return out


def paired_difference_interval(replicates_a: np.ndarray, replicates_b: np.ndarray,
                               *, level: float = CONFIDENCE_LEVEL,
                               ) -> Tuple[float, float]:
    """Percentile interval of the PAIRED difference a - b, replicate by replicate."""
    if replicates_a.shape != replicates_b.shape:
        raise BootstrapContractError("paired families must share a replicate count")
    if not 0.0 < level < 1.0:
        raise BootstrapContractError("the confidence level must lie in (0, 1)")
    difference = replicates_a - replicates_b
    tail = (1.0 - level) / 2.0
    lower = float(np.percentile(difference, 100.0 * tail))
    upper = float(np.percentile(difference, 100.0 * (1.0 - tail)))
    return lower, upper
