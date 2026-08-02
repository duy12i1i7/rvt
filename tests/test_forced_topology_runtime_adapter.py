"""Forced topology is immutable and each adapter invokes one local controller."""

import inspect
from dataclasses import replace
from unittest.mock import Mock

import numpy as np
import pytest

from rvt_swarm.decentralized.forced_topology_runtime import ForcedTopologyRuntimeAdapter
from rvt_swarm.decentralized.robot_local_controller import RobotLocalController
from rvt_swarm.decentralized.system_model import CentralizedAccessError
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


@pytest.mark.parametrize("topology", (KEEP, COMPACT, LINE))
def test_adapter_invokes_controller_once_for_one_robot(phase6_input_factory, topology):
    runtime, adapter, view, controller_input = phase6_input_factory(topology=topology)
    expected = adapter.controller.evaluate(controller_input)
    spy = Mock(spec=RobotLocalController)
    spy.evaluate.return_value = expected
    bound = ForcedTopologyRuntimeAdapter(
        runtime,
        adapter.local_topology_metadata,
        topology,
        controller=spy,
    )
    actual = bound.evaluate(view, 0.0)
    assert actual == expected
    spy.evaluate.assert_called_once()
    passed = spy.evaluate.call_args.args[0]
    assert passed.observer_robot_id == view.robot_id
    assert passed.forced_topology_id == topology


def test_topology_is_bound_once_and_cannot_be_changed_online(phase6_input_factory):
    _, adapter, view, _ = phase6_input_factory(topology=COMPACT)
    output_a = adapter.evaluate(view, 0.0)
    output_b = adapter.evaluate(replace(view, committed_mode=KEEP), 0.15)
    assert output_a.forced_topology_id == output_b.forced_topology_id == COMPACT


def test_joint_observation_dictionary_is_rejected(phase6_input_factory):
    _, adapter, _, _ = phase6_input_factory()
    with pytest.raises(CentralizedAccessError):
        adapter.evaluate({"positions": np.zeros((6, 2))}, 0.0)


def test_model_output_has_no_adapter_input_path():
    signature = inspect.signature(ForcedTopologyRuntimeAdapter.evaluate)
    assert tuple(signature.parameters) == ("self", "view", "timestamp_seconds")
    source = inspect.getsource(ForcedTopologyRuntimeAdapter)
    assert "RVTFD24" not in source
    assert "recoverability" not in source
    assert "residual_action" not in source


def test_controller_output_is_one_robot_action(phase6_input_factory):
    _, adapter, view, _ = phase6_input_factory(n=24, topology=LINE)
    output = adapter.evaluate(view, 0.0)
    assert np.asarray(output.projected_action).shape == (2,)
    assert output.observer_robot_id == view.robot_id
    assert not hasattr(output, "joint_action")
