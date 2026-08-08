"""RB-A.3-8 -- publication executor: initialization, forced topologies, F8/F9,
and all six source policies executing beyond simulator step 0.

These replace the blocked phase's direct-execution evidence, which RB-A says may
not count as a passing gate.
"""

from __future__ import annotations

import json
import math
import pathlib

import pytest

from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.binding import build_binding, load_execution_specification
from rvt_swarm.phase9c_rb.session import SimulatorEpisodeSession, build_event_plan
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG
from rvt_swarm.topology_registry import COMPACT, LINE

ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
POLICIES = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())
SEEDS = {"initial_condition": 11, "communication": 22, "dynamic_obstacle": 33}


def build_session(layout: str, split: str = "train", team_size: int = 6,
                  policy_id: str = P.S1, seeds=None) -> SimulatorEpisodeSession:
    binding = build_binding(
        load_execution_specification(ROOT, split, layout), team_size=team_size,
        source_policy=policy_id, protocol=PROTOCOL, target_contract=TARGET,
        source_policy_contracts=POLICIES)
    plan = build_event_plan(binding, POLICIES) if policy_id == P.S0 else ()
    policy = P.build_source_policy(
        policy_id, contracts=POLICIES, seed=7, horizon_seconds=binding.horizon_seconds,
        team_size=team_size, family_id=binding.family, runtime_config=CONFIG,
        event_plan=plan)
    return SimulatorEpisodeSession(
        binding, protocol=PROTOCOL, target_contract=TARGET, seeds=seeds or SEEDS,
        source_policy=policy)


def run(session, steps: int = 60):
    for _ in range(steps):
        session.step()
        if session.termination is not None:
            break
    return session


# -- initialization ----------------------------------------------------------
def test_executor_initializes_all_robots_at_compact() -> None:
    session = build_session("train-f1-00")
    assert len(session.robots) == 6
    assert all(r.committed_topology == COMPACT for r in session.robots)
    assert session.control_step == 0 and session.time_seconds == 0.0
    assert session.termination is None


def test_initial_positions_are_perturbed_within_the_declared_bound() -> None:
    session = build_session("train-f1-00")
    bound = float(session.binding.initialization["position_perturbation_bound_meters"])
    for robot, nominal in zip(session.robots, session.binding.nominal_positions):
        assert math.dist(robot.position, nominal) <= bound * math.sqrt(2.0) + 1e-9


def test_initial_speed_never_exceeds_the_platform_maximum() -> None:
    maximum = float(CONFIG.physical.maximum_speed_meters_per_second)
    for team_size in (5, 6, 8, 12):
        session = build_session("train-f1-00", team_size=team_size)
        for robot in session.robots:
            assert math.hypot(*robot.velocity) <= maximum + 1e-9


def test_initialization_is_deterministic_from_the_seed() -> None:
    a = build_session("train-f1-00")
    b = build_session("train-f1-00")
    assert [r.position for r in a.robots] == [r.position for r in b.robots]
    assert [r.velocity for r in a.robots] == [r.velocity for r in b.robots]


def test_a_different_seed_gives_a_different_initial_state() -> None:
    a = build_session("train-f1-00")
    b = build_session("train-f1-00", seeds={**SEEDS, "initial_condition": 999})
    assert [r.position for r in a.robots] != [r.position for r in b.robots]


# -- RB-A.4 / RB-A.5 forced topologies ---------------------------------------
@pytest.mark.parametrize("policy_id,topology", [(P.S1, COMPACT), (P.S2, LINE)])
def test_forced_topology_executes_beyond_step_zero(policy_id, topology) -> None:
    session = run(build_session("train-f1-00", policy_id=policy_id), steps=30)
    assert session.control_step > 0
    assert session.time_seconds == pytest.approx(
        session.control_step * float(CONFIG.physical.control_period_seconds))


def test_forced_policies_perform_no_topology_selection() -> None:
    """S1 creates no epoch at all. S2 creates exactly one *mechanical*
    initialization epoch to realize its fixed LINE target from the common
    COMPACT start -- never a selection epoch."""
    s1 = run(build_session("train-f1-00", policy_id=P.S1), steps=40)
    assert s1.event_log == []
    assert s1.topology_selection_epoch_count == 0
    assert s1.mechanical_transition_epoch_count == 0
    s2 = run(build_session("train-f1-00", policy_id=P.S2), steps=40)
    assert s2.topology_selection_epoch_count == 0
    assert s2.mechanical_transition_epoch_count == 1


def test_open_field_mission_reaches_the_goal() -> None:
    session = run(build_session("train-f1-00", policy_id=P.S1), steps=400)
    assert session.termination is not None
    assert session.termination.cause == "GOAL_COMPLETE"


# -- RB-A.8: all six policies execute beyond step 0 --------------------------
@pytest.mark.parametrize("policy_id", P.ALL_SOURCE_POLICIES)
def test_every_source_policy_executes_beyond_step_zero(policy_id) -> None:
    session = run(build_session("train-f1-00", policy_id=policy_id), steps=25)
    assert session.control_step > 0, policy_id
    assert session.numerically_valid


@pytest.mark.parametrize("policy_id", P.ALL_SOURCE_POLICIES)
def test_every_source_policy_keeps_state_finite(policy_id) -> None:
    session = run(build_session("train-f2-00", policy_id=policy_id), steps=25)
    for robot in session.robots:
        assert all(math.isfinite(v) for v in robot.position + robot.velocity)


# -- integration matches the frozen environment step -------------------------
def test_integration_is_the_frozen_semi_implicit_step() -> None:
    session = build_session("train-f1-00")
    robot = session.robots[0]
    before_position, before_velocity = robot.position, robot.velocity
    session.step()
    dt = float(CONFIG.physical.control_period_seconds)
    expected_velocity = (before_velocity[0] + robot.acceleration[0] * dt,
                         before_velocity[1] + robot.acceleration[1] * dt)
    speed = math.hypot(*expected_velocity)
    maximum = float(CONFIG.physical.maximum_speed_meters_per_second)
    if speed > maximum:
        expected_velocity = (expected_velocity[0] / speed * maximum,
                             expected_velocity[1] / speed * maximum)
    assert robot.velocity == pytest.approx(expected_velocity)
    assert robot.position == pytest.approx(
        (before_position[0] + robot.velocity[0] * dt,
         before_position[1] + robot.velocity[1] * dt))


def test_acceleration_never_exceeds_the_platform_maximum() -> None:
    session = run(build_session("train-f2-00"), steps=20)
    maximum = float(CONFIG.physical.maximum_acceleration_meters_per_second_squared)
    for robot in session.robots:
        assert math.hypot(*robot.acceleration) <= maximum + 1e-6


# -- termination vocabulary ---------------------------------------------------
def test_termination_causes_come_from_the_frozen_vocabulary() -> None:
    declared = set(TARGET["termination_causes"])
    for layout in ("train-f1-00", "train-f2-00", "train-f9-00", "train-f10-00"):
        session = run(build_session(layout), steps=400)
        if session.termination is not None:
            assert session.termination.cause in declared, (layout, session.termination)


def test_horizon_terminates_the_episode() -> None:
    session = build_session("train-f1-00")
    session.horizon_seconds = 5 * float(CONFIG.physical.control_period_seconds)
    run(session, steps=50)
    assert session.termination is not None
    assert session.time_seconds >= session.horizon_seconds
