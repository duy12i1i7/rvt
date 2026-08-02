"""Robot-local candidate-evidence head contract."""

import torch

from rvt_swarm.fd24.model import (
    FD24_MODEL_OUTPUT_SCHEMA_VERSION,
    prepare_fd24_model_batch,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def test_one_finite_logit_and_sigmoid_probability_per_robot_candidate(
    fd24_graph_factory, fd24_model_factory
):
    graphs = []
    case = None
    for root, candidate in enumerate((KEEP, COMPACT, LINE)):
        case, graph = fd24_graph_factory(root=root, candidate_topology=candidate)
        graphs.append(graph)
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch(graphs))
    assert output.schema_version == FD24_MODEL_OUTPUT_SCHEMA_VERSION
    assert output.recoverability_logit.shape == (3,)
    assert output.recoverability_probability.shape == (3,)
    torch.testing.assert_close(
        output.recoverability_probability,
        torch.sigmoid(output.recoverability_logit),
    )
    assert bool((output.recoverability_probability > 0.0).all())
    assert bool((output.recoverability_probability < 1.0).all())


def test_head_exposes_evidence_not_a_candidate_winner(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch((graph,)))
    candidate = output.candidate_outputs[0]
    assert candidate.observer_robot_id == graph.observer_robot_id
    assert candidate.candidate_topology_id == graph.candidate_topology_id
    assert candidate.validity is True
    assert not hasattr(output, "selected_topology")
    assert not hasattr(output, "global_recoverability")
    assert not hasattr(model.recoverability_head, "softmax")


def test_recoverability_head_gradient_is_finite_and_nonzero(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch((graph,)))
    output.recoverability_logit.sum().backward()
    gradients = [
        parameter.grad
        for parameter in model.recoverability_head.parameters()
    ]
    assert all(gradient is not None for gradient in gradients)
    assert all(bool(torch.isfinite(gradient).all()) for gradient in gradients)
    assert sum(float(gradient.abs().sum()) for gradient in gradients) > 0.0
