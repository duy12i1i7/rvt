"""Shared typed robot-local encoder mechanics."""

from dataclasses import replace

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import NODE_FEATURE_SLICES
from rvt_swarm.fd24.model import (
    FD24ModelContractError,
    prepare_fd24_model_batch,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("candidate", (KEEP, COMPACT, LINE))
def test_shared_encoder_supports_every_required_size_and_candidate(
    fd24_graph_factory, fd24_model_factory, n, candidate
):
    case, graph = fd24_graph_factory(n=n, candidate_topology=candidate)
    model = fd24_model_factory(case.config)
    root = model.encoder(prepare_fd24_model_batch((graph,)))
    assert root.shape == (1, model.model_config.hidden_dimension)
    assert bool(torch.isfinite(root).all())


def test_zero_peer_zero_obstacle_graph_has_valid_root_output(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(peer_ids=(), obstacles=())
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch((graph,)))
    assert graph.n_nodes == 1
    assert graph.n_edges == 0
    assert output.validity.tolist() == [True]


def test_mixed_node_classes_use_one_shared_encoder(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(
        n=12,
        peer_ids=(1, 2, 3),
        obstacles=((1.0, 0.2, 0.1), (1.4, -0.3, 0.2)),
    )
    model = fd24_model_factory(case.config)
    root = model.encoder(prepare_fd24_model_batch((graph,)))
    assert graph.n_peer_nodes == 3
    assert graph.n_obstacle_nodes == 2
    assert root.shape[0] == 1
    assert len(model.encoder.node_type_projections) == 3
    assert len(model.encoder.edge_type_projections) == 4


def test_masked_feature_values_cannot_affect_encoder(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(peer_ids=(1,))
    velocity = NODE_FEATURE_SLICES["relative_velocity_speed"]
    node_x = graph.node_x.clone()
    feature_mask = graph.node_feature_valid_mask.clone()
    feature_mask[1, velocity] = False
    graph_a = replace(
        graph,
        node_x=node_x.clone(),
        node_feature_valid_mask=feature_mask,
    )
    node_x[1, velocity] = torch.tensor((999.0, -999.0))
    graph_b = replace(
        graph,
        node_x=node_x,
        node_feature_valid_mask=feature_mask,
    )
    model = fd24_model_factory(case.config)
    model.eval()
    a = model.encoder(prepare_fd24_model_batch((graph_a,)))
    b = model.encoder(prepare_fd24_model_batch((graph_b,)))
    torch.testing.assert_close(a, b, rtol=0.0, atol=0.0)


def test_encoder_rejects_untyped_or_legacy_batch(fd24_graph_factory, fd24_model_factory):
    case, _ = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    with pytest.raises(FD24ModelContractError):
        model.encoder({"node_x": torch.zeros((6, 68))})


def test_parameter_shapes_do_not_contain_team_size(
    fd24_graph_factory, fd24_model_factory
):
    case, _ = fd24_graph_factory(n=24)
    model = fd24_model_factory(case.config)
    assert all(24 not in parameter.shape for parameter in model.parameters())
