"""Authoritative Phase 6 robot-local forced-topology controller stack."""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from ..topology_registry import rotate_template_vector
from .local_control_types import (
    LOCAL_CONTROLLER_OUTPUT_SCHEMA_VERSION,
    RobotLocalControllerInput,
    RobotLocalControllerOutput,
    Vec2,
)
from .local_safety_projection import RobotLocalSafetyProjection


def _array(value: Vec2) -> np.ndarray:
    return np.asarray(value, dtype=np.float64)


def _tuple(value: Vec2) -> Vec2:
    array = np.asarray(value, dtype=np.float64)
    return (float(array[0]), float(array[1]))


def _unit(value: Vec2) -> np.ndarray:
    array = _array(value)
    length = float(np.linalg.norm(array))
    if length <= np.finfo(np.float64).tiny:
        return np.zeros(2, dtype=np.float64)
    return array / length


def _unit_ball_clip(value: Vec2) -> np.ndarray:
    array = _array(value)
    length = float(np.linalg.norm(array))
    if length <= 1.0:
        return array
    return array / max(length, np.finfo(np.float64).tiny)


def _eligible_fresh_peer_ids(
    controller_input: RobotLocalControllerInput,
    runtime_config: RuntimeConfig,
) -> Tuple[int, ...]:
    maximum_age = runtime_config.communication.maximum_message_age_seconds
    communication_range = runtime_config.communication.communication_range_meters
    return tuple(
        peer.peer_robot_id
        for peer in controller_input.peer_states
        if peer.valid
        and peer.message_age_seconds <= maximum_age
        and math.hypot(*peer.relative_position_meters) <= communication_range
    )


def robot_local_formation_term(
    controller_input: RobotLocalControllerInput,
    runtime_config: RuntimeConfig,
) -> Tuple[Vec2, int, int]:
    """Registry-edge pairwise term using only fresh observed formation peers."""
    eligible = set(_eligible_fresh_peer_ids(controller_input, runtime_config))
    peer_by_id = {
        peer.peer_robot_id: peer
        for peer in controller_input.peer_states
        if peer.peer_robot_id in eligible
    }
    residuals: List[np.ndarray] = []
    local_neighbours = controller_input.local_topology.formation_neighbours
    for formation_peer in local_neighbours:
        peer = peer_by_id.get(formation_peer.peer_robot_id)
        if peer is None:
            continue
        desired = rotate_template_vector(
            formation_peer.desired_offset_from_observer_meters,
            controller_input.mission_direction,
        )
        residuals.append(
            _array(peer.relative_position_meters) - _array(desired)
        )
    if residuals:
        normalized = np.mean(np.stack(residuals), axis=0) / (
            runtime_config.formation.nominal_spacing_meters
        )
    else:
        normalized = np.zeros(2, dtype=np.float64)
    magnitude = (
        runtime_config.physical.maximum_acceleration_meters_per_second_squared
        * runtime_config.controller.formation_gain
    )
    return (
        _tuple(normalized * magnitude),
        len(residuals),
        len(local_neighbours) - len(residuals),
    )


def robot_local_goal_term(
    controller_input: RobotLocalControllerInput,
    runtime_config: RuntimeConfig,
) -> Tuple[Vec2, Vec2]:
    own_offset_world = rotate_template_vector(
        controller_input.local_topology.own_role_offset_meters,
        controller_input.mission_direction,
    )
    own_target = (
        _array(controller_input.shared_goal_origin_meters)
        + _array(own_offset_world)
    )
    normalized_error = (
        own_target - _array(controller_input.own_position_meters)
    ) / runtime_config.formation.nominal_spacing_meters
    magnitude = (
        runtime_config.physical.maximum_acceleration_meters_per_second_squared
        * runtime_config.controller.goal_gain
    )
    return _tuple(_unit_ball_clip(_tuple(normalized_error)) * magnitude), _tuple(own_target)


def robot_local_damping_term(
    controller_input: RobotLocalControllerInput,
    runtime_config: RuntimeConfig,
) -> Vec2:
    physical = runtime_config.physical
    normalized_velocity = (
        _array(controller_input.own_velocity_meters_per_second)
        / physical.maximum_speed_meters_per_second
    )
    return _tuple(
        -physical.maximum_acceleration_meters_per_second_squared
        * runtime_config.controller.damping_gain
        * normalized_velocity
    )


def robot_local_obstacle_term(
    controller_input: RobotLocalControllerInput,
    runtime_config: RuntimeConfig,
) -> Tuple[Vec2, int]:
    physical = runtime_config.physical
    sensing_range = runtime_config.sensing.obstacle_sensing_range_meters
    responses: List[np.ndarray] = []
    for obstacle in controller_input.obstacle_states:
        distance = math.hypot(*obstacle.relative_center_meters)
        if not obstacle.valid or distance > sensing_range:
            continue
        away = _unit((
            -obstacle.relative_center_meters[0],
            -obstacle.relative_center_meters[1],
        ))
        safe_distance = physical.robot_radius_meters + max(
            runtime_config.safety.obstacle_clearance_margin_meters,
            obstacle.radius_meters,
        )
        braking_distance = (
            physical.maximum_speed_meters_per_second ** 2
            / (2.0 * physical.maximum_acceleration_meters_per_second_squared)
        )
        response_distance = min(
            sensing_range,
            safe_distance + braking_distance,
        )
        response_span = max(
            response_distance - safe_distance,
            np.finfo(np.float64).tiny,
        )
        proximity = float(np.clip(
            (response_distance - distance) / response_span,
            0.0,
            1.0,
        ))
        relative_distance_rate = float(np.dot(
            away,
            -_array(obstacle.relative_velocity_meters_per_second),
        ))
        closing_speed = max(-relative_distance_rate, 0.0)
        closing_required = safe_distance + (
            closing_speed ** 2
            / (2.0 * physical.maximum_acceleration_meters_per_second_squared)
        )
        closing_span = max(
            closing_required - safe_distance,
            np.finfo(np.float64).tiny,
        )
        closing = float(np.clip(
            (closing_required - distance) / closing_span,
            0.0,
            1.0,
        ))
        severity = max(proximity, closing)
        responses.append(away * severity)
    if not responses:
        return (0.0, 0.0), 0
    magnitude = (
        physical.maximum_acceleration_meters_per_second_squared
        * runtime_config.controller.obstacle_clearance_gain
    )
    return _tuple(np.mean(np.stack(responses), axis=0) * magnitude), len(responses)


class RobotLocalController:
    """Shared KEEP/COMPACT/LINE controller producing only observer i's action."""

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        safety_projection: RobotLocalSafetyProjection | None = None,
    ) -> None:
        if not isinstance(runtime_config, RuntimeConfig):
            raise TypeError("robot-local controller requires RuntimeConfig")
        self.runtime_config = runtime_config
        self.runtime_config_sha256 = canonical_runtime_hash(runtime_config)
        self.safety_projection = safety_projection or RobotLocalSafetyProjection(
            runtime_config
        )

    def evaluate(
        self,
        controller_input: RobotLocalControllerInput,
    ) -> RobotLocalControllerOutput:
        if not isinstance(controller_input, RobotLocalControllerInput):
            raise TypeError("controller requires RobotLocalControllerInput")
        if controller_input.runtime_config_sha256 != self.runtime_config_sha256:
            raise ValueError("controller input runtime configuration hash mismatch")
        formation, used_neighbours, missing_neighbours = robot_local_formation_term(
            controller_input, self.runtime_config
        )
        goal, own_target = robot_local_goal_term(
            controller_input, self.runtime_config
        )
        damping = robot_local_damping_term(controller_input, self.runtime_config)
        obstacle, used_obstacles = robot_local_obstacle_term(
            controller_input, self.runtime_config
        )
        base = (
            _array(formation)
            + _array(goal)
            + _array(damping)
            + _array(obstacle)
        )
        projection = self.safety_projection.project(
            _tuple(base), controller_input
        )
        limit = (
            self.runtime_config.physical
            .maximum_acceleration_meters_per_second_squared
        )
        projected_norm = math.hypot(*projection.projected_action)
        base_norm = float(np.linalg.norm(base))
        tolerance = np.finfo(np.float64).eps * max(1.0, limit, base_norm)
        if projection.infeasible:
            saturation = "infeasible_fallback"
        elif projected_norm >= limit - tolerance:
            saturation = "physical_limit"
        elif projection.intervened:
            saturation = "local_constraint"
        else:
            saturation = "none"
        diagnostics = (
            ("used_formation_neighbours", float(used_neighbours)),
            ("missing_formation_neighbours", float(missing_neighbours)),
            ("used_local_obstacles", float(used_obstacles)),
            ("base_action_norm", base_norm),
            ("projected_action_norm", projected_norm),
            ("own_target_x_meters", own_target[0]),
            ("own_target_y_meters", own_target[1]),
        )
        return RobotLocalControllerOutput(
            schema_version=LOCAL_CONTROLLER_OUTPUT_SCHEMA_VERSION,
            observer_robot_id=controller_input.observer_robot_id,
            forced_topology_id=controller_input.forced_topology_id,
            formation_term=formation,
            goal_term=goal,
            damping_term=damping,
            obstacle_term=obstacle,
            base_action=_tuple(base),
            projected_action=projection.projected_action,
            projection_intervened=projection.intervened,
            projection_infeasible=projection.infeasible,
            projection_solver_failed=projection.solver_failed,
            projection_status=projection.status,
            active_constraints=projection.constraints,
            saturation_state=saturation,
            diagnostics=diagnostics,
            validity=True,
        )
