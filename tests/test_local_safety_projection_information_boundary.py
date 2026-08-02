"""Safety projection invariance to unavailable robots and obstacles."""

from dataclasses import replace

import numpy as np
import pytest

from rvt_swarm.decentralized.local_control_types import (
    LocalObstacleControlState,
    LocalPeerControlState,
)


def test_out_of_range_robot_cannot_affect_projection(phase6_input_factory):
    runtime, adapter, _, controller_input = phase6_input_factory()
    proposed = (0.2, -0.1)
    expected = adapter.controller.safety_projection.project(proposed, controller_input)
    outside = LocalPeerControlState(
        peer_robot_id=999,
        relative_position_meters=(runtime.communication.communication_range_meters + 0.01, 0.0),
        relative_velocity_meters_per_second=(-100.0, 0.0),
        message_age_seconds=0.0,
    )
    changed = replace(controller_input, peer_states=controller_input.peer_states + (outside,))
    actual = adapter.controller.safety_projection.project(proposed, changed)
    assert actual.projected_action == pytest.approx(expected.projected_action, abs=1e-12)


def test_unobserved_obstacle_cannot_affect_projection(phase6_input_factory):
    runtime, adapter, _, controller_input = phase6_input_factory()
    proposed = (0.2, 0.0)
    outside = LocalObstacleControlState(
        source_key="outside",
        relative_center_meters=(runtime.sensing.obstacle_sensing_range_meters + 0.01, 0.0),
        radius_meters=100.0,
        relative_velocity_meters_per_second=(-100.0, 0.0),
    )
    changed = replace(controller_input, obstacle_states=(outside,))
    assert adapter.controller.safety_projection.project(proposed, changed).projected_action == pytest.approx(
        adapter.controller.safety_projection.project(proposed, controller_input).projected_action,
        abs=1e-12,
    )


def test_stale_peer_is_more_conservative_than_fresh_peer(phase6_input_factory):
    runtime, adapter, _, controller_input = phase6_input_factory()
    distance = runtime.derived.robot_robot_required_clearance_meters + 0.1
    peer = LocalPeerControlState(1, (distance, 0.0), (0.0, 0.0), 0.0)
    fresh = replace(controller_input, peer_states=(peer,), obstacle_states=())
    stale = replace(
        controller_input,
        peer_states=(replace(peer, message_age_seconds=(
            runtime.communication.maximum_message_age_seconds
            + runtime.communication.communication_period_seconds
        )),),
        obstacle_states=(),
    )
    proposed = (0.0, 0.0)
    fresh_result = adapter.controller.safety_projection.project(proposed, fresh)
    stale_result = adapter.controller.safety_projection.project(proposed, stale)
    assert stale_result.intervened
    assert stale_result.constraints[0].required_clearance_meters > (
        fresh_result.constraints[0].required_clearance_meters
    )


def test_constraint_order_does_not_change_projection(phase6_input_factory):
    _, adapter, _, controller_input = phase6_input_factory()
    a = LocalObstacleControlState("a", (0.7, 0.2), 0.35, (0.0, 0.0))
    b = LocalObstacleControlState("b", (0.8, -0.3), 0.35, (0.0, 0.0))
    first = replace(controller_input, peer_states=(), obstacle_states=(a, b))
    second = replace(controller_input, peer_states=(), obstacle_states=(b, a))
    proposed = (0.4, 0.0)
    result_a = adapter.controller.safety_projection.project(proposed, first)
    result_b = adapter.controller.safety_projection.project(proposed, second)
    np.testing.assert_allclose(result_a.projected_action, result_b.projected_action, atol=1e-12)


def test_translation_does_not_change_relative_projection(phase6_input_factory):
    _, adapter, _, controller_input = phase6_input_factory()
    translated = replace(
        controller_input,
        own_position_meters=(controller_input.own_position_meters[0] + 10.0,
                             controller_input.own_position_meters[1] - 7.0),
    )
    proposed = (0.2, 0.1)
    assert adapter.controller.safety_projection.project(proposed, translated).projected_action == pytest.approx(
        adapter.controller.safety_projection.project(proposed, controller_input).projected_action,
        abs=1e-12,
    )
