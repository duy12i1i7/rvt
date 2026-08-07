"""RB-A.9 / RB-G3 -- the robot-local information boundary, by intervention.

Inspection cannot prove a boundary; mutation can. Each test below changes a
global quantity that robot i is not allowed to observe and asserts that robot
i's controller input is byte-identical afterwards.
"""

from __future__ import annotations

import dataclasses
import json
import math
import pathlib

import pytest

from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.session import SimulatorEpisodeSession
from tests.test_phase9c_publication_executor import build_session, run

ROOT = pathlib.Path("results/rvt_fd24")


def _controller_input(session: SimulatorEpisodeSession, robot_index: int = 0):
    robot = session.robots[robot_index]
    view = session._build_robot_view(robot)
    adapter = robot.adapter_by_topology[robot.committed_topology]
    return adapter.build_input(view, session.time_seconds)


def _fingerprint(controller_input) -> str:
    return json.dumps(dataclasses.asdict(controller_input), sort_keys=True, default=str)


# -- prohibited fields are structurally absent -------------------------------
def test_controller_input_has_no_layout_family_or_headroom_field() -> None:
    session = run(build_session("train-f2-00"), steps=5)
    blob = _fingerprint(_controller_input(session)).lower()
    for prohibited in ("family_id", "headroom", "scenario_layout", "bypass_available",
                       "nominal_passage_width", "world_bounds", "split", "layout_id",
                       "goal_contract", "episode_horizon"):
        assert prohibited not in blob, prohibited


def test_robot_view_exposes_no_joint_state_container() -> None:
    session = run(build_session("train-f2-00"), steps=5)
    view = session._build_robot_view(session.robots[0])
    for field in dataclasses.fields(view):
        value = getattr(view, field.name)
        if field.name in ("neighbours", "obstacles"):
            continue
        assert not hasattr(value, "shape"), field.name


def test_peers_come_from_delivered_messages_not_the_joint_state() -> None:
    """Clearing the neighbour table must empty the peer set even though every
    robot is still physically present in the simulator."""
    session = run(build_session("train-f1-00"), steps=6)
    robot = session.robots[0]
    assert session._build_robot_view(robot).neighbours, "precondition: peers exist"
    robot.neighbour_table.clear()
    assert session._build_robot_view(robot).neighbours == ()
    assert len(session.robots) == 6, "the peers are still physically present"


# -- interventions on unobserved global state --------------------------------
def test_moving_a_far_away_robot_does_not_change_local_input() -> None:
    session = run(build_session("train-f1-00"), steps=6)
    before = _fingerprint(_controller_input(session))
    far = session.robots[-1]
    far.position = (far.position[0] + 500.0, far.position[1] + 500.0)
    assert _fingerprint(_controller_input(session)) == before


def test_mutating_the_binding_family_and_headroom_does_not_change_local_input() -> None:
    session = run(build_session("train-f2-00"), steps=6)
    before = _fingerprint(_controller_input(session))
    object.__setattr__(session.binding, "family", "F99")
    object.__setattr__(session.binding, "layout_id", "mutated")
    assert _fingerprint(_controller_input(session)) == before


def test_future_dynamic_obstacle_waypoints_are_not_visible() -> None:
    session = run(build_session("train-f9-00"), steps=6)
    robot = session.robots[0]
    states = session._dynamic_obstacle_relative_states(robot)
    blob = json.dumps([dataclasses.asdict(s) for s in states], default=str)
    obstacle = session.dynamic_world.obstacles[0]
    for waypoint in obstacle.waypoints[1:]:
        assert str(waypoint[2]) not in blob, "a future waypoint time leaked"
    assert "waypoint" not in blob.lower()


def test_out_of_range_obstacles_are_not_observable() -> None:
    session = run(build_session("train-f7-00"), steps=2)
    robot = session.robots[0]
    sensing = float(session.runtime_config.sensing.obstacle_sensing_range_meters)
    for (ox, oy, _radius) in session._build_robot_view(robot).obstacles:
        assert math.hypot(ox, oy) <= sensing + 1e-9


def test_a_distant_obstacle_added_to_the_world_stays_invisible() -> None:
    from rvt_swarm.phase9c_rb.world import CirclePrimitive

    session = run(build_session("train-f1-00"), steps=4)
    before = _fingerprint(_controller_input(session))
    far_circle = CirclePrimitive(center_meters=(400.0, 400.0), radius_meters=1.0,
                                 primitive_index=99, source_primitive_type="circle")
    object.__setattr__(session.static_world, "circles",
                       session.static_world.circles + (far_circle,))
    assert _fingerprint(_controller_input(session)) == before


def test_evaluator_state_does_not_reach_the_controller_input() -> None:
    session = run(build_session("train-f2-00"), steps=6)
    before = _fingerprint(_controller_input(session))
    session.max_longitudinal_progress += 123.0
    session.deadlock_window_elapsed += 5.0
    session.irreversible_loss_open = True
    session.collision_detected = True
    assert _fingerprint(_controller_input(session)) == before


def test_stale_messages_are_excluded_from_the_local_neighbour_set() -> None:
    session = run(build_session("train-f1-00"), steps=6)
    robot = session.robots[0]
    assert session._build_robot_view(robot).neighbours
    maximum_age = float(session.runtime_config.communication.maximum_message_age_seconds)
    for entry in robot.neighbour_table.values():
        entry["timestamp"] = session.time_seconds - (maximum_age + 1.0)
    assert session._build_robot_view(robot).neighbours == ()


# -- non-vacuity: the boundary is not trivially inert -------------------------
def test_moving_a_near_peer_does_change_local_input() -> None:
    """Guards against a boundary that ignores everything."""
    session = run(build_session("train-f1-00"), steps=6)
    before = _fingerprint(_controller_input(session))
    peer = session.robots[1]
    entry = session.robots[0].neighbour_table.get(peer.robot_id)
    assert entry is not None, "precondition: robot 0 has heard from robot 1"
    entry["position"] = (entry["position"][0] + 0.5, entry["position"][1])
    assert _fingerprint(_controller_input(session)) != before


def test_moving_a_near_obstacle_does_change_local_input() -> None:
    session = run(build_session("train-f7-00"), steps=6)
    before = _fingerprint(_controller_input(session))
    session.robots[0].position = (session.robots[0].position[0] + 1.0,
                                  session.robots[0].position[1])
    assert _fingerprint(_controller_input(session)) != before
