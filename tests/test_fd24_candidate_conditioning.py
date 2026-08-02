"""Explicit shared KEEP/COMPACT/LINE conditioning tests."""

from dataclasses import replace

import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    NODE_FEATURE_SLICES,
    build_robot_local_ego_graph,
)
from rvt_swarm.fd24.model import (
    CANDIDATE_LOCAL_NODE_FEATURE_INDICES,
    FD24_TOPOLOGY_VOCABULARY,
    prepare_fd24_model_batch,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def _outputs_by_candidate(model, graphs):
    model.eval()
    output = model(prepare_fd24_model_batch(graphs))
    return {
        int(candidate): (
            output.recoverability_logit[index].detach(),
            output.residual_action[index].detach(),
        )
        for index, candidate in enumerate(output.candidate_topology_id)
    }


def test_same_local_observation_supports_all_three_candidates(
    ego_v2_factory, fd24_model_factory
):
    case = ego_v2_factory()
    graphs = tuple(build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate,
        case.observation_step,
    ) for candidate in (KEEP, COMPACT, LINE))
    model = fd24_model_factory(case.config)
    outputs = _outputs_by_candidate(model, graphs)
    assert set(outputs) == {KEEP, COMPACT, LINE}
    assert tuple(item[0] for item in FD24_TOPOLOGY_VOCABULARY) == (
        KEEP, COMPACT, LINE
    )


def test_candidate_input_order_preserves_candidate_association(
    ego_v2_factory, fd24_model_factory
):
    case = ego_v2_factory()
    graphs = tuple(build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate,
        case.observation_step,
    ) for candidate in (KEEP, COMPACT, LINE))
    model = fd24_model_factory(case.config)
    forward = _outputs_by_candidate(model, graphs)
    reverse = _outputs_by_candidate(model, tuple(reversed(graphs)))
    for candidate in forward:
        torch.testing.assert_close(forward[candidate][0], reverse[candidate][0])
        torch.testing.assert_close(forward[candidate][1], reverse[candidate][1])


def test_topology_registry_iteration_order_does_not_affect_model_output(
    ego_v2_factory, fd24_model_factory
):
    case = ego_v2_factory()
    reversed_local = replace(
        case.local_topology,
        candidates=tuple(reversed(case.local_topology.candidates)),
    )
    a = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, COMPACT, case.observation_step
    )
    b = build_robot_local_ego_graph(
        case.view, case.config, reversed_local, COMPACT, case.observation_step
    )
    model = fd24_model_factory(case.config)
    model.eval()
    out_a = model(prepare_fd24_model_batch((a,)))
    out_b = model(prepare_fd24_model_batch((b,)))
    torch.testing.assert_close(out_a.recoverability_logit, out_b.recoverability_logit)
    torch.testing.assert_close(out_a.residual_action, out_b.residual_action)


def test_unobserved_role_metadata_cannot_affect_conditioning(
    ego_v2_factory, fd24_model_factory
):
    case = ego_v2_factory(n=12, peer_ids=())
    candidate = case.local_topology.candidate(COMPACT)
    altered = replace(
        candidate,
        formation_neighbours=tuple(replace(
            item,
            candidate_role_offset_meters=(1000.0, -1000.0),
            desired_offset_from_observer_meters=(500.0, -500.0),
        ) for item in candidate.formation_neighbours),
    )
    local = replace(
        case.local_topology,
        candidates=tuple(
            altered if item.topology_id == COMPACT else item
            for item in case.local_topology.candidates
        ),
    )
    a = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, COMPACT, case.observation_step
    )
    b = build_robot_local_ego_graph(
        case.view, case.config, local, COMPACT, case.observation_step
    )
    assert a.fingerprint() == b.fingerprint()
    model = fd24_model_factory(case.config)
    model.eval()
    out_a = model(prepare_fd24_model_batch((a,)))
    out_b = model(prepare_fd24_model_batch((b,)))
    torch.testing.assert_close(out_a.recoverability_logit, out_b.recoverability_logit)


def test_candidate_gradients_reach_embedding_and_local_metadata_projection(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(candidate_topology=LINE)
    model = fd24_model_factory(case.config)
    conditioned = model.conditioned_representation(prepare_fd24_model_batch((graph,)))
    conditioned.square().sum().backward()
    embedding_grad = model.candidate_conditioner.topology_embedding.weight.grad
    local_grad = model.candidate_conditioner.local_metadata_projection[0].weight.grad
    assert embedding_grad is not None and float(embedding_grad.abs().sum()) > 0.0
    assert local_grad is not None and float(local_grad.abs().sum()) > 0.0


def test_controlled_weights_prove_local_candidate_metadata_can_change_output(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(peer_ids=(), candidate_topology=LINE)
    feature_index = CANDIDATE_LOCAL_NODE_FEATURE_INDICES[0]
    node_a = graph.node_x.clone()
    node_b = graph.node_x.clone()
    node_a[0, feature_index] = 1.0
    node_b[0, feature_index] = 2.0
    graph_a = replace(graph, node_x=node_a)
    graph_b = replace(graph, node_x=node_b)
    model = fd24_model_factory(case.config)
    conditioner = model.candidate_conditioner
    with torch.no_grad():
        for parameter in conditioner.parameters():
            parameter.zero_()
        conditioner.local_metadata_projection[0].weight[0, 0] = 1.0
        hidden = model.model_config.hidden_dimension
        candidate_dim = model.model_config.candidate_embedding_dimension
        conditioner.fusion[0].weight[0, hidden + candidate_dim] = 1.0
        conditioner.fusion[3].weight[0, 0] = 1.0
        conditioner.fusion[4].weight.fill_(1.0)
    root = torch.zeros((1, model.model_config.hidden_dimension))
    a = conditioner(root, prepare_fd24_model_batch((graph_a,)))
    b = conditioner(root, prepare_fd24_model_batch((graph_b,)))
    assert not torch.equal(a, b)
