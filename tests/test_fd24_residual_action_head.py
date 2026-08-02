"""Bounded robot-local residual action semantics."""

import torch

from rvt_swarm.fd24.model import (
    DirectLocalActionAblationHead,
    bounded_residual_action,
    prepare_fd24_model_batch,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def test_zero_raw_residual_is_exactly_zero():
    raw = torch.zeros((3, 2))
    limits = torch.tensor((0.1, 0.2))
    assert torch.equal(bounded_residual_action(raw, limits), raw)


def test_positive_negative_saturation_and_per_dimension_limits():
    raw = torch.tensor(((100.0, -100.0), (-100.0, 100.0)))
    limits = torch.tensor((0.1, 0.25))
    output = bounded_residual_action(raw, limits)
    torch.testing.assert_close(
        output,
        torch.tensor(((0.1, -0.25), (-0.1, 0.25))),
        rtol=0.0,
        atol=1e-6,
    )
    assert bool((output.abs() <= limits.view(1, -1)).all())


def test_model_emits_one_bounded_residual_per_local_graph(
    fd24_graph_factory, fd24_model_factory
):
    graphs = []
    case = None
    for n, root, candidate in ((5, 0, KEEP), (8, 2, COMPACT), (24, 7, LINE)):
        case, graph = fd24_graph_factory(
            n=n, root=root, candidate_topology=candidate
        )
        graphs.append(graph)
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch(graphs))
    assert output.residual_action.shape == (len(graphs), model.action_dimension)
    assert bool((output.residual_action.abs() <= model.residual_action_limits).all())
    assert output.residual_action.shape[0] != sum(graph.n_nodes for graph in graphs)


def test_bounded_mapping_preserves_gradients():
    raw = torch.tensor(((0.2, -0.3),), requires_grad=True)
    limits = torch.tensor((0.1, 0.25))
    bounded_residual_action(raw, limits).sum().backward()
    assert raw.grad is not None
    assert bool(torch.isfinite(raw.grad).all())
    assert bool((raw.grad.abs() > 0.0).all())


def test_residual_output_is_candidate_conditioned(
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
    residual = model(prepare_fd24_model_batch(graphs)).residual_action
    assert torch.unique(residual, dim=0).shape[0] > 1


def test_direct_local_action_ablation_is_separate_and_bounded(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    assert not hasattr(model, "direct_local_action_ablation")
    conditioned = model.conditioned_representation(
        prepare_fd24_model_batch((graph,))
    )
    maximum = case.config.physical.maximum_acceleration_meters_per_second_squared
    ablation = DirectLocalActionAblationHead(
        model.model_config.hidden_dimension,
        (maximum, maximum),
    )
    action = ablation(conditioned)
    assert ablation.ablation_name == "direct_local_action_ablation"
    assert action.shape == (1, 2)
    assert bool((action.abs() <= maximum).all())
