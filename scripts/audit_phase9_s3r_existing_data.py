#!/usr/bin/env python3
"""Requalify the 342-row S3 dependency cone under the owner rule."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9c_rb import policies
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.phase9g0r.producer import build_source_session
from audit_phase9_s3r_owner_rule import _component_identity, _observation


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def _old_component_pair(observation: dict) -> list[str]:
    direction = tuple(observation["local_frame_diagnostic"]["t_world"])
    # The historical estimator used the frozen mission tangent. Existing
    # dependency cases have straight corridor frames aligned to that tangent;
    # relative token coordinates are sufficient to reconstruct its pair.
    left = []
    right = []
    for row in observation["support_table"]:
        if not row["participates_in_existing_s3_lookahead"]:
            continue
        ox, oy = row["relative_center_meters"]
        lateral = (-direction[1], direction[0])
        offset = float(ox) * lateral[0] + float(oy) * lateral[1]
        value = abs(offset) - float(row["radius_meters"])
        target = left if offset >= 0.0 else right
        target.append((value, _component_identity(row["source_key"])))
    if not left or not right:
        return []
    return sorted({min(left)[1], min(right)[1]})


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
        args.checkpoint, "phase9_s3_staging_checkpoint_sha256"
    )
    previous = _canonical(
        args.previous_dependency,
        "phase9_s3_staging_dependency_audit_sha256",
    )
    if checkpoint["prefix"]["scientific_rows"] != 342:
        raise ValueError("S3R requires the exact 342-row checkpoint")
    expected_partition = {
        "DEPENDENCY_PRESENT_BUT_VALUE_VALID": 88,
        "POTENTIALLY_AFFECTED": 0,
        "PROVEN_AFFECTED": 0,
        "UNAFFECTED": 254,
    }
    if previous["row_classification_counts"] != expected_partition:
        raise ValueError("previous dependency partition changed")

    tasks = {
        task.event_id: task
        for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train"
        )
    }
    by_source = defaultdict(list)
    for transaction in previous["transaction_audits"]:
        if transaction["s3_width_dependency"]:
            task = tasks[transaction["decision_event_id"]]
            by_source[task.source.job_id].append(task)
    if len(by_source) != 12:
        raise ValueError("committed S3/S4 source dependency universe changed")

    original = policies.s3_local_geometric_decision
    source_records = []
    total_calls = 0
    total_width_bit_differences = 0
    total_decision_differences = 0
    total_component_differences = 0
    total_degeneracies = 0
    maximum_width_absolute_difference = 0.0
    for source_id, events in sorted(by_source.items()):
        events.sort(key=lambda item: item.resolved_control_step)
        session = build_source_session(root, events[0].source)
        step_counts = Counter()
        call_records = []

        def observed(committed_topology, **kwargs):
            robot_id = step_counts[session.control_step]
            step_counts[session.control_step] += 1
            owner = _observation(session, session.robots[robot_id])
            selection = owner["selection"]
            participating = [
                row for row in owner["support_table"]
                if row["participates_in_existing_s3_lookahead"]
            ]
            complete_open = not participating
            new_kwargs = dict(kwargs)
            new_kwargs.update({
                "measured_width_meters": selection["width_meters"],
                "complete_open_observation": complete_open,
                "complete_observation": complete_open or selection["both_sides"],
            })
            historical_decision = original(committed_topology, **kwargs)
            owner_decision = original(committed_topology, **new_kwargs)
            old_width = kwargs["measured_width_meters"]
            new_width = selection["width_meters"]
            width_abs_difference = (
                abs(float(old_width) - float(new_width))
                if old_width is not None and new_width is not None else None
            )
            owner_components = sorted(
                selection["selected_negative_component_equivalence"]
                + selection["selected_positive_component_equivalence"]
            ) if selection["both_sides"] else []
            old_components = _old_component_pair(owner)
            component_equivalent = (
                (not old_components and not owner_components)
                or old_components == owner_components
            )
            call_records.append({
                "control_step": session.control_step,
                "robot_id": robot_id,
                "historical_width_meters": old_width,
                "owner_width_meters": new_width,
                "width_bit_equal": (
                    old_width == new_width
                    or (old_width is None and new_width is None)
                ),
                "width_absolute_difference_meters": width_abs_difference,
                "historical_decision": historical_decision,
                "owner_decision": owner_decision,
                "decision_exact": historical_decision == owner_decision,
                "historical_component_equivalence": old_components,
                "owner_component_equivalence": owner_components,
                "physical_pair_equivalent": component_equivalent,
                "centerline_degenerate_support_count": owner[
                    "centerline_degenerate_support_count"
                ],
            })
            return historical_decision

        policies.s3_local_geometric_decision = observed
        caught = None
        try:
            for event in events:
                while (
                    session.termination is None
                    and session.control_step < event.resolved_control_step
                ):
                    session.step()
        except Exception as exc:
            caught = {"class": type(exc).__name__, "message": str(exc)}
        finally:
            policies.s3_local_geometric_decision = original
        bit_differences = sum(not row["width_bit_equal"] for row in call_records)
        decision_differences = sum(not row["decision_exact"] for row in call_records)
        component_differences = sum(
            not row["physical_pair_equivalent"] for row in call_records
        )
        degeneracies = sum(
            row["centerline_degenerate_support_count"] for row in call_records
        )
        local_maximum = max(
            (
                float(row["width_absolute_difference_meters"])
                for row in call_records
                if row["width_absolute_difference_meters"] is not None
            ),
            default=0.0,
        )
        source_records.append({
            "source_task_id": source_id,
            "source_class": events[0].source.source_class,
            "family": events[0].source.family,
            "layout_id": events[0].source.layout_id,
            "team_size": events[0].source.team_size,
            "episode_index": events[0].source.episode_index,
            "event_count_in_committed_prefix": len(events),
            "call_count": len(call_records),
            "width_bit_difference_count": bit_differences,
            "maximum_width_absolute_difference_meters": local_maximum,
            "decision_difference_count": decision_differences,
            "physical_pair_difference_count": component_differences,
            "centerline_degenerate_support_count": degeneracies,
            "source_exception": caught,
            "call_records": call_records,
        })
        total_calls += len(call_records)
        total_width_bit_differences += bit_differences
        total_decision_differences += decision_differences
        total_component_differences += component_differences
        total_degeneracies += degeneracies
        maximum_width_absolute_difference = max(
            maximum_width_absolute_difference, local_maximum
        )

    if any(record["source_exception"] is not None for record in source_records):
        raise ValueError("committed dependency source replay failed")
    if total_decision_differences or total_component_differences or total_degeneracies:
        raise ValueError(
            "owner rule changes the committed dependency cone: "
            f"decisions={total_decision_differences}, "
            f"components={total_component_differences}, "
            f"degeneracies={total_degeneracies}"
        )
    semantic_projection = {
        "sources": [
            {
                key: value for key, value in record.items()
                if key != "call_records"
            }
            for record in source_records
        ],
        "calls": [
            [
                record["source_task_id"],
                call["control_step"],
                call["robot_id"],
                call["historical_decision"],
                call["owner_decision"],
                call["historical_component_equivalence"],
                call["owner_component_equivalence"],
            ]
            for record in source_records for call in record["call_records"]
        ],
    }
    report = {
        "schema_version": "rvt-phase9-s3r-existing-data-requalification/v1",
        "mode": "NON_OFFICIAL_READ_ONLY_DIAGNOSTIC_REPLAY",
        "execution_environment": args.execution_environment,
        "staging_checkpoint_sha256": checkpoint[
            "phase9_s3_staging_checkpoint_sha256"
        ],
        "previous_dependency_audit_sha256": previous[
            "phase9_s3_staging_dependency_audit_sha256"
        ],
        "row_count": 342,
        "row_classification_counts": expected_partition,
        "dependent_transaction_count": previous[
            "transactions_with_s3_dependency"
        ],
        "dependent_row_count": previous["rows_with_s3_dependency"],
        "source_replay_count": len(source_records),
        "s3_call_count": total_calls,
        "width_bit_difference_count": total_width_bit_differences,
        "maximum_width_absolute_difference_meters": (
            maximum_width_absolute_difference
        ),
        "decision_difference_count": total_decision_differences,
        "physical_pair_difference_count": total_component_differences,
        "centerline_degenerate_support_count": total_degeneracies,
        "semantic_conclusion": {
            "historical_physical_pairs_equivalent_to_owner_rule": True,
            "all_s3_decisions_exact": True,
            "source_trajectory_semantic_projection_exact_by_induction": True,
            "binary64_width_identity_required_for_existing_rows": False,
            "binary64_width_note": (
                "Equivalent frame translation arithmetic changes some last bits; "
                "width is not serialized and every threshold decision is exact."
            ),
            "existing_rows_changed": 0,
        },
        "source_records": source_records,
        "semantic_projection_sha256": sha256_document(semantic_projection),
        "official_data_action": "RETAIN_ALL_342",
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
        report, "phase9_s3r_existing_data_requalification_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "hash": report["phase9_s3r_existing_data_requalification_sha256"],
        "calls": total_calls,
        "width_bit_differences": total_width_bit_differences,
        "maximum_width_absolute_difference": maximum_width_absolute_difference,
        "decision_differences": total_decision_differences,
        "component_differences": total_component_differences,
        "action": report["official_data_action"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
