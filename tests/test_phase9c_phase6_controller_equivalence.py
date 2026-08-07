"""RB-A.10 / RB-G4 -- Phase 6 behaviour is composed, not reimplemented."""

from __future__ import annotations

import ast
import json
import math
import pathlib

import pytest

from rvt_swarm.decentralized.robot_local_controller import RobotLocalController
from rvt_swarm.decentralized.local_safety_projection import RobotLocalSafetyProjection
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG
from tests.test_phase9c_publication_executor import build_session, run

PACKAGE = pathlib.Path("rvt_swarm/phase9c_rb")


def test_same_local_input_gives_the_same_base_and_projected_action() -> None:
    """The publication path and a bare frozen controller must agree exactly."""
    session = run(build_session("train-f2-00"), steps=8)
    robot = session.robots[0]
    view = session._build_robot_view(robot)
    adapter = robot.adapter_by_topology[robot.committed_topology]
    controller_input = adapter.build_input(view, session.time_seconds)

    reference = RobotLocalController(session.runtime_config)
    expected = reference.evaluate(controller_input)
    actual = adapter.controller.evaluate(controller_input)
    assert actual.base_action == pytest.approx(expected.base_action)
    assert actual.projected_action == pytest.approx(expected.projected_action)


@pytest.mark.parametrize("layout", ["train-f1-00", "train-f2-00", "train-f7-00"])
@pytest.mark.parametrize("policy_index", [0, 1])
def test_equivalence_holds_across_topologies_and_layouts(layout, policy_index) -> None:
    from rvt_swarm.phase9c_rb import policies as P
    session = run(build_session(layout, policy_id=[P.S1, P.S2][policy_index]), steps=8)
    reference = RobotLocalController(session.runtime_config)
    for robot in session.robots:
        adapter = robot.adapter_by_topology[robot.committed_topology]
        controller_input = adapter.build_input(
            session._build_robot_view(robot), session.time_seconds)
        assert reference.evaluate(controller_input).base_action == pytest.approx(
            adapter.controller.evaluate(controller_input).base_action)


def test_sparse_peer_sets_are_handled() -> None:
    from dataclasses import replace
    session = run(build_session("train-f1-00"), steps=8)
    robot = session.robots[0]
    adapter = robot.adapter_by_topology[robot.committed_topology]
    base = adapter.build_input(session._build_robot_view(robot), session.time_seconds)
    for peers in ((), base.peer_states[:1], base.peer_states):
        output = adapter.controller.evaluate(replace(base, peer_states=peers))
        assert all(math.isfinite(v) for v in output.projected_action)


def test_safety_projection_is_the_frozen_class() -> None:
    session = build_session("train-f2-00")
    for robot in session.robots:
        for adapter in robot.adapter_by_topology.values():
            assert isinstance(adapter.controller.safety_projection,
                              RobotLocalSafetyProjection)


def test_action_saturation_respects_the_platform_bound() -> None:
    session = run(build_session("train-f2-00"), steps=15)
    maximum = float(session.runtime_config.physical.maximum_acceleration_meters_per_second_squared)
    for robot in session.robots:
        assert math.hypot(*robot.acceleration) <= maximum + 1e-6


def test_publication_package_defines_no_controller_gain() -> None:
    """RB-5: gains must not be duplicated anywhere in the new package."""
    gain_names = {f.name for f in __import__(
        "dataclasses").fields(CONFIG.controller)}
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="ascii"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in gain_names:
                        raise AssertionError(f"{path}: redefines gain {target.id}")


def test_publication_package_defines_no_controller_or_projection_class() -> None:
    """It must compose the frozen classes, never declare its own."""
    forbidden = {"RobotLocalController", "RobotLocalSafetyProjection",
                 "TransitionProtocolNode"}
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="ascii"))
        declared = {node.name for node in ast.walk(tree)
                    if isinstance(node, ast.ClassDef)}
        assert not (declared & forbidden), (path, declared & forbidden)
    source = "\n".join(p.read_text(encoding="ascii") for p in PACKAGE.glob("*.py"))
    assert "ForcedTopologyRuntimeAdapter" in source, "the frozen adapter must be used"


def test_safety_latches_are_tracked_separately_for_the_two_causes() -> None:
    """RB-14 precondition: the causes must never be merged in the raw state."""
    session = build_session("train-f2-00")
    robot = session.robots[0]
    assert hasattr(robot, "safety_infeasible_seen")
    assert hasattr(robot, "safety_solver_failure_seen")
    robot.safety_infeasible_seen = True
    assert robot.safety_solver_failure_seen is False
