#!/usr/bin/env python3
"""Audit the owner S3 pairing rule without changing executable science."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import struct
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import compile_source_tasks
from rvt_swarm.phase9g0r.producer import build_source_session


S3 = "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR"
BLOCKED_SOURCE_ID = (
    "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F3/"
    "59dd0a284ff8482c2831245429ba843d4439d9ec6f8735696ae84e651d714dd1/"
    "N12/S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR/episode-0"
)


def _number(value: float) -> dict[str, Any]:
    number = float(value)
    return {
        "value": number,
        "float_hex": number.hex(),
        "binary64_big_endian_hex": struct.pack(">d", number).hex(),
        "data_type": "IEEE-754 binary64 / Python float",
        "unit": "meters",
    }


def _project_segment(point, start, end):
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    denominator = dx * dx + dy * dy
    if denominator <= 0.0:
        raise ValueError("compiled corridor segment must be nondegenerate")
    u = (
        (float(point[0]) - float(start[0])) * dx
        + (float(point[1]) - float(start[1])) * dy
    ) / denominator
    u = max(0.0, min(1.0, u))
    center = (float(start[0]) + u * dx, float(start[1]) + u * dy)
    distance_squared = (
        (float(point[0]) - center[0]) ** 2
        + (float(point[1]) - center[1]) ** 2
    )
    length = math.sqrt(denominator)
    return distance_squared, center, (dx / length, dy / length), u


def _diagnostic_local_frame(session, robot) -> dict[str, Any]:
    """Recover c/t/n only from existing compiled runtime geometry.

    This is diagnostic evidence, not a deployable rule. In particular, the
    pre-A1S3R RobotView does not carry this local corridor frame.
    """
    candidates = []
    for corridor in session.static_world.corridors:
        points = corridor.centerline_meters
        for segment_index in range(len(points) - 1):
            distance, center, tangent, u = _project_segment(
                robot.position, points[segment_index], points[segment_index + 1]
            )
            if (
                tangent[0] * session.mission_direction[0]
                + tangent[1] * session.mission_direction[1]
            ) < 0.0:
                tangent = (-tangent[0], -tangent[1])
            candidates.append({
                "distance_squared_meters2": distance,
                "primitive_index": corridor.primitive_index,
                "segment_index": segment_index,
                "segment_parameter": u,
                "center_world_meters": list(center),
                "tangent_world": list(tangent),
                "source": "compiled polyline corridor nearest-point projection",
            })
    if candidates:
        minimum = min(item["distance_squared_meters2"] for item in candidates)
        nearest = [
            item for item in candidates
            if item["distance_squared_meters2"] == minimum
        ]
        selected = min(
            nearest,
            key=lambda item: (item["primitive_index"], item["segment_index"]),
        )
        frame_tie = len({
            (
                tuple(item["center_world_meters"]),
                tuple(item["tangent_world"]),
            )
            for item in nearest
        }) > 1
    else:
        tangent = tuple(map(float, session.mission_direction))
        origin = tuple(map(float, session.mission_origin))
        delta = (
            float(robot.position[0]) - origin[0],
            float(robot.position[1]) - origin[1],
        )
        longitudinal = delta[0] * tangent[0] + delta[1] * tangent[1]
        center = (
            origin[0] + longitudinal * tangent[0],
            origin[1] + longitudinal * tangent[1],
        )
        selected = {
            "distance_squared_meters2": (
                (float(robot.position[0]) - center[0]) ** 2
                + (float(robot.position[1]) - center[1]) ** 2
            ),
            "primitive_index": None,
            "segment_index": None,
            "segment_parameter": longitudinal,
            "center_world_meters": list(center),
            "tangent_world": list(tangent),
            "source": "compiled mission-frame reference-line projection",
        }
        nearest = [selected]
        frame_tie = False
    tangent = tuple(selected["tangent_world"])
    normal = (-tangent[1], tangent[0])
    return {
        "c_world_meters": selected["center_world_meters"],
        "t_world": list(tangent),
        "n_world": list(normal),
        "source": selected["source"],
        "primitive_index": selected["primitive_index"],
        "segment_index": selected["segment_index"],
        "segment_parameter": selected["segment_parameter"],
        "nearest_frame_candidate_count": len(nearest),
        "physically_distinct_frame_tie": frame_tie,
    }


def _component_identity(source_key: str) -> str:
    parts = source_key.split("-")
    if len(parts) >= 4 and parts[0] == "corridor":
        return "-".join(parts[:3])
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return source_key


def _selection(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    negative = [row for row in rows if row["owner_side"] == "NEGATIVE"]
    positive = [row for row in rows if row["owner_side"] == "POSITIVE"]
    d_neg = max(
        (float(row["signed_inner_surface_coordinate_meters"]) for row in negative),
        default=None,
    )
    d_pos = min(
        (float(row["signed_inner_surface_coordinate_meters"]) for row in positive),
        default=None,
    )
    selected_negative = [
        row for row in negative
        if row["signed_inner_surface_coordinate_meters"] == d_neg
    ]
    selected_positive = [
        row for row in positive
        if row["signed_inner_surface_coordinate_meters"] == d_pos
    ]
    width = d_pos - d_neg if d_neg is not None and d_pos is not None else None
    distinct_tie = any(
        len({_component_identity(row["source_key"]) for row in selected}) > 1
        for selected in (selected_negative, selected_positive)
    )
    return {
        "valid_negative_side_support": bool(negative),
        "valid_positive_side_support": bool(positive),
        "both_sides": bool(negative and positive),
        "missing_side": not bool(negative and positive),
        "d_neg_meters": d_neg,
        "d_pos_meters": d_pos,
        "width_meters": width,
        "selected_negative_supports": [row["source_key"] for row in selected_negative],
        "selected_positive_supports": [row["source_key"] for row in selected_positive],
        "selected_negative_component_equivalence": sorted({
            _component_identity(row["source_key"]) for row in selected_negative
        }),
        "selected_positive_component_equivalence": sorted({
            _component_identity(row["source_key"]) for row in selected_positive
        }),
        "equal_distance_tie": (
            len(selected_negative) > 1 or len(selected_positive) > 1
        ),
        "physically_distinct_equal_distance_tie": distinct_tie,
    }


def _observation(session, robot) -> dict[str, Any]:
    frame = _diagnostic_local_frame(session, robot)
    c = tuple(frame["c_world_meters"])
    normal = tuple(frame["n_world"])
    direction = tuple(map(float, session.mission_direction))
    lookahead = float(session.runtime_config.derived.lookahead_distance_meters)
    tokens = session.static_world.observable_tokens(
        robot.position,
        float(session.runtime_config.sensing.obstacle_sensing_range_meters),
    )
    anonymous = tuple(
        (float(offset[0]), float(offset[1]), float(radius))
        for offset, radius, _ in tokens
    )
    view = session._build_robot_view(robot)
    if anonymous != tuple(view.obstacles):
        raise ValueError("diagnostic identity-bearing tokens differ from RobotView")
    rows = []
    centerline_degenerate = []
    for token_index, (offset, radius, source_key) in enumerate(tokens):
        ox, oy = map(float, offset)
        radius = float(radius)
        longitudinal = ox * direction[0] + oy * direction[1]
        participating = 0.0 <= longitudinal <= lookahead
        world_center = (
            float(robot.position[0]) + ox,
            float(robot.position[1]) + oy,
        )
        relative_to_c = (world_center[0] - c[0], world_center[1] - c[1])
        signed_center = (
            relative_to_c[0] * normal[0] + relative_to_c[1] * normal[1]
        )
        if signed_center > 0.0:
            signed_inner = signed_center - radius
        elif signed_center < 0.0:
            signed_inner = signed_center + radius
        else:
            signed_inner = None
        if not participating:
            owner_side = "OUTSIDE_EXISTING_LOOKAHEAD"
        elif signed_center == 0.0 or signed_inner == 0.0:
            owner_side = "CENTERLINE_DEGENERATE"
        elif signed_inner is not None and signed_inner < 0.0:
            owner_side = "NEGATIVE"
        else:
            owner_side = "POSITIVE"
        row = {
            "token_index_diagnostic_only": token_index,
            "source_key": str(source_key),
            "physical_component_diagnostic": _component_identity(str(source_key)),
            "relative_center_meters": [ox, oy],
            "world_center_meters": list(world_center),
            "radius_meters": radius,
            "existing_lookahead_longitudinal_meters": longitudinal,
            "participates_in_existing_s3_lookahead": participating,
            "signed_center_coordinate_meters": signed_center,
            "signed_center_float_hex": signed_center.hex(),
            "signed_inner_surface_coordinate_meters": signed_inner,
            "signed_inner_surface_float_hex": (
                signed_inner.hex() if signed_inner is not None else None
            ),
            "owner_side": owner_side,
        }
        rows.append(row)
        if participating and owner_side == "CENTERLINE_DEGENERATE":
            centerline_degenerate.append(row)
    participating_rows = [
        row for row in rows
        if row["participates_in_existing_s3_lookahead"]
        and row["owner_side"] != "CENTERLINE_DEGENERATE"
    ]
    selection = _selection(participating_rows)
    canonical_order = sorted(
        rows,
        key=lambda row: (
            row["source_key"],
            row["relative_center_meters"],
            row["radius_meters"],
        ),
    )
    reversed_selection = _selection(list(reversed(participating_rows)))
    canonical_selection = _selection([
        row for row in canonical_order
        if row["participates_in_existing_s3_lookahead"]
        and row["owner_side"] != "CENTERLINE_DEGENERATE"
    ])
    invariant_projection = lambda item: {
        key: item[key]
        for key in (
            "valid_negative_side_support", "valid_positive_side_support",
            "both_sides", "missing_side", "d_neg_meters", "d_pos_meters",
            "width_meters", "selected_negative_component_equivalence",
            "selected_positive_component_equivalence",
            "physically_distinct_equal_distance_tie",
        )
    }
    return {
        "robot_id": robot.robot_id,
        "role_id": robot.role_id,
        "robot_position_meters": list(robot.position),
        "local_frame_diagnostic": frame,
        "support_table": rows,
        "selection": selection,
        "centerline_degenerate_support_count": len(centerline_degenerate),
        "centerline_degenerate_supports": [
            row["source_key"] for row in centerline_degenerate
        ],
        "token_order_invariance": {
            "canonical_vs_runtime_exact": (
                invariant_projection(selection)
                == invariant_projection(canonical_selection)
            ),
            "reversed_vs_runtime_exact": (
                invariant_projection(selection)
                == invariant_projection(reversed_selection)
            ),
        },
    }


def _distribution(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    records = list(records)
    widths = [
        float(record["selection"]["width_meters"])
        for record in records if record["selection"]["width_meters"] is not None
    ]
    return {
        "observation_count": len(records),
        "valid_negative_side_support": sum(
            record["selection"]["valid_negative_side_support"] for record in records
        ),
        "valid_positive_side_support": sum(
            record["selection"]["valid_positive_side_support"] for record in records
        ),
        "both_sides": sum(record["selection"]["both_sides"] for record in records),
        "missing_side": sum(record["selection"]["missing_side"] for record in records),
        "centerline_degenerate": sum(
            record["centerline_degenerate_support_count"] > 0 for record in records
        ),
        "equal_distance_tie": sum(
            record["selection"]["equal_distance_tie"] for record in records
        ),
        "physically_distinct_equal_distance_tie": sum(
            record["selection"]["physically_distinct_equal_distance_tie"]
            for record in records
        ),
        "width_count": len(widths),
        "minimum_width_meters": min(widths) if widths else None,
        "median_width_meters": statistics.median(widths) if widths else None,
        "maximum_width_meters": max(widths) if widths else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-environment", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    tasks = tuple(
        task
        for split in ("train", "validation")
        for task in compile_source_tasks(
            root, study="study_a_zero_shot", split=split
        )
        if task.source_class == S3
    )
    if len(tasks) != 250 or any(task.team_size == 24 for task in tasks):
        raise ValueError("authorized S3 universe changed")

    instance_records = []
    observation_records = []
    for task in tasks:
        session = build_source_session(root, task)
        source_exception = None
        for _ in range(3):
            if session.termination is not None:
                break
            try:
                session.step()
            except Exception as exc:  # diagnostic records source totality only
                source_exception = {
                    "class": type(exc).__name__, "message": str(exc)
                }
                break
        observations = []
        if session.termination is None and source_exception is None:
            observations = [_observation(session, robot) for robot in session.robots]
            for observation in observations:
                observation_records.append({
                    "source_task_id": task.job_id,
                    "study": task.study,
                    "split": task.split,
                    "family": task.family,
                    "layout_id": task.layout_id,
                    "layout_sha256": task.layout_sha256,
                    "team_size": task.team_size,
                    "episode_index": task.episode_index,
                    "control_step": session.control_step,
                    "time_seconds": session.time_seconds,
                    **observation,
                })
        instance_records.append({
            "source_task_id": task.job_id,
            "study": task.study,
            "split": task.split,
            "family": task.family,
            "layout_id": task.layout_id,
            "layout_sha256": task.layout_sha256,
            "team_size": task.team_size,
            "episode_index": task.episode_index,
            "scientific_episode_seeds": dict(task.seeds),
            "source_termination": (
                session.termination.cause if session.termination is not None else None
            ),
            "source_exception": source_exception,
            "robot_observation_count": len(observations),
            "valid_negative_side_support": sum(
                item["selection"]["valid_negative_side_support"]
                for item in observations
            ),
            "valid_positive_side_support": sum(
                item["selection"]["valid_positive_side_support"]
                for item in observations
            ),
            "both_sides": sum(item["selection"]["both_sides"] for item in observations),
            "missing_side": sum(item["selection"]["missing_side"] for item in observations),
            "centerline_degenerate_support_count": sum(
                item["centerline_degenerate_support_count"] for item in observations
            ),
        })

    degenerate = [
        record for record in observation_records
        if record["centerline_degenerate_support_count"] > 0
    ]
    distinct_ties = [
        record for record in observation_records
        if record["selection"]["physically_distinct_equal_distance_tie"]
    ]
    if not degenerate:
        raise ValueError("expected authorized centerline degeneracy disappeared")
    if distinct_ties:
        raise ValueError("physically distinct support tie requires separate stop")
    if any(
        not record["token_order_invariance"]["canonical_vs_runtime_exact"]
        or not record["token_order_invariance"]["reversed_vs_runtime_exact"]
        for record in observation_records
    ):
        raise ValueError("owner-rule scalar projection depends on token order")

    blocked = next(
        record for record in observation_records
        if record["source_task_id"] == BLOCKED_SOURCE_ID
        and record["robot_id"] == 8
    )
    grouped = defaultdict(list)
    for record in observation_records:
        grouped[(record["split"], record["family"], record["team_size"],
                 record["layout_id"])].append(record)
    by_group = [
        {
            "split": key[0], "family": key[1], "team_size": key[2],
            "layout_id": key[3], **_distribution(records),
        }
        for key, records in sorted(grouped.items())
    ]
    semantic_projection = {
        "instances": instance_records,
        "observations": [
            {
                "source_task_id": record["source_task_id"],
                "robot_id": record["robot_id"],
                "local_frame_diagnostic": record["local_frame_diagnostic"],
                "selection": record["selection"],
                "centerline_degenerate_supports": record[
                    "centerline_degenerate_supports"
                ],
                "support_projection": [
                    {
                        "source_key": row["source_key"],
                        "participates": row[
                            "participates_in_existing_s3_lookahead"
                        ],
                        "signed_center": row["signed_center_coordinate_meters"],
                        "signed_inner": row[
                            "signed_inner_surface_coordinate_meters"
                        ],
                        "owner_side": row["owner_side"],
                    }
                    for row in record["support_table"]
                ],
            }
            for record in observation_records
        ],
    }
    report = {
        "schema_version": "rvt-phase9-s3r-owner-rule-audit/v1",
        "mode": "NON_OFFICIAL_AUTHORIZED_READ_ONLY_DIAGNOSTIC",
        "execution_environment": args.execution_environment,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "selection_contract": {
            "study": "study_a_zero_shot",
            "splits": ["train", "validation"],
            "source_class": S3,
            "source_instance_count": 250,
            "diagnostic_control_steps": 3,
            "study_a_n24_excluded": True,
            "study_b_excluded": True,
            "final_test_excluded": True,
            "official_staging_writes": 0,
        },
        "owner_rule_projection": {
            "frame": (
                "existing compiled corridor nearest-point frame, or existing "
                "compiled mission reference line when no corridor exists"
            ),
            "lookahead_admission_unchanged": (
                "0 <= dot(ego support center, frozen mission direction) <= "
                "derived lookahead"
            ),
            "support_inner_surface": (
                "existing sensor support center shifted by one token radius "
                "toward free space along the diagnostic local normal"
            ),
            "negative_selection": "max(d_k where d_k < 0)",
            "positive_selection": "min(d_k where d_k > 0)",
            "width": "d_pos-d_neg",
            "numerical_epsilon": None,
        },
        "population": {
            "source_instance_count": len(instance_records),
            "active_source_instance_count": sum(
                record["robot_observation_count"] > 0 for record in instance_records
            ),
            "source_terminated_before_diagnostic": sum(
                record["source_termination"] is not None for record in instance_records
            ),
            **_distribution(observation_records),
        },
        "by_split_family_team_size_layout": by_group,
        "blocked_case_robot_8": blocked,
        "centerline_degeneracy": {
            "status": "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED",
            "affected_observation_count": len(degenerate),
            "observations": degenerate,
            "existing_authoritative_epsilon_found": False,
            "existing_boundary_on_centerline_rule_found": False,
            "new_epsilon_introduced": False,
        },
        "tie_audit": {
            "equal_distance_observation_count": sum(
                record["selection"]["equal_distance_tie"]
                for record in observation_records
            ),
            "physically_distinct_equal_distance_observation_count": len(distinct_ties),
            "equivalent_representation_ties_do_not_change_width": True,
            "runtime_token_order_used_as_tie_break": False,
            "status": "NO_DISTINCT_SCIENTIFIC_TIE_BLOCKER",
        },
        "token_order_audit": {
            "observations_tested": len(observation_records),
            "orders_per_observation": 3,
            "semantic_projection_mismatches": 0,
            "note": (
                "This is a diagnostic projection of the owner rule, not an "
                "implemented executable path."
            ),
        },
        "instance_records": instance_records,
        "semantic_projection_sha256": sha256_document(semantic_projection),
        "scientific_stop": {
            "required": True,
            "reason": "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED",
            "executable_repair_permitted": False,
        },
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    report = attach_canonical_hash(report, "phase9_s3r_owner_rule_audit_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "hash": report["phase9_s3r_owner_rule_audit_sha256"],
        "population": report["population"],
        "degenerate": len(degenerate),
        "semantic_projection": report["semantic_projection_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
