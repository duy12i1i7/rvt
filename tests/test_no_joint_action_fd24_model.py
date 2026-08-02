"""The FD24 model emits one robot action correction per local graph."""

import inspect

import torch

from rvt_swarm.decentralized import guards
from rvt_swarm.fd24.configuration import ROBOT_LOCAL_ACTION_COMPONENTS
from rvt_swarm.fd24.model import RVTFD24LocalModel, prepare_fd24_model_batch
from test_no_global_pooling_fd24_model import injected_fd24_module, _kinds


def test_output_shape_is_graph_count_by_robot_action_dimension(
    fd24_graph_factory, fd24_model_factory
):
    case, graph_a = fd24_graph_factory(
        n=24, root=0, peer_ids=tuple(range(1, 24))
    )
    _, graph_b = fd24_graph_factory(n=5, root=2, peer_ids=())
    model = fd24_model_factory(case.config)
    output = model(prepare_fd24_model_batch((graph_a, graph_b)))
    assert output.residual_action.shape == (
        2,
        len(ROBOT_LOCAL_ACTION_COMPONENTS),
    )
    assert output.residual_action.shape[0] != graph_a.n_nodes + graph_b.n_nodes
    assert not hasattr(output, "joint_action")


def test_model_action_width_is_independent_of_team_size(
    fd24_graph_factory, fd24_model_factory
):
    dimensions = set()
    for n in (5, 6, 8, 12, 16, 24):
        case, graph = fd24_graph_factory(n=n)
        model = fd24_model_factory(case.config)
        output = model(prepare_fd24_model_batch((graph,)))
        dimensions.add(output.residual_action.shape[1])
    assert dimensions == {2}


def test_model_source_has_no_robot_count_dependent_action_head():
    source = inspect.getsource(RVTFD24LocalModel)
    assert "n_robots" not in source
    assert "team_size" not in source
    assert "joint_action" not in source


def test_guard_detects_injected_joint_action_output():
    with injected_fd24_module(
        "def joint_action_output(n_robots: int, action_dim: int):\n"
        "    return torch.zeros((n_robots, action_dim))\n"
    ):
        violations = guards.audit()
    assert "joint-action-output" in _kinds(violations), violations


def test_candidate_outputs_never_contain_another_robot_action(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory(n=12, root=7, peer_ids=(0, 1, 2, 3))
    model = fd24_model_factory(case.config)
    candidate = model(prepare_fd24_model_batch((graph,))).candidate_outputs[0]
    assert candidate.observer_robot_id == 7
    assert candidate.residual_action.shape == torch.Size((2,))
