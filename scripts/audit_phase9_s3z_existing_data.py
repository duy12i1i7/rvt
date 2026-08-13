#!/usr/bin/env python3
"""Requalify the immutable 342-row prefix under combined S3 owner rules."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9c_rb import policies
from rvt_swarm.phase9c_rb.s3_geometry import measure_s3_opposing_boundaries
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.phase9g0r.producer import build_source_session
from scripts.audit_phase9_s3r_owner_rule import _component_identity
from scripts.audit_phase9_s3z_centerline import _legacy_measurement, _observation


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def _component_pair(indices, tokens) -> list[str]:
    return sorted({_component_identity(tokens[index][2]) for index in indices})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--previous-dependency", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-environment", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    checkpoint = _canonical(
        args.checkpoint, "phase9_s3_staging_checkpoint_sha256")
    previous = _canonical(
        args.previous_dependency, "phase9_s3_staging_dependency_audit_sha256")
    if checkpoint["prefix"]["scientific_rows"] != 342:
        raise ValueError("A1S3Z requires the exact immutable 342-row checkpoint")
    expected_partition = {
        "DEPENDENCY_PRESENT_BUT_VALUE_VALID": 88,
        "POTENTIALLY_AFFECTED": 0,
        "PROVEN_AFFECTED": 0,
        "UNAFFECTED": 254,
    }
    if previous["row_classification_counts"] != expected_partition:
        raise ValueError("historical dependency partition changed")

    tasks = {
        task.event_id: task
        for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train")
    }
    by_source = defaultdict(list)
    for transaction in previous["transaction_audits"]:
        if transaction["s3_width_dependency"]:
            task = tasks[transaction["decision_event_id"]]
            by_source[task.source.job_id].append(task)
    if len(by_source) != 12:
        raise ValueError("committed S3 dependency universe changed")

    decision = policies.s3_local_geometric_decision
    source_records = []
    totals = Counter()
    maximum_width_difference = 0.0
    for source_id, events in sorted(by_source.items()):
        events.sort(key=lambda item: item.resolved_control_step)
        session = build_source_session(root, events[0].source)
        step_counts = Counter()
        call_records = []

        def compare_and_preserve_historical(committed_topology, **new_kwargs):
            robot_id = step_counts[session.control_step]
            step_counts[session.control_step] += 1
            robot = session.robots[robot_id]
            view = session._build_robot_view(robot)
            lookahead = float(session.runtime_config.derived.lookahead_distance_meters)
            tokens = session.static_world.observable_tokens(
                robot.position,
                float(session.runtime_config.sensing.obstacle_sensing_range_meters),
            )
            historical = _legacy_measurement(
                view.obstacles,
                mission_direction=view.mission_dir,
                lookahead_distance_meters=lookahead,
            )
            repaired = measure_s3_opposing_boundaries(
                view.obstacles,
                mission_direction=view.mission_dir,
                support_origin_world_meters=view.position,
                local_frame_center_world_meters=view.s3_frame_center_world_meters,
                local_frame_normal=view.s3_frame_normal,
                lookahead_distance_meters=lookahead,
            )
            if repaired.measured_width_meters != new_kwargs["measured_width_meters"]:
                raise ValueError("runtime S3 kwargs differ from executable pairing helper")
            historical_kwargs = dict(new_kwargs)
            historical_kwargs.update({
                "measured_width_meters": historical.measured_width_meters,
                "complete_open_observation": historical.complete_open_observation,
                "complete_observation": historical.complete_observation,
            })
            historical_decision = decision(committed_topology, **historical_kwargs)
            repaired_decision = decision(committed_topology, **new_kwargs)
            old_width = historical.measured_width_meters
            new_width = repaired.measured_width_meters
            difference = (
                abs(float(old_width) - float(new_width))
                if old_width is not None and new_width is not None else None
            )
            old_pair = sorted(
                _component_pair(historical.selected_negative_indices, tokens)
                + _component_pair(historical.selected_positive_indices, tokens)
            ) if old_width is not None else []
            new_pair = sorted(
                _component_pair(repaired.selected_negative_indices, tokens)
                + _component_pair(repaired.selected_positive_indices, tokens)
            ) if new_width is not None else []
            neutral_count = sum(
                row.classification == "CENTERLINE_NEUTRAL"
                for row in repaired.projections
            )
            call_records.append({
                "control_step": session.control_step,
                "robot_id": robot_id,
                "historical_width_meters": old_width,
                "repaired_width_meters": new_width,
                "width_bit_equal": old_width == new_width,
                "width_absolute_difference_meters": difference,
                "historical_decision": historical_decision,
                "repaired_decision": repaired_decision,
                "decision_exact": historical_decision == repaired_decision,
                "historical_component_equivalence": old_pair,
                "repaired_component_equivalence": new_pair,
                "physical_pair_equivalent": old_pair == new_pair,
                "centerline_neutral_support_count": neutral_count,
            })
            # Preserve the historical trajectory while comparing the repaired
            # semantics; no official row is produced by this diagnostic.
            return historical_decision

        current = policies.s3_local_geometric_decision
        policies.s3_local_geometric_decision = compare_and_preserve_historical
        caught = None
        try:
            for event in events:
                while (session.termination is None
                       and session.control_step < event.resolved_control_step):
                    session.step()
        except Exception as exc:
            caught = {"class": type(exc).__name__, "message": str(exc)}
        finally:
            policies.s3_local_geometric_decision = current

        local = Counter({
            "calls": len(call_records),
            "width_bit_differences": sum(not row["width_bit_equal"] for row in call_records),
            "decision_differences": sum(not row["decision_exact"] for row in call_records),
            "physical_pair_differences": sum(
                not row["physical_pair_equivalent"] for row in call_records),
            "centerline_neutral_supports": sum(
                row["centerline_neutral_support_count"] for row in call_records),
        })
        local_maximum = max((
            row["width_absolute_difference_meters"]
            for row in call_records
            if row["width_absolute_difference_meters"] is not None
        ), default=0.0)
        maximum_width_difference = max(maximum_width_difference, local_maximum)
        totals.update(local)
        source_records.append({
            "source_task_id": source_id,
            "source_class": events[0].source.source_class,
            "family": events[0].source.family,
            "layout_id": events[0].source.layout_id,
            "team_size": events[0].source.team_size,
            "episode_index": events[0].source.episode_index,
            "event_count_in_committed_prefix": len(events),
            **dict(local),
            "maximum_width_absolute_difference_meters": local_maximum,
            "source_exception": caught,
            "call_records": call_records,
        })

    if any(record["source_exception"] for record in source_records):
        print(json.dumps({
            "source_exceptions": [
                {
                    "source_task_id": record["source_task_id"],
                    "source_exception": record["source_exception"],
                }
                for record in source_records if record["source_exception"]
            ]
        }, sort_keys=True))
        raise ValueError("committed dependency source replay failed")
    if (totals["decision_differences"] or totals["physical_pair_differences"]
            or totals["centerline_neutral_supports"]):
        raise ValueError("combined S3 rule changes the committed dependency cone")
    semantic_projection = {
        "sources": [
            {key: value for key, value in record.items() if key != "call_records"}
            for record in source_records
        ],
        "calls": [
            [
                record["source_task_id"], call["control_step"], call["robot_id"],
                call["historical_decision"], call["repaired_decision"],
                call["historical_component_equivalence"],
                call["repaired_component_equivalence"],
            ]
            for record in source_records for call in record["call_records"]
        ],
    }
    report = {
        "schema_version": "rvt-phase9-s3-existing-data-requalification/v2",
        "mode": "NON_OFFICIAL_READ_ONLY_DIAGNOSTIC_REPLAY",
        "execution_environment": args.execution_environment,
        "staging_checkpoint_sha256": checkpoint[
            "phase9_s3_staging_checkpoint_sha256"],
        "previous_dependency_audit_sha256": previous[
            "phase9_s3_staging_dependency_audit_sha256"],
        "combined_owner_rules": [
            "rvt-s3-opposing-boundary-pairing/v1",
            "rvt-s3-exact-centerline-support/v1",
        ],
        "row_count": 342,
        "row_classification_counts": expected_partition,
        "dependent_transaction_count": previous["transactions_with_s3_dependency"],
        "dependent_row_count": previous["rows_with_s3_dependency"],
        "source_replay_count": len(source_records),
        "s3_call_count": totals["calls"],
        "width_bit_difference_count": totals["width_bit_differences"],
        "maximum_width_absolute_difference_meters": maximum_width_difference,
        "decision_difference_count": totals["decision_differences"],
        "physical_pair_difference_count": totals["physical_pair_differences"],
        "centerline_neutral_support_count": totals["centerline_neutral_supports"],
        "semantic_conclusion": {
            "all_s3_decisions_exact": True,
            "all_selected_physical_pairs_equivalent": True,
            "source_trajectory_semantic_projection_exact_by_induction": True,
            "existing_rows_changed": 0,
        },
        "source_records": source_records,
        "semantic_projection_sha256": sha256_document(semantic_projection),
        "official_data_action": "RETAIN_ALL_342",
        "rows_rebuilt": 0,
        "row_ids_changed": 0,
        "provenance_payloads_rewritten": 0,
        "official_staging_writes": 0,
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    report = attach_canonical_hash(
        report, "phase9_s3_existing_data_requalification_v2_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "hash": report["phase9_s3_existing_data_requalification_v2_sha256"],
        "calls": totals["calls"],
        "decision_differences": totals["decision_differences"],
        "physical_pair_differences": totals["physical_pair_differences"],
        "centerline_neutral_supports": totals["centerline_neutral_supports"],
        "action": report["official_data_action"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
