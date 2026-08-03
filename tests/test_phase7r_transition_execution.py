from pathlib import Path

import pytest

from rvt_swarm.decentralized.guards import audit
from rvt_swarm.decentralized.transition_execution import (
    derive_transition_motion_profile,
    prepare_robot_local_role_space_path,
)
from rvt_swarm.decentralized.local_safety_projection import RobotLocalSafetyProjection
from rvt_swarm.decentralized.phase7r_qualification import (
    OPTIONAL_DIRECT_TRANSITIONS,
    PRIMARY_HUB_TRANSITIONS,
)
from rvt_swarm.decentralized.transition_protocol import TransitionProtocolRuntimeOptions
from rvt_swarm.decentralized.transition_runtime import (
    StrictTransitionRuntime,
    communication_graph,
    run_phase7_transition_episode,
)
from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def test_motion_profile_is_derived_from_physical_limits_and_has_exact_endpoints():
    config = RuntimeConfig.for_team_size(6)
    profile = derive_transition_motion_profile(1.8, config)
    assert profile.progress(0.0) == 0.0
    assert profile.progress(profile.duration_seconds) == 1.0
    assert profile.progress(profile.duration_seconds + 10.0) == 1.0
    assert profile.velocity_limit_meters_per_second <= (
        config.physical.maximum_speed_meters_per_second
    )
    samples = [
        profile.progress(index * profile.duration_seconds / 1000.0)
        * profile.maximum_displacement_meters
        for index in range(1001)
    ]
    sample_dt = profile.duration_seconds / 1000.0
    velocities = [
        (samples[index + 1] - samples[index]) / sample_dt
        for index in range(1000)
    ]
    assert max(velocities) <= config.physical.maximum_speed_meters_per_second + 1e-6
    accelerations = [
        (velocities[index + 1] - velocities[index]) / sample_dt
        for index in range(999)
    ]
    assert max(abs(value) for value in accelerations) <= (
        config.physical.maximum_acceleration_meters_per_second_squared + 1e-6
    )


def test_local_role_path_interpolates_own_and_target_graph_neighbour_offsets():
    runtime = StrictTransitionRuntime(
        6,
        KEEP,
        communication_graph(6, "path"),
        options=TransitionProtocolRuntimeOptions(True),
    )
    path = prepare_robot_local_role_space_path(
        runtime.role_set, 0, runtime.runtime_config.formation, KEEP, LINE
    )
    source = path.intermediate_topology(0.0)
    midpoint = path.intermediate_topology(0.5)
    target = path.intermediate_topology(1.0)
    assert source.own_role_offset_meters == pytest.approx(path.source_role_offset_meters)
    assert target.own_role_offset_meters == pytest.approx(path.target_role_offset_meters)
    assert midpoint.own_role_offset_meters == pytest.approx(tuple(
        (left + right) / 2.0
        for left, right in zip(
            path.source_role_offset_meters, path.target_role_offset_meters
        )
    ))
    target_slice = runtime.local_metadata[0].candidate(LINE)
    assert tuple(item.peer_robot_id for item in target.formation_neighbours) == tuple(
        item.peer_robot_id for item in target_slice.formation_neighbours
    )


def test_default_runtime_preserves_the_phase7_immediate_negative_result():
    result = run_phase7_transition_episode(5, KEEP, COMPACT, "exact_source", "path")
    assert result.abort_or_timeout == "safety_projection_failure"
    assert result.projection_infeasible_count == 2
    assert result.controller_calls == 55
    assert result.mode_epoch_count == 1


def test_generic_executor_completes_a_previously_unreliable_keep_line_cell():
    result = run_phase7_transition_episode(
        8,
        KEEP,
        LINE,
        "exact_source",
        "path",
        execution_strategy="generic_role_space_profile",
    )
    assert result.transition_success
    assert result.projection_infeasible_count == 0
    assert result.collision_free
    assert result.mode_epoch_count == 1
    assert result.no_op_epoch_count == 0
    assert result.learned_model_calls == 0


def test_generic_executor_invokes_exactly_one_local_projection_per_robot_action(
    monkeypatch,
):
    calls = []
    original = RobotLocalSafetyProjection.project

    def spy(self, proposed_action, controller_input):
        calls.append((controller_input.observer_robot_id, proposed_action))
        return original(self, proposed_action, controller_input)

    monkeypatch.setattr(RobotLocalSafetyProjection, "project", spy)
    result = run_phase7_transition_episode(
        5,
        KEEP,
        LINE,
        "exact_source",
        "path",
        execution_strategy="generic_role_space_profile",
    )
    assert len(calls) == result.controller_calls
    assert all(isinstance(robot_id, int) for robot_id, _ in calls)


def test_primary_and_optional_graph_scope_is_semantic_and_frozen():
    assert PRIMARY_HUB_TRANSITIONS == (
        (KEEP, COMPACT),
        (COMPACT, KEEP),
        (KEEP, LINE),
        (LINE, KEEP),
    )
    assert OPTIONAL_DIRECT_TRANSITIONS == (
        (COMPACT, LINE),
        (LINE, COMPACT),
    )


def test_deployable_executor_declares_no_coordinator_or_joint_path_api():
    source = (
        Path(__file__).resolve().parents[1]
        / "rvt_swarm/decentralized/transition_execution.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "TransitionCoordinator",
        "GlobalProgressController",
        "JointTrajectory",
        "CentralizedFeasibility",
    )
    assert all(token not in source for token in forbidden)


def test_transition_executor_adds_no_strict_decentralization_violation():
    violations = audit()
    assert violations == []


def test_unknown_execution_strategy_is_rejected():
    with pytest.raises(ValueError, match="unknown transition execution strategy"):
        run_phase7_transition_episode(
            5, KEEP, LINE, execution_strategy="scenario_tuned_duration"
        )
