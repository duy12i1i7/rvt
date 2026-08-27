"""Clean-room pre-generation enumeration and seed ledgers.

Every expected source episode of every role is enumerable before any simulator
runs. Seeds come from the FROZEN builder, not from a local reimplementation.
"""
from __future__ import annotations

from typing import Iterator, Mapping, Sequence

from rvt_swarm.cleanroom.composition import FAMILIES, SOURCE_POLICIES, TEAM_SIZES
from rvt_swarm.cleanroom.generation.budget import budget
from rvt_swarm.cleanroom.generation.identity import (
    CleanRoomSourceEpisodeIdentity, make_identity,
)
from rvt_swarm.cleanroom.generation.layouts import role_layouts
from rvt_swarm.cleanroom.generation.roles import ROLES
from rvt_swarm.cleanroom.generation.seeds import (
    SOURCE_EPISODE_SEED_NAMESPACES, source_episode_seeds,
)
from rvt_swarm.phase8.common import sha256_document


def enumerate_role(role_name: str) -> Iterator[CleanRoomSourceEpisodeIdentity]:
    """The role's complete expected source-episode universe, canonical order."""
    b = budget(role_name)
    layouts = {item.family_id: item for item in role_layouts(role_name)}
    for family in FAMILIES:
        lay = layouts[family]
        for team_size in TEAM_SIZES:
            for policy in SOURCE_POLICIES:
                for index in range(b.episodes_per_cell):
                    yield make_identity(role_name, family, team_size, policy, index,
                                        lay.layout_id, lay.layout_sha256)


def episode_record(identity: CleanRoomSourceEpisodeIdentity) -> Mapping[str, object]:
    """One fully bound pre-generation record, seeds from the frozen builder."""
    cell = identity.cell
    return {
        "role": identity.role,
        "dataset_id": cell.dataset_id,
        "study": cell.study,
        "split": cell.split,
        "family": cell.family_id,
        "team_size": cell.team_size,
        "source_policy": identity.source_class,
        "episode_index": identity.episode_index,
        "layout_id": identity.layout_id,
        "layout_sha256": cell.layout_sha256,
        "source_episode_id": identity.source_episode_id(),
        "seeds": dict(source_episode_seeds(identity)),
    }


def role_ledger(role_name: str) -> Sequence[Mapping[str, object]]:
    return [episode_record(i) for i in enumerate_role(role_name)]


def role_roots(role_name: str) -> Mapping[str, object]:
    records = role_ledger(role_name)
    b = budget(role_name)
    if len(records) != b.expected_source_episode_count:
        raise ValueError(
            f"{role_name}: enumerated {len(records)} but the frozen budget says "
            f"{b.expected_source_episode_count}")
    ids = [r["source_episode_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{role_name}: duplicate source-episode identity")
    seeds = [r["seeds"] for r in records]
    flat = [v for s in seeds for _, v in sorted(s.items())]
    return {
        "role": role_name,
        "expected_source_episode_count": len(records),
        "episode_universe_root": sha256_document(sorted(ids)),
        "seed_ledger_root": sha256_document(
            [[r["source_episode_id"], sorted(r["seeds"].items())] for r in records]),
        "distinct_seed_values": len(set(flat)),
        "total_seed_values": len(flat),
        "seed_namespaces": list(SOURCE_EPISODE_SEED_NAMESPACES),
    }


def all_roots() -> Mapping[str, object]:
    per_role = {name: role_roots(name) for name in ROLES}
    return {
        "per_role": per_role,
        "total_source_episodes": sum(
            r["expected_source_episode_count"] for r in per_role.values()),
        "global_episode_universe_root": sha256_document(
            [per_role[n]["episode_universe_root"] for n in sorted(per_role)]),
        "global_seed_ledger_root": sha256_document(
            [per_role[n]["seed_ledger_root"] for n in sorted(per_role)]),
    }
