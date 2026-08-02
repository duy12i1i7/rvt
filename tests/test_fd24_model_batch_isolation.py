"""Critical no-cross-ego-graph information-flow tests."""

import torch

from rvt_swarm.fd24.model import prepare_fd24_model_batch
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def _output_by_fingerprint(model, graphs):
    model.eval()
    output = model(prepare_fd24_model_batch(graphs))
    return {
        fingerprint: (
            output.recoverability_logit[index].detach().clone(),
            output.residual_action[index].detach().clone(),
            int(output.observer_robot_id[index]),
            int(output.candidate_topology_id[index]),
        )
        for index, fingerprint in enumerate(output.graph_fingerprint)
    }


def test_adding_unrelated_ego_graphs_cannot_change_target_output(
    fd24_graph_factory, fd24_model_factory
):
    target_case, target = fd24_graph_factory(
        n=6,
        root=0,
        candidate_topology=LINE,
        peer_ids=(1, 2),
        obstacles=((1.0, 0.2, 0.1),),
    )
    _, other_n5 = fd24_graph_factory(
        n=5, root=3, candidate_topology=KEEP, peer_ids=()
    )
    _, other_n24 = fd24_graph_factory(
        n=24,
        root=12,
        candidate_topology=COMPACT,
        peer_ids=(1, 2, 3, 4),
        obstacles=((1.1, 0.0, 0.2), (1.5, -0.2, 0.1)),
        observation_step=19,
    )
    model = fd24_model_factory(target_case.config)
    alone = _output_by_fingerprint(model, (target,))[target.fingerprint()]
    mixed = _output_by_fingerprint(
        model, (other_n24, target, other_n5)
    )[target.fingerprint()]
    torch.testing.assert_close(alone[0], mixed[0], rtol=0.0, atol=1e-7)
    torch.testing.assert_close(alone[1], mixed[1], rtol=0.0, atol=1e-7)
    assert alone[2:] == mixed[2:]


def test_batch_order_cannot_change_local_outputs(
    fd24_graph_factory, fd24_model_factory
):
    graphs = []
    case = None
    for n, root, candidate in (
        (5, 4, KEEP), (8, 1, COMPACT), (12, 7, LINE), (24, 18, KEEP)
    ):
        case, graph = fd24_graph_factory(
            n=n, root=root, candidate_topology=candidate,
            peer_ids=tuple(index for index in range(min(n, 4)) if index != root),
        )
        graphs.append(graph)
    model = fd24_model_factory(case.config)
    forward = _output_by_fingerprint(model, graphs)
    reverse = _output_by_fingerprint(model, tuple(reversed(graphs)))
    assert forward.keys() == reverse.keys()
    for fingerprint in forward:
        torch.testing.assert_close(forward[fingerprint][0], reverse[fingerprint][0])
        torch.testing.assert_close(forward[fingerprint][1], reverse[fingerprint][1])
        assert forward[fingerprint][2:] == reverse[fingerprint][2:]


def test_parallel_candidate_evaluation_does_not_mix_candidates(
    ego_v2_factory, fd24_model_factory
):
    from rvt_swarm.decentralized.ego_graph_v2 import build_robot_local_ego_graph

    case = ego_v2_factory()
    graphs = tuple(build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate,
        case.observation_step,
    ) for candidate in (KEEP, COMPACT, LINE))
    model = fd24_model_factory(case.config)
    together = _output_by_fingerprint(model, graphs)
    for graph in graphs:
        alone = _output_by_fingerprint(model, (graph,))[graph.fingerprint()]
        parallel = together[graph.fingerprint()]
        torch.testing.assert_close(alone[0], parallel[0], rtol=0.0, atol=1e-7)
        torch.testing.assert_close(alone[1], parallel[1], rtol=0.0, atol=1e-7)


def test_batch_is_disjoint_union_without_padding_size_channel(
    fd24_graph_factory,
):
    _, small = fd24_graph_factory(peer_ids=(), obstacles=())
    _, large = fd24_graph_factory(
        n=24,
        root=5,
        peer_ids=(0, 1, 2, 3, 4, 6, 7),
        obstacles=tuple((1.0 + index * 0.2, 0.1, 0.1) for index in range(5)),
    )
    local_batch = prepare_fd24_model_batch((small, large))
    batch = local_batch.graph_batch
    assert batch.node_x.shape[0] == small.n_nodes + large.n_nodes
    assert batch.edge_index.shape[1] == small.n_edges + large.n_edges
    assert batch.node_valid_mask.tolist() == [True] * batch.node_x.shape[0]
    assert torch.equal(
        batch.graph_index[batch.edge_index[0]],
        batch.graph_index[batch.edge_index[1]],
    )


def test_output_mapping_tracks_canonical_sort_back_to_input_order(
    fd24_graph_factory, fd24_model_factory
):
    case_a, graph_a = fd24_graph_factory(root=4, candidate_topology=LINE)
    _, graph_b = fd24_graph_factory(root=0, candidate_topology=KEEP)
    model = fd24_model_factory(case_a.config)
    output = model(prepare_fd24_model_batch((graph_a, graph_b)))
    assert output.graph_batch_mapping == (1, 0)
    assert output.graph_fingerprint == (graph_b.fingerprint(), graph_a.fingerprint())
