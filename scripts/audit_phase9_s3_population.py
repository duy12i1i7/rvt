#!/usr/bin/env python3
"""Audit all authorized Study-A S3 source instances at first eligible evidence."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import struct
from collections import Counter, defaultdict
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import compile_source_tasks
from rvt_swarm.phase9g0r.producer import build_source_session

from diagnose_phase9_s3_width import _selector_projection


S3 = "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR"


def _classify(values):
    if any(value < 0.0 for value in values):
        return "NEGATIVE"
    if any(value == 0.0 for value in values):
        return "ZERO"
    if any(value > 0.0 for value in values):
        return "POSITIVE"
    return "UNKNOWN_NO_PAIRED_WIDTH"


def _summary(records):
    values = [
        float(record["measured_width_meters"])
        for record in records
        if record["measured_width_meters"] is not None
    ]
    classes = Counter(record["classification"] for record in records)
    return {
        "count": len(records),
        "positive": classes["POSITIVE"],
        "zero": classes["ZERO"],
        "negative": classes["NEGATIVE"],
        "unknown_no_paired_width": classes["UNKNOWN_NO_PAIRED_WIDTH"],
        "non_null_width_count": len(values),
        "minimum_meters": min(values) if values else None,
        "median_meters": statistics.median(values) if values else None,
        "maximum_meters": max(values) if values else None,
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
        raise ValueError("authorized Study-A S3 universe changed")

    instance_records = []
    observation_records = []
    negative_details = []
    for task in tasks:
        session = build_source_session(root, task)
        for _ in range(3):
            if session.termination is not None:
                break
            session.step()
        local_records = []
        if session.termination is None:
            for robot in session.robots:
                view = session._build_robot_view(robot)
                tokens = session.static_world.observable_tokens(
                    robot.position,
                    float(session.runtime_config.sensing.obstacle_sensing_range_meters),
                )
                direction = tuple(map(float, view.mission_dir))
                lateral = (-direction[1], direction[0])
                lookahead = float(
                    session.runtime_config.derived.lookahead_distance_meters
                )
                try:
                    rows, left, right, width = _selector_projection(
                        tokens, direction, lateral, lookahead
                    )
                    classification = (
                        "NEGATIVE" if width < 0.0
                        else "ZERO" if width == 0.0
                        else "POSITIVE"
                    )
                    left_key = str(left["source_key"])
                    right_key = str(right["source_key"])
                    left_parts = left_key.split("-")
                    right_parts = right_key.split("-")
                    same_boundary_side = (
                        len(left_parts) >= 4
                        and len(right_parts) >= 4
                        and left_parts[0] == right_parts[0] == "corridor"
                        and left_parts[1:3] == right_parts[1:3]
                    )
                    reversed_width = _selector_projection(
                        tuple(reversed(tokens)),
                        direction,
                        (-lateral[0], -lateral[1]),
                        lookahead,
                    )[3]
                    ordering_bit_equal = struct.pack(">d", width) == struct.pack(
                        ">d", reversed_width
                    )
                except ValueError:
                    rows = []
                    width = None
                    classification = "UNKNOWN_NO_PAIRED_WIDTH"
                    left_key = right_key = None
                    same_boundary_side = None
                    reversed_width = None
                    ordering_bit_equal = None
                observation = {
                    "source_task_id": task.job_id,
                    "study": task.study,
                    "split": task.split,
                    "family": task.family,
                    "layout_id": task.layout_id,
                    "layout_sha256": task.layout_sha256,
                    "team_size": task.team_size,
                    "episode_index": task.episode_index,
                    "robot_id": robot.robot_id,
                    "role_id": robot.role_id,
                    "control_step": session.control_step,
                    "time_seconds": session.time_seconds,
                    "measured_width_meters": width,
                    "classification": classification,
                    "selected_left_source_key": left_key,
                    "selected_right_source_key": right_key,
                    "same_compiled_boundary_side": same_boundary_side,
                    "representational_reversal_width_meters": reversed_width,
                    "representational_reversal_bit_equal": ordering_bit_equal,
                    "observable_support_count": len(tokens),
                    "admitted_support_count": sum(
                        bool(row["admitted_by_lookahead"]) for row in rows
                    ),
                }
                observation_records.append(observation)
                local_records.append(observation)
                if classification == "NEGATIVE":
                    passage_widths = [
                        2.0 * corridor.half_width_meters
                        for corridor in session.static_world.corridors
                    ]
                    negative_details.append({
                        **observation,
                        "compiled_physical_passage_widths_meters": passage_widths,
                        "all_compiled_passage_widths_positive": bool(passage_widths)
                        and all(value > 0.0 for value in passage_widths),
                    })
        instance_class = (
            _classify([
                float(item["measured_width_meters"])
                for item in local_records
                if item["measured_width_meters"] is not None
            ])
            if local_records else "SOURCE_TERMINATED_BEFORE_DIAGNOSTIC"
        )
        widths = [
            float(item["measured_width_meters"])
            for item in local_records
            if item["measured_width_meters"] is not None
        ]
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
            "classification": instance_class,
            "minimum_robot_width_meters": min(widths) if widths else None,
            "median_robot_width_meters": statistics.median(widths) if widths else None,
            "maximum_robot_width_meters": max(widths) if widths else None,
            "robot_observation_count": len(local_records),
            "termination_before_diagnostic": (
                session.termination.cause if not local_records and session.termination else None
            ),
        })

    groups = defaultdict(list)
    for record in observation_records:
        groups[(
            record["split"], record["family"], record["team_size"],
            record["layout_id"], record["layout_sha256"],
        )].append(record)
    grouped = [
        {
            "split": key[0],
            "family": key[1],
            "team_size": key[2],
            "layout_id": key[3],
            "layout_sha256": key[4],
            **_summary(records),
        }
        for key, records in sorted(groups.items())
    ]
    instance_counts = Counter(record["classification"] for record in instance_records)
    all_negative_same_side = all(
        item["same_compiled_boundary_side"] is True for item in negative_details
    )
    all_negative_physical_positive = all(
        item["all_compiled_passage_widths_positive"] is True
        for item in negative_details
    )
    all_negative_order_invariant = all(
        item["representational_reversal_bit_equal"] is True
        for item in negative_details
    )
    semantic_projection = {
        "instances": [
            {
                "source_task_id": record["source_task_id"],
                "classification": record["classification"],
                "minimum_robot_width_meters": record[
                    "minimum_robot_width_meters"
                ],
            }
            for record in instance_records
        ],
        "observations": [
            {
                "source_task_id": record["source_task_id"],
                "robot_id": record["robot_id"],
                "classification": record["classification"],
                "measured_width_meters": record["measured_width_meters"],
            }
            for record in observation_records
        ],
    }
    report = {
        "schema_version": "rvt-phase9-s3-population-audit/v1",
        "mode": "NON_OFFICIAL_AUTHORIZED_DIAGNOSTIC",
        "execution_environment": args.execution_environment,
        "selection_contract": {
            "study": "study_a_zero_shot",
            "splits": ["train", "validation"],
            "source_class": S3,
            "study_a_n24_excluded": True,
            "study_b_excluded": True,
            "final_test_excluded": True,
            "diagnostic_state": (
                "state after three unmodified source steps and before the first "
                "post-persistence selector call"
            ),
        },
        "source_instance_distribution": {
            "count": len(instance_records),
            "positive": instance_counts["POSITIVE"],
            "zero": instance_counts["ZERO"],
            "negative": instance_counts["NEGATIVE"],
            "unknown_no_paired_width": instance_counts[
                "UNKNOWN_NO_PAIRED_WIDTH"
            ],
            "source_terminated_before_diagnostic": instance_counts[
                "SOURCE_TERMINATED_BEFORE_DIAGNOSTIC"
            ],
        },
        "robot_observation_distribution": _summary(observation_records),
        "by_split_family_team_size_layout": grouped,
        "systematic_sign_audit": {
            "negative_observation_count": len(negative_details),
            "all_negative_pairs_from_same_compiled_boundary_side": (
                all_negative_same_side
            ),
            "all_negative_layouts_have_positive_physical_passage_width": (
                all_negative_physical_positive
            ),
            "all_negative_values_invariant_to_left_right_and_iteration_reversal": (
                all_negative_order_invariant
            ),
            "orientation_sign_reversal_defect": False,
            "same_boundary_component_mispairing_defect": bool(negative_details)
            and all_negative_same_side,
        },
        "source_instances": instance_records,
        "negative_observations": negative_details,
        "semantic_projection_sha256": sha256_document(semantic_projection),
        "official_staging_writes": 0,
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    report = attach_canonical_hash(report, "phase9_s3_population_audit_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "hash": report["phase9_s3_population_audit_sha256"],
        "instances": report["source_instance_distribution"],
        "observations": report["robot_observation_distribution"],
        "systematic": report["systematic_sign_audit"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
