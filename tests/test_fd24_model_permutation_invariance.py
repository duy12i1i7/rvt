"""Node, edge, candidate, and mixed-batch permutation contracts."""

from dataclasses import replace

import torch

from rvt_swarm.decentralized.ego_graph_v2 import NODE_OBSTACLE, NODE_PEER
from rvt_swarm.fd24.model import prepare_fd24_model_batch
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def _permute_nonroot_nodes(graph, nonroot_order):
    order = torch.tensor((0,) + tuple(nonroot_order), dtype=torch.int64)
    inverse = torch.empty_like(order)
    inverse[order] = torch.arange(order.numel(), dtype=torch.int64)
    remapped_edges = inverse[graph.edge_index]
    return replace(
        graph,
        node_x=graph.node_x[order],
        node_feature_valid_mask=graph.node_feature_valid_mask[order],
        node_valid_mask=graph.node_valid_mask[order],
        node_kind=graph.node_kind[order],
        node_source_key=tuple(graph.node_source_key[index] for index in order.tolist()),
        edge_index=remapped_edges,
    )


def _permute_edges(graph, edge_order):
    order = torch.tensor(tuple(edge_order), dtype=torch.int64)
    return replace(
        graph,
        edge_index=graph.edge_index[:, order],
        edge_attr=graph.edge_attr[order],
        edge_feature_valid_mask=graph.edge_feature_valid_mask[order],
        edge_valid_mask=graph.edge_valid_mask[order],
        edge_type=graph.edge_type[order],
    )


def _numeric_output(model, graph):
    model.eval()
    output = model(prepare_fd24_model_batch((graph,)))
    return output.recoverability_logit, output.residual_action


def test_peer_and_obstacle_node_permutation_is_invariant(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(
        n=12,
        peer_ids=(1, 2, 3),
        obstacles=((1.0, 0.0, 0.1), (1.4, 0.3, 0.2), (1.8, -0.2, 0.1)),
    )
    nonroot = list(range(1, graph.n_nodes))
    permuted = _permute_nonroot_nodes(graph, tuple(reversed(nonroot)))
    assert int((graph.node_kind == NODE_PEER).sum()) == 3
    assert int((graph.node_kind == NODE_OBSTACLE).sum()) == 3
    model = fd24_model_factory(case.config)
    a = _numeric_output(model, graph)
    b = _numeric_output(model, permuted)
    torch.testing.assert_close(a[0], b[0], rtol=0.0, atol=1e-6)
    torch.testing.assert_close(a[1], b[1], rtol=0.0, atol=1e-6)


def test_edge_order_permutation_is_invariant(fd24_graph_factory, fd24_model_factory):
    case, graph = fd24_graph_factory(
        peer_ids=(1, 2, 3),
        obstacles=((1.0, 0.0, 0.1), (1.4, 0.3, 0.2)),
    )
    permuted = _permute_edges(graph, reversed(range(graph.n_edges)))
    model = fd24_model_factory(case.config)
    a = _numeric_output(model, graph)
    b = _numeric_output(model, permuted)
    torch.testing.assert_close(a[0], b[0], rtol=0.0, atol=1e-6)
    torch.testing.assert_close(a[1], b[1], rtol=0.0, atol=1e-6)


def test_candidate_ordering_is_association_preserving(
    ego_v2_factory, fd24_model_factory
):
    from rvt_swarm.decentralized.ego_graph_v2 import build_robot_local_ego_graph

    case = ego_v2_factory()
    graphs = tuple(build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate,
        case.observation_step,
    ) for candidate in (KEEP, COMPACT, LINE))
    model = fd24_model_factory(case.config)
    model.eval()
    a = model(prepare_fd24_model_batch(graphs))
    b = model(prepare_fd24_model_batch((graphs[2], graphs[0], graphs[1])))
    a_by_id = {
        int(a.candidate_topology_id[index]): a.recoverability_logit[index]
        for index in range(3)
    }
    b_by_id = {
        int(b.candidate_topology_id[index]): b.recoverability_logit[index]
        for index in range(3)
    }
    for candidate in (KEEP, COMPACT, LINE):
        torch.testing.assert_close(a_by_id[candidate], b_by_id[candidate])


def test_mixed_size_batch_ordering_is_invariant(
    fd24_graph_factory, fd24_model_factory
):
    graphs = []
    case = None
    for n, root in ((5, 0), (8, 2), (12, 4), (24, 9)):
        case, graph = fd24_graph_factory(n=n, root=root)
        graphs.append(graph)
    model = fd24_model_factory(case.config)
    model.eval()
    a = model(prepare_fd24_model_batch(graphs))
    b = model(prepare_fd24_model_batch(tuple(reversed(graphs))))
    a_by_graph = dict(zip(a.graph_fingerprint, a.recoverability_logit))
    b_by_graph = dict(zip(b.graph_fingerprint, b.recoverability_logit))
    for fingerprint in a_by_graph:
        torch.testing.assert_close(a_by_graph[fingerprint], b_by_graph[fingerprint])
