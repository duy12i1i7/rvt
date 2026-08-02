"""Local obstacle response uses only accepted sensor primitives."""

from dataclasses import replace

import numpy as np
import pytest

from rvt_swarm.decentralized.local_control_types import LocalObstacleControlState
from rvt_swarm.decentralized.robot_local_controller import robot_local_obstacle_term
from rvt_swarm.topology_registry import PRIMARY_TOPOLOGY_IDS


def obstacle(key, center, *, valid=True):
    return LocalObstacleControlState(
        source_key=key,
        relative_center_meters=center,
        radius_meters=0.35,
        relative_velocity_meters_per_second=(0.0, 0.0),
        valid=valid,
    )


def test_no_obstacle_gives_exact_zero(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory()
    assert robot_local_obstacle_term(controller_input, runtime) == ((0.0, 0.0), 0)


def test_closer_obstacle_increases_response(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory()
    far = replace(controller_input, obstacle_states=(obstacle("far", (1.1, 0.0)),))
    close = replace(controller_input, obstacle_states=(obstacle("close", (0.7, 0.0)),))
    far_term = np.linalg.norm(robot_local_obstacle_term(far, runtime)[0])
    close_term = np.linalg.norm(robot_local_obstacle_term(close, runtime)[0])
    assert close_term > far_term > 0.0


def test_out_of_range_and_invalid_obstacles_have_no_effect(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory()
    outside = obstacle(
        "outside",
        (runtime.sensing.obstacle_sensing_range_meters + 0.1, 0.0),
    )
    invalid = obstacle("invalid", (0.6, 0.0), valid=False)
    changed = replace(controller_input, obstacle_states=(outside, invalid))
    assert robot_local_obstacle_term(changed, runtime) == ((0.0, 0.0), 0)


def test_obstacle_order_is_invariant(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory()
    first = obstacle("a", (0.7, 0.2))
    second = obstacle("b", (0.8, -0.3))
    a = replace(controller_input, obstacle_states=(first, second))
    b = replace(controller_input, obstacle_states=(second, first))
    assert robot_local_obstacle_term(a, runtime)[0] == pytest.approx(
        robot_local_obstacle_term(b, runtime)[0], abs=1e-12
    )


def test_obstacle_response_rotates_consistently(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory()
    a = replace(controller_input, obstacle_states=(obstacle("x", (0.7, 0.0)),))
    b = replace(controller_input, obstacle_states=(obstacle("x", (0.0, 0.7)),))
    response_a = robot_local_obstacle_term(a, runtime)[0]
    response_b = robot_local_obstacle_term(b, runtime)[0]
    np.testing.assert_allclose(response_b, (-response_a[1], response_a[0]), atol=1e-12)


@pytest.mark.parametrize("topology_id", PRIMARY_TOPOLOGY_IDS)
def test_obstacle_response_is_shared_across_primary_topologies(
    phase6_input_factory,
    topology_id,
):
    runtime, _, _, controller_input = phase6_input_factory(topology=topology_id)
    local = replace(
        controller_input,
        obstacle_states=(obstacle("shared", (0.7, 0.2)),),
    )
    expected = robot_local_obstacle_term(local, runtime)

    _, _, _, keep_input = phase6_input_factory(topology=PRIMARY_TOPOLOGY_IDS[0])
    keep_local = replace(
        keep_input,
        obstacle_states=(obstacle("shared", (0.7, 0.2)),),
    )
    actual = robot_local_obstacle_term(keep_local, runtime)

    np.testing.assert_allclose(expected[0], actual[0], atol=1e-12)
    assert expected[1] == actual[1]
