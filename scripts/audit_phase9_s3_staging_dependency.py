#!/usr/bin/env python3
"""Prove the S3 dependency status of every row in read-only STAGING."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9c_rb import policies
from rvt_swarm.phase9c_rb.counterfactual import snapshot
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.phase9g0r.producer import build_source_session


DEPENDENT_POLICIES = frozenset({
    "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR",
    "S4_FROZEN_TRANSITION_PROTOCOL",
})


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-environment", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    data_root = args.data_root.resolve()
    checkpoint = _canonical(
        args.checkpoint, "phase9_s3_staging_checkpoint_sha256"
    )
    staging = data_root / "staging/study_a_zero_shot-train-recoverability"
    transaction_root = staging / "recoverability"
    records = {}
    for descriptor in checkpoint["candidate_pair_transactions"]:
        path = transaction_root / descriptor["file_name"]
        record = _canonical(path, "canonical_record_sha256")
        if record["decision_event_id"] != descriptor["decision_event_id"]:
            raise ValueError("checkpoint transaction identity mismatch")
        records[record["decision_event_id"]] = record
    if len(records) != 210:
        raise ValueError("exactly 210 official transactions are required")

    tasks = {
        task.event_id: task
        for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train"
        )
    }
    events_by_source = defaultdict(list)
    for event_id in records:
        task = tasks[event_id]
        if task.source.source_class in DEPENDENT_POLICIES:
            events_by_source[task.source.job_id].append(task)

    source_audits = {}
    event_replays = {}
    original = policies.s3_local_geometric_decision
    for source_id, source_events in sorted(events_by_source.items()):
        source_events.sort(key=lambda item: item.resolved_control_step)
        session = build_source_session(root, source_events[0].source)
        calls = []
        step_counts = Counter()

        def observed(committed_topology, **kwargs):
            robot_id = step_counts[session.control_step]
            step_counts[session.control_step] += 1
            calls.append({
                "control_step": session.control_step,
                "time_seconds": session.time_seconds,
                "robot_id": robot_id,
                "committed_topology": committed_topology,
                **kwargs,
            })
            return original(committed_topology, **kwargs)

        policies.s3_local_geometric_decision = observed
        caught = None
        try:
            for task in source_events:
                while (
                    session.termination is None
                    and session.control_step < task.resolved_control_step
                ):
                    session.step()
                official = records[task.event_id]
                official_audit = official["audit"]
                if session.termination is None:
                    replay_snapshot = snapshot(session).canonical_hash
                    replay = {
                        "kind": "LABELABLE_SNAPSHOT",
                        "control_step": session.control_step,
                        "replayed_source_snapshot_sha256": replay_snapshot,
                        "official_source_snapshot_sha256": official_audit[
                            "source_snapshot_sha256"
                        ],
                        "exact_match": replay_snapshot
                        == official_audit["source_snapshot_sha256"],
                    }
                else:
                    termination = official_audit["termination"]
                    replay = {
                        "kind": "SOURCE_TERMINATION",
                        "replayed_cause": session.termination.cause,
                        "official_cause": termination["cause"],
                        "replayed_control_step": session.termination.control_step,
                        "official_control_step": termination["control_step"],
                        "exact_match": (
                            session.termination.cause == termination["cause"]
                            and session.termination.control_step
                            == int(termination["control_step"])
                        ),
                    }
                event_replays[task.event_id] = replay
        except Exception as exc:
            caught = {"class": type(exc).__name__, "message": str(exc)}
        finally:
            policies.s3_local_geometric_decision = original
        widths = [
            float(call["measured_width_meters"])
            for call in calls
            if call["measured_width_meters"] is not None
        ]
        source_audits[source_id] = {
            "source_task_id": source_id,
            "source_class": source_events[0].source.source_class,
            "family": source_events[0].source.family,
            "layout_id": source_events[0].source.layout_id,
            "layout_sha256": source_events[0].source.layout_sha256,
            "team_size": source_events[0].source.team_size,
            "episode_index": source_events[0].source.episode_index,
            "event_count_in_official_prefix": len(source_events),
            "s3_call_count": len(calls),
            "non_null_width_count": len(widths),
            "negative_width_count": sum(value < 0.0 for value in widths),
            "zero_width_count": sum(value == 0.0 for value in widths),
            "positive_width_count": sum(value > 0.0 for value in widths),
            "minimum_width_meters": min(widths) if widths else None,
            "maximum_width_meters": max(widths) if widths else None,
            "exception": caught,
            "event_replay_exact": all(
                event_replays[item.event_id]["exact_match"] for item in source_events
            ) if caught is None else False,
            "event_log": list(session.event_log),
        }

    if any(
        audit["exception"] is not None
        or audit["negative_width_count"] != 0
        or not audit["event_replay_exact"]
        for audit in source_audits.values()
    ):
        raise ValueError("an existing S3/S4 source prefix is not dependency-valid")

    row_records = []
    transaction_audits = []
    for event_id, record in sorted(records.items()):
        task = tasks[event_id]
        dependency = task.source.source_class in DEPENDENT_POLICIES
        if dependency:
            source_audit = source_audits[task.source.job_id]
            replay = event_replays[event_id]
            row_classification = "DEPENDENCY_PRESENT_BUT_VALUE_VALID"
        else:
            source_audit = None
            replay = None
            row_classification = "UNAFFECTED"
        transaction_audits.append({
            "decision_event_id": event_id,
            "source_task_id": task.source.job_id,
            "source_class": task.source.source_class,
            "family": task.source.family,
            "team_size": task.source.team_size,
            "status": record["status"],
            "scientific_row_count": len(record["rows"]),
            "s3_executed": dependency,
            "s3_width_dependency": dependency,
            "dependency_classification": row_classification,
            "replay": replay,
            "source_negative_width_count": (
                source_audit["negative_width_count"] if source_audit else 0
            ),
        })
        for row in record["rows"]:
            row_records.append({
                "scientific_row_id": row["scientific_row_id"],
                "decision_event_id": event_id,
                "robot_id": row["scientific_identity"]["robot_id"],
                "candidate_topology_id": row["candidate_topology_id"],
                "source_class": task.source.source_class,
                "classification": row_classification,
                "dependency": {
                    "s3_executed": dependency,
                    "width_value_evaluated": dependency,
                    "source_episode_state": dependency,
                    "source_transition_event_timing": dependency,
                    "candidate_rollout_initial_state": dependency,
                    "controller_and_safety_trajectory": dependency,
                    "target_v4_predicates_and_label": dependency,
                    "ego_graph_payload": dependency,
                    "row_identity_directly_contains_width": False,
                    "label_directly_contains_width": False,
                },
            })
    if len(row_records) != 342 or len({r["scientific_row_id"] for r in row_records}) != 342:
        raise ValueError("row dependency partition is not exact")
    counts = Counter(record["classification"] for record in row_records)
    for name in (
        "UNAFFECTED", "DEPENDENCY_PRESENT_BUT_VALUE_VALID",
        "POTENTIALLY_AFFECTED", "PROVEN_AFFECTED",
    ):
        counts[name] += 0
    if counts["POTENTIALLY_AFFECTED"] or counts["PROVEN_AFFECTED"]:
        raise ValueError("official row impact is unresolved")
    semantic_projection = {
        "row_partition": [
            [record["scientific_row_id"], record["classification"]]
            for record in row_records
        ],
        "event_replays": event_replays,
        "source_width_summaries": {
            key: {
                "negative_width_count": value["negative_width_count"],
                "minimum_width_meters": value["minimum_width_meters"],
                "maximum_width_meters": value["maximum_width_meters"],
                "event_replay_exact": value["event_replay_exact"],
            }
            for key, value in source_audits.items()
        },
    }
    report = {
        "schema_version": "rvt-phase9-s3-staging-dependency-audit/v1",
        "mode": "NON_OFFICIAL_READ_ONLY_REPLAY",
        "execution_environment": args.execution_environment,
        "staging_checkpoint_sha256": checkpoint[
            "phase9_s3_staging_checkpoint_sha256"
        ],
        "row_count": len(row_records),
        "row_classification_counts": dict(sorted(counts.items())),
        "transaction_count": len(transaction_audits),
        "transactions_with_s3_dependency": sum(
            item["s3_width_dependency"] for item in transaction_audits
        ),
        "rows_with_s3_dependency": counts[
            "DEPENDENCY_PRESENT_BUT_VALUE_VALID"
        ],
        "source_replays": list(source_audits.values()),
        "event_replays": event_replays,
        "transaction_audits": transaction_audits,
        "row_audits": row_records,
        "semantic_projection_sha256": sha256_document(semantic_projection),
        "data_action_evidence": {
            "all_342_rows_classified": True,
            "all_dependent_source_snapshots_or_terminations_reproduced": True,
            "negative_width_in_committed_dependency_cone": False,
            "existing_rows_may_remain_frozen_evidence": True,
            "deletion_or_rewrite_performed": False,
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
    report = attach_canonical_hash(
        report, "phase9_s3_staging_dependency_audit_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "hash": report["phase9_s3_staging_dependency_audit_sha256"],
        "rows": report["row_classification_counts"],
        "dependent_transactions": report["transactions_with_s3_dependency"],
        "source_replays": len(source_audits),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
