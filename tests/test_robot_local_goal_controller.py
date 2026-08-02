"""Robot-local static topology-origin goal semantics."""

from dataclasses import replace

import numpy as np
import pytest

from rvt_swarm.decentralized.robot_local_controller import (
    robot_local_damping_term,
    robot_local_goal_term,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


@pytest.mark.parametrize("topology", (KEEP, COMPACT, LINE))
def test_exact_role_target_has_zero_goal_term(phase6_input_factory, topology):
    runtime, _, _, controller_input = phase6_input_factory(topology=topology)
    term, target = robot_local_goal_term(controller_input, runtime)
    np.testing.assert_allclose(term, (0.0, 0.0), atol=1e-12)
    np.testing.assert_allclose(target, controller_input.own_position_meters, atol=1e-12)


def test_shared_goal_is_topology_origin_not_common_robot_point(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory(topology=KEEP, goal=(2.0, 0.0))
    term, target = robot_local_goal_term(controller_input, runtime)
    assert target[0] == pytest.approx(controller_input.own_position_meters[0] + 2.0)
    assert term[0] > 0.0


def test_translation_invariance(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory(topology=COMPACT, goal=(2.0, 1.0))
    expected = robot_local_goal_term(controller_input, runtime)[0]
    shift = (7.0, -3.0)
    translated = replace(
        controller_input,
        own_position_meters=(controller_input.own_position_meters[0] + shift[0],
                             controller_input.own_position_meters[1] + shift[1]),
        shared_goal_origin_meters=(controller_input.shared_goal_origin_meters[0] + shift[0],
                                   controller_input.shared_goal_origin_meters[1] + shift[1]),
    )
    assert robot_local_goal_term(translated, runtime)[0] == pytest.approx(expected, abs=1e-12)


def test_rotation_consistency(phase6_input_factory):
    runtime_a, _, _, input_a = phase6_input_factory(topology=LINE, goal=(2.0, 0.0))
    runtime_b, _, _, input_b = phase6_input_factory(
        topology=LINE,
        mission_direction=(0.0, 1.0),
        goal=(0.0, 2.0),
    )
    action_a = robot_local_goal_term(input_a, runtime_a)[0]
    action_b = robot_local_goal_term(input_b, runtime_b)[0]
    np.testing.assert_allclose(action_b, (-action_a[1], action_a[0]), atol=1e-12)


def test_damping_opposes_own_velocity(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory()
    moving = replace(controller_input, own_velocity_meters_per_second=(0.3, -0.2))
    damping = robot_local_damping_term(moving, runtime)
    assert damping[0] < 0.0 and damping[1] > 0.0
