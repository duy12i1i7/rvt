"""Deterministic, non-executing compiler for frozen nonfinal layout records."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from ..phase8.common import attach_canonical_hash
from ..phase8.scenario import (
    GEOMETRY_GENERATOR_VERSION,
    SCENARIO_LAYOUT_SCHEMA_VERSION,
    SUPPORTED_TEAM_SIZES,
)
from ..phase8.splits import load_nonfinal_split_manifest
from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from ..topology_registry import (
    COMPACT,
    construct_topology,
    generate_persistent_roles,
    template_world_positions,
)
from .protocol import (
    LAYOUT_EXECUTION_SPECIFICATION_SCHEMA_VERSION,
    NUMERICAL_GEOMETRY_TOLERANCE_METERS,
    OBSTACLE_SURFACE_MARGIN_METERS,
    SOURCE_POLICY_IDS,
    WORLD_BOUNDS_METERS,
    mission_axes,
    validate_executable_protocol,
)


Vec2 = Tuple[float, float]
_GEOMETRY_KEYS = frozenset({
    "generator_version",
    "family_id",
    "start_center_meters",
    "goal_center_meters",
    "corridor_centerline_meters",
    "nominal_passage_width_meters",
    "static_obstacles",
    "dynamic_obstacle_paths",
    "bypass_available",
    "communication_profile",
    "initial_topology_id",
    "episode_horizon_seconds",
    "canonical_parameters",
})


def _finite(value: object, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _vec2(value: object, field: str) -> Vec2:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        raise ValueError(f"{field} must be a length-two vector")
    return (_finite(value[0], field), _finite(value[1], field))


def _polyline(value: object) -> Tuple[Vec2, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        raise ValueError("corridor centerline must contain at least two points")
    points = tuple(_vec2(point, "corridor_centerline_meters") for point in value)
    if any(points[index + 1][0] <= points[index][0] for index in range(len(points) - 1)):
        raise ValueError("corridor centerline x coordinates must increase strictly")
    return points


def _point_at_x(points: Sequence[Vec2], x: float) -> Vec2:
    tolerance = NUMERICAL_GEOMETRY_TOLERANCE_METERS
    for first, second in zip(points, points[1:]):
        if first[0] - tolerance <= x <= second[0] + tolerance:
            ratio = (x - first[0]) / (second[0] - first[0])
            return (float(x), first[1] + ratio * (second[1] - first[1]))
    raise ValueError("passage entry or exit lies outside centerline")


def _clipped_polyline(points: Sequence[Vec2], entry_x: float, exit_x: float) -> Tuple[Vec2, ...]:
    if not entry_x < exit_x:
        raise ValueError("passage entry must precede exit")
    clipped = [_point_at_x(points, entry_x)]
    clipped.extend(point for point in points if entry_x < point[0] < exit_x)
    clipped.append(_point_at_x(points, exit_x))
    return tuple(clipped)


def _polyline_length(points: Sequence[Vec2]) -> float:
    return math.fsum(
        math.hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(points, points[1:])
    )


def _distance_point_segment(point: Vec2, first: Vec2, second: Vec2) -> float:
    vx, vy = second[0] - first[0], second[1] - first[1]
    denominator = vx * vx + vy * vy
    if denominator <= 0.0:
        return math.hypot(point[0] - first[0], point[1] - first[1])
    ratio = max(0.0, min(1.0, (
        (point[0] - first[0]) * vx + (point[1] - first[1]) * vy
    ) / denominator))
    closest = (first[0] + ratio * vx, first[1] + ratio * vy)
    return math.hypot(point[0] - closest[0], point[1] - closest[1])


def _distance_point_polyline(point: Vec2, points: Sequence[Vec2]) -> float:
    return min(
        _distance_point_segment(point, first, second)
        for first, second in zip(points, points[1:])
    )


def _canonical_parameters(raw: object) -> Dict[str, float]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("canonical_parameters must be a sequence")
    result: Dict[str, float] = {}
    for entry in raw:
        if not isinstance(entry, Sequence) or len(entry) != 2:
            raise ValueError("canonical parameter entry must have name and value")
        name = str(entry[0])
        if name in result:
            raise ValueError("duplicate canonical parameter")
        result[name] = _finite(entry[1], f"canonical_parameters.{name}")
    return result


def _passage(
    primitive_index: int,
    primitive_type: str,
    points: Sequence[Vec2],
    entry_x: float,
    exit_x: float,
    width: float,
) -> Dict[str, object]:
    clipped = _clipped_polyline(points, entry_x, exit_x)
    if width <= 0.0:
        raise ValueError("passage width must be positive")
    return {
        "primitive_index": primitive_index,
        "primitive_type": primitive_type,
        "geometry": "analytic_world_complement_of_closed_polyline_tube",
        "entry_position_meters": list(clipped[0]),
        "exit_position_meters": list(clipped[-1]),
        "active_longitudinal_world_x_meters": [entry_x, exit_x],
        "centerline_control_points_meters": [list(point) for point in clipped],
        "free_width_meters": width,
        "half_width_meters": width / 2.0,
        "passage_length_meters": _polyline_length(clipped),
        "curvature_representation": "piecewise_linear_with_closed_round_distance_tube",
        "inner_boundary_sensor_conversion": "phase8e_analytic_boundary_support_discs/v1",
    }


def _compile_static_geometry(
    family_id: str,
    points: Sequence[Vec2],
    raw_obstacles: object,
    parameters: Mapping[str, float],
    nominal_width: float,
    bypass_available: bool,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Dict[str, object]]:
    if not isinstance(raw_obstacles, Sequence) or isinstance(raw_obstacles, (str, bytes)):
        raise ValueError("static_obstacles must be a sequence")
    obstacles: List[Dict[str, object]] = []
    passages: List[Dict[str, object]] = []
    for index, raw in enumerate(raw_obstacles):
        if not isinstance(raw, Mapping) or frozenset(raw) != {"primitive_type", "values"}:
            raise ValueError("static obstacle primitive has unknown fields")
        primitive_type = str(raw["primitive_type"])
        values = tuple(_finite(value, f"static_obstacles[{index}]") for value in raw["values"])
        if primitive_type in ("circle", "central_blocker"):
            if len(values) != 3 or values[2] <= 0.0:
                raise ValueError("circle primitive requires x, y and positive radius")
            obstacles.append({
                "primitive_index": index,
                "primitive_type": "circle",
                "center_meters": [values[0], values[1]],
                "radius_meters": values[2],
                "source_primitive_type": primitive_type,
            })
        elif primitive_type == "straight_corridor":
            if len(values) != 3:
                raise ValueError("straight corridor requires x0, x1 and width")
            passage = _passage(index, primitive_type, points, values[0], values[1], values[2])
            passages.append(passage)
            obstacles.append({
                "primitive_index": index,
                "primitive_type": "analytic_corridor_walls",
                "passage_reference": index,
            })
        elif primitive_type == "polyline_corridor":
            if len(values) != 2 or len(points) < 4:
                raise ValueError("polyline corridor requires width, entry and four centerline points")
            entry_x = points[1][0]
            exit_x = -entry_x
            if abs(abs(points[1][1]) - values[1]) > NUMERICAL_GEOMETRY_TOLERANCE_METERS:
                raise ValueError("polyline entry offset conflicts with centerline")
            passage = _passage(index, primitive_type, points, entry_x, exit_x, values[0])
            passages.append(passage)
            obstacles.append({
                "primitive_index": index,
                "primitive_type": "analytic_corridor_walls",
                "passage_reference": index,
            })
        elif primitive_type == "s_corridor":
            if len(values) != 2 or len(points) < 5:
                raise ValueError("S corridor requires width, amplitude and five centerline points")
            if max(abs(point[1]) for point in points[1:-1]) + NUMERICAL_GEOMETRY_TOLERANCE_METERS < values[1]:
                raise ValueError("S amplitude conflicts with centerline")
            passage = _passage(
                index, primitive_type, points, points[1][0], points[-2][0], values[0]
            )
            passages.append(passage)
            obstacles.append({
                "primitive_index": index,
                "primitive_type": "analytic_corridor_walls",
                "passage_reference": index,
            })
        else:
            raise ValueError(f"unknown static obstacle primitive {primitive_type!r}")

    if passages and any(
        abs(float(item["free_width_meters"]) - nominal_width) > NUMERICAL_GEOMETRY_TOLERANCE_METERS
        for item in passages
    ):
        raise ValueError("nominal passage width conflicts with primitive width")
    if family_id == "F6":
        if not bypass_available or "bypass_turn_radius_m" not in parameters:
            raise ValueError("F6 requires an explicit bypass and turn radius")
        bypass = {
            "available": True,
            "control_points_meters": [list(point) for point in points],
            "curve": "polyline_with_circular_fillets",
            "fillet_radius_meters": parameters["bypass_turn_radius_m"],
            "clearance_meters": parameters["bypass_clearance_m"],
            "validity": "fillet tangent points must remain on adjacent segments and clear the inflated blocker",
        }
    else:
        if bypass_available:
            raise ValueError("only F6 may declare a bypass")
        bypass = {
            "available": False,
            "control_points_meters": [],
            "curve": "not_applicable",
            "fillet_radius_meters": None,
            "clearance_meters": None,
            "validity": "not_applicable",
        }
    return obstacles, passages, bypass


def _compile_dynamic(raw_paths: object, parameters: Mapping[str, float]) -> List[Dict[str, object]]:
    if not isinstance(raw_paths, Sequence) or isinstance(raw_paths, (str, bytes)):
        raise ValueError("dynamic_obstacle_paths must be a sequence")
    result = []
    for index, raw in enumerate(raw_paths):
        if not isinstance(raw, Mapping) or frozenset(raw) != {"radius_meters", "waypoints"}:
            raise ValueError("dynamic obstacle path has unknown fields")
        radius = _finite(raw["radius_meters"], "dynamic radius")
        if radius <= 0.0:
            raise ValueError("dynamic obstacle radius must be positive")
        waypoints = []
        for waypoint in raw["waypoints"]:
            if not isinstance(waypoint, Sequence) or len(waypoint) != 3:
                raise ValueError("dynamic waypoint must be x, y, t")
            waypoints.append(tuple(_finite(value, "dynamic waypoint") for value in waypoint))
        if len(waypoints) < 2 or any(
            waypoints[i + 1][2] <= waypoints[i][2] for i in range(len(waypoints) - 1)
        ):
            raise ValueError("dynamic waypoint times must increase")
        segments = []
        for first, second in zip(waypoints, waypoints[1:]):
            duration = second[2] - first[2]
            velocity = ((second[0] - first[0]) / duration, (second[1] - first[1]) / duration)
            segments.append({
                "start_time_seconds": first[2],
                "end_time_seconds": second[2],
                "start_position_meters": [first[0], first[1]],
                "end_position_meters": [second[0], second[1]],
                "velocity_meters_per_second": list(velocity),
                "speed_meters_per_second": math.hypot(*velocity),
            })
        result.append({
            "dynamic_obstacle_index": index,
            "primitive_type": "circle",
            "radius_meters": radius,
            "motion": "timestamped_piecewise_linear_hold_after_final",
            "waypoints": [list(item) for item in waypoints],
            "segments": segments,
            "declared_speed_meters_per_second_audit_only": parameters.get("obstacle_speed_mps"),
            "future_trajectory_robot_visible": False,
        })
    return result


def dynamic_obstacle_state(
    compiled_obstacle: Mapping[str, object],
    episode_time_seconds: float,
) -> Dict[str, object]:
    """Evaluate the timestamp-authoritative F9 specification without simulation."""
    time = float(episode_time_seconds)
    if not math.isfinite(time) or time < 0.0:
        raise ValueError("dynamic obstacle time must be finite and nonnegative")
    waypoints = compiled_obstacle.get("waypoints")
    if not isinstance(waypoints, Sequence) or len(waypoints) < 2:
        raise ValueError("compiled dynamic obstacle lacks waypoints")
    first = waypoints[0]
    last = waypoints[-1]
    if time <= float(first[2]):
        return {
            "segment_index": 0,
            "episode_time_seconds": time,
            "position_meters": [float(first[0]), float(first[1])],
            "velocity_meters_per_second": [0.0, 0.0],
        }
    for index, (start, end) in enumerate(zip(waypoints, waypoints[1:])):
        if time <= float(end[2]):
            ratio = (time - float(start[2])) / (float(end[2]) - float(start[2]))
            velocity = [
                (float(end[axis]) - float(start[axis]))
                / (float(end[2]) - float(start[2]))
                for axis in (0, 1)
            ]
            return {
                "segment_index": index,
                "episode_time_seconds": time,
                "position_meters": [
                    float(start[axis]) + ratio * (float(end[axis]) - float(start[axis]))
                    for axis in (0, 1)
                ],
                "velocity_meters_per_second": velocity,
            }
    return {
        "segment_index": len(waypoints) - 1,
        "episode_time_seconds": time,
        "position_meters": [float(last[0]), float(last[1])],
        "velocity_meters_per_second": [0.0, 0.0],
    }


def _initial_role_contracts(start: Vec2, direction: Vec2) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for team_size in SUPPORTED_TEAM_SIZES:
        config = RuntimeConfig.for_team_size(team_size)
        roles = generate_persistent_roles(team_size)
        template = construct_topology(COMPACT, config.formation, role_set=roles)
        positions = template_world_positions(template, start, direction)
        result[str(team_size)] = {
            "runtime_configuration_sha256": canonical_runtime_hash(config),
            "role_ids": list(template.role_ids),
            "nominal_positions_meters": [list(position) for position in positions],
            "position_perturbation_bound_meters": config.formation.spacing_margin_meters,
            "velocity_component_bound_meters_per_second": (
                config.physical.maximum_speed_meters_per_second
                * config.physical.control_period_seconds
            ),
            "goal_tolerance_meters": config.derived.formation_tolerance_meters,
        }
    return result


def _nominal_initial_validity(
    initial_contracts: Mapping[str, object],
    obstacles: Sequence[Mapping[str, object]],
    passages: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    result: Dict[str, object] = {}
    passage_by_index = {int(item["primitive_index"]): item for item in passages}
    for team_size, contract in initial_contracts.items():
        config = RuntimeConfig.for_team_size(int(team_size))
        reasons = []
        for robot_index, raw_position in enumerate(contract["nominal_positions_meters"]):
            position = (float(raw_position[0]), float(raw_position[1]))
            if not (
                WORLD_BOUNDS_METERS[0][0] + config.physical.robot_radius_meters <= position[0]
                <= WORLD_BOUNDS_METERS[0][1] - config.physical.robot_radius_meters
                and WORLD_BOUNDS_METERS[1][0] + config.physical.robot_radius_meters <= position[1]
                <= WORLD_BOUNDS_METERS[1][1] - config.physical.robot_radius_meters
            ):
                reasons.append(f"robot_{robot_index}:outside_world_bounds")
            for obstacle in obstacles:
                if obstacle["primitive_type"] == "circle":
                    center = tuple(obstacle["center_meters"])
                    threshold = config.physical.robot_radius_meters + max(
                        config.safety.obstacle_clearance_margin_meters,
                        float(obstacle["radius_meters"]),
                    )
                    if math.hypot(position[0] - center[0], position[1] - center[1]) <= threshold:
                        reasons.append(f"robot_{robot_index}:circle_{obstacle['primitive_index']}_collision")
                elif obstacle["primitive_type"] == "analytic_corridor_walls":
                    passage = passage_by_index[int(obstacle["passage_reference"])]
                    x0, x1 = passage["active_longitudinal_world_x_meters"]
                    if x0 <= position[0] <= x1:
                        centerline = tuple(tuple(point) for point in passage["centerline_control_points_meters"])
                        free_center_half_width = (
                            float(passage["half_width_meters"])
                            - config.physical.robot_radius_meters
                            - OBSTACLE_SURFACE_MARGIN_METERS
                        )
                        if _distance_point_polyline(position, centerline) >= free_center_half_width:
                            reasons.append(f"robot_{robot_index}:corridor_{obstacle['primitive_index']}_collision")
        unique = sorted(set(reasons))
        result[team_size] = {"valid": not unique, "reasons": unique}
    return result


def _communication_spec(
    profile: str,
    parameters: Mapping[str, float],
    start: Vec2,
    passages: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    if profile == "nominal":
        return {
            "profile": profile,
            "delay_upper_bound_seconds": 0.0,
            "packet_drop_probability": 0.0,
            "assumption_class": "inside_method_assumptions",
            "team_size_schedule": {},
        }
    if profile not in ("bounded_delay_loss", "temporary_disconnection_then_restore"):
        raise ValueError("unknown communication profile")
    delay = parameters.get("delay_s")
    loss = parameters.get("packet_loss")
    if delay is None or loss is None or delay < 0.0 or not 0.0 <= loss <= 1.0:
        raise ValueError("F8 delay/loss parameters are invalid")
    schedules: Dict[str, object] = {}
    if profile == "temporary_disconnection_then_restore":
        if not passages:
            raise ValueError("temporary disconnection needs a passage entry")
        entry = passages[0]["entry_position_meters"]
        distance = math.hypot(entry[0] - start[0], entry[1] - start[1])
        for team_size in SUPPORTED_TEAM_SIZES:
            config = RuntimeConfig.for_team_size(team_size)
            period = config.communication.communication_period_seconds
            start_tick = math.ceil(
                distance / config.physical.maximum_speed_meters_per_second / period
            )
            duration_ticks = 2 * ((team_size - 1) + 1)
            schedules[str(team_size)] = {
                "start_tick": start_tick,
                "start_seconds": start_tick * period,
                "duration_ticks": duration_ticks,
                "duration_seconds": duration_ticks * period,
                "partition_ordinal": math.ceil(team_size / 2),
            }
    return {
        "profile": profile,
        "delay_upper_bound_seconds": delay,
        "packet_drop_probability": loss,
        "assumption_class": (
            "explicit_assumption_violation_stress"
            if profile == "temporary_disconnection_then_restore"
            else "inside_method_assumptions"
        ),
        "team_size_schedule": schedules,
    }


def compile_layout_record(
    record: Mapping[str, object],
    split: str,
    protocol: Mapping[str, object],
) -> Dict[str, object]:
    validate_executable_protocol(protocol)
    if split not in ("train", "validation"):
        raise PermissionError("Phase 8E compiler accepts train and validation only")
    if not isinstance(record, Mapping):
        raise ValueError("layout record must be an object")
    geometry = record.get("geometry")
    if not isinstance(geometry, Mapping) or frozenset(geometry) != _GEOMETRY_KEYS:
        raise ValueError("layout geometry has unknown or missing fields")
    if geometry["generator_version"] != GEOMETRY_GENERATOR_VERSION:
        raise ValueError("unknown geometry generator")
    family_id = str(geometry["family_id"])
    if family_id != record.get("family_id") or family_id not in {f"F{i}" for i in range(1, 11)}:
        raise ValueError("layout family is invalid")
    start = _vec2(geometry["start_center_meters"], "start_center_meters")
    goal = _vec2(geometry["goal_center_meters"], "goal_center_meters")
    direction, lateral = mission_axes(start, goal)
    points = _polyline(geometry["corridor_centerline_meters"])
    nominal_width = _finite(
        geometry["nominal_passage_width_meters"], "nominal_passage_width_meters"
    )
    horizon = _finite(geometry["episode_horizon_seconds"], "episode_horizon_seconds")
    if nominal_width <= 0.0 or horizon <= 0.0:
        raise ValueError("layout width and horizon must be positive")
    if int(geometry["initial_topology_id"]) != COMPACT:
        raise ValueError("publication layout must initialize COMPACT")
    parameters = _canonical_parameters(geometry["canonical_parameters"])
    if not isinstance(geometry["bypass_available"], bool):
        raise ValueError("bypass_available must be boolean")
    obstacles, passages, bypass = _compile_static_geometry(
        family_id,
        points,
        geometry["static_obstacles"],
        parameters,
        nominal_width,
        geometry["bypass_available"],
    )
    dynamic = _compile_dynamic(geometry["dynamic_obstacle_paths"], parameters)
    if (family_id == "F9") != bool(dynamic):
        raise ValueError("only F9 must define one dynamic obstacle")
    initial_contracts = _initial_role_contracts(start, direction)
    document: Dict[str, object] = {
        "schema_version": LAYOUT_EXECUTION_SPECIFICATION_SCHEMA_VERSION,
        "scenario_layout_schema_version": SCENARIO_LAYOUT_SCHEMA_VERSION,
        "executable_protocol_sha256": protocol["protocol_hash"],
        "source_layout": {
            "layout_id": record["layout_id"],
            "family_id": family_id,
            "split": split,
            "geometry_sha256": record["geometry_sha256"],
            "generation_seed_commitment": record["generation_seed_commitment"],
        },
        "mission_frame": {
            "world_origin_meters": [0.0, 0.0],
            "mission_origin_meters": list(start),
            "initial_topology_origin_meters": list(start),
            "goal_center_meters": list(goal),
            "longitudinal_axis": list(direction),
            "lateral_axis": list(lateral),
            "heading_radians": math.atan2(direction[1], direction[0]),
        },
        "world_bounds_meters": [list(WORLD_BOUNDS_METERS[0]), list(WORLD_BOUNDS_METERS[1])],
        "initial_topology_id": COMPACT,
        "initialization_by_team_size": initial_contracts,
        "nominal_initial_validity_by_team_size": _nominal_initial_validity(
            initial_contracts, obstacles, passages
        ),
        "goal_contract": {
            "center_meters": list(goal),
            "origin_tolerance_formula": "runtime_config.derived.formation_tolerance_meters",
            "dwell_seconds_formula": "runtime_config.physical.control_period_seconds",
        },
        "centerline": {
            "representation": "piecewise_linear_polyline",
            "control_points_meters": [list(point) for point in points],
            "full_length_meters": _polyline_length(points),
        },
        "nominal_passage_width_meters": nominal_width,
        "static_obstacles": obstacles,
        "passages": passages,
        "bypass": bypass,
        "dynamic_obstacles": dynamic,
        "communication": _communication_spec(
            str(geometry["communication_profile"]), parameters, start, passages
        ),
        "disturbance_contract": "executable_protocol.disturbance_contract",
        "source_policy_ids": list(SOURCE_POLICY_IDS),
        "target_v4_contract_sha256": protocol["target_v4_execution_contract"]["sha256"],
        "episode_horizon_seconds": horizon,
        "canonical_parameters": [[name, parameters[name]] for name in sorted(parameters)],
        "audit_only_fields": [
            "diagnostic_headroom_by_team_size", "variant_index", "layout_id",
            "generation_seed_commitment",
        ],
        "category_d_count": 0,
        "validity": "COMPILED_SPECIFICATION",
    }
    return attach_canonical_hash(document, "layout_execution_specification_sha256")


def compile_nonfinal_split(
    root: Path,
    split: str,
    protocol: Mapping[str, object],
) -> Tuple[Dict[str, object], ...]:
    if split not in ("train", "validation"):
        raise PermissionError("sealed final-test geometry cannot be compiled")
    manifest = load_nonfinal_split_manifest(
        root / f"results/rvt_fd24/splits/{split}_layouts.json"
    )
    records = manifest.get("layout_records")
    if not isinstance(records, list):
        raise ValueError("split manifest lacks layout records")
    return tuple(
        compile_layout_record(record, split, protocol)
        for record in sorted(records, key=lambda item: str(item["layout_id"]))
    )
