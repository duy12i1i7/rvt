"""Robot-local swept envelope and SAFE/UNSAFE/UNKNOWN readiness certificate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from ..runtime_configuration import RuntimeConfig
from ..topology_registry import PRIMARY_TOPOLOGY_IDS, rotate_template_vector
from .ego_graph_v2 import LocalCandidateTopologySlice
from .local_control_types import LocalObstacleControlState, LocalPeerControlState


TRANSITION_ENVELOPE_SCHEMA_VERSION = "rvt-local-transition-envelope/v1"
TRANSITION_READINESS_SCHEMA_VERSION = "rvt-local-transition-readiness/v1"
Vec2 = Tuple[float, float]


class TransitionReadinessError(ValueError):
    """A local transition input is structurally invalid."""


@dataclass(frozen=True)
class RobotLocalTransitionInput:
    observer_robot_id: int
    observer_role_id: str
    team_size: int
    timestamp_seconds: float
    lifecycle_id: int
    epoch_id: int
    committed_topology_id: int
    source_topology_id: int
    candidate_topology_id: int
    mission_direction: Vec2
    own_position_meters: Vec2
    own_velocity_meters_per_second: Vec2
    source_topology: LocalCandidateTopologySlice
    target_topology: LocalCandidateTopologySlice
    peer_states: Tuple[LocalPeerControlState, ...]
    obstacle_states: Tuple[LocalObstacleControlState, ...]
    observed_extent_meters: float
    projection_infeasible: bool = False
    projection_solver_failed: bool = False
    projection_failure_persistent: bool = False
    proposed_action_meters_per_second_squared: Vec2 = (0.0, 0.0)

    def __post_init__(self) -> None:
        if isinstance(self.observer_robot_id, bool) or self.observer_robot_id < 0:
            raise TransitionReadinessError("observer robot ID must be nonnegative")
        if not self.observer_role_id:
            raise TransitionReadinessError("observer role ID must be nonempty")
        if isinstance(self.team_size, bool) or self.team_size <= 0:
            raise TransitionReadinessError("team size must be positive")
        for name, value in (
            ("timestamp", self.timestamp_seconds),
            ("observed extent", self.observed_extent_meters),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise TransitionReadinessError(f"{name} must be finite and nonnegative")
        if self.lifecycle_id <= 0 or self.epoch_id <= 0:
            raise TransitionReadinessError("lifecycle and epoch must be positive")
        for topology in (
            self.committed_topology_id,
            self.source_topology_id,
            self.candidate_topology_id,
        ):
            if topology not in PRIMARY_TOPOLOGY_IDS:
                raise TransitionReadinessError("transition topology is not primary")
        if self.source_topology_id == self.candidate_topology_id:
            raise TransitionReadinessError("readiness pair must change topology")
        if self.source_topology.topology_id != self.source_topology_id:
            raise TransitionReadinessError("source local slice does not match source")
        if self.target_topology.topology_id != self.candidate_topology_id:
            raise TransitionReadinessError("target local slice does not match target")
        for name, vector in (
            ("mission direction", self.mission_direction),
            ("own position", self.own_position_meters),
            ("own velocity", self.own_velocity_meters_per_second),
            ("proposed action", self.proposed_action_meters_per_second_squared),
        ):
            if len(vector) != 2 or not all(math.isfinite(float(x)) for x in vector):
                raise TransitionReadinessError(f"{name} must be a finite 2-vector")
        if math.hypot(*self.mission_direction) <= 1e-12:
            raise TransitionReadinessError("mission direction must be nonzero")
        if any(not isinstance(item, LocalPeerControlState) for item in self.peer_states):
            raise TransitionReadinessError("peer state type is invalid")
        if any(
            not isinstance(item, LocalObstacleControlState)
            for item in self.obstacle_states
        ):
            raise TransitionReadinessError("obstacle state type is invalid")


@dataclass(frozen=True)
class RobotLocalTransitionEnvelope:
    schema_version: str
    observer_robot_id: int
    source_topology_id: int
    candidate_topology_id: int
    full_role_displacement_world_meters: Vec2
    certified_segment_displacement_world_meters: Vec2
    certified_fraction: float
    capsule_start_relative_meters: Vec2
    capsule_end_relative_meters: Vec2
    capsule_radius_meters: float
    prediction_horizon_seconds: float
    required_observation_extent_meters: float
    observed_extent_meters: float
    observation_complete: bool
    supported: bool
    unknown_reasons: Tuple[str, ...]


@dataclass(frozen=True)
class RobotLocalReadinessCertificate:
    schema_version: str
    observer_robot_id: int
    lifecycle_id: int
    epoch_id: int
    source_topology_id: int
    candidate_topology_id: int
    readiness_state: str
    readiness_margin_meters: float
    obstacle_margin_meters: float
    peer_margin_meters: float
    observation_margin_meters: float
    dynamics_margin: float
    blocking_reasons: Tuple[str, ...]
    unknown_reasons: Tuple[str, ...]
    envelope: RobotLocalTransitionEnvelope


def _norm(vector: Vec2) -> float:
    return math.hypot(float(vector[0]), float(vector[1]))


def _point_segment_distance(point: Vec2, start: Vec2, end: Vec2) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    denominator = dx * dx + dy * dy
    if denominator <= math.ulp(1.0):
        return math.hypot(px - sx, py - sy)
    fraction = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / denominator))
    nearest = (sx + fraction * dx, sy + fraction * dy)
    return math.hypot(px - nearest[0], py - nearest[1])


def construct_robot_local_transition_envelope(
    local_input: RobotLocalTransitionInput,
    runtime_config: RuntimeConfig,
) -> RobotLocalTransitionEnvelope:
    if not isinstance(local_input, RobotLocalTransitionInput):
        raise TypeError("envelope accepts RobotLocalTransitionInput only")
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("envelope requires RuntimeConfig")
    source = local_input.source_topology.own_role_offset_meters
    target = local_input.target_topology.own_role_offset_meters
    template_delta = (target[0] - source[0], target[1] - source[1])
    world_delta = rotate_template_vector(template_delta, local_input.mission_direction)
    full_distance = _norm(world_delta)
    physical = runtime_config.physical
    communication = runtime_config.communication
    reaction_time = (
        physical.control_period_seconds
        + communication.maximum_message_delay_seconds
    )
    braking_time = (
        physical.maximum_speed_meters_per_second
        / physical.maximum_acceleration_meters_per_second_squared
    )
    horizon = reaction_time + braking_time
    stopping_extent = (
        physical.maximum_speed_meters_per_second * reaction_time
        + physical.maximum_speed_meters_per_second ** 2
        / (2.0 * physical.maximum_acceleration_meters_per_second_squared)
    )
    certified_distance = min(full_distance, stopping_extent)
    fraction = 1.0 if full_distance <= 1e-12 else certified_distance / full_distance
    certified_delta = (world_delta[0] * fraction, world_delta[1] * fraction)
    capsule_radius = (
        runtime_config.derived.robot_obstacle_required_clearance_meters
        + runtime_config.safety.transition_observation_margin_meters
    )
    required_extent = certified_distance + capsule_radius
    observed_extent = min(
        float(local_input.observed_extent_meters),
        runtime_config.sensing.obstacle_sensing_range_meters,
    )
    unknown = []
    if required_extent > observed_extent + 1e-12:
        unknown.append("incomplete_obstacle_observation")
    if local_input.team_size > runtime_config.protocol.maximum_team_size:
        unknown.append("unsupported_team_size")
    supported = not unknown
    return RobotLocalTransitionEnvelope(
        schema_version=TRANSITION_ENVELOPE_SCHEMA_VERSION,
        observer_robot_id=local_input.observer_robot_id,
        source_topology_id=local_input.source_topology_id,
        candidate_topology_id=local_input.candidate_topology_id,
        full_role_displacement_world_meters=tuple(map(float, world_delta)),
        certified_segment_displacement_world_meters=tuple(map(float, certified_delta)),
        certified_fraction=float(fraction),
        capsule_start_relative_meters=(0.0, 0.0),
        capsule_end_relative_meters=tuple(map(float, certified_delta)),
        capsule_radius_meters=float(capsule_radius),
        prediction_horizon_seconds=float(horizon),
        required_observation_extent_meters=float(required_extent),
        observed_extent_meters=float(observed_extent),
        observation_complete=required_extent <= observed_extent + 1e-12,
        supported=supported,
        unknown_reasons=tuple(unknown),
    )


def evaluate_robot_local_transition_readiness(
    local_input: RobotLocalTransitionInput,
    runtime_config: RuntimeConfig,
) -> RobotLocalReadinessCertificate:
    envelope = construct_robot_local_transition_envelope(local_input, runtime_config)
    blocking = []
    unknown = list(envelope.unknown_reasons)
    if local_input.committed_topology_id != local_input.source_topology_id:
        blocking.append("source_topology_mismatch")
    if (
        local_input.projection_infeasible
        or local_input.projection_solver_failed
        or local_input.projection_failure_persistent
    ):
        blocking.append("local_safety_projection_failure")

    speed = _norm(local_input.own_velocity_meters_per_second)
    action = _norm(local_input.proposed_action_meters_per_second_squared)
    speed_margin = runtime_config.physical.maximum_speed_meters_per_second - speed
    action_margin = (
        runtime_config.physical.maximum_acceleration_meters_per_second_squared
        - action
    )
    dynamics_margin = min(speed_margin, action_margin)
    if dynamics_margin < -1e-12:
        blocking.append("phase6_action_dynamics_violation")

    obstacle_margin = float("inf")
    obstacle_evaluated = False
    for obstacle in local_input.obstacle_states:
        if not obstacle.valid:
            unknown.append("invalid_local_obstacle")
            continue
        if (
            obstacle.observation_age_seconds
            > runtime_config.physical.control_period_seconds + 1e-12
        ):
            unknown.append("stale_local_obstacle")
            continue
        distance = _point_segment_distance(
            obstacle.relative_center_meters,
            envelope.capsule_start_relative_meters,
            envelope.capsule_end_relative_meters,
        )
        margin = distance - obstacle.radius_meters - envelope.capsule_radius_meters
        obstacle_margin = min(obstacle_margin, margin)
        obstacle_evaluated = True
    if math.isinf(obstacle_margin):
        obstacle_margin = envelope.observed_extent_meters
    if obstacle_evaluated and obstacle_margin < -1e-12:
        blocking.append("local_obstacle_envelope_clearance")

    peer_margin = float("inf")
    peers_by_id = {peer.peer_robot_id: peer for peer in local_input.peer_states}
    # Source-neighbour records are required to establish current local geometry.
    # A target-only neighbour may still be outside radio range in the source
    # formation; under the declared lossless discovery fixture, absence then
    # means out of local range rather than stale evidence.
    required_peer_ids = {
        item.peer_robot_id for item in local_input.source_topology.formation_neighbours
    }
    for peer_id in sorted(required_peer_ids):
        if peer_id not in peers_by_id:
            unknown.append(f"missing_required_peer:{peer_id}")
    maximum_age = runtime_config.communication.maximum_message_age_seconds
    clearance = runtime_config.derived.robot_robot_required_clearance_meters
    dt = runtime_config.physical.control_period_seconds
    for peer in local_input.peer_states:
        current_distance = _norm(peer.relative_position_meters)
        if current_distance > runtime_config.sensing.peer_sensing_range_meters:
            continue
        if not peer.valid or peer.message_age_seconds > maximum_age + 1e-12:
            unknown.append(f"stale_required_peer:{peer.peer_robot_id}")
            continue
        target_neighbour = local_input.target_topology.neighbour(peer.peer_robot_id)
        if target_neighbour is not None:
            target_relative = rotate_template_vector(
                target_neighbour.desired_offset_from_observer_meters,
                local_input.mission_direction,
            )
            relative_change = (
                target_relative[0] - peer.relative_position_meters[0],
                target_relative[1] - peer.relative_position_meters[1],
            )
            relative_change_norm = _norm(relative_change)
            first_step_relative_reach = (
                runtime_config.physical.maximum_acceleration_meters_per_second_squared
                * dt * dt
            )
            fraction = (
                1.0 if relative_change_norm <= 1e-12
                else min(1.0, first_step_relative_reach / relative_change_norm)
            )
            certified_relative = (
                peer.relative_position_meters[0] + relative_change[0] * fraction,
                peer.relative_position_meters[1] + relative_change[1] * fraction,
            )
            path_margin = _point_segment_distance(
                (0.0, 0.0),
                peer.relative_position_meters,
                certified_relative,
            ) - clearance
        else:
            predicted = (
                peer.relative_position_meters[0]
                + peer.relative_velocity_meters_per_second[0] * dt,
                peer.relative_position_meters[1]
                + peer.relative_velocity_meters_per_second[1] * dt,
            )
            path_margin = min(current_distance, _norm(predicted)) - clearance
        peer_margin = min(peer_margin, path_margin)
    if math.isinf(peer_margin):
        peer_margin = runtime_config.sensing.peer_sensing_range_meters - clearance
    if peer_margin < -1e-12:
        blocking.append("local_peer_transition_clearance")

    observation_margin = (
        envelope.observed_extent_meters - envelope.required_observation_extent_meters
    )
    finite_margins = (
        obstacle_margin,
        peer_margin,
        observation_margin,
        dynamics_margin,
    )
    total_margin = min(float(value) for value in finite_margins)
    blocking = tuple(sorted(set(blocking)))
    unknown = tuple(sorted(set(unknown)))
    if blocking:
        state = "UNSAFE"
    elif unknown:
        state = "UNKNOWN"
    else:
        state = "SAFE"
    return RobotLocalReadinessCertificate(
        schema_version=TRANSITION_READINESS_SCHEMA_VERSION,
        observer_robot_id=local_input.observer_robot_id,
        lifecycle_id=local_input.lifecycle_id,
        epoch_id=local_input.epoch_id,
        source_topology_id=local_input.source_topology_id,
        candidate_topology_id=local_input.candidate_topology_id,
        readiness_state=state,
        readiness_margin_meters=float(total_margin),
        obstacle_margin_meters=float(obstacle_margin),
        peer_margin_meters=float(peer_margin),
        observation_margin_meters=float(observation_margin),
        dynamics_margin=float(dynamics_margin),
        blocking_reasons=blocking,
        unknown_reasons=unknown,
        envelope=envelope,
    )
