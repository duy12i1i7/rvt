"""Clean-room seed authority.

There is NO master seed. Every seed is produced by the frozen
phase9b.identity.derive_generation_seed over the frozen phase8.seeds namespaces,
exactly as the pilot produced its own. The V4 role-level seeds are decorative
metadata and are refused here.
"""
from __future__ import annotations

from typing import Mapping

from rvt_swarm.cleanroom.generation.identity import CleanRoomSourceEpisodeIdentity
from rvt_swarm.phase8.seeds import SEED_NAMESPACES
from rvt_swarm.phase9b.identity import derive_generation_seed

# The four per-source-episode streams the frozen manifest builder derives.
SOURCE_EPISODE_SEED_NAMESPACES = (
    "initial_condition", "communication", "dynamic_obstacle", "data_sampling")
SEED_NAMESPACE_ROOTS: Mapping[str, int] = {
    item.name: item.root_seed for item in SEED_NAMESPACES}

# Retired V4 values, reproduced only so this module can refuse them.
DECORATIVE_V4_ROLE_SEEDS = frozenset({
    3650100380, 3751336945, 3304876695, 2439304766, 3420783843, 1912935458})


class SeedAuthorityError(ValueError):
    """A clean-room seed-authority violation that must fail closed."""


def refuse_master_seed(value: object) -> None:
    """The frozen law takes no master seed; a V4 role seed must never be injected."""
    if isinstance(value, int) and value in DECORATIVE_V4_ROLE_SEEDS:
        raise SeedAuthorityError(
            "a decorative V4 role-level master seed was passed to the generator; the "
            "frozen seed law derives per-episode seeds from identity and accepts no "
            "master seed")


def source_episode_seeds(identity: CleanRoomSourceEpisodeIdentity) -> Mapping[str, int]:
    """The four frozen per-episode seeds for one clean-room source episode."""
    cell = identity.cell
    common = {
        "study": cell.study,
        "split": cell.split,
        "scenario_family": cell.family_id,
        "layout_sha256": cell.layout_sha256,
        "team_size": cell.team_size,
        "source_class": identity.source_class,
        "episode_index": identity.episode_index,
    }
    for namespace in SOURCE_EPISODE_SEED_NAMESPACES:
        if namespace not in SEED_NAMESPACE_ROOTS:
            raise SeedAuthorityError(f"unbound seed namespace {namespace!r}")
    return {ns: derive_generation_seed(ns, **common)
            for ns in SOURCE_EPISODE_SEED_NAMESPACES}
