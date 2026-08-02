"""Separate local invocations cannot exchange state through the controller."""

from dataclasses import replace

import numpy as np
import pytest

from rvt_swarm.decentralized.local_control_types import LocalPeerControlState
from rvt_swarm.decentralized.robot_local_controller import RobotLocalController
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def test_adding_unrelated_robot_does_not_change_action(phase6_input_factory):
    runtime, adapter, _, controller_input = phase6_input_factory(topology=COMPACT)
    expected = adapter.controller.evaluate(controller_input).projected_action
    unrelated = LocalPeerControlState(
        999,
        (runtime.communication.communication_range_meters + 1.0, 0.0),
        (100.0, 0.0),
        0.0,
    )
    changed = replace(controller_input, peer_states=controller_input.peer_states + (unrelated,))
    assert adapter.controller.evaluate(changed).projected_action == pytest.approx(expected, abs=1e-12)


def test_invocation_order_does_not_change_outputs(phase6_input_factory):
    _, adapter_a, _, input_a = phase6_input_factory(robot_id=0, topology=KEEP)
    _, adapter_b, _, input_b = phase6_input_factory(robot_id=1, topology=KEEP)
    first = (
        adapter_a.controller.evaluate(input_a).projected_action,
        adapter_b.controller.evaluate(input_b).projected_action,
    )
    second_b = adapter_b.controller.evaluate(input_b).projected_action
    second_a = adapter_a.controller.evaluate(input_a).projected_action
    np.testing.assert_allclose((second_a, second_b), first, atol=1e-12)


@pytest.mark.parametrize("topology", (KEEP, COMPACT, LINE))
def test_controller_has_no_mutable_cross_robot_state(phase6_input_factory, topology):
    runtime, _, _, controller_input = phase6_input_factory(topology=topology)
    shared = RobotLocalController(runtime)
    before = dict(shared.__dict__)
    shared.evaluate(controller_input)
    after = dict(shared.__dict__)
    assert before.keys() == after.keys()
    assert shared.runtime_config is before["runtime_config"]
    assert shared.runtime_config_sha256 == before["runtime_config_sha256"]


def test_mixed_team_size_orchestration_keeps_local_calls_separate(phase6_input_factory):
    _, adapter_five, _, input_five = phase6_input_factory(n=5, topology=LINE)
    _, adapter_twenty_four, _, input_twenty_four = phase6_input_factory(n=24, topology=LINE)
    expected = adapter_five.controller.evaluate(input_five).projected_action
    adapter_twenty_four.controller.evaluate(input_twenty_four)
    actual = adapter_five.controller.evaluate(input_five).projected_action
    assert actual == pytest.approx(expected, abs=1e-12)
