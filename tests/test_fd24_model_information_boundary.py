"""Actual builder-to-model intervention invariance tests."""

import pytest
import torch

from rvt_swarm.fd24.model import prepare_fd24_model_batch


def _output(model, graph):
    model.eval()
    result = model(prepare_fd24_model_batch((graph,)))
    return (
        result.recoverability_logit.detach().clone(),
        result.residual_action.detach().clone(),
    )


@pytest.mark.parametrize(
    "external_variable",
    (
        "out_of_range_robot",
        "unobserved_obstacle",
        "global_centroid",
        "global_formation_error",
        "unobserved_role",
        "evaluation_label",
        "simulator_global_ordering",
    ),
)
def test_unobserved_and_evaluation_interventions_have_no_model_channel(
    fd24_graph_factory, fd24_model_factory, external_variable
):
    case, graph = fd24_graph_factory(peer_ids=(), obstacles=())
    model = fd24_model_factory(case.config)
    external_state = {external_variable: "before"}
    before = _output(model, graph)
    external_state[external_variable] = "after"
    after = _output(model, graph)
    assert external_state[external_variable] == "after"
    torch.testing.assert_close(before[0], after[0], rtol=0.0, atol=0.0)
    torch.testing.assert_close(before[1], after[1], rtol=0.0, atol=0.0)


def test_local_fresh_peer_changes_actual_model_representation(
    fd24_graph_factory, fd24_model_factory
):
    case_a, graph_a = fd24_graph_factory(
        peer_ids=(1,), peer_local_positions={1: (0.8, 0.0)}
    )
    _, graph_b = fd24_graph_factory(
        peer_ids=(1,), peer_local_positions={1: (1.4, 0.3)}
    )
    model = fd24_model_factory(case_a.config)
    model.eval()
    a = model.conditioned_representation(prepare_fd24_model_batch((graph_a,)))
    b = model.conditioned_representation(prepare_fd24_model_batch((graph_b,)))
    assert not torch.equal(a, b)

def test_local_obstacle_changes_actual_model_representation(
    fd24_graph_factory, fd24_model_factory
):
    case_a, graph_a = fd24_graph_factory(
        peer_ids=(), obstacles=((1.0, 0.0, 0.1),)
    )
    _, graph_b = fd24_graph_factory(
        peer_ids=(), obstacles=((1.8, 0.4, 0.3),)
    )
    model = fd24_model_factory(case_a.config)
    model.eval()
    a = model.conditioned_representation(prepare_fd24_model_batch((graph_a,)))
    b = model.conditioned_representation(prepare_fd24_model_batch((graph_b,)))
    assert not torch.equal(a, b)
