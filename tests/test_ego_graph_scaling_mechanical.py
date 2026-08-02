"""Mechanical variable-N and variable-degree construction matrix."""

import math

import pytest

from rvt_swarm.decentralized.ego_graph_v2 import (
    build_robot_local_ego_graph,
    tensor_memory_bytes,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


TEAM_SIZES = (5, 6, 8, 12, 16, 24)
TOPOLOGIES = (KEEP, COMPACT, LINE)
PATTERNS = ("none", "one", "path_endpoint", "ring", "bounded", "complete")


def _peer_ids(n, root, pattern):
    others = tuple(robot for robot in range(n) if robot != root)
    if pattern == "none":
        return ()
    if pattern in ("one", "path_endpoint"):
        return others[:1]
    if pattern == "ring":
        return tuple(sorted({(root - 1) % n, (root + 1) % n}))
    if pattern == "bounded":
        return others[: min(4, len(others))]
    if pattern == "complete":
        return others
    raise AssertionError(pattern)


@pytest.mark.parametrize("n", TEAM_SIZES)
@pytest.mark.parametrize("candidate", TOPOLOGIES)
@pytest.mark.parametrize("pattern", PATTERNS)
def test_required_variable_size_degree_and_topology_matrix(
    ego_v2_factory, n, candidate, pattern
):
    root = n // 2
    peers = _peer_ids(n, root, pattern)
    positions = {
        peer: (0.45 + index * 0.06, -0.4 + index * 0.035)
        for index, peer in enumerate(peers)
    }
    case = ego_v2_factory(
        n=n, root=root, peer_ids=peers, peer_local_positions=positions
    )
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate, case.observation_step
    )
    assert graph.n_peer_nodes == len(peers)
    assert graph.n_nodes == 1 + len(peers)
    assert graph.n_edges == 2 * len(peers)
    assert tensor_memory_bytes(graph) > 0
    assert math.isfinite(float(graph.node_x.sum()))


def test_n24_dense_diagnostic_has_no_fixed_maximum_neighbour_limit(
    ego_v2_factory,
):
    n = 24
    root = 0
    peers = tuple(range(1, n))
    positions = {peer: (0.5 + index * 0.05, 0.1) for index, peer in enumerate(peers)}
    case = ego_v2_factory(
        n=n, root=root, peer_ids=peers, peer_local_positions=positions
    )
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, LINE, case.observation_step
    )
    assert graph.n_peer_nodes == 23
    assert graph.n_nodes == 24
    assert graph.n_edges == 46
