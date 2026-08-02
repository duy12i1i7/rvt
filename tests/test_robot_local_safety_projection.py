"""Correctness properties of the exact one-robot safety projection."""

from dataclasses import replace

import numpy as np
import pytest

from rvt_swarm.decentralized.local_control_types import (
    LocalObstacleControlState,
    LocalPeerControlState,
)
from rvt_swarm.decentralized.phase6_qualification import (
    run_phase6_safety_stress_case,
)


def local_obstacle(key, center, relative_velocity=(0.0, 0.0)):
    return LocalObstacleControlState(
        source_key=key,
        relative_center_meters=center,
        radius_meters=0.35,
        relative_velocity_meters_per_second=relative_velocity,
    )


def test_safe_action_with_no_active_constraint_is_unchanged(phase6_input_factory):
    _, adapter, _, controller_input = phase6_input_factory()
    result = adapter.controller.safety_projection.project((0.1, -0.1), controller_input)
    assert result.projected_action == pytest.approx((0.1, -0.1), abs=1e-12)
    assert not result.intervened
    assert result.status == "unchanged"


def test_physical_bound_is_enforced(phase6_input_factory):
    runtime, adapter, _, controller_input = phase6_input_factory()
    result = adapter.controller.safety_projection.project((10.0, -10.0), controller_input)
    assert np.linalg.norm(result.projected_action) <= (
        runtime.physical.maximum_acceleration_meters_per_second_squared + 1e-12
    )
    assert result.intervened
    assert result.status == "physical_bound_projection"


def test_action_toward_close_obstacle_is_modified(phase6_input_factory):
    runtime, adapter, _, controller_input = phase6_input_factory()
    moving = replace(
        controller_input,
        own_velocity_meters_per_second=(runtime.physical.maximum_speed_meters_per_second, 0.0),
        peer_states=(),
        obstacle_states=(local_obstacle(
            "ahead",
            (runtime.derived.robot_obstacle_required_clearance_meters + 0.01, 0.0),
            (-runtime.physical.maximum_speed_meters_per_second, 0.0),
        ),),
    )
    result = adapter.controller.safety_projection.project((0.4, 0.0), moving)
    assert result.intervened
    assert result.projected_action[0] < 0.0
    assert result.infeasible


def test_action_toward_close_fresh_peer_is_modified(phase6_input_factory):
    runtime, adapter, _, controller_input = phase6_input_factory()
    peer = LocalPeerControlState(
        peer_robot_id=1,
        relative_position_meters=(runtime.derived.robot_robot_required_clearance_meters, 0.0),
        relative_velocity_meters_per_second=(0.0, 0.0),
        message_age_seconds=0.0,
    )
    local = replace(controller_input, peer_states=(peer,), obstacle_states=())
    result = adapter.controller.safety_projection.project((0.4, 0.0), local)
    assert result.intervened
    assert result.projected_action[0] <= -runtime.physical.maximum_acceleration_meters_per_second_squared + 1e-12


def test_infeasible_constraints_use_explicit_bounded_fallback(phase6_input_factory):
    runtime, adapter, _, controller_input = phase6_input_factory()
    clearance = runtime.derived.robot_obstacle_required_clearance_meters
    blocked = replace(
        controller_input,
        peer_states=(),
        obstacle_states=(
            local_obstacle("left", (-clearance + 0.01, 0.0)),
            local_obstacle("right", (clearance - 0.01, 0.0)),
        ),
    )
    proposed = (0.2, 0.0)
    result = adapter.controller.safety_projection.project(proposed, blocked)
    assert result.infeasible
    assert result.intervened
    assert result.status == "infeasible_conservative_fallback"
    assert result.projected_action != pytest.approx(proposed)
    assert np.isfinite(result.projected_action).all()
    assert np.linalg.norm(result.projected_action) <= (
        runtime.physical.maximum_acceleration_meters_per_second_squared + 1e-12
    )


def test_nonfinite_proposed_action_fails_closed(phase6_input_factory):
    _, adapter, _, controller_input = phase6_input_factory()
    result = adapter.controller.safety_projection.project((float("nan"), 0.0), controller_input)
    assert result.projected_action == (0.0, 0.0)
    assert result.solver_failed and result.intervened
    assert result.status == "invalid_proposed_action_fail_closed"


@pytest.mark.parametrize("case_name", ("two_sided_restriction", "moving_obstacle"))
def test_declared_feasible_stress_hazard_is_mitigated(case_name):
    base = run_phase6_safety_stress_case(case_name, projection_enabled=False)
    projected = run_phase6_safety_stress_case(case_name, projection_enabled=True)

    assert base.collision_after_step
    assert not projected.collision_after_step
    assert projected.intervention_step == 0
    assert not projected.infeasible_fallback
    assert not projected.solver_failure


def test_safe_stress_uses_not_applicable_clearance_instead_of_infinity():
    result = run_phase6_safety_stress_case("safe_open", projection_enabled=True)
    assert result.minimum_clearance_meters is None
    assert not result.false_intervention
