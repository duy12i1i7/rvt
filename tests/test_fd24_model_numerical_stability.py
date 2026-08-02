"""Synthetic forward/backward numerical sanity without mission outcomes."""

from dataclasses import replace

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import NODE_FEATURE_SLICES
from rvt_swarm.fd24.model import (
    FD24ModelContractError,
    prepare_fd24_model_batch,
)


@pytest.mark.parametrize(
    "peers,obstacles",
    (
        ((), ()),
        ((1,), ()),
        ((), ((1.0, 0.0, 0.1),)),
        ((1, 2, 3), ((1.0, 0.0, 0.1), (1.4, 0.2, 0.2))),
    ),
)
def test_zero_and_mixed_local_entity_cases_are_finite(
    fd24_graph_factory, fd24_model_factory, peers, obstacles
):
    case, graph = fd24_graph_factory(peer_ids=peers, obstacles=obstacles)
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch((graph,)))
    assert bool(torch.isfinite(output.recoverability_logit).all())
    assert bool(torch.isfinite(output.recoverability_probability).all())
    assert bool(torch.isfinite(output.residual_action).all())
    assert output.validity.tolist() == [True]


def test_large_finite_feature_values_remain_numerically_finite(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(
        peer_ids=(1, 2), obstacles=((1.0, 0.0, 0.1),)
    )
    node_x = graph.node_x.clone()
    edge_attr = graph.edge_attr.clone()
    node_x[graph.node_feature_valid_mask] *= 1.0e6
    edge_attr[graph.edge_feature_valid_mask] *= -1.0e6
    candidate_block = NODE_FEATURE_SLICES["candidate_topology_onehot"]
    node_x[0, candidate_block] = graph.node_x[0, candidate_block]
    extreme = replace(graph, node_x=node_x, edge_attr=edge_attr)
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch((extreme,)))
    loss = output.recoverability_logit.square().mean() + output.residual_action.square().mean()
    loss.backward()
    assert bool(torch.isfinite(loss))
    assert all(
        parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )


def test_dense_n24_diagnostic_forward_is_finite(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(
        n=24,
        root=0,
        peer_ids=tuple(range(1, 24)),
        peer_local_positions={
            peer: (0.5 + 0.05 * index, 0.1)
            for index, peer in enumerate(range(1, 24))
        },
        obstacles=tuple((1.0 + index * 0.2, 0.1, 0.1) for index in range(6)),
    )
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch((graph,)))
    assert graph.n_peer_nodes == 23
    assert bool(output.validity.all())


def test_missing_feature_validity_mask_is_rejected(
    fd24_graph_factory,
):
    _, graph = fd24_graph_factory()
    local_batch = prepare_fd24_model_batch((graph,))
    malformed_graph_batch = replace(
        local_batch.graph_batch,
        node_feature_valid_mask=torch.zeros((1, 1), dtype=torch.bool),
    )
    with pytest.raises(FD24ModelContractError, match="validity mask"):
        replace(local_batch, graph_batch=malformed_graph_batch)


def test_raw_legacy_like_input_is_rejected(fd24_graph_factory, fd24_model_factory):
    case, _ = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    with pytest.raises(FD24ModelContractError):
        model({"node_x": torch.zeros((6, 68)), "edge_attr": torch.zeros((4, 11))})


@pytest.mark.parametrize(
    "field,value",
    (
        ("ego_graph_schema_version", "rvt-ego-graph/v1"),
        ("ego_feature_schema_sha256", "0" * 64),
        ("topology_registry_schema_version", "unknown"),
    ),
)
def test_closed_model_batch_rejects_schema_mismatch(
    fd24_graph_factory, field, value
):
    _, graph = fd24_graph_factory()
    local_batch = prepare_fd24_model_batch((graph,))
    with pytest.raises(FD24ModelContractError):
        replace(local_batch, **{field: value})


def test_closed_model_batch_rejects_unknown_candidate_id(fd24_graph_factory):
    _, graph = fd24_graph_factory()
    local_batch = prepare_fd24_model_batch((graph,))
    malformed_graph_batch = replace(
        local_batch.graph_batch,
        candidate_topology_id=torch.tensor((3,), dtype=torch.int64),
    )
    with pytest.raises(FD24ModelContractError, match="vocabulary"):
        replace(local_batch, graph_batch=malformed_graph_batch)


def test_candidate_id_and_root_candidate_features_must_agree(fd24_graph_factory):
    _, graph = fd24_graph_factory()
    local_batch = prepare_fd24_model_batch((graph,))
    node_x = local_batch.graph_batch.node_x.clone()
    candidate_block = NODE_FEATURE_SLICES["candidate_topology_onehot"]
    node_x[local_batch.graph_batch.root_index[0], candidate_block] = torch.tensor(
        (0.0, 1.0, 0.0)
    )
    malformed_graph_batch = replace(local_batch.graph_batch, node_x=node_x)
    with pytest.raises(FD24ModelContractError, match="conflict"):
        replace(local_batch, graph_batch=malformed_graph_batch)
