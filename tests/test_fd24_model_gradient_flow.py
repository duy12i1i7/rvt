"""Architecture-only finite and nonzero gradient connectivity."""

import pytest
import torch

from rvt_swarm.fd24.model import prepare_fd24_model_batch
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def _assert_module_has_finite_nonzero_gradient(module, name):
    gradients = [parameter.grad for parameter in module.parameters()]
    assert gradients and all(gradient is not None for gradient in gradients), name
    assert all(bool(torch.isfinite(gradient).all()) for gradient in gradients), name
    assert sum(float(gradient.abs().sum()) for gradient in gradients) > 0.0, name


def test_synthetic_loss_reaches_every_intended_trainable_module(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(
        n=12,
        root=4,
        candidate_topology=COMPACT,
        peer_ids=(0, 1, 2, 3, 5),
        obstacles=((1.0, 0.0, 0.1), (1.4, 0.3, 0.2)),
    )
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch((graph,)))
    synthetic_loss = (
        output.recoverability_logit.square().mean()
        + output.residual_action.square().mean()
        + output.recoverability_logit.mean()
        + output.residual_action.mean()
    )
    assert bool(torch.isfinite(synthetic_loss))
    synthetic_loss.backward()

    for index, projection in enumerate(model.encoder.node_type_projections):
        _assert_module_has_finite_nonzero_gradient(
            projection, f"node_type_projection_{index}"
        )
    for index, projection in enumerate(model.encoder.edge_type_projections):
        _assert_module_has_finite_nonzero_gradient(
            projection, f"edge_type_projection_{index}"
        )
    for index, block in enumerate(model.encoder.message_blocks):
        _assert_module_has_finite_nonzero_gradient(block, f"message_block_{index}")
    _assert_module_has_finite_nonzero_gradient(
        model.candidate_conditioner, "candidate_conditioner"
    )
    _assert_module_has_finite_nonzero_gradient(
        model.recoverability_head, "recoverability_head"
    )
    _assert_module_has_finite_nonzero_gradient(
        model.residual_action_head, "residual_action_head"
    )

def test_mixed_size_all_candidate_forward_backward_matrix(
    fd24_graph_factory, fd24_model_factory
):
    graphs = []
    case = None
    for n in (5, 6, 8, 12, 16, 24):
        for candidate in (KEEP, COMPACT, LINE):
            case, graph = fd24_graph_factory(
                n=n,
                root=n // 2,
                candidate_topology=candidate,
                peer_ids=tuple(
                    robot for robot in range(min(n, 5)) if robot != n // 2
                ),
                obstacles=((1.0, 0.0, 0.1),),
            )
            graphs.append(graph)
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch(graphs))
    loss = output.recoverability_logit.square().mean() + output.residual_action.square().mean()
    loss.backward()
    assert output.recoverability_logit.shape == (18,)
    assert output.residual_action.shape == (18, 2)
    assert all(
        parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )
