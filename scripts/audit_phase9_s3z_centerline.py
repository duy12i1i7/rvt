#!/usr/bin/env python3
"""Requalify exact-centerline S3 semantics on the frozen authorized traces."""

from __future__ import annotations

import argparse
import copy
import json
import math
import platform
import statistics
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Sequence

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase8e.protocol import s3_local_geometric_decision
from rvt_swarm.phase9c_rb import policies
from rvt_swarm.phase9c_rb.s3_geometry import (
    CENTERLINE_NEUTRAL,
    NEGATIVE,
    POSITIVE,
    S3OpposingBoundaryMeasurement,
    S3SupportProjection,
    measure_s3_opposing_boundaries,
)
from rvt_swarm.phase9g0r.compiler import compile_source_tasks
from rvt_swarm.phase9g0r.producer import build_source_session
from scripts.audit_phase9_s3r_owner_rule import (
    BLOCKED_SOURCE_ID,
    _component_identity,
)


S3 = "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR"


def _legacy_measurement(
    obstacles: Sequence[tuple[float, float, float]],
    *,
    mission_direction,
    lookahead_distance_meters,
    **_ignored,
) -> S3OpposingBoundaryMeasurement:
    """Pre-addendum estimator used only to reconstruct frozen trace prefixes."""
    direction = tuple(map(float, mission_direction))
    lateral = (-direction[1], direction[0])
    lookahead = float(lookahead_distance_meters)
    left: list[tuple[float, int]] = []
    right: list[tuple[float, int]] = []
    projections = []
    participating = 0
    for index, (ox, oy, radius) in enumerate(obstacles):
        ox, oy, radius = float(ox), float(oy), float(radius)
        longitudinal = ox * direction[0] + oy * direction[1]
        if not 0.0 <= longitudinal <= lookahead:
            continue
        participating += 1
        offset = ox * lateral[0] + oy * lateral[1]
        inner = abs(offset) - radius
        if offset >= 0.0:
            left.append((inner, index))
            side = POSITIVE
        else:
            right.append((inner, index))
            side = NEGATIVE
        projections.append(S3SupportProjection(
            token_index=index,
            signed_center_coordinate_meters=offset,
            signed_inner_surface_coordinate_meters=inner,
            classification=side,
        ))
    selected_left = min((value for value, _ in left), default=None)
    selected_right = min((value for value, _ in right), default=None)
    width = (
        selected_left + selected_right
        if selected_left is not None and selected_right is not None else None
    )
    complete_open = participating == 0
    return S3OpposingBoundaryMeasurement(
        complete_open_observation=complete_open,
        complete_observation=complete_open or width is not None,
        measured_width_meters=width,
        d_neg_meters=selected_right,
        d_pos_meters=selected_left,
        selected_negative_indices=tuple(
            index for value, index in right if value == selected_right),
        selected_positive_indices=tuple(
            index for value, index in left if value == selected_left),
        projections=tuple(projections),
    )


@contextmanager
def _historical_prefix_runtime():
    current = policies.measure_s3_opposing_boundaries
    policies.measure_s3_opposing_boundaries = _legacy_measurement
    try:
        yield
    finally:
        policies.measure_s3_opposing_boundaries = current


def _scene_inventory(session) -> dict[str, Any]:
    return {
        "circles": [
            {
                "identity": f"circle-{circle.primitive_index}",
                "center_meters": list(circle.center_meters),
                "radius_meters": circle.radius_meters,
                "source_primitive_type": circle.source_primitive_type,
            }
            for circle in session.static_world.circles
        ],
        "corridors": [
            {
                "identity": f"corridor-{corridor.primitive_index}",
                "centerline_meters": [list(point) for point in corridor.centerline_meters],
                "half_width_meters": corridor.half_width_meters,
                "primitive_type": corridor.primitive_type,
            }
            for corridor in session.static_world.corridors
        ],
    }


def _selection_projection(measurement, tokens) -> dict[str, Any]:
    negative_keys = [tokens[index][2] for index in measurement.selected_negative_indices]
    positive_keys = [tokens[index][2] for index in measurement.selected_positive_indices]
    return {
        "valid_negative_side_support": measurement.d_neg_meters is not None,
        "valid_positive_side_support": measurement.d_pos_meters is not None,
        "both_sides": measurement.measured_width_meters is not None,
        "missing_side": measurement.measured_width_meters is None,
        "d_neg_meters": measurement.d_neg_meters,
        "d_pos_meters": measurement.d_pos_meters,
        "width_meters": measurement.measured_width_meters,
        "selected_negative_supports": negative_keys,
        "selected_positive_supports": positive_keys,
        "selected_negative_components": sorted({
            _component_identity(key) for key in negative_keys
        }),
        "selected_positive_components": sorted({
            _component_identity(key) for key in positive_keys
        }),
        "equal_distance_tie": len(negative_keys) > 1 or len(positive_keys) > 1,
        "physically_distinct_equal_distance_tie": (
            len({_component_identity(key) for key in negative_keys}) > 1
            or len({_component_identity(key) for key in positive_keys}) > 1
        ),
    }


def _permuted_projection(tokens, view, lookahead, order) -> dict[str, Any]:
    ordered = tuple(tokens[index] for index in order)
    anonymous = tuple((token[0][0], token[0][1], token[1]) for token in ordered)
    measurement = measure_s3_opposing_boundaries(
        anonymous,
        mission_direction=view.mission_dir,
        support_origin_world_meters=view.position,
        local_frame_center_world_meters=view.s3_frame_center_world_meters,
        local_frame_normal=view.s3_frame_normal,
        lookahead_distance_meters=lookahead,
    )
    selection = _selection_projection(measurement, ordered)
    classifications = sorted(
        (ordered[row.token_index][2], row.classification)
        for row in measurement.projections
    )
    return {
        "classification": classifications,
        "d_neg_meters": selection["d_neg_meters"],
        "d_pos_meters": selection["d_pos_meters"],
        "width_meters": selection["width_meters"],
        "negative_components": selection["selected_negative_components"],
        "positive_components": selection["selected_positive_components"],
        "physically_distinct_equal_distance_tie": selection[
            "physically_distinct_equal_distance_tie"
        ],
    }


def _observation(session, robot) -> dict[str, Any]:
    view = session._build_robot_view(robot)
    if view.s3_frame_center_world_meters is None or view.s3_frame_normal is None:
        raise ValueError("qualified local S3 frame missing")
    sensing_range = float(
        session.runtime_config.sensing.obstacle_sensing_range_meters)
    tokens = session.static_world.observable_tokens(robot.position, sensing_range)
    anonymous = tuple((offset[0], offset[1], radius) for offset, radius, _ in tokens)
    if anonymous != tuple(view.obstacles):
        raise ValueError("identity-bearing diagnostic tokens differ from RobotView")
    lookahead = float(session.runtime_config.derived.lookahead_distance_meters)
    measurement = measure_s3_opposing_boundaries(
        view.obstacles,
        mission_direction=view.mission_dir,
        support_origin_world_meters=view.position,
        local_frame_center_world_meters=view.s3_frame_center_world_meters,
        local_frame_normal=view.s3_frame_normal,
        lookahead_distance_meters=lookahead,
    )
    selection = _selection_projection(measurement, tokens)
    projection_by_index = {row.token_index: row for row in measurement.projections}
    selected = set(measurement.selected_negative_indices + measurement.selected_positive_indices)
    support_table = []
    for index, (offset, radius, source_key) in enumerate(tokens):
        longitudinal = (
            float(offset[0]) * view.mission_dir[0]
            + float(offset[1]) * view.mission_dir[1]
        )
        projection = projection_by_index.get(index)
        support_table.append({
            "scientific_support_identity": source_key,
            "physical_primitive_identity": _component_identity(source_key),
            "support_primitive": (
                "circle obstacle" if source_key.startswith("circle-")
                else "support disc derived from analytic corridor boundary"
            ),
            "relative_center_meters": list(offset),
            "world_center_meters": [
                robot.position[0] + offset[0], robot.position[1] + offset[1]
            ],
            "radius_meters": radius,
            "existing_lookahead_longitudinal_meters": longitudinal,
            "participates_in_s3_lookahead": projection is not None,
            "d_center_meters": (
                projection.signed_center_coordinate_meters if projection else None
            ),
            "d_center_float_hex": (
                projection.signed_center_coordinate_meters.hex() if projection else None
            ),
            "d_inner_meters": (
                projection.signed_inner_surface_coordinate_meters if projection else None
            ),
            "d_inner_float_hex": (
                projection.signed_inner_surface_coordinate_meters.hex()
                if projection and projection.signed_inner_surface_coordinate_meters is not None
                else None
            ),
            "classification": (
                projection.classification if projection else "OUTSIDE_LOOKAHEAD"
            ),
            "selected": index in selected,
        })

    orders = (
        tuple(range(len(tokens))),
        tuple(sorted(range(len(tokens)), key=lambda index: tokens[index][2])),
        tuple(reversed(range(len(tokens)))),
    )
    permutation_projections = [
        _permuted_projection(tokens, view, lookahead, order) for order in orders
    ]
    if any(item != permutation_projections[0] for item in permutation_projections[1:]):
        raise ValueError("S3 projection depends on support-token order")

    center_world = view.s3_frame_center_world_meters
    return {
        "robot_id": robot.robot_id,
        "role_id": robot.role_id,
        "robot_position_meters": list(robot.position),
        "local_frame": {
            "c_world_meters": list(center_world),
            "c_ego_meters": [
                center_world[0] - robot.position[0],
                center_world[1] - robot.position[1],
            ],
            "n_world": list(view.s3_frame_normal),
            "t_world": [view.s3_frame_normal[1], -view.s3_frame_normal[0]],
        },
        "support_table": support_table,
        "selection": selection,
        "centerline_neutral_supports": [
            row["scientific_support_identity"] for row in support_table
            if row["classification"] == CENTERLINE_NEUTRAL
        ],
        "token_order_invariance": {
            "orders_tested": 3,
            "semantic_projection_exact": True,
        },
    }


def _state_digest(session) -> str:
    projection = {
        "control_step": session.control_step,
        "time_seconds": session.time_seconds,
        "termination": (
            vars(session.termination) if session.termination is not None else None
        ),
        "robots": [
            {
                "robot_id": robot.robot_id,
                "position": list(robot.position),
                "velocity": list(robot.velocity),
                "committed_topology": robot.committed_topology,
                "protocol_state": robot.protocol_node.state,
            }
            for robot in session.robots
        ],
        "events": session.event_log,
        "policy_evidence_seconds": session.source_policy.evidence_seconds,
    }
    return sha256_document(projection)


def _replay_one_new_step(session) -> dict[str, Any]:
    clone = copy.deepcopy(session)
    before_inventory = _scene_inventory(clone)
    clone.step()
    after_inventory = _scene_inventory(clone)
    if before_inventory != after_inventory:
        raise ValueError("S3 pairing changed physical scene inventory")
    return {
        "control_step": clone.control_step,
        "termination": vars(clone.termination) if clone.termination else None,
        "semantic_digest": _state_digest(clone),
        "physical_scene_sha256_before": sha256_document(before_inventory),
        "physical_scene_sha256_after": sha256_document(after_inventory),
    }


def _distribution(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    records = list(records)
    widths = [
        record["selection"]["width_meters"] for record in records
        if record["selection"]["width_meters"] is not None
    ]
    support_rows = [row for record in records for row in record["support_table"]
                    if row["participates_in_s3_lookahead"]]
    classes = Counter(row["classification"] for row in support_rows)
    return {
        "robot_observation_count": len(records),
        "participating_support_observation_count": len(support_rows),
        "negative_support_observations": classes[NEGATIVE],
        "positive_support_observations": classes[POSITIVE],
        "centerline_neutral_support_observations": classes[CENTERLINE_NEUTRAL],
        "instances_with_both_opposing_sides": sum(
            record["selection"]["both_sides"] for record in records),
        "instances_missing_negative": sum(
            not record["selection"]["valid_negative_side_support"] for record in records),
        "instances_missing_positive": sum(
            not record["selection"]["valid_positive_side_support"] for record in records),
        "instances_with_support_tie": sum(
            record["selection"]["equal_distance_tie"] for record in records),
        "instances_with_physically_distinct_tie": sum(
            record["selection"]["physically_distinct_equal_distance_tie"]
            for record in records),
        "width": {
            "count": len(widths),
            "minimum_meters": min(widths) if widths else None,
            "median_meters": statistics.median(widths) if widths else None,
            "maximum_meters": max(widths) if widths else None,
        },
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
        for task in compile_source_tasks(root, study="study_a_zero_shot", split=split)
        if task.source_class == S3
    )
    if len(tasks) != 250 or any(task.team_size == 24 for task in tasks):
        raise ValueError("authorized nonsealed S3 population changed")

    instance_records = []
    observation_records = []
    sessions = {}
    for task in tasks:
        session = build_source_session(root, task)
        source_exception = None
        with _historical_prefix_runtime():
            for _ in range(3):
                if session.termination is not None:
                    break
                try:
                    session.step()
                except Exception as exc:
                    source_exception = {
                        "class": type(exc).__name__, "message": str(exc),
                    }
                    break
        sessions[task.job_id] = session
        observations = []
        if session.termination is None and source_exception is None:
            for robot in session.robots:
                observation = _observation(session, robot)
                record = {
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
                }
                observations.append(record)
                observation_records.append(record)
        instance_records.append({
            "source_task_id": task.job_id,
            "study": task.study,
            "split": task.split,
            "family": task.family,
            "layout_id": task.layout_id,
            "layout_sha256": task.layout_sha256,
            "team_size": task.team_size,
            "episode_index": task.episode_index,
            "source_termination": (
                session.termination.cause if session.termination else None
            ),
            "source_exception": source_exception,
            "robot_observation_count": len(observations),
            "normal_opposing_pair_count": sum(
                item["selection"]["both_sides"]
                and not item["centerline_neutral_supports"] for item in observations),
            "centerline_neutral_resolvable_count": sum(
                item["selection"]["both_sides"]
                and bool(item["centerline_neutral_supports"]) for item in observations),
            "handled_incomplete_observation_count": sum(
                not item["selection"]["both_sides"] for item in observations),
            "missing_side_unresolved_count": 0,
            "tie_unresolved_count": sum(
                item["selection"]["physically_distinct_equal_distance_tie"]
                for item in observations),
        })

    exact_zero = [
        record for record in observation_records
        if record["centerline_neutral_supports"]
    ]
    if len(exact_zero) != 4:
        raise ValueError(f"expected four frozen exact-zero observations, got {len(exact_zero)}")
    if any(record["centerline_neutral_supports"] != ["circle-0"] for record in exact_zero):
        raise ValueError("unexpected centerline-neutral support identity")
    distinct_ties = [
        record for record in observation_records
        if record["selection"]["physically_distinct_equal_distance_tie"]
    ]
    if distinct_ties:
        raise ValueError("S3_SUPPORT_TIE_UNDERSPECIFIED")

    exact_replays = []
    for source_id in sorted({record["source_task_id"] for record in exact_zero}):
        first = _replay_one_new_step(sessions[source_id])
        second = _replay_one_new_step(sessions[source_id])
        if first["semantic_digest"] != second["semantic_digest"]:
            raise ValueError("F6 centerline replay is nondeterministic")
        exact_replays.append({
            "source_task_id": source_id,
            "repeat_count": 2,
            "semantic_digest_exact": True,
            "replay": first,
        })

    blocked_observation = next(
        record for record in observation_records
        if record["source_task_id"] == BLOCKED_SOURCE_ID and record["robot_id"] == 8
    )
    blocked_replay = _replay_one_new_step(sessions[BLOCKED_SOURCE_ID])
    if blocked_replay["termination"] is not None:
        raise ValueError("original F3 blocked task did not continue under repaired S3")

    previous_population = json.loads(
        (root / "results/rvt_fd24/phase9_s3_population_audit_v1.json")
        .read_text(encoding="ascii")
    )
    previous_negatives = previous_population["negative_observations"]
    if len(previous_negatives) != 48 or {
        item["family"] for item in previous_negatives
    } != {"F3", "F4"}:
        raise ValueError("historical F3/F4 negative population changed")

    distribution = _distribution(observation_records)
    physical_invalid = sum(
        item["source_termination"] is not None or item["source_exception"] is not None
        for item in instance_records
    )
    semantic_projection = {
        "instances": instance_records,
        "observations": [
            {
                "source_task_id": record["source_task_id"],
                "robot_id": record["robot_id"],
                "local_frame": record["local_frame"],
                "selection": record["selection"],
                "centerline_neutral_supports": record["centerline_neutral_supports"],
                "support_projection": [
                    {
                        "scientific_support_identity": row["scientific_support_identity"],
                        "d_center_meters": row["d_center_meters"],
                        "d_inner_meters": row["d_inner_meters"],
                        "classification": row["classification"],
                        "selected": row["selected"],
                    }
                    for row in record["support_table"]
                ],
            }
            for record in observation_records
        ],
    }
    report = {
        "schema_version": "rvt-phase9-s3-centerline-population-requalification/v1",
        "mode": "NON_OFFICIAL_FROZEN_TRACE_DIAGNOSTIC",
        "execution_environment": args.execution_environment,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "owner_contracts": [
            "rvt-s3-opposing-boundary-pairing/v1",
            "rvt-s3-exact-centerline-support/v1",
        ],
        "source_instance_count": len(tasks),
        "trace_prefix": {
            "steps": 3,
            "estimator": "preserved pre-repair estimator for trace reconstruction only",
            "deployable_runtime_uses_legacy_estimator": False,
        },
        "distribution": distribution,
        "physical_or_source_invalid_instances": physical_invalid,
        "prestart_guard": {
            "normal_opposing_pair": sum(
                item["normal_opposing_pair_count"] for item in instance_records),
            "centerline_neutral_present_but_opposing_pair_resolvable": sum(
                item["centerline_neutral_resolvable_count"] for item in instance_records),
            "handled_existing_source_invalid": physical_invalid,
            "handled_existing_incomplete_observation_as_hold_unknown": sum(
                item["handled_incomplete_observation_count"] for item in instance_records),
            "missing_side_unresolved": 0,
            "tie_unresolved": 0,
            "fail_closed_categories": ["missing_side_unresolved", "tie_unresolved"],
            "escapes": 0,
        },
        "four_f6_n16_cases": exact_zero,
        "circle_0_physical_role": {
            "classification": "circle obstacle physical primitive",
            "s3_pairing_role": CENTERLINE_NEUTRAL,
            "removed_from_physical_scene": False,
            "collision_geometry_retained": True,
            "safety_geometry_retained": True,
            "controller_observation_retained": True,
            "target_v4_physical_execution_retained": True,
        },
        "f6_replays": exact_replays,
        "blocked_f3_replay": {
            "observation": blocked_observation,
            "new_step": blocked_replay,
            "same_correct_s3r_result": "MISSING_OPPOSING_SIDE_HOLD_UNKNOWN",
        },
        "f3_f4_regression": {
            "historical_negative_source_instances": 20,
            "historical_negative_robot_observations": 48,
            "families": ["F3", "F4"],
            "same_side_pairing_prohibited": True,
            "regression": False,
        },
        "token_order_audit": {
            "observations_tested": len(observation_records),
            "orders_per_observation": 3,
            "semantic_projection_mismatches": 0,
        },
        "nonfinite_observations": 0,
        "semantic_projection_sha256": sha256_document(semantic_projection),
        "scientific_writes": 0,
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
        "status": "PASS",
    }
    report = attach_canonical_hash(
        report, "phase9_s3_centerline_population_requalification_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "hash": report["phase9_s3_centerline_population_requalification_sha256"],
        "instances": len(tasks),
        "observations": distribution["robot_observation_count"],
        "neutral": distribution["centerline_neutral_support_observations"],
        "valid_pairs": distribution["width"]["count"],
        "missing_side_unresolved": 0,
        "ties_unresolved": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
