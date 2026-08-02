"""Offline Phase 6 forced-topology mechanical qualification harness.

This module is simulator infrastructure. It may orchestrate all robots and
compute Metric V3 after the fact; every controller call still receives one
RobotView reduced to one-hop peers and local obstacles.
"""

from __future__ import annotations

import math
import time
import tracemalloc
from dataclasses import asdict, dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..runtime_configuration import RuntimeConfig, SUPPORTED_MECHANICAL_TEAM_SIZES
from ..topology_registry import (
    PRIMARY_TOPOLOGY_IDS,
    construct_topology,
    generate_persistent_roles,
    template_world_positions,
)
from .ego_graph_v2 import prepare_robot_local_topology_metadata
from .forced_topology_runtime import ForcedTopologyRuntimeAdapter
from .formation_metric_v3 import EPSILON_FORM, e_inf, e_rms
from .local_control_types import (
    LocalObstacleControlState,
    LocalPeerControlState,
)
from .roles import RoleAssignment
from .system_model import NeighbourRecord, RobotView


PHASE6_QUALIFICATION_SCHEMA_VERSION = "rvt-phase6-qualification/v1"
PHASE6_SEEDS: Tuple[int, ...] = (61001, 61002, 61003, 61004, 61005)
PHASE6_STABILIZATION_FIXTURES: Tuple[str, ...] = (
    "exact_topology",
    "bounded_position",
    "bounded_velocity",
    "combined_perturbation",
)
PHASE6_TRANSLATION_HEADINGS_RADIANS: Tuple[float, ...] = (0.0, math.pi / 3.0)


@dataclass(frozen=True)
class Phase6InitialCondition:
    fixture_class: str
    seed: int
    mission_direction: Tuple[float, float]
    shared_goal_origin_meters: Tuple[float, float]
    positions: np.ndarray
    velocities: np.ndarray
    validity: bool
    rejection_reasons: Tuple[str, ...]


@dataclass(frozen=True)
class Phase6EpisodeResult:
    schema_version: str
    team_size: int
    topology_id: int
    fixture_class: str
    seed: int
    heading_radians: float
    valid_initial_condition: bool
    rejection_reasons: Tuple[str, ...]
    initial_formation_error_meters: float
    maximum_formation_error_meters: float
    final_formation_error_meters: float
    final_formation_rms_meters: float
    first_tube_entry_step: Optional[int]
    dwell_completed: bool
    goal_reached: bool
    final_goal_error_meters: float
    completion_step: Optional[int]
    minimum_robot_robot_distance_meters: float
    collision_free: bool
    saturation_rate: float
    projection_intervention_rate: float
    projection_infeasible_count: int
    solver_failure_count: int
    deadlock: bool
    numerical_failure: bool
    controller_calls: int
    per_robot_latency_median_seconds: float
    per_robot_latency_p95_seconds: float
    per_robot_latency_p99_seconds: float
    simulator_orchestration_seconds: float

    def source(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Phase6ScalingResult:
    team_size: int
    dense_communication: bool
    local_degree_median: float
    obstacle_count: int
    iterations: int
    per_robot_latency_median_seconds: float
    per_robot_latency_p95_seconds: float
    per_robot_latency_p99_seconds: float
    neighbour_discovery_median_seconds: float
    simulator_aggregate_median_seconds: float
    safety_projection_median_seconds: float
    intervention_latency_median_seconds: Optional[float]
    peak_memory_bytes: int


@dataclass(frozen=True)
class Phase6SafetyStressResult:
    case_name: str
    projection_enabled: bool
    collision_after_step: bool
    minimum_clearance_meters: Optional[float]
    action_modification_meters_per_second_squared: float
    intervention_step: Optional[int]
    intervention_duration_steps: int
    projection_status: str
    solver_failure: bool
    infeasible_fallback: bool
    goal_progress_meters: float
    deadlock: bool
    false_intervention: bool
    base_action: Tuple[float, float]
    executed_action: Tuple[float, float]


def _mission_direction(heading_radians: float) -> Tuple[float, float]:
    return (math.cos(heading_radians), math.sin(heading_radians))


def _role_assignment(team_size: int, runtime_config: RuntimeConfig) -> RoleAssignment:
    return RoleAssignment.from_index(
        team_size,
        runtime_config.formation.nominal_spacing_meters,
    )


def _template_positions(
    team_size: int,
    topology_id: int,
    mission_direction: Tuple[float, float],
    runtime_config: RuntimeConfig,
) -> np.ndarray:
    role_set = generate_persistent_roles(team_size)
    template = construct_topology(
        topology_id,
        runtime_config.formation,
        role_set=role_set,
    )
    return np.asarray(
        template_world_positions(template, (0.0, 0.0), mission_direction),
        dtype=np.float64,
    )


def _minimum_pair_distance(robot_positions: np.ndarray) -> float:
    if len(robot_positions) < 2:
        return float("inf")
    minimum = float("inf")
    for first in range(len(robot_positions)):
        for second in range(first + 1, len(robot_positions)):
            minimum = min(
                minimum,
                float(np.linalg.norm(robot_positions[first] - robot_positions[second])),
            )
    return minimum


def generate_phase6_initial_condition(
    team_size: int,
    topology_id: int,
    fixture_class: str,
    seed: int,
    heading_radians: float,
    runtime_config: RuntimeConfig,
) -> Phase6InitialCondition:
    if team_size not in SUPPORTED_MECHANICAL_TEAM_SIZES:
        raise ValueError("team size is outside the Phase 6 matrix")
    if topology_id not in PRIMARY_TOPOLOGY_IDS:
        raise ValueError("topology is outside the Phase 6 matrix")
    if fixture_class not in PHASE6_STABILIZATION_FIXTURES + ("open_translation",):
        raise ValueError("unknown Phase 6 fixture class")
    if seed not in PHASE6_SEEDS:
        raise ValueError("seed is outside the frozen Phase 6 seed set")
    direction = _mission_direction(heading_radians)
    robot_positions = _template_positions(
        team_size, topology_id, direction, runtime_config
    )
    robot_velocities = np.zeros_like(robot_positions)
    rng = np.random.default_rng(seed)
    position_bound = runtime_config.formation.spacing_margin_meters
    velocity_bound = (
        runtime_config.physical.maximum_speed_meters_per_second
        * runtime_config.physical.control_period_seconds
    )
    if fixture_class in ("bounded_position", "combined_perturbation", "open_translation"):
        robot_positions += rng.uniform(
            -position_bound,
            position_bound,
            size=robot_positions.shape,
        )
    if fixture_class in ("bounded_velocity", "combined_perturbation", "open_translation"):
        robot_velocities += rng.uniform(
            -velocity_bound,
            velocity_bound,
            size=robot_velocities.shape,
        )
    if fixture_class == "open_translation":
        distance = 4.0 * runtime_config.formation.nominal_spacing_meters
        goal = (direction[0] * distance, direction[1] * distance)
    else:
        goal = (0.0, 0.0)
    reasons: List[str] = []
    if robot_positions.shape != (team_size, 2) or robot_velocities.shape != (team_size, 2):
        reasons.append("invalid_array_shape")
    if not bool(np.isfinite(robot_positions).all()) or not bool(
        np.isfinite(robot_velocities).all()
    ):
        reasons.append("nonfinite_initial_state")
    minimum_distance = _minimum_pair_distance(robot_positions)
    if minimum_distance <= runtime_config.derived.robot_robot_required_clearance_meters:
        reasons.append("robot_robot_clearance")
    speeds = np.linalg.norm(robot_velocities, axis=1)
    if bool((speeds > runtime_config.physical.maximum_speed_meters_per_second).any()):
        reasons.append("initial_speed_bound")
    roles = _role_assignment(team_size, runtime_config)
    initial_error = e_inf(robot_positions, roles, topology_id, direction)
    exact_tolerance = np.finfo(np.float32).eps * max(
        1.0,
        float(np.max(np.abs(robot_positions))),
    )
    if fixture_class == "exact_topology" and initial_error > exact_tolerance:
        reasons.append("exact_template_error")
    if fixture_class != "open_translation" and initial_error > EPSILON_FORM:
        reasons.append("outside_initial_metric_tube")
    return Phase6InitialCondition(
        fixture_class=fixture_class,
        seed=seed,
        mission_direction=direction,
        shared_goal_origin_meters=goal,
        positions=robot_positions,
        velocities=robot_velocities,
        validity=not reasons,
        rejection_reasons=tuple(reasons),
    )


def semi_implicit_acceleration_step(
    own_position: Tuple[float, float],
    own_velocity: Tuple[float, float],
    own_action: Tuple[float, float],
    runtime_config: RuntimeConfig,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    action = np.asarray(own_action, dtype=np.float64)
    acceleration_limit = (
        runtime_config.physical.maximum_acceleration_meters_per_second_squared
    )
    action_norm = float(np.linalg.norm(action))
    if action_norm > acceleration_limit:
        action *= acceleration_limit / action_norm
    velocity = np.asarray(own_velocity, dtype=np.float64) + (
        action * runtime_config.physical.control_period_seconds
    )
    speed = float(np.linalg.norm(velocity))
    if speed > runtime_config.physical.maximum_speed_meters_per_second:
        velocity *= runtime_config.physical.maximum_speed_meters_per_second / speed
    position = np.asarray(own_position, dtype=np.float64) + (
        velocity * runtime_config.physical.control_period_seconds
    )
    return (
        (float(position[0]), float(position[1])),
        (float(velocity[0]), float(velocity[1])),
    )


def simulate_received_robot_views(
    robot_positions: np.ndarray,
    robot_velocities: np.ndarray,
    role_assignment: RoleAssignment,
    forced_topology_id: int,
    goal_origin: Tuple[float, float],
    mission_direction: Tuple[float, float],
    runtime_config: RuntimeConfig,
    *,
    dense_communication: bool = False,
) -> Tuple[RobotView, ...]:
    """BOUNDARY: emulate radio discovery, then emit one closed view per robot."""
    count = len(robot_positions)
    views = []
    range_limit = runtime_config.communication.communication_range_meters
    for observer in range(count):
        neighbours = []
        for peer in range(count):
            if peer == observer:
                continue
            relative_position = robot_positions[peer] - robot_positions[observer]
            if not dense_communication and float(np.linalg.norm(relative_position)) > range_limit:
                continue
            relative_velocity = robot_velocities[peer] - robot_velocities[observer]
            neighbours.append(NeighbourRecord(
                robot_id=peer,
                rel_position=(float(relative_position[0]), float(relative_position[1])),
                rel_velocity=(float(relative_velocity[0]), float(relative_velocity[1])),
                role_keep=role_assignment.role_of(peer, 0),
                role_line=role_assignment.role_of(peer, 2),
                committed_mode=forced_topology_id,
                epoch_id=0,
                message_age_steps=0,
                degree=0,
                link_valid=True,
            ))
        views.append(RobotView(
            robot_id=observer,
            position=(float(robot_positions[observer, 0]), float(robot_positions[observer, 1])),
            velocity=(float(robot_velocities[observer, 0]), float(robot_velocities[observer, 1])),
            role_keep=role_assignment.role_of(observer, 0),
            role_line=role_assignment.role_of(observer, 2),
            committed_mode=forced_topology_id,
            epoch_id=0,
            steps_since_decision=0,
            local_progress=0.0,
            goal=goal_origin,
            mission_dir=mission_direction,
            neighbours=tuple(neighbours),
            obstacles=(),
        ))
    return tuple(views)


def _percentile(values: Sequence[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def run_phase6_episode(
    team_size: int,
    topology_id: int,
    fixture_class: str,
    seed: int,
    heading_radians: float = 0.0,
) -> Phase6EpisodeResult:
    runtime_config = RuntimeConfig.for_team_size(team_size)
    initial = generate_phase6_initial_condition(
        team_size,
        topology_id,
        fixture_class,
        seed,
        heading_radians,
        runtime_config,
    )
    roles = _role_assignment(team_size, runtime_config)
    initial_error = e_inf(
        initial.positions, roles, topology_id, initial.mission_direction
    )
    if not initial.validity:
        return Phase6EpisodeResult(
            schema_version=PHASE6_QUALIFICATION_SCHEMA_VERSION,
            team_size=team_size,
            topology_id=topology_id,
            fixture_class=fixture_class,
            seed=seed,
            heading_radians=heading_radians,
            valid_initial_condition=False,
            rejection_reasons=initial.rejection_reasons,
            initial_formation_error_meters=initial_error,
            maximum_formation_error_meters=initial_error,
            final_formation_error_meters=initial_error,
            final_formation_rms_meters=e_rms(
                initial.positions, roles, topology_id, initial.mission_direction
            ),
            first_tube_entry_step=None,
            dwell_completed=False,
            goal_reached=False,
            final_goal_error_meters=float("inf"),
            completion_step=None,
            minimum_robot_robot_distance_meters=_minimum_pair_distance(initial.positions),
            collision_free=False,
            saturation_rate=0.0,
            projection_intervention_rate=0.0,
            projection_infeasible_count=0,
            solver_failure_count=0,
            deadlock=False,
            numerical_failure=False,
            controller_calls=0,
            per_robot_latency_median_seconds=0.0,
            per_robot_latency_p95_seconds=0.0,
            per_robot_latency_p99_seconds=0.0,
            simulator_orchestration_seconds=0.0,
        )
    role_set = generate_persistent_roles(team_size)
    adapters = tuple(
        ForcedTopologyRuntimeAdapter(
            runtime_config,
            prepare_robot_local_topology_metadata(
                role_set, robot_id, runtime_config.formation
            ),
            topology_id,
        )
        for robot_id in range(team_size)
    )
    robot_positions = initial.positions.copy()
    robot_velocities = initial.velocities.copy()
    duration_seconds = 4.0 * runtime_config.mission.recovery_dwell_seconds
    step_count = int(math.ceil(
        duration_seconds / runtime_config.physical.control_period_seconds
    ))
    dwell_steps = runtime_config.derived.recovery_dwell_steps
    errors = [initial_error]
    in_tube_steps: List[bool] = [initial_error <= EPSILON_FORM]
    goal_errors = [float(np.linalg.norm(
        robot_positions.mean(axis=0)
        - np.asarray(initial.shared_goal_origin_meters, dtype=np.float64)
    ))]
    minimum_distance = _minimum_pair_distance(robot_positions)
    collision_free = (
        minimum_distance
        > runtime_config.derived.robot_robot_required_clearance_meters
    )
    latencies: List[float] = []
    saturation_count = 0
    intervention_count = 0
    infeasible_count = 0
    solver_failure_count = 0
    controller_calls = 0
    numerical_failure = False
    orchestration_seconds = 0.0
    completion_step: Optional[int] = None
    for step in range(step_count):
        orchestration_start = time.perf_counter()
        views = simulate_received_robot_views(
            robot_positions,
            robot_velocities,
            roles,
            topology_id,
            initial.shared_goal_origin_meters,
            initial.mission_direction,
            runtime_config,
        )
        orchestration_seconds += time.perf_counter() - orchestration_start
        actions = []
        for robot_id, adapter in enumerate(adapters):
            started = time.perf_counter()
            output = adapter.evaluate(
                views[robot_id],
                step * runtime_config.physical.control_period_seconds,
            )
            latencies.append(time.perf_counter() - started)
            actions.append(output.projected_action)
            controller_calls += 1
            saturation_count += output.saturation_state != "none"
            intervention_count += output.projection_intervened
            infeasible_count += output.projection_infeasible
            solver_failure_count += output.projection_solver_failed
        next_positions = np.zeros_like(robot_positions)
        next_velocities = np.zeros_like(robot_velocities)
        for robot_id, own_action in enumerate(actions):
            next_position, next_velocity = semi_implicit_acceleration_step(
                (float(robot_positions[robot_id, 0]), float(robot_positions[robot_id, 1])),
                (float(robot_velocities[robot_id, 0]), float(robot_velocities[robot_id, 1])),
                own_action,
                runtime_config,
            )
            next_positions[robot_id] = next_position
            next_velocities[robot_id] = next_velocity
        robot_positions = next_positions
        robot_velocities = next_velocities
        if not bool(np.isfinite(robot_positions).all()) or not bool(
            np.isfinite(robot_velocities).all()
        ):
            numerical_failure = True
            break
        current_error = e_inf(
            robot_positions, roles, topology_id, initial.mission_direction
        )
        errors.append(current_error)
        in_tube_steps.append(current_error <= EPSILON_FORM)
        goal_error = float(np.linalg.norm(
            robot_positions.mean(axis=0)
            - np.asarray(initial.shared_goal_origin_meters, dtype=np.float64)
        ))
        goal_errors.append(goal_error)
        current_minimum = _minimum_pair_distance(robot_positions)
        minimum_distance = min(minimum_distance, current_minimum)
        collision_free = collision_free and (
            current_minimum
            > runtime_config.derived.robot_robot_required_clearance_meters
        )
        if (
            completion_step is None
            and goal_error <= runtime_config.derived.formation_tolerance_meters
            and len(in_tube_steps) >= dwell_steps
            and all(in_tube_steps[-dwell_steps:])
        ):
            completion_step = step + 1
    first_tube = next(
        (index for index, inside in enumerate(in_tube_steps) if inside),
        None,
    )
    dwell_completed = (
        len(in_tube_steps) >= dwell_steps
        and all(in_tube_steps[-dwell_steps:])
    )
    goal_reached = (
        goal_errors[-1] <= runtime_config.derived.formation_tolerance_meters
    )
    total_calls = max(controller_calls, 1)
    displacement = float(np.linalg.norm(
        robot_positions.mean(axis=0) - initial.positions.mean(axis=0)
    ))
    required_displacement = float(np.linalg.norm(
        np.asarray(initial.shared_goal_origin_meters)
        - initial.positions.mean(axis=0)
    ))
    deadlock = bool(
        fixture_class == "open_translation"
        and not goal_reached
        and displacement < runtime_config.formation.nominal_spacing_meters
        and required_displacement > runtime_config.formation.nominal_spacing_meters
    )
    return Phase6EpisodeResult(
        schema_version=PHASE6_QUALIFICATION_SCHEMA_VERSION,
        team_size=team_size,
        topology_id=topology_id,
        fixture_class=fixture_class,
        seed=seed,
        heading_radians=heading_radians,
        valid_initial_condition=True,
        rejection_reasons=(),
        initial_formation_error_meters=initial_error,
        maximum_formation_error_meters=max(errors),
        final_formation_error_meters=errors[-1],
        final_formation_rms_meters=e_rms(
            robot_positions, roles, topology_id, initial.mission_direction
        ),
        first_tube_entry_step=first_tube,
        dwell_completed=dwell_completed,
        goal_reached=goal_reached,
        final_goal_error_meters=goal_errors[-1],
        completion_step=completion_step,
        minimum_robot_robot_distance_meters=minimum_distance,
        collision_free=collision_free,
        saturation_rate=saturation_count / total_calls,
        projection_intervention_rate=intervention_count / total_calls,
        projection_infeasible_count=infeasible_count,
        solver_failure_count=solver_failure_count,
        deadlock=deadlock,
        numerical_failure=numerical_failure,
        controller_calls=controller_calls,
        per_robot_latency_median_seconds=_percentile(latencies, 50.0),
        per_robot_latency_p95_seconds=_percentile(latencies, 95.0),
        per_robot_latency_p99_seconds=_percentile(latencies, 99.0),
        simulator_orchestration_seconds=orchestration_seconds,
    )


def benchmark_phase6_controller_stack(
    team_size: int,
    *,
    dense_communication: bool,
    local_obstacle_count: int = 0,
    iterations: int = 100,
) -> Phase6ScalingResult:
    if local_obstacle_count < 0:
        raise ValueError("local obstacle count must be nonnegative")
    runtime_config = RuntimeConfig.for_team_size(team_size)
    topology_id = PRIMARY_TOPOLOGY_IDS[0]
    initial = generate_phase6_initial_condition(
        team_size,
        topology_id,
        "combined_perturbation",
        PHASE6_SEEDS[0],
        0.0,
        runtime_config,
    )
    role_set = generate_persistent_roles(team_size)
    roles = _role_assignment(team_size, runtime_config)
    adapters = tuple(
        ForcedTopologyRuntimeAdapter(
            runtime_config,
            prepare_robot_local_topology_metadata(
                role_set, robot_id, runtime_config.formation
            ),
            topology_id,
        )
        for robot_id in range(team_size)
    )
    local_latencies: List[float] = []
    simulator_latencies: List[float] = []
    projection_latencies: List[float] = []
    intervention_latencies: List[float] = []
    discovery_latencies: List[float] = []
    degrees = []
    tracemalloc.start()
    for iteration in range(iterations):
        simulator_start = time.perf_counter()
        views = simulate_received_robot_views(
            initial.positions,
            initial.velocities,
            roles,
            topology_id,
            initial.shared_goal_origin_meters,
            initial.mission_direction,
            runtime_config,
            dense_communication=dense_communication,
        )
        discovery_latencies.append(time.perf_counter() - simulator_start)
        for robot_id, adapter in enumerate(adapters):
            if local_obstacle_count:
                distance = (
                    runtime_config.derived.robot_obstacle_required_clearance_meters
                    - runtime_config.formation.spacing_margin_meters
                )
                radius = runtime_config.safety.obstacle_clearance_margin_meters
                local_obstacles = tuple(
                    (
                        distance * math.cos(2.0 * math.pi * index / local_obstacle_count),
                        distance * math.sin(2.0 * math.pi * index / local_obstacle_count),
                        radius,
                    )
                    for index in range(local_obstacle_count)
                )
                local_view = replace(views[robot_id], obstacles=local_obstacles)
            else:
                local_view = views[robot_id]
            started = time.perf_counter()
            controller_input = adapter.build_input(
                local_view,
                iteration * runtime_config.physical.control_period_seconds,
            )
            output = adapter.controller.evaluate(controller_input)
            elapsed = time.perf_counter() - started
            local_latencies.append(elapsed)
            degrees.append(len(controller_input.peer_states))
            projection_started = time.perf_counter()
            projection = adapter.controller.safety_projection.project(
                output.base_action, controller_input
            )
            projection_elapsed = time.perf_counter() - projection_started
            projection_latencies.append(projection_elapsed)
            if projection.intervened:
                intervention_latencies.append(projection_elapsed)
        simulator_latencies.append(time.perf_counter() - simulator_start)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return Phase6ScalingResult(
        team_size=team_size,
        dense_communication=dense_communication,
        local_degree_median=_percentile(degrees, 50.0),
        obstacle_count=local_obstacle_count,
        iterations=iterations,
        per_robot_latency_median_seconds=_percentile(local_latencies, 50.0),
        per_robot_latency_p95_seconds=_percentile(local_latencies, 95.0),
        per_robot_latency_p99_seconds=_percentile(local_latencies, 99.0),
        neighbour_discovery_median_seconds=_percentile(discovery_latencies, 50.0),
        simulator_aggregate_median_seconds=_percentile(simulator_latencies, 50.0),
        safety_projection_median_seconds=_percentile(projection_latencies, 50.0),
        intervention_latency_median_seconds=(
            None
            if not intervention_latencies
            else _percentile(intervention_latencies, 50.0)
        ),
        peak_memory_bytes=int(peak),
    )


def run_phase6_safety_stress_case(
    case_name: str,
    *,
    projection_enabled: bool,
) -> Phase6SafetyStressResult:
    """Run one declared one-step local hazard without global collision repair."""
    declared_cases = {
        "safe_open",
        "static_obstacle_uncertain",
        "two_sided_restriction",
        "fresh_peer_approach",
        "stale_peer",
        "moving_obstacle",
        "infeasible_constraints",
    }
    if case_name not in declared_cases:
        raise ValueError("unknown Phase 6 local safety stress case")
    team_size = SUPPORTED_MECHANICAL_TEAM_SIZES[0]
    runtime_config = RuntimeConfig.for_team_size(team_size)
    topology_id = PRIMARY_TOPOLOGY_IDS[0]
    role_set = generate_persistent_roles(team_size)
    roles = _role_assignment(team_size, runtime_config)
    robot_positions = _template_positions(
        team_size, topology_id, (1.0, 0.0), runtime_config
    )
    robot_velocities = np.zeros_like(robot_positions)
    view = simulate_received_robot_views(
        robot_positions,
        robot_velocities,
        roles,
        topology_id,
        (4.0 * runtime_config.formation.nominal_spacing_meters, 0.0),
        (1.0, 0.0),
        runtime_config,
    )[0]
    adapter = ForcedTopologyRuntimeAdapter(
        runtime_config,
        prepare_robot_local_topology_metadata(
            role_set, 0, runtime_config.formation
        ),
        topology_id,
    )
    controller_input = replace(
        adapter.build_input(view, 0.0),
        peer_states=(),
        obstacle_states=(),
    )
    rr_clearance = runtime_config.derived.robot_robot_required_clearance_meters
    ro_clearance = runtime_config.derived.robot_obstacle_required_clearance_meters
    physical = runtime_config.physical
    speed = physical.maximum_speed_meters_per_second
    if case_name == "static_obstacle_uncertain":
        controller_input = replace(
            controller_input,
            obstacle_states=(LocalObstacleControlState(
                "static-uncertain",
                (ro_clearance + runtime_config.formation.spacing_margin_meters, 0.0),
                runtime_config.safety.obstacle_clearance_margin_meters,
                (0.0, 0.0),
                confidence=0.0,
            ),),
        )
    elif case_name == "two_sided_restriction":
        acceleration_displacement = (
            physical.maximum_acceleration_meters_per_second_squared
            * physical.control_period_seconds ** 2
        )
        near_distance = ro_clearance + 0.5 * acceleration_displacement
        far_distance = ro_clearance + 2.0 * acceleration_displacement
        controller_input = replace(
            controller_input,
            obstacle_states=(
                LocalObstacleControlState(
                    "left", (-far_distance, 0.0),
                    runtime_config.safety.obstacle_clearance_margin_meters,
                    (0.0, 0.0),
                ),
                LocalObstacleControlState(
                    "right", (near_distance, 0.0),
                    runtime_config.safety.obstacle_clearance_margin_meters,
                    (0.0, 0.0),
                ),
            ),
        )
    elif case_name == "infeasible_constraints":
        distance = ro_clearance - runtime_config.formation.spacing_margin_meters
        controller_input = replace(
            controller_input,
            obstacle_states=(
                LocalObstacleControlState(
                    "left", (-distance, 0.0),
                    runtime_config.safety.obstacle_clearance_margin_meters,
                    (0.0, 0.0),
                ),
                LocalObstacleControlState(
                    "right", (distance, 0.0),
                    runtime_config.safety.obstacle_clearance_margin_meters,
                    (0.0, 0.0),
                ),
            ),
        )
    elif case_name == "fresh_peer_approach":
        peer_distance = rr_clearance + 2.0 * runtime_config.formation.spacing_margin_meters
        controller_input = replace(
            controller_input,
            own_velocity_meters_per_second=(speed / 3.0, 0.0),
            peer_states=(LocalPeerControlState(
                peer_robot_id=999,
                relative_position_meters=(peer_distance, 0.0),
                relative_velocity_meters_per_second=(-2.0 * speed / 3.0, 0.0),
                message_age_seconds=0.0,
            ),),
        )
    elif case_name == "stale_peer":
        controller_input = replace(
            controller_input,
            peer_states=(LocalPeerControlState(
                peer_robot_id=999,
                relative_position_meters=(
                    rr_clearance + runtime_config.formation.spacing_margin_meters,
                    0.0,
                ),
                relative_velocity_meters_per_second=(0.0, 0.0),
                message_age_seconds=(
                    runtime_config.communication.maximum_message_age_seconds
                    + runtime_config.communication.communication_period_seconds
                ),
            ),),
        )
    elif case_name == "moving_obstacle":
        distance = (
            ro_clearance
            + speed * physical.control_period_seconds
            - 0.5
            * physical.maximum_acceleration_meters_per_second_squared
            * physical.control_period_seconds ** 2
        )
        controller_input = replace(
            controller_input,
            obstacle_states=(LocalObstacleControlState(
                "moving",
                (distance, 0.0),
                runtime_config.safety.obstacle_clearance_margin_meters,
                (-speed, 0.0),
            ),),
        )
    output = adapter.controller.evaluate(controller_input)
    base = np.asarray(output.base_action, dtype=np.float64)
    projected = np.asarray(output.projected_action, dtype=np.float64)
    executed = projected if projection_enabled else base
    own_position, own_velocity = semi_implicit_acceleration_step(
        controller_input.own_position_meters,
        controller_input.own_velocity_meters_per_second,
        (float(executed[0]), float(executed[1])),
        runtime_config,
    )
    own_displacement = np.asarray(own_position) - np.asarray(
        controller_input.own_position_meters
    )
    minimum_clearance = float("inf")
    collision = False
    for peer in controller_input.peer_states:
        peer_displacement = (
            np.asarray(peer.relative_velocity_meters_per_second)
            + np.asarray(controller_input.own_velocity_meters_per_second)
        ) * runtime_config.physical.control_period_seconds
        relative_after = (
            np.asarray(peer.relative_position_meters)
            + peer_displacement
            - own_displacement
        )
        distance = float(np.linalg.norm(relative_after))
        minimum_clearance = min(minimum_clearance, distance)
        collision = collision or distance < rr_clearance
    for obstacle in controller_input.obstacle_states:
        obstacle_displacement = (
            np.asarray(obstacle.relative_velocity_meters_per_second)
            + np.asarray(controller_input.own_velocity_meters_per_second)
        ) * runtime_config.physical.control_period_seconds
        relative_after = (
            np.asarray(obstacle.relative_center_meters)
            + obstacle_displacement
            - own_displacement
        )
        distance = float(np.linalg.norm(relative_after))
        required = runtime_config.physical.robot_radius_meters + max(
            runtime_config.safety.obstacle_clearance_margin_meters,
            obstacle.radius_meters,
        )
        minimum_clearance = min(minimum_clearance, distance)
        collision = collision or distance < required
    modification = float(np.linalg.norm(projected - base)) if projection_enabled else 0.0
    intervened = bool(projection_enabled and output.projection_intervened)
    goal_progress = float(own_displacement[0])
    return Phase6SafetyStressResult(
        case_name=case_name,
        projection_enabled=projection_enabled,
        collision_after_step=collision,
        minimum_clearance_meters=(
            minimum_clearance if math.isfinite(minimum_clearance) else None
        ),
        action_modification_meters_per_second_squared=modification,
        intervention_step=0 if intervened else None,
        intervention_duration_steps=1 if intervened else 0,
        projection_status=(output.projection_status if projection_enabled else "disabled_diagnostic"),
        solver_failure=bool(projection_enabled and output.projection_solver_failed),
        infeasible_fallback=bool(projection_enabled and output.projection_infeasible),
        goal_progress_meters=goal_progress,
        deadlock=bool(abs(goal_progress) <= np.finfo(np.float64).eps),
        false_intervention=bool(case_name == "safe_open" and intervened),
        base_action=(float(base[0]), float(base[1])),
        executed_action=(float(executed[0]), float(executed[1])),
    )
