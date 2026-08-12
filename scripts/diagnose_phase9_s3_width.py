#!/usr/bin/env python3
"""Reconstruct the exact blocked S3 width without scientific writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import struct
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb import policies
from rvt_swarm.phase9c_rb.world import _offset_polyline
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.phase9g0r.producer import build_source_session


EVENT_ID = (
    "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F3/"
    "59dd0a284ff8482c2831245429ba843d4439d9ec6f8735696ae84e651d714dd1/"
    "N12/S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR/episode-0/event-0"
)


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: float, *, frame: str, signed: bool, source: str) -> dict:
    number = float(value)
    return {
        "value": number,
        "float_hex": number.hex(),
        "binary64_big_endian_hex": struct.pack(">d", number).hex(),
        "data_type": "IEEE-754 binary64 / Python float",
        "unit": "meters",
        "coordinate_frame": frame,
        "signed": signed,
        "source_contract": source,
    }


def _selector_projection(tokens, direction, lateral, lookahead):
    rows = []
    left = []
    right = []
    for offset, radius, key in tokens:
        ox, oy = map(float, offset)
        radius = float(radius)
        longitudinal = ox * direction[0] + oy * direction[1]
        lateral_offset = ox * lateral[0] + oy * lateral[1]
        admitted = 0.0 <= longitudinal <= lookahead
        inner = abs(lateral_offset) - radius
        row = {
            "source_key": key,
            "relative_center_meters": [ox, oy],
            "radius_meters": radius,
            "longitudinal_projection_meters": longitudinal,
            "lateral_projection_meters": lateral_offset,
            "absolute_lateral_projection_meters": abs(lateral_offset),
            "inner_surface_projection_meters": inner,
            "selector_side": "left" if lateral_offset >= 0.0 else "right",
            "admitted_by_lookahead": admitted,
        }
        rows.append(row)
        if admitted:
            (left if lateral_offset >= 0.0 else right).append(row)
    selected_left = min(left, key=lambda item: item["inner_surface_projection_meters"])
    selected_right = min(right, key=lambda item: item["inner_surface_projection_meters"])
    width = (
        selected_left["inner_surface_projection_meters"]
        + selected_right["inner_surface_projection_meters"]
    )
    return rows, selected_left, selected_right, width


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-environment", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    task = next(
        task for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train"
        )
        if task.event_id == EVENT_ID
    )
    session = build_source_session(root, task.source)
    original = policies.s3_local_geometric_decision
    calls = []

    def observed(committed_topology, **kwargs):
        same_step_calls = sum(
            item["control_step"] == session.control_step for item in calls
        )
        calls.append({
            "control_step": session.control_step,
            "time_seconds": session.time_seconds,
            "robot_id": same_step_calls,
            "committed_topology": committed_topology,
            **kwargs,
        })
        return original(committed_topology, **kwargs)

    policies.s3_local_geometric_decision = observed
    caught = None
    try:
        while session.termination is None and session.control_step < task.resolved_control_step:
            session.step()
    except Exception as exc:
        caught = exc
    finally:
        policies.s3_local_geometric_decision = original
    if caught is None or str(caught) != "S3 measured width must be finite and nonnegative":
        raise ValueError("the exact frozen-source exception was not reproduced")
    trigger = calls[-1]
    robot = session.robots[int(trigger["robot_id"])]
    view = session._build_robot_view(robot)
    tokens = session.static_world.observable_tokens(
        robot.position,
        float(session.runtime_config.sensing.obstacle_sensing_range_meters),
    )
    direction = tuple(map(float, view.mission_dir))
    lateral = (-direction[1], direction[0])
    lookahead = float(session.runtime_config.derived.lookahead_distance_meters)
    token_rows, selected_left, selected_right, reconstructed_width = (
        _selector_projection(tokens, direction, lateral, lookahead)
    )
    if reconstructed_width != float(trigger["measured_width_meters"]):
        raise ValueError("first-principles selector reconstruction differs")

    # Reversing only the representational left/right axis swaps classifications.
    # The current abs/min/sum algebra must retain the same scalar.
    reversed_rows, reversed_left, reversed_right, reversed_width = (
        _selector_projection(
            tuple(reversed(tokens)), direction, (-lateral[0], -lateral[1]), lookahead
        )
    )
    corridor = session.static_world.corridors[0]
    centerline = tuple(corridor.centerline_meters)
    positive_boundary = _offset_polyline(centerline, corridor.half_width_meters)
    negative_boundary = _offset_polyline(centerline, -corridor.half_width_meters)
    entry_aperture = math.dist(positive_boundary[0], negative_boundary[0])
    exit_aperture = math.dist(positive_boundary[-1], negative_boundary[-1])
    physical_free_width = 2.0 * corridor.half_width_meters
    if not (
        math.isclose(entry_aperture, physical_free_width, abs_tol=1e-15)
        and math.isclose(exit_aperture, physical_free_width, abs_tol=1e-15)
    ):
        raise ValueError("analytic boundary aperture differs from compiled width")
    selected_euclidean_center_separation = math.dist(
        selected_left["relative_center_meters"],
        selected_right["relative_center_meters"],
    )
    selected_euclidean_surface_separation = (
        selected_euclidean_center_separation
        - selected_left["radius_meters"]
        - selected_right["radius_meters"]
    )

    layout_path = (
        root / "results/rvt_fd24/layout_execution_specifications/train/train-f3-01.json"
    )
    report = {
        "schema_version": "rvt-phase9-s3-width-derivation/v1",
        "mode": "NON_OFFICIAL_READ_ONLY_DIAGNOSTIC",
        "execution_environment": args.execution_environment,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "blocked_task": {
            "study": task.source.study,
            "split": task.source.split,
            "family": task.source.family,
            "layout_id": task.source.layout_id,
            "layout_sha256": task.source.layout_sha256,
            "team_size": task.source.team_size,
            "episode_id": task.source.job_id,
            "scientific_episode_seeds": dict(task.source.seeds),
            "decision_event_id": task.event_id,
            "decision_timestep": task.resolved_control_step,
            "decision_timestamp_seconds": task.resolved_timestamp_seconds,
            "source_task_id": task.source.job_id,
            "candidate_topology_id": 5,
            "replica_identities": [
                item["job_id"] for item in task.candidate_replica_jobs
                if int(item["candidate_topology"]) == 5
            ],
            "matched_stream_identities": [
                int(item["seeds"]["matched_disturbance_seed"])
                for item in task.candidate_replica_jobs
                if int(item["candidate_topology"]) == 5
            ],
            "scientific_atomic_unit_id": hashlib.sha256(json.dumps(
                {"candidate_topology_id": 5, "event_id": task.event_id},
                ensure_ascii=True, separators=(",", ":"), sort_keys=True,
            ).encode("ascii")).hexdigest(),
        },
        "failure_call": {
            "session_control_step": trigger["control_step"],
            "session_time_seconds": trigger["time_seconds"],
            "robot_id": trigger["robot_id"],
            "role_id": robot.role_id,
            "robot_position_meters": list(robot.position),
            "robot_velocity_meters_per_second": list(robot.velocity),
            "committed_topology_id": trigger["committed_topology"],
            "line_required_width_meters": trigger["line_required_width_meters"],
            "compact_required_width_meters": trigger[
                "compact_required_width_meters"
            ],
            "spacing_margin_meters": trigger["spacing_margin_meters"],
            "evidence_duration_seconds": trigger["evidence_duration_seconds"],
            "evidence_persistence_seconds": trigger[
                "evidence_persistence_seconds"
            ],
            "exception_class": type(caught).__name__,
            "exception_message": str(caught),
        },
        "coordinate_frames": {
            "world": {"x_axis": [1.0, 0.0], "y_axis": [0.0, 1.0]},
            "mission": {
                "longitudinal_axis": list(direction),
                "lateral_axis": list(lateral),
                "origin_meters": list(session.mission_origin),
                "right_handed": True,
                "mission_tangent_definition": "(goal-start)/norm(goal-start)",
                "mission_normal_definition": "(-tangent_y,tangent_x)",
                "selector_left_definition": "nonnegative ego lateral projection",
                "selector_right_definition": "negative ego lateral projection",
            },
        },
        "formula": {
            "longitudinal": "dot(ego_support_center, mission_tangent)",
            "lateral_offset": "dot(ego_support_center, mission_normal)",
            "admission": "0 <= longitudinal <= derived_lookahead",
            "inner_surface_projection": "abs(lateral_offset) - support_radius",
            "left": "minimum inner_surface_projection where lateral_offset >= 0",
            "right": "minimum inner_surface_projection where lateral_offset < 0",
            "measured_width": "left + right",
        },
        "direct_operands": {
            "lookahead_distance": _number(
                lookahead,
                frame="mission longitudinal axis",
                signed=False,
                source="RuntimeConfig.derived.lookahead_distance_meters",
            ),
            "selected_left_lateral_offset": _number(
                selected_left["lateral_projection_meters"],
                frame="ego-relative mission lateral axis",
                signed=True,
                source=selected_left["source_key"],
            ),
            "selected_left_radius": _number(
                selected_left["radius_meters"],
                frame="Euclidean support disc",
                signed=False,
                source="static_obstacle_contract.sensor_conversion",
            ),
            "selected_left_inner": _number(
                selected_left["inner_surface_projection_meters"],
                frame="ego-relative mission lateral axis",
                signed=True,
                source="abs(left lateral projection)-support radius",
            ),
            "selected_right_lateral_offset": _number(
                selected_right["lateral_projection_meters"],
                frame="ego-relative mission lateral axis",
                signed=True,
                source=selected_right["source_key"],
            ),
            "selected_right_radius": _number(
                selected_right["radius_meters"],
                frame="Euclidean support disc",
                signed=False,
                source="static_obstacle_contract.sensor_conversion",
            ),
            "selected_right_inner": _number(
                selected_right["inner_surface_projection_meters"],
                frame="ego-relative mission lateral axis",
                signed=True,
                source="abs(right lateral projection)-support radius",
            ),
            "measured_width": _number(
                reconstructed_width,
                frame="ego-relative mission lateral projection",
                signed=True,
                source="LocalGeometricSelectorPolicy.observe left+right",
            ),
        },
        "selected_supports": {
            "left": selected_left,
            "right": selected_right,
            "same_compiled_boundary_side": (
                selected_left["source_key"].split("-")[2]
                == selected_right["source_key"].split("-")[2]
            ),
            "euclidean_center_separation_meters": (
                selected_euclidean_center_separation
            ),
            "euclidean_surface_separation_meters": (
                selected_euclidean_surface_separation
            ),
        },
        "observable_supports": token_rows,
        "physical_geometry": {
            "source_layout_file": str(layout_path.relative_to(root)),
            "source_layout_file_sha256": _file_sha(layout_path),
            "primitive_type": corridor.primitive_type,
            "primitive_index": corridor.primitive_index,
            "centerline_control_points_meters": [list(p) for p in centerline],
            "active_world_x_slab_meters": list(corridor.slab_world_x_meters),
            "half_width_meters": corridor.half_width_meters,
            "independent_physical_free_width_meters": physical_free_width,
            "positive_boundary_control_points_meters": [
                list(p) for p in positive_boundary
            ],
            "negative_boundary_control_points_meters": [
                list(p) for p in negative_boundary
            ],
            "entry_aperture_meters": entry_aperture,
            "exit_aperture_meters": exit_aperture,
            "robot_euclidean_surface_distance_meters": corridor.surface_distance(
                robot.position
            ),
            "classification": "A_PHYSICALLY_POSITIVE_WIDTH_FEASIBLE",
        },
        "representational_ordering_tests": {
            "token_iteration_reversed": True,
            "mission_lateral_axis_reversed": True,
            "reversed_left_source_key": reversed_left["source_key"],
            "reversed_right_source_key": reversed_right["source_key"],
            "original_width_meters": reconstructed_width,
            "reversed_width_meters": reversed_width,
            "bit_equal": struct.pack(">d", reconstructed_width)
            == struct.pack(">d", reversed_width),
            "sign_changed": math.copysign(1.0, reconstructed_width)
            != math.copysign(1.0, reversed_width),
            "physical_geometry_changed": False,
            "reversed_observable_support_count": len(reversed_rows),
        },
        "call_audit": {
            "s3_calls_before_exception": len(calls),
            "negative_calls_before_exception": sum(
                item["measured_width_meters"] is not None
                and float(item["measured_width_meters"]) < 0.0
                for item in calls
            ),
            "calls": calls,
        },
        "official_staging_writes": 0,
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    report = attach_canonical_hash(report, "phase9_s3_width_derivation_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "hash": report["phase9_s3_width_derivation_sha256"],
        "robot_id": trigger["robot_id"],
        "width": reconstructed_width,
        "physical_width": physical_free_width,
        "same_boundary_side": report["selected_supports"][
            "same_compiled_boundary_side"
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
