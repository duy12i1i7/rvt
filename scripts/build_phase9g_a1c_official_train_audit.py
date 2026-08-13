#!/usr/bin/env python3
"""Summarize official A1C TRAIN execution without changing scientific data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path}")
    return document


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot summarize an empty runtime set")
    rank = probability * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    audit = data_root / "audit" / args.run_id
    final = data_root / "final/phase9g-a1-study-a-train-recoverability-v1"
    telemetry_path = audit / "train-operational-telemetry.jsonl"
    telemetry = [
        json.loads(line) for line in telemetry_path.read_text(encoding="ascii").splitlines()
        if line.strip()
    ]
    status = _canonical(
        audit / "train-continuation-status.json",
        "phase9g_a1c_continuation_status_sha256",
    )
    reconciliation = _canonical(
        audit / "train_reconciliation.json",
        "phase9g_a1c_recoverability_train_reconciliation_sha256",
    )
    finalization = _canonical(
        audit / "train_finalization.json",
        "phase9g_a1c_recoverability_train_finalization_sha256",
    )
    validation = _canonical(
        audit / "postfinal_dataset_validation.json",
        "phase9g_a1c_postfinal_dataset_validation_sha256",
    )
    manifest = _canonical(final / "dataset_manifest.json", "dataset_manifest_sha256")
    seal = _canonical(final / "DATASET_SEAL.json", "dataset_seal_sha256")
    if len(telemetry) != 5790 or status["state"] != "COMPLETE":
        raise ValueError("official continuation telemetry/status is incomplete")
    event_ids = [item["decision_event_id"] for item in telemetry]
    if len(set(event_ids)) != len(event_ids):
        raise ValueError("duplicate event identity in continuation telemetry")

    dispositions: Counter[str] = Counter()
    transaction_statuses: Counter[str] = Counter()
    candidate_walls = []
    candidate_cpus = []
    replica_walls = []
    reconciliation_walls = []
    peak_rss = 0
    duplicate_replays = 0
    official_writes = 0
    scientific_rows = 0
    for event in telemetry:
        transaction_statuses[str(event["transaction_status"])] += 1
        duplicate_replays += int(bool(event["duplicate_replay"]))
        official_writes += int(event["official_counter_delta"])
        scientific_rows += int(event["scientific_row_count"])
        reconciliation_walls.append(
            float(event["candidate_pair_reconciliation_wall_seconds"])
        )
        for unit in event["candidate_units"]:
            dispositions[str(unit["disposition"]["disposition"])] += 1
            candidate_walls.append(float(unit["wall_seconds"]))
            candidate_cpus.append(float(unit["cpu_seconds"]))
            peak_rss = max(peak_rss, int(unit["peak_rss_bytes"]))
            replica_walls.extend(
                float(value)
                for value in unit["operational_timing"]["replica_rollout_seconds"]
            )

    expected_continuation_dispositions = {
        "GENERATION_INVALID": 10734,
        "RECOVERABLE_POSITIVE": 502,
        "VALID_TASK_NEGATIVE": 344,
    }
    if dict(dispositions) != expected_continuation_dispositions:
        raise ValueError("continuation disposition totals do not reconcile")
    if transaction_statuses != Counter({
        "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID": 5367,
        "SCIENTIFICALLY_RECONCILED_LABELABLE": 423,
    }):
        raise ValueError("continuation candidate-pair states do not reconcile")
    if (
        official_writes != 5790
        or duplicate_replays != 0
        or scientific_rows != 7998
        or len(replica_walls) != 1042
        or reconciliation["observed"]["scientific_rows"] != 8340
        or validation["status"] != "PASS"
        or finalization["status"] != "FINALIZED"
    ):
        raise ValueError("official continuation/final dataset accounting mismatch")

    runtime_summary = lambda values: {
        "n": len(values),
        "median_seconds": statistics.median(values),
        "p90_seconds": _percentile(values, 0.90),
        "p95_seconds": _percentile(values, 0.95),
        "maximum_seconds": max(values),
    }
    report = {
        "schema_version": "rvt-phase9g-a1c-official-train-continuation-audit/v1",
        "phase": "PHASE_9G_A1C",
        "status": "PASS",
        "run_id": args.run_id,
        "parent_run_id": status["parent_run_id"],
        "identity": {
            "evidence_commit_at_authorization": "af5c083e58476f5bd8a08710ce567176108e8f06",
            "authority_commit": "869db24fac87b24b60a95fd192a6a75a63fc0ed0",
            "startup_requalification_commit": "982349d92863a0a3c5a6bcdce25332877df27be0",
            "executable_source_commit": "848e8b352a91e95af777ebbeccd5fbb43d53777e",
            "production_image": "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90",
            "authorization_continuation_sha256": status[
                "authorization_continuation_sha256"
            ],
            "initial_checkpoint_sha256": status["initial_checkpoint_sha256"],
        },
        "profile": {
            "workers": status["workers"],
            "numeric_threads_per_worker": status["numeric_threads"],
            "chunk_size_atomic_units": status["chunk_size_atomic_units"],
            "infrastructure_timeout_seconds": status[
                "infrastructure_timeout_seconds"
            ],
        },
        "resume": {
            "initial_completed_events_reused": status[
                "completed_event_identities_reused"
            ],
            "initial_scientific_rows_reused": status[
                "initial_scientific_rows_reused"
            ],
            "unresolved_events_scheduled": status[
                "unresolved_event_identities_scheduled"
            ],
            "existing_rows_reemitted": status["existing_rows_reemitted"],
            "startup_launch_failures_before_scientific_execution": 1,
            "scientific_retries": 0,
            "official_producer_scientific_execution_attempts": 1,
        },
        "continuation_execution": {
            "events": len(telemetry),
            "candidate_aggregates": len(candidate_walls),
            "replica_executions": len(replica_walls),
            "scientific_rows": scientific_rows,
            "official_transactions_written": official_writes,
            "duplicate_replays": duplicate_replays,
            "candidate_dispositions": dict(sorted(dispositions.items())),
            "candidate_pair_states": dict(sorted(transaction_statuses.items())),
            "candidate_runtime": runtime_summary(candidate_walls),
            "replica_runtime": runtime_summary(replica_walls),
            "reconciliation_writer_runtime": runtime_summary(reconciliation_walls),
            "candidate_cpu_hours": sum(candidate_cpus) / 3600.0,
            "peak_worker_rss_bytes": peak_rss,
            "wall_seconds": status["execution_summary"]["wall_seconds"],
            "maximum_atomic_unit_wall_seconds": status[
                "execution_summary"
            ]["maximum_atomic_unit_wall_seconds"],
            "infrastructure_timeouts": 0,
            "infrastructure_retries": 0,
            "writer_failures": 0,
            "partial_transactions": 0,
        },
        "complete_train": {
            "source_episodes": reconciliation["observed"][
                "source_episodes_completed"
            ],
            "events": reconciliation["observed"]["decision_events"],
            "candidate_aggregates": reconciliation["observed"][
                "candidate_aggregates"
            ],
            "replica_executions": reconciliation["observed"]["replica_executions"],
            "scientific_rows": reconciliation["observed"]["scientific_rows"],
            "candidate_pair_retained_events": reconciliation["observed"][
                "candidate_pair_retained_events"
            ],
            "candidate_pair_dropped_events": reconciliation["observed"][
                "candidate_pair_dropped_events"
            ],
            "candidate_dispositions": {
                key: reconciliation["observed"].get(f"{key}_aggregates", 0)
                for key in (
                    "GENERATION_INVALID", "RECOVERABLE_POSITIVE",
                    "VALID_TASK_NEGATIVE",
                )
            },
        },
        "s3": {
            "counter_semantics": (
                "remaining authorized TRAIN source trace-prefix guard carried "
                "through production status; denominator levels are distinct"
            ),
            **status["s3_counter_levels"],
        },
        "integrity": reconciliation["observed"],
        "existing_342_row_lineage": reconciliation["existing_342_row_lineage"],
        "dataset": {
            "dataset_id": manifest["dataset_id"],
            "manifest_sha256": manifest["dataset_manifest_sha256"],
            "seal_sha256": seal["dataset_seal_sha256"],
            "postfinal_validation_sha256": validation[
                "phase9g_a1c_postfinal_dataset_validation_sha256"
            ],
            "shards": len(manifest["shards"]),
            "storage_bytes": validation["dataset_storage_bytes"],
            "validation_included": False,
        },
        "raw_telemetry": {
            "target_path": str(telemetry_path),
            "file_sha256": _file_sha(telemetry_path),
            "bytes": telemetry_path.stat().st_size,
            "jsonl_records": len(telemetry),
        },
        "sealed_domains": reconciliation["sealed_domains"],
        "downstream": {
            "recoverability_validation_started": False,
            "residual_v2_started": False,
            "training_operations": 0,
        },
    }
    report = attach_canonical_hash(
        report, "phase9g_a1c_official_train_continuation_audit_sha256"
    )
    output = audit / "official_train_continuation_audit.json"
    output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": report["status"],
        "hash": report["phase9g_a1c_official_train_continuation_audit_sha256"],
        "events": report["complete_train"]["events"],
        "rows": report["complete_train"]["scientific_rows"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
