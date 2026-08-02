"""Variable-N, variable-degree disjoint batching tests."""

import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    batch_robot_local_ego_graphs,
    build_robot_local_ego_graph,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def test_mixed_team_sizes_batch_without_padding_or_cross_graph_edges(
    ego_v2_factory,
):
    specifications = (
        (5, 0, (), (), KEEP),
        (8, 2, (0,), ((1.0, 0.0, 0.2),), COMPACT),
        (12, 5, (0, 1, 2), (), LINE),
        (24, 11, tuple(range(6)), tuple((1.0 + i * .1, .1, .1) for i in range(4)), KEEP),
    )
    graphs = []
    for n, root, peers, obstacles, candidate in specifications:
        peers = tuple(peer for peer in peers if peer != root)
        case = ego_v2_factory(n=n, root=root, peer_ids=peers, obstacles=obstacles)
        graphs.append(build_robot_local_ego_graph(
            case.view, case.config, case.local_topology, candidate,
            case.observation_step,
        ))
    batch = batch_robot_local_ego_graphs(tuple(reversed(graphs)))

    assert batch.n_graphs == 4
    assert batch.node_x.shape[0] == sum(graph.n_nodes for graph in graphs)
    assert batch.edge_index.shape[1] == sum(graph.n_edges for graph in graphs)
    assert batch.node_valid_mask.tolist() == [True] * batch.node_x.shape[0]
    assert batch.edge_valid_mask.tolist() == [True] * batch.edge_index.shape[1]
    assert torch.equal(
        batch.graph_index[batch.edge_index[0]],
        batch.graph_index[batch.edge_index[1]],
    )
    assert torch.equal(
        batch.graph_index[batch.root_index],
        torch.arange(batch.n_graphs, dtype=torch.int64),
    )
    assert batch.observer_robot_id.tolist() == sorted(
        graph.observer_robot_id for graph in graphs
    )
    assert batch.node_x.shape[0] != 4 * 24


def test_batch_candidate_topologies_remain_explicit(ego_v2_factory):
    graphs = []
    for root, candidate in enumerate((LINE, KEEP, COMPACT)):
        case = ego_v2_factory(root=root, peer_ids=())
        graphs.append(build_robot_local_ego_graph(
            case.view, case.config, case.local_topology, candidate,
            case.observation_step,
        ))
    batch = batch_robot_local_ego_graphs(tuple(reversed(graphs)))
    assert batch.observer_robot_id.tolist() == [0, 1, 2]
    assert batch.candidate_topology_id.tolist() == [LINE, KEEP, COMPACT]
