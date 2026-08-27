"""Clean-room budget authority.

There is exactly ONE composition object in the clean-room programme: the frozen
V4 composition in rvt_swarm.cleanroom.composition. This module does not restate
it and does not define a competing budget; it reads it and exposes it in the
shape the compiler needs. Any runtime value that disagrees with V4 is refused.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from rvt_swarm.cleanroom.composition import (
    ACQUISITION_RULE, CELLS, FAMILIES, K_MAX_SELECTED_SOURCE_EVENTS_PER_EPISODE,
    ROLE_COMPOSITION, SOURCE_POLICIES, TEAM_SIZES, replicas_per_candidate,
)
from rvt_swarm.cleanroom.generation.roles import ROLES, role


class BudgetAuthorityError(ValueError):
    """A clean-room budget violation that must fail closed."""


@dataclass(frozen=True)
class CleanRoomBudget:
    role: str
    dataset_id: str
    study: str
    split: str
    offset: float
    families: tuple[str, ...]
    team_sizes: tuple[int, ...]
    source_policies: tuple[str, ...]
    episodes_per_cell: int
    expected_source_episode_count: int
    layout_count: int
    k_max_selected_source_events_per_episode: int
    acquisition_rule: str


def budget(role_name: str) -> CleanRoomBudget:
    """The role's budget, sourced from the frozen V4 composition."""
    from rvt_swarm.cleanroom.generation.roles import CLEAN_ROOM_STUDY
    r = role(role_name)
    comp = ROLE_COMPOSITION.get(role_name)
    if comp is None:
        raise BudgetAuthorityError(f"no V4 composition for role {role_name!r}")
    if comp.offset != r.offset:
        raise BudgetAuthorityError(
            f"{role_name}: V4 offset {comp.offset} disagrees with the role registry {r.offset}")
    return CleanRoomBudget(
        role=role_name, dataset_id=r.dataset_id, study=CLEAN_ROOM_STUDY, split=r.split,
        offset=comp.offset, families=tuple(FAMILIES), team_sizes=tuple(TEAM_SIZES),
        source_policies=tuple(SOURCE_POLICIES),
        episodes_per_cell=comp.episodes_per_cell,
        expected_source_episode_count=comp.source_episode_count,
        layout_count=comp.layout_count,
        k_max_selected_source_events_per_episode=K_MAX_SELECTED_SOURCE_EVENTS_PER_EPISODE,
        acquisition_rule=ACQUISITION_RULE)


def assert_matches_budget(role_name: str, *, episodes_per_cell: int,
                          expected_source_episode_count: int, families: tuple[str, ...],
                          team_sizes: tuple[int, ...], source_policies: tuple[str, ...],
                          offset: float, k: int) -> None:
    """Refuse any runtime value that differs from the frozen budget."""
    b = budget(role_name)
    for name, got, want in (
        ("episodes_per_cell", episodes_per_cell, b.episodes_per_cell),
        ("expected_source_episode_count", expected_source_episode_count,
         b.expected_source_episode_count),
        ("families", tuple(families), b.families),
        ("team_sizes", tuple(team_sizes), b.team_sizes),
        ("source_policies", tuple(source_policies), b.source_policies),
        ("offset", offset, b.offset),
        ("k", k, b.k_max_selected_source_events_per_episode),
    ):
        if got != want:
            raise BudgetAuthorityError(
                f"{role_name}: runtime {name}={got!r} disagrees with the frozen budget {want!r}")


def all_budgets() -> Mapping[str, CleanRoomBudget]:
    return {name: budget(name) for name in ROLES}


def total_source_episodes() -> int:
    return sum(b.expected_source_episode_count for b in all_budgets().values())


__all__ = ["CleanRoomBudget", "BudgetAuthorityError", "budget", "all_budgets",
           "assert_matches_budget", "total_source_episodes", "replicas_per_candidate", "CELLS"]
