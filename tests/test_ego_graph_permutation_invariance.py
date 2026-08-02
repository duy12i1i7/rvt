"""Canonical ordering and semantic permutation invariance."""

from dataclasses import replace

import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    batch_robot_local_ego_graphs,
    build_robot_local_ego_graph,
)
from rvt_swarm.topology_registry import COMPACT


def _build(case):
    return build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, COMPACT, case.observation_step
    )


def test_peer_message_order_does_not_change_graph(ego_v2_factory):
    case = ego_v2_factory(peer_ids=(1, 3, 2))
    a = _build(case)
    b = _build(replace(case, view=replace(
        case.view, neighbours=tuple(reversed(case.view.neighbours))
    )))
    assert a.fingerprint() == b.fingerprint()


def test_obstacle_input_order_does_not_change_graph(ego_v2_factory):
    obstacles = ((2.0, 0.2, 0.3), (1.2, -0.5, 0.1), (2.8, 0.0, 0.4))
    a = _build(ego_v2_factory(peer_ids=(), obstacles=obstacles))
    b = _build(ego_v2_factory(peer_ids=(), obstacles=tuple(reversed(obstacles))))
    assert a.fingerprint() == b.fingerprint()


def test_simulator_robot_array_order_does_not_change_persistent_role_graph(
    ego_v2_factory,
):
    ascending = ego_v2_factory(n=8, root=2, robot_keys=tuple(range(8)))
    shuffled = ego_v2_factory(
        n=8, root=2, robot_keys=(7, 2, 5, 0, 6, 1, 4, 3)
    )
    assert ascending.local_topology == shuffled.local_topology
    assert _build(ascending).fingerprint() == _build(shuffled).fingerprint()


def test_topology_registry_iteration_order_does_not_change_graph(ego_v2_factory):
    case = ego_v2_factory()
    reversed_local = replace(
        case.local_topology,
        candidates=tuple(reversed(case.local_topology.candidates)),
    )
    a = _build(case)
    b = build_robot_local_ego_graph(
        case.view, case.config, reversed_local, COMPACT, case.observation_step
    )
    assert a.fingerprint() == b.fingerprint()


def test_batch_input_order_has_identical_canonical_tensors(ego_v2_factory):
    graphs = [
        _build(ego_v2_factory(n=8, root=3, peer_ids=(1, 2))),
        _build(ego_v2_factory(n=5, root=0, peer_ids=())),
        _build(ego_v2_factory(n=12, root=7, peer_ids=(2,), obstacles=((1, 0, .2),))),
    ]
    a = batch_robot_local_ego_graphs(graphs)
    b = batch_robot_local_ego_graphs(tuple(reversed(graphs)))
    for name in (
        "node_x", "node_feature_valid_mask", "node_valid_mask", "node_kind",
        "edge_index", "edge_attr", "edge_feature_valid_mask", "edge_valid_mask",
        "edge_type", "graph_index", "edge_graph_index", "root_index",
        "candidate_topology_id", "observer_robot_id",
    ):
        assert torch.equal(getattr(a, name), getattr(b, name)), name
