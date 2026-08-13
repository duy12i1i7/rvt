#!/usr/bin/env python3
"""Fail-fast S3 guard for unresolved Study-A Recoverability TRAIN events."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.phase9g0r.producer import build_source_session
from scripts.audit_phase9_s3z_centerline import (
    _distribution,
    _historical_prefix_runtime,
    _observation,
)


S3 = "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR"


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-environment", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    checkpoint = _canonical(
        args.checkpoint, "phase9_s3_staging_checkpoint_sha256"
    )
    completed = {
        item["decision_event_id"] for item in checkpoint["candidate_pair_transactions"]
    }
    tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="train"
    )
    remaining = tuple(task for task in tasks if task.event_id not in completed)
    s3_events = tuple(task for task in remaining if task.source.source_class == S3)
    sources = {task.source.job_id: task.source for task in s3_events}
    if len(tasks) != 6000 or len(completed) != 210 or len(remaining) != 5790:
        raise ValueError("frozen A1C TRAIN resume boundary changed")
    if len(s3_events) != 970 or len(sources) != 194:
        raise ValueError("remaining S3 TRAIN universe changed")

    source_records = []
    observations = []
    for source_id in sorted(sources):
        task = sources[source_id]
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
                        "class": type(exc).__name__, "message": str(exc)
                    }
                    break
        local = []
        if session.termination is None and source_exception is None:
            for robot in session.robots:
                record = _observation(session, robot)
                local.append(record)
                observations.append(record)
        normal = sum(
            item["selection"]["both_sides"]
            and not item["centerline_neutral_supports"] for item in local
        )
        neutral_resolvable = sum(
            item["selection"]["both_sides"]
            and bool(item["centerline_neutral_supports"]) for item in local
        )
        hold_unknown = sum(not item["selection"]["both_sides"] for item in local)
        unresolved_ties = sum(
            item["selection"]["physically_distinct_equal_distance_tie"]
            for item in local
        )
        if source_exception is not None or session.termination is not None:
            classification = "EXISTING_FROZEN_SOURCE_INVALID_HANDLING"
        elif neutral_resolvable and not normal and not hold_unknown:
            classification = "CENTERLINE_NEUTRAL_WITH_RESOLVABLE_OPPOSING_PAIR"
        elif normal or neutral_resolvable:
            classification = (
                "MIXED_RESOLVED_OPPOSING_PAIR_AND_EXISTING_HOLD_UNKNOWN"
                if hold_unknown else "NORMAL_OPPOSING_PAIR"
            )
        else:
            classification = "EXISTING_HOLD_UNKNOWN"
        source_records.append({
            "source_task_id": source_id,
            "family": task.family,
            "layout_id": task.layout_id,
            "layout_sha256": task.layout_sha256,
            "team_size": task.team_size,
            "episode_index": task.episode_index,
            "remaining_event_ids": sorted(
                item.event_id for item in s3_events if item.source.job_id == source_id
            ),
            "classification": classification,
            "robot_local_s3_observations": len(local),
            "normal_opposing_pairs": normal,
            "centerline_neutral_resolvable_pairs": neutral_resolvable,
            "existing_hold_unknown": hold_unknown,
            "source_invalid": int(
                source_exception is not None or session.termination is not None
            ),
            "missing_side_unresolved": 0,
            "support_tie_unresolved": unresolved_ties,
        })

    distribution = _distribution(observations)
    classes = Counter(item["classification"] for item in source_records)
    unresolved = sum(
        item["missing_side_unresolved"] + item["support_tie_unresolved"]
        for item in source_records
    )
    report = {
        "schema_version": "rvt-phase9g-a1c-s3-prestart-guard/v1",
        "phase": "PHASE_9G_A1C",
        "mode": "NON_OFFICIAL_AUTHORIZED_READ_ONLY_DIAGNOSTIC",
        "execution_environment": args.execution_environment,
        "scope": {
            "study": "study_a_zero_shot",
            "split": "train",
            "source_class": S3,
            "remaining_train_events_total": len(remaining),
            "remaining_s3_event_identities": len(s3_events),
            "remaining_s3_source_instances": len(sources),
            "completed_event_identities_excluded": len(completed),
            "checkpoint_sha256": checkpoint[
                "phase9_s3_staging_checkpoint_sha256"
            ],
        },
        "counter_levels": {
            "source_s3_instances": len(sources),
            "robot_local_s3_observations": len(observations),
            "participating_support_observations": distribution[
                "participating_support_observation_count"
            ],
            "centerline_neutral_support_observations": distribution[
                "centerline_neutral_support_observations"
            ],
            "resolved_opposing_pairs": sum(
                item["normal_opposing_pairs"]
                + item["centerline_neutral_resolvable_pairs"]
                for item in source_records
            ),
            "hold_unknown_robot_observations": sum(
                item["existing_hold_unknown"] for item in source_records
            ),
            "source_invalid_instances": sum(
                item["source_invalid"] for item in source_records
            ),
            "support_ties_resolved_by_frozen_identity": distribution[
                "instances_with_support_tie"
            ],
            "unresolved_s3_ambiguities": unresolved,
        },
        "source_classification_distribution": dict(sorted(classes.items())),
        "source_records": source_records,
        "fail_closed": {
            "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED": 0,
            "S3_MISSING_OPPOSING_SIDE_UNDERSPECIFIED": 0,
            "S3_SUPPORT_TIE_UNDERSPECIFIED": unresolved,
            "escapes": unresolved,
        },
        "scientific_writes": 0,
        "official_staging_checkpoint_unchanged": True,
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
        "status": "PASS" if unresolved == 0 else "FAIL",
    }
    report = attach_canonical_hash(
        report, "phase9g_a1c_s3_prestart_guard_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    if unresolved:
        raise SystemExit("unresolved S3 ambiguity")
    print(json.dumps({
        "status": report["status"],
        "hash": report["phase9g_a1c_s3_prestart_guard_sha256"],
        **report["counter_levels"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
