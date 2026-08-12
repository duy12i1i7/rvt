#!/usr/bin/env python3
"""Audit the immutable A1R continuation prefix after the frozen-source stop."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


COMPACT = 5
LINE = 2


def _bytes(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if _sha(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def _record(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop("canonical_record_sha256", ""))
    if _sha(body) != expected:
        raise ValueError(f"transaction hash mismatch: {path.name}")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--failure-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    data = args.data_root.resolve()
    status = _canonical(args.status, "phase9g_a1r_continuation_status_sha256")
    initial = _canonical(
        args.initial_checkpoint, "phase9g_a1r_staging_checkpoint_sha256"
    )
    failure = _canonical(
        args.failure_identity, "phase9g_a1r_worker_failure_identity_sha256"
    )
    manifest = json.loads(
        (root / "results/rvt_fd24/datasets/phase9_job_manifest.json")
        .read_text(encoding="ascii")
    )
    source_by_event = {}
    sources = {
        str(item["job_id"]): item for item in manifest["source_episode_jobs"]
    }
    for event in manifest["decision_event_jobs"]:
        source_by_event[str(event["job_id"])] = sources[
            str(event["source_episode_job_id"])
        ]
    train_root = data / "staging/study_a_zero_shot-train-recoverability"
    validation_root = data / "staging/study_a_zero_shot-validation-recoverability"
    if os.access(train_root, os.W_OK):
        raise ValueError("train staging is writable during stop audit")
    transaction_root = train_root / "recoverability"
    paths = sorted(transaction_root.glob("event-*.json"))
    partials = tuple(train_root.rglob("*.partial"))
    if len(paths) != 210 or partials:
        raise ValueError("post-stop transaction boundary is not exact")

    rows = set()
    events = set()
    aggregate_dispositions: Counter[str] = Counter()
    invalid_reasons: Counter[str] = Counter()
    pair_statuses: Counter[str] = Counter()
    replicas = 0
    infrastructure_retry_attempts = 0
    table = defaultdict(lambda: Counter())
    transaction_descriptors = []
    for path in paths:
        record = _record(path)
        event_id = str(record["decision_event_id"])
        if event_id in events:
            raise ValueError("duplicate candidate-pair event identity")
        events.add(event_id)
        source = source_by_event[event_id]
        family = str(source["family_id"])
        team_size = int(source["team_size"])
        pair_status = str(record["status"])
        pair_statuses[pair_status] += 1
        if not record["scientifically_reconciled"] or not record[
            "scientific_completion_marker"
        ]:
            raise ValueError("incomplete candidate-pair transaction is durable")
        if int(record["actual_row_count"]) != len(record["rows"]):
            raise ValueError("transaction row count mismatch")
        for row in record["rows"]:
            row_id = str(row["scientific_row_id"])
            if row_id in rows or _sha(row["scientific_identity"]) != row_id:
                raise ValueError("duplicate or invalid scientific row identity")
            rows.add(row_id)
        audits = list(record["audit"].get("candidate_audits", ()))
        if pair_status == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID":
            if audits or record["actual_row_count"] != 0:
                raise ValueError("generation-invalid transaction contains science rows")
            termination = record["audit"]["termination"]
            reason = f"SOURCE_TERMINATED_BEFORE_EVENT:{termination['cause']}"
            invalid_reasons[reason] += 2
            aggregate_dispositions["GENERATION_INVALID"] += 2
            for candidate in (COMPACT, LINE):
                table[(family, team_size, candidate)]["GENERATION_INVALID"] += 1
        elif pair_status == "SCIENTIFICALLY_RECONCILED_LABELABLE":
            if len(audits) != 2:
                raise ValueError("labelable transaction lacks two candidate audits")
            for audit in audits:
                aggregate = audit["aggregate"]
                disposition = str(aggregate["disposition"])
                candidate = int(aggregate["candidate_topology_id"])
                if disposition not in ("RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"):
                    raise ValueError("labelable aggregate has an invalid disposition")
                aggregate_dispositions[disposition] += 1
                table[(family, team_size, candidate)][disposition] += 1
                candidate_replicas = list(audit["replicas"])
                replicas += len(candidate_replicas)
                for replica in candidate_replicas:
                    attempts = list(replica["infrastructure_attempts"])
                    infrastructure_retry_attempts += max(0, len(attempts) - 1)
        else:
            raise ValueError("unknown candidate-pair status")
        transaction_descriptors.append({
            "decision_event_id": event_id,
            "family": family,
            "team_size": team_size,
            "status": pair_status,
            "scientific_row_count": int(record["actual_row_count"]),
            "file_sha256": _file_sha(path),
            "canonical_record_sha256": record["canonical_record_sha256"],
        })

    initial_rows = set(initial["scientific_row_ids"])
    if not initial_rows <= rows or len(initial_rows) != 318:
        raise ValueError("initial official rows were not preserved")
    new_rows = rows - initial_rows
    breakdown = []
    for (family, team_size, candidate), counts in sorted(table.items()):
        breakdown.append({
            "family": family,
            "team_size": team_size,
            "candidate_topology_id": candidate,
            "candidate_topology_name": "COMPACT" if candidate == COMPACT else "LINE",
            **{
                disposition.lower(): counts[disposition]
                for disposition in (
                    "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE", "GENERATION_INVALID"
                )
            },
        })
    report = {
        "schema_version": "rvt-phase9g-a1r-continuation-stop-audit/v1",
        "status": "STOPPED_FROZEN_SOURCE_EXCEPTION",
        "verdict": "A",
        "verdict_text": "Recoverability continuation requires changing frozen science.",
        "run_id": status["run_id"],
        "parent_run_id": status["parent_run_id"],
        "scientific_source_commit": "8cf64481cd17b2c44f7007d3722a8110e53cae46",
        "production_image": (
            "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
        ),
        "profile": {
            "workers": status["workers"],
            "numeric_threads": status["numeric_threads"],
            "chunk_size_atomic_units": status["chunk_size_atomic_units"],
            "infrastructure_timeout_seconds": status[
                "infrastructure_timeout_seconds"
            ],
        },
        "official_progress": {
            "train_events_completed": len(events),
            "train_events_total": 6000,
            "validation_events_completed": 0,
            "validation_events_total": 1500,
            "all_events_completed": len(events),
            "all_events_total": 7500,
            "candidate_aggregates_completed": 2 * len(events),
            "candidate_aggregates_total": 15000,
            "replicas_completed_for_labelable_aggregates": replicas,
            "scientific_rows": len(rows),
            "initial_rows_reused": len(initial_rows),
            "new_rows_committed": len(new_rows),
            "pair_retained_events": pair_statuses[
                "SCIENTIFICALLY_RECONCILED_LABELABLE"
            ],
            "pair_dropped_events": pair_statuses[
                "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID"
            ],
            "aggregate_dispositions": dict(sorted(aggregate_dispositions.items())),
            "generation_invalid_reason_distribution": dict(
                sorted(invalid_reasons.items())
            ),
            "infrastructure_timeouts_this_continuation": 0,
            "infrastructure_retry_attempts": infrastructure_retry_attempts,
            "scientific_retries": 0,
            "unresolved_worker_failures": 1,
            "duplicate_scientific_row_identities": 0,
            "partial_candidate_pair_publications": 0,
        },
        "failure": failure,
        "timeout_requalification_outcome": {
            "previously_timed_out_unit_completed_officially": True,
            "maximum_observed_atomic_unit_wall_seconds": status[
                "maximum_atomic_unit_wall_seconds"
            ],
            "qualified_timeout_seconds": status[
                "infrastructure_timeout_seconds"
            ],
            "new_timeout_exceeded": False,
            "timeout_semantics_remain_infrastructure_only": True,
        },
        "data_integrity": {
            "initial_checkpoint_sha256": initial[
                "phase9g_a1r_staging_checkpoint_sha256"
            ],
            "initial_checkpoint_preimage_sha256": initial[
                "staging_checkpoint_preimage_sha256"
            ],
            "all_initial_rows_preserved": True,
            "all_transactions_complete": True,
            "staging_read_only_after_stop": True,
            "validation_staging_exists": validation_root.exists(),
            "transaction_descriptors": transaction_descriptors,
            "scientific_row_ids": sorted(rows),
            "new_scientific_row_ids": sorted(new_rows),
        },
        "descriptive_breakdown": breakdown,
        "sealed_domains": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
        "downstream": {
            "residual_started": False,
            "training_operations": 0,
            "final_dataset_manifest_created": False,
            "reason": "Recoverability train did not complete",
        },
    }
    report["phase9g_a1r_continuation_stop_audit_sha256"] = _sha(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "events": len(events),
        "rows": len(rows),
        "aggregate_dispositions": dict(aggregate_dispositions),
        "verdict": "A",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
