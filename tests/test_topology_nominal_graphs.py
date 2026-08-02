"""Sparse nominal formation graphs are deterministic and connected."""

from __future__ import annotations

import pytest

from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    construct_topology,
    generate_persistent_roles,
    graph_statistics,
)

TEAM_SIZES = (5, 6, 8, 12, 16, 24)


@pytest.mark.parametrize("n", TEAM_SIZES)
@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_nominal_graph_is_sparse_connected_and_deterministic(
    n: int, topology_id: int,
) -> None:
    config = RuntimeConfig.for_team_size(n)
    first = construct_topology(topology_id, config.formation, robot_keys_or_team_size=n)
    second = construct_topology(topology_id, config.formation, robot_keys_or_team_size=n)
    stats = graph_statistics(first)
    assert first.edges == second.edges
    assert stats.connected
    assert stats.node_count == n
    assert stats.edge_count < n * (n - 1) // 2


@pytest.mark.parametrize("n", TEAM_SIZES)
def test_degree_bounds_match_topology_geometry(n: int) -> None:
    config = RuntimeConfig.for_team_size(n)
    keep = graph_statistics(construct_topology(KEEP, config.formation, robot_keys_or_team_size=n))
    compact = graph_statistics(construct_topology(COMPACT, config.formation, robot_keys_or_team_size=n))
    line = graph_statistics(construct_topology(LINE, config.formation, robot_keys_or_team_size=n))
    assert keep.maximum_degree <= 4
    assert compact.maximum_degree <= 3
    assert line.maximum_degree <= 2
    assert line.edge_count == n - 1
    assert line.diameter_hops == n - 1


def test_graph_is_permutation_equivariant_under_role_relabelling() -> None:
    config = RuntimeConfig.for_team_size(8)
    first_roles = generate_persistent_roles(tuple("abcdefgh"))
    second_roles = generate_persistent_roles(tuple(reversed("abcdefgh")))
    first = construct_topology(COMPACT, config.formation, role_set=first_roles)
    second = construct_topology(COMPACT, config.formation, role_set=second_roles)
    assert first.role_ids == second.role_ids
    assert first.edges == second.edges


def test_nominal_graph_is_not_the_dynamic_communication_graph() -> None:
    template = construct_topology(
        KEEP, RuntimeConfig.for_team_size(6).formation, robot_keys_or_team_size=6
    )
    assert not hasattr(template, "communication_range")
    assert not hasattr(template, "packet_loss")
    assert not hasattr(template, "message_age")
