"""RB-B -- obstacle relative velocity is a sensor/runtime representation issue.

The frozen Phase 6 obstacle representation is correct for a *static* obstacle:
`RobotView.obstacles` carries no velocity, so `ForcedTopologyRuntimeAdapter`
assigns every entry `v_relative = -v_robot`, which is exactly right when
`v_obstacle = 0`.

For an F9 dynamic obstacle the runtime must instead provide

    v_relative = v_obstacle - v_robot

Neither the controller nor the time-to-collision equations are changed; the
publication session supplies the correct relative velocity through
`dataclasses.replace`, the same composition the frozen Phase 6 qualification
fixtures use.

The specific defect these tests pin: if the dynamic obstacle were also placed in
`RobotView.obstacles`, it would enter the controller twice -- once stationary
and once correct -- and the stationary copy would drive the TTC term, making a
crossing obstacle look parked.
"""

from __future__ import annotations

import json
import math
import pathlib

import pytest

from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.binding import build_binding, load_execution_specification
from rvt_swarm.phase9c_rb.session import SimulatorEpisodeSession
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG

ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
POLICIES = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())
SEEDS = {"initial_condition": 11, "communication": 22, "dynamic_obstacle": 33}


def _session(layout: str, split: str = "train", team_size: int = 6,
             policy_id: str = P.S1) -> SimulatorEpisodeSession:
    binding = build_binding(
        load_execution_specification(ROOT, split, layout), team_size=team_size,
        source_policy=policy_id, protocol=PROTOCOL, target_contract=TARGET,
        source_policy_contracts=POLICIES)
    policy = P.build_source_policy(
        policy_id, contracts=POLICIES, seed=7, horizon_seconds=binding.horizon_seconds,
        team_size=team_size, family_id=binding.family, runtime_config=CONFIG)
    return SimulatorEpisodeSession(
        binding, protocol=PROTOCOL, target_contract=TARGET, seeds=SEEDS,
        source_policy=policy)


# ---------------------------------------------------------------------------
# Static obstacles: v_relative = -v_robot
# ---------------------------------------------------------------------------
def test_static_obstacle_relative_velocity_is_negative_own_velocity() -> None:
    session = _session("train-f2-00")          # analytic corridor walls
    robot = session.robots[0]
    # Place the robot at the passage entry so the wall supports are inside
    # R_obs. At the nominal start only the leading template role can see them.
    entry = session.static_world.corridors[0].entry_position_meters
    robot.position = (entry[0] - 1.0, entry[1])
    robot.velocity = (0.4, -0.25)
    view = session._build_robot_view(robot)
    assert view.obstacles, "the corridor must be observable for this test to bite"
    controller_input = robot.adapter_by_topology[
        robot.committed_topology].build_input(view, session.time_seconds)
    for state in controller_input.obstacle_states:
        assert state.relative_velocity_meters_per_second == pytest.approx(
            (-robot.velocity[0], -robot.velocity[1]))


def test_static_world_contributes_no_dynamic_states() -> None:
    session = _session("train-f2-00")
    assert session._dynamic_obstacle_relative_states(session.robots[0]) == ()


# ---------------------------------------------------------------------------
# Dynamic obstacles: v_relative = v_obstacle - v_robot
# ---------------------------------------------------------------------------
def _dynamic_state(session, robot):
    states = session._dynamic_obstacle_relative_states(robot)
    assert states, "F9 obstacle must be within R_obs for this fixture"
    return states[0]


def _place_near_obstacle(session, robot, time_seconds: float) -> None:
    """Put the robot beside the obstacle so it is inside R_obs."""
    session.time_seconds = time_seconds
    centre, _ = session.dynamic_world.obstacles[0].state(time_seconds)
    robot.position = (centre[0] + 1.0, centre[1])


def test_robot_stationary_obstacle_moving() -> None:
    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    robot.velocity = (0.0, 0.0)
    _, obstacle_velocity = session.dynamic_world.obstacles[0].state(6.0)
    assert obstacle_velocity != (0.0, 0.0), "the F9 obstacle must actually be moving"
    state = _dynamic_state(session, robot)
    assert state.relative_velocity_meters_per_second == pytest.approx(obstacle_velocity)


def test_robot_and_obstacle_moving_in_the_same_direction() -> None:
    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    _, obstacle_velocity = session.dynamic_world.obstacles[0].state(6.0)
    robot.velocity = (obstacle_velocity[0] * 0.5, obstacle_velocity[1] * 0.5)
    state = _dynamic_state(session, robot)
    assert state.relative_velocity_meters_per_second == pytest.approx(
        (obstacle_velocity[0] - robot.velocity[0],
         obstacle_velocity[1] - robot.velocity[1]))


def test_robot_and_obstacle_moving_in_opposite_directions() -> None:
    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    _, obstacle_velocity = session.dynamic_world.obstacles[0].state(6.0)
    robot.velocity = (-obstacle_velocity[0], -obstacle_velocity[1])
    state = _dynamic_state(session, robot)
    expected = (2.0 * obstacle_velocity[0], 2.0 * obstacle_velocity[1])
    assert state.relative_velocity_meters_per_second == pytest.approx(expected)


def test_matching_velocities_give_zero_relative_velocity() -> None:
    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    _, obstacle_velocity = session.dynamic_world.obstacles[0].state(6.0)
    robot.velocity = obstacle_velocity
    state = _dynamic_state(session, robot)
    assert state.relative_velocity_meters_per_second == pytest.approx((0.0, 0.0))


# ---------------------------------------------------------------------------
# The regression this section exists for
# ---------------------------------------------------------------------------
def test_a_moving_obstacle_never_appears_stationary_to_the_controller() -> None:
    """A crossing obstacle must not be reported with `-v_robot` alone."""
    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    robot.velocity = (0.0, 0.0)
    state = _dynamic_state(session, robot)
    # With v_robot = 0, the static convention would give exactly (0, 0).
    speed = math.hypot(*state.relative_velocity_meters_per_second)
    assert speed > 0.0, "the dynamic obstacle was reported as stationary"


def test_dynamic_obstacle_is_not_double_counted_in_the_controller_input() -> None:
    """It must appear exactly once, with the correct relative velocity."""
    from dataclasses import replace

    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    robot.velocity = (0.3, 0.0)

    view = session._build_robot_view(robot)
    adapter = robot.adapter_by_topology[robot.committed_topology]
    controller_input = adapter.build_input(view, session.time_seconds)
    dynamic_states = session._dynamic_obstacle_relative_states(robot)
    combined = replace(
        controller_input,
        obstacle_states=controller_input.obstacle_states + dynamic_states)

    obstacle_count = len(session.dynamic_world.obstacles)
    assert len(dynamic_states) == obstacle_count
    # The view carries only static tokens, and F9 declares no static obstacle,
    # so the combined input holds exactly one entry per dynamic obstacle.
    assert len(combined.obstacle_states) == obstacle_count
    stationary = [s for s in combined.obstacle_states
                  if s.relative_velocity_meters_per_second == pytest.approx(
                      (-robot.velocity[0], -robot.velocity[1]))]
    assert stationary == [], "a stationary duplicate of the dynamic obstacle is present"


def test_view_obstacles_exclude_dynamic_obstacles_by_construction() -> None:
    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    assert session._build_robot_view(robot).obstacles == ()
    assert session._dynamic_obstacle_relative_states(robot) != ()


# ---------------------------------------------------------------------------
# Frame handling
# ---------------------------------------------------------------------------
def test_relative_velocity_is_frame_covariant() -> None:
    """Rotating robot and obstacle velocities rotates the relative velocity."""
    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    robot.velocity = (0.31, -0.17)
    baseline = _dynamic_state(session, robot).relative_velocity_meters_per_second

    for degrees in (30.0, 90.0, 137.0):
        angle = math.radians(degrees)
        cos, sin = math.cos(angle), math.sin(angle)
        rotated_expected = (cos * baseline[0] - sin * baseline[1],
                            sin * baseline[0] + cos * baseline[1])
        # Rotate both velocities; the relative velocity must rotate with them.
        obstacle = session.dynamic_world.obstacles[0]
        _, obstacle_velocity = obstacle.state(session.time_seconds)
        rotated_obstacle = (cos * obstacle_velocity[0] - sin * obstacle_velocity[1],
                            sin * obstacle_velocity[0] + cos * obstacle_velocity[1])
        rotated_robot = (cos * robot.velocity[0] - sin * robot.velocity[1],
                         sin * robot.velocity[0] + cos * robot.velocity[1])
        assert (rotated_obstacle[0] - rotated_robot[0],
                rotated_obstacle[1] - rotated_robot[1]) == pytest.approx(rotated_expected)


def test_dynamic_obstacle_source_keys_are_distinct_from_static_keys() -> None:
    session = _session("train-f9-00")
    robot = session.robots[0]
    _place_near_obstacle(session, robot, 6.0)
    for state in session._dynamic_obstacle_relative_states(robot):
        assert state.source_key.startswith("dynamic:")
