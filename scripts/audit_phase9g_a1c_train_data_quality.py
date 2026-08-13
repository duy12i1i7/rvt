#!/usr/bin/env python3
"""Build a descriptive A1C TRAIN audit directly from finalized transactions."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.topology_registry import COMPACT, LINE


TOPOLOGY_NAMES = {COMPACT: "COMPACT", LINE: "LINE"}
S3 = "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR"


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path}")
    return document


def _records(counter: Counter, keys: tuple[str, ...]) -> list[dict]:
    return [
        {**dict(zip(keys, key)), "count": count}
        for key, count in sorted(counter.items())
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    data_root = args.data_root.resolve()
    audit_root = data_root / "audit" / args.run_id
    final = data_root / "final/phase9g-a1-study-a-train-recoverability-v1"
    manifest = _canonical(final / "dataset_manifest.json", "dataset_manifest_sha256")
    guard = _canonical(
        audit_root / "prestart/s3-prestart-guard-target.json",
        "phase9g_a1c_s3_prestart_guard_sha256",
    )
    tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="train"
    )
    task_by_id = {task.event_id: task for task in tasks}
    if len(tasks) != 6000 or len(task_by_id) != 6000:
        raise ValueError("TRAIN task universe changed")

    aggregate_distribution: Counter[tuple] = Counter()
    pair_distribution: Counter[tuple] = Counter()
    invalid_reason_events: Counter[tuple] = Counter()
    source_distribution: Counter[tuple] = Counter()
    s3_aggregates: Counter[tuple] = Counter()
    s3_pairs: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    rows = set()

    transaction_root = final / "transactions/train"
    paths = tuple(sorted(transaction_root.glob("event-*.json")))
    if len(paths) != 6000:
        raise ValueError("final transaction universe is not 6000")
    for path in paths:
        document = _canonical(path, "canonical_record_sha256")
        event_id = str(document["decision_event_id"])
        task = task_by_id.get(event_id)
        if task is None:
            raise ValueError("final transaction is outside TRAIN manifest")
        family = task.source.family
        team_size = task.source.team_size
        source_class = task.source.source_class
        pair_status = str(document["status"])
        totals["events"] += 1
        totals["candidate_aggregates"] += 2
        source_distribution[(family, team_size, source_class)] += 1
        if pair_status == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID":
            pair_state = "DROPPED_NONPUBLISHED"
            audit = document["audit"]
            termination = audit.get("termination")
            if not audit.get("source_terminated_before_event") or not termination:
                raise ValueError("generation-invalid transaction lacks frozen source cause")
            reason = f"SOURCE_TERMINATED_BEFORE_EVENT:{termination['cause']}"
            invalid_reason_events[(family, team_size, source_class, reason)] += 1
            for candidate in (COMPACT, LINE):
                aggregate_distribution[(
                    family, team_size, source_class, candidate,
                    TOPOLOGY_NAMES[candidate], "GENERATION_INVALID",
                )] += 1
                if source_class == S3:
                    s3_aggregates[(TOPOLOGY_NAMES[candidate], "GENERATION_INVALID")] += 1
            totals["GENERATION_INVALID"] += 2
        elif pair_status == "SCIENTIFICALLY_RECONCILED_LABELABLE":
            pair_state = "RETAINED"
            candidate_audits = {
                int(item["candidate_topology_id"]): item
                for item in document["audit"]["candidate_audits"]
            }
            if set(candidate_audits) != {COMPACT, LINE}:
                raise ValueError("retained pair lacks both candidate audits")
            for candidate in (COMPACT, LINE):
                disposition = str(
                    candidate_audits[candidate]["aggregate"]["disposition"]
                )
                if disposition not in {
                    "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"
                }:
                    raise ValueError("unexpected labelable aggregate disposition")
                aggregate_distribution[(
                    family, team_size, source_class, candidate,
                    TOPOLOGY_NAMES[candidate], disposition,
                )] += 1
                totals[disposition] += 1
                if source_class == S3:
                    s3_aggregates[(TOPOLOGY_NAMES[candidate], disposition)] += 1
            if len(document["rows"]) != 2 * team_size:
                raise ValueError("retained pair does not publish 2*N rows")
            for row in document["rows"]:
                row_id = str(row["scientific_row_id"])
                if row_id in rows:
                    raise ValueError("duplicate scientific row identity")
                rows.add(row_id)
        else:
            raise ValueError("unknown candidate-pair state")
        pair_distribution[(family, team_size, source_class, pair_state)] += 1
        totals[f"PAIR_{pair_state}"] += 1
        if source_class == S3:
            s3_pairs[pair_state] += 1

    source_instances = {
        task.source.job_id: task.source for task in tasks
    }
    s3_source_instances = sum(
        source.source_class == S3 for source in source_instances.values()
    )
    if (
        totals["events"] != 6000
        or totals["candidate_aggregates"] != 12000
        or sum(totals[key] for key in (
            "GENERATION_INVALID", "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"
        )) != 12000
        or totals["PAIR_RETAINED"] + totals["PAIR_DROPPED_NONPUBLISHED"] != 6000
        or len(rows) != manifest["scientific_row_count"] != 8340
        or s3_source_instances != 200
    ):
        raise ValueError("descriptive TRAIN accounting does not reconcile")

    report = {
        "schema_version": "rvt-phase9g-a1c-train-data-quality-audit/v1",
        "phase": "PHASE_9G_A1C",
        "status": "PASS_DESCRIPTIVE_ONLY",
        "dataset_manifest_sha256": manifest["dataset_manifest_sha256"],
        "counting_units": {
            "source_instance": "one frozen source episode identity",
            "decision_event": "one source decision event candidate-pair transaction",
            "candidate_aggregate": "one COMPACT or LINE aggregate at one event",
            "scientific_row": "one robot-local candidate-conditioned row",
            "s3_robot_observation": "one robot view at the frozen three-step guard prefix",
            "s3_support_observation": "one participating support projection in one robot view",
        },
        "totals": {
            "source_episodes": len(source_instances),
            "decision_events": totals["events"],
            "candidate_aggregates": totals["candidate_aggregates"],
            "RECOVERABLE_POSITIVE": totals["RECOVERABLE_POSITIVE"],
            "VALID_TASK_NEGATIVE": totals["VALID_TASK_NEGATIVE"],
            "GENERATION_INVALID": totals["GENERATION_INVALID"],
            "candidate_pair_retained_events": totals["PAIR_RETAINED"],
            "candidate_pair_dropped_nonpublished_events": totals[
                "PAIR_DROPPED_NONPUBLISHED"
            ],
            "scientific_rows": len(rows),
        },
        "aggregate_distribution_by_family_n_source_topology_disposition": _records(
            aggregate_distribution,
            (
                "family", "team_size", "source_class", "candidate_topology_id",
                "candidate_topology", "disposition",
            ),
        ),
        "candidate_pair_distribution_by_family_n_source_state": _records(
            pair_distribution,
            ("family", "team_size", "source_class", "state"),
        ),
        "scientific_invalid_reason_distribution": _records(
            invalid_reason_events,
            ("family", "team_size", "source_class", "reason"),
        ),
        "source_event_distribution_by_family_n_source_class": _records(
            source_distribution,
            ("family", "team_size", "source_class"),
        ),
        "s3": {
            "complete_train_source_instances": s3_source_instances,
            "complete_train_decision_events": sum(s3_pairs.values()),
            "complete_train_candidate_aggregates": sum(s3_aggregates.values()),
            "complete_train_candidate_pair_distribution": dict(sorted(s3_pairs.items())),
            "complete_train_candidate_aggregate_distribution": _records(
                s3_aggregates, ("candidate_topology", "disposition")
            ),
            "continuation_remaining_prestart_counter_levels": guard["counter_levels"],
            "continuation_remaining_source_classification_distribution": guard[
                "source_classification_distribution"
            ],
            "unresolved_ambiguities": guard["counter_levels"][
                "unresolved_s3_ambiguities"
            ],
        },
        "original_rows": {
            "retained": 342,
            "regenerated": 0,
            "UNAFFECTED": 254,
            "DEPENDENCY_PRESENT_BUT_VALUE_VALID": 88,
            "POTENTIALLY_AFFECTED": 0,
            "PROVEN_AFFECTED": 0,
        },
        "class_weighting": "NOT_SELECTED",
        "sampling_changed": False,
        "thresholds_changed": False,
        "target_v4_changed": False,
        "scenario_counts_changed": False,
        "descriptive_only": True,
        "sealed_scope": {
            "recoverability_validation_operations": 0,
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    report = attach_canonical_hash(
        report, "phase9g_a1c_train_data_quality_audit_sha256"
    )
    output = audit_root / "train_data_quality_audit.json"
    output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": report["status"],
        "hash": report["phase9g_a1c_train_data_quality_audit_sha256"],
        **report["totals"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
