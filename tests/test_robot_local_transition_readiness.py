from dataclasses import replace

import numpy as np
import pytest

import rvt_swarm.decentralized.transition_runtime as transition_runtime
from rvt_swarm.decentralized.forced_topology_runtime import ForcedTopologyRuntimeAdapter
from rvt_swarm.decentralized.local_control_types import (
    LocalObstacleControlState,
    LocalPeerControlState,
)
from rvt_swarm.decentralized.phase6_qualification import simulate_received_robot_views
from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.decentralized.transition_protocol import TransitionProtocolRuntimeOptions
from rvt_swarm.decentralized.transition_readiness import (
    RobotLocalTransitionInput,
    evaluate_robot_local_transition_readiness,
)


def _local_input(source=2, target=0, robot_id=0, fixture="exact_source"):
    n = 6
    runtime = transition_runtime.StrictTransitionRuntime(
        n, source, transition_runtime.communication_graph(n, "complete"),
        options=TransitionProtocolRuntimeOptions(True),
    )
    positions, velocities, origin, direction = transition_runtime._initial_state(
        n, source, fixture, runtime.runtime_config
    )
    intent = runtime.nodes[0].request_intent(
        1, target, "externally_forced_diagnostic", 0.0
    )
    assert intent is not None
    for node in runtime.nodes:
        node.adopt_intent(intent, 0.0)
    roles = RoleAssignment.from_index(n, runtime.runtime_config.formation.nominal_spacing_meters)
    view = simulate_received_robot_views(
        positions, velocities, roles, source, origin, direction,
        runtime.runtime_config,
    )[robot_id]
    local_controller_input = ForcedTopologyRuntimeAdapter(
        runtime.runtime_config, runtime.local_metadata[robot_id], source
    ).build_input(view, 0.0)
    return RobotLocalTransitionInput(
        observer_robot_id=robot_id,
        observer_role_id=runtime.local_metadata[robot_id].observer_role_id,
        team_size=n,
        timestamp_seconds=0.0,
        lifecycle_id=1,
        epoch_id=intent.epoch_id,
        committed_topology_id=source,
        source_topology_id=source,
        candidate_topology_id=target,
        mission_direction=direction,
        own_position_meters=tuple(map(float, positions[robot_id])),
        own_velocity_meters_per_second=tuple(map(float, velocities[robot_id])),
        source_topology=runtime.local_metadata[robot_id].candidate(source),
        target_topology=runtime.local_metadata[robot_id].candidate(target),
        peer_states=local_controller_input.peer_states,
        obstacle_states=(),
        observed_extent_meters=runtime.runtime_config.sensing.obstacle_sensing_range_meters,
    ), runtime.runtime_config


def test_fully_observed_open_space_is_safe_and_deterministic():
    local_input, config = _local_input()
    first = evaluate_robot_local_transition_readiness(local_input, config)
    second = evaluate_robot_local_transition_readiness(local_input, config)
    assert first == second
    assert first.readiness_state == "SAFE"


def test_outer_wall_constraint_is_unsafe_while_centre_can_be_safe():
    outer_input, config = _local_input(robot_id=0)
    baseline = evaluate_robot_local_transition_readiness(outer_input, config)
    end = baseline.envelope.capsule_end_relative_meters
    obstacle = LocalObstacleControlState(
        "wall", (end[0] * 0.5, end[1] * 0.5), 0.35, (0.0, 0.0)
    )
    blocked = evaluate_robot_local_transition_readiness(
        replace(outer_input, obstacle_states=(obstacle,)), config
    )
    centre_input, centre_config = _local_input(robot_id=1)
    centre = evaluate_robot_local_transition_readiness(centre_input, centre_config)
    assert blocked.readiness_state == "UNSAFE"
    assert centre.readiness_state == "SAFE"


def test_stale_peer_and_incomplete_sensing_cannot_produce_safe():
    local_input, config = _local_input()
    stale = tuple(
        replace(peer, message_age_seconds=10.0)
        for peer in local_input.peer_states
    )
    stale_result = evaluate_robot_local_transition_readiness(
        replace(local_input, peer_states=stale), config
    )
    incomplete = evaluate_robot_local_transition_readiness(
        replace(local_input, observed_extent_meters=0.1), config
    )
    assert stale_result.readiness_state == "UNKNOWN"
    assert incomplete.readiness_state == "UNKNOWN"


def test_out_of_range_peer_and_absent_obstacle_cannot_affect_result():
    local_input, config = _local_input()
    baseline = evaluate_robot_local_transition_readiness(local_input, config)
    remote = LocalPeerControlState(99, (10.0, 0.0), (0.0, 0.0), 99.0, False)
    with_remote = evaluate_robot_local_transition_readiness(
        replace(local_input, peer_states=local_input.peer_states + (remote,)), config
    )
    assert with_remote.readiness_state == baseline.readiness_state
    assert with_remote.readiness_margin_meters == baseline.readiness_margin_meters


def test_translation_rotation_and_closed_input_contract():
    exact, config = _local_input(fixture="exact_source")
    rotated, rotated_config = _local_input(fixture="rotated_mission")
    assert evaluate_robot_local_transition_readiness(exact, config).readiness_state == "SAFE"
    assert evaluate_robot_local_transition_readiness(
        rotated, rotated_config
    ).readiness_state == "SAFE"
    with pytest.raises(TypeError):
        evaluate_robot_local_transition_readiness(np.zeros((6, 2)), config)
