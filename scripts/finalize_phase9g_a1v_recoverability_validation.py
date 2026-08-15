#!/usr/bin/env python3
"""Reconcile and atomically finalize Study-A Recoverability VALIDATION."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from time import monotonic
from typing import Any, Mapping

from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9g0r.compiler import JOB_MANIFEST_SHA256, compile_recoverability_tasks
from rvt_swarm.phase9g0r.contracts import recoverability_scientific_row_id
from rvt_swarm.topology_registry import COMPACT, LINE
from scripts.finalize_phase9g_a1_recoverability import (
    ReconciliationError,
    _ShardWriter,
    _atomic_json,
    _candidate_dispositions,
    _canonical,
    _sha256_file,
    _timestamp,
    _write_jsonl,
)


STUDY = "study_a_zero_shot"
SPLIT = "validation"
DATASET_ID = "phase9g-a1-study-a-validation-recoverability-v1"
SOURCE_COMMIT = "848e8b352a91e95af777ebbeccd5fbb43d53777e"
IMAGE = "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
PROVENANCE = "9f209cd4b5ae591b2f576a085bcbdb6b7d30a7f3fecb9840d6e0eb56bb03adc8"
TRAIN_MANIFEST = "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
TRAIN_SEAL = "5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5"


def _transaction_map(staging: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    transaction_root = staging / "recoverability"
    if tuple(transaction_root.glob("*.partial")):
        raise ReconciliationError("partial candidate-pair transaction remains")
    result = {}
    for path in sorted(transaction_root.glob("event-*.json")):
        document = json.loads(path.read_text(encoding="ascii"))
        body = dict(document)
        expected = str(body.pop("canonical_record_sha256", ""))
        if len(expected) != 64 or sha256_document(body) != expected:
            raise ReconciliationError(f"transaction hash mismatch: {path.name}")
        event_id = str(document["decision_event_id"])
        if event_id in result:
            raise ReconciliationError("duplicate decision-event transaction")
        result[event_id] = (path, document)
    return result


def _load_telemetry(audit_root: Path) -> tuple[list[dict], dict]:
    records = [
        json.loads(line)
        for line in (audit_root / "validation-operational-telemetry.jsonl")
        .read_text(encoding="ascii")
        .splitlines()
        if line.strip()
    ]
    status, _ = _canonical(
        audit_root / "validation-status.json",
        "phase9g_a1v_validation_status_sha256",
    )
    if status["state"] != "COMPLETE" or len(records) != 1500:
        raise ReconciliationError("A1V execution is not complete")
    return records, status


def reconcile(
    root: Path,
    data_root: Path,
    run_id: str,
    task_manifest_path: Path,
    s3_guard_path: Path,
) -> Mapping[str, Any]:
    tasks = compile_recoverability_tasks(root, study=STUDY, split=SPLIT)
    if len(tasks) != 1500:
        raise ReconciliationError("frozen VALIDATION event universe changed")
    task_by_id = {task.event_id: task for task in tasks}
    staging = data_root / "staging" / f"{STUDY}-{SPLIT}-recoverability"
    observed = _transaction_map(staging)
    if set(observed) != set(task_by_id):
        raise ReconciliationError(
            f"event universe mismatch: missing={len(set(task_by_id)-set(observed))}, "
            f"unexpected={len(set(observed)-set(task_by_id))}"
        )

    task_manifest, task_manifest_sha = _canonical(
        task_manifest_path, "phase9g_a1v_validation_task_manifest_sha256"
    )
    if (
        task_manifest["decision_events"] != 1500
        or task_manifest["candidate_aggregates"] != 3000
        or {item["decision_event_id"] for item in task_manifest["decision_event_tasks"]}
        != set(task_by_id)
    ):
        raise ReconciliationError("validation task manifest changed")
    guard, guard_sha = _canonical(
        s3_guard_path, "phase9g_a1v_s3_prestart_guard_sha256"
    )
    if (
        guard["status"] != "PASS"
        or guard["counter_levels"]["unresolved_s3_ambiguities"] != 0
        or guard["scope"]["task_manifest_sha256"] != task_manifest_sha
    ):
        raise ReconciliationError("S3 prestart population guard did not pass")

    telemetry, status = _load_telemetry(data_root / "audit" / run_id)
    if (
        status["total_event_identities"] != 1500
        or status["preexisting_event_identities"] != 0
        or status["execution_summary"]["events"] != 1500
        or status["execution_summary"]["official_counter_delta"] != 1500
        or status["execution_summary"]["duplicate_replays"] != 0
    ):
        raise ReconciliationError("validation execution summary does not reconcile")
    if {item["decision_event_id"] for item in telemetry} != set(task_by_id):
        raise ReconciliationError("telemetry identity set differs from task manifest")

    counters: Counter[str] = Counter()
    aggregate_distribution: Counter[tuple[str, int, str, int, str]] = Counter()
    pair_distribution: Counter[tuple[str, int, str, str]] = Counter()
    invalid_distribution: Counter[tuple[str, int, str, str]] = Counter()
    source_events: dict[str, set[str]] = defaultdict(set)
    row_ids: set[str] = set()
    transaction_descriptors = []

    for event_id in sorted(task_by_id):
        task = task_by_id[event_id]
        path, document = observed[event_id]
        if (
            document.get("scientifically_reconciled") is not True
            or document.get("scientific_completion_marker") is not True
        ):
            raise ReconciliationError("unresolved transaction entered completion set")
        n = task.source.team_size
        if n == 24:
            raise ReconciliationError("Study A N24 entered VALIDATION staging")
        expected_rows = 2 * n
        actual_rows = int(document["actual_row_count"])
        if (
            int(document["expected_row_count"]) != expected_rows
            or actual_rows not in (0, expected_rows)
            or actual_rows != len(document["rows"])
        ):
            raise ReconciliationError("partial candidate-pair row set was published")
        source_events[task.source.job_id].add(event_id)
        counters["decision_events"] += 1
        counters["candidate_aggregates"] += 2
        candidates, replicas, retries, failures = _candidate_dispositions(document)
        counters["replica_executions"] += replicas
        counters["infrastructure_retries"] += retries
        counters["infrastructure_failure_attempts"] += failures
        tx_status = str(document["status"])

        if tx_status == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID":
            if actual_rows or document["training_rows_committable"]:
                raise ReconciliationError("generation-invalid event emitted rows")
            audit = document.get("audit", {})
            termination = audit.get("termination")
            if not audit.get("source_terminated_before_event") or not termination:
                raise ReconciliationError("generation-invalid lacks frozen source cause")
            reason = f"SOURCE_TERMINATED_BEFORE_EVENT:{termination['cause']}"
            counters["candidate_pair_dropped_events"] += 1
            counters["GENERATION_INVALID_aggregates"] += 2
            pair_distribution[(task.source.family, n, task.source.source_class, "DROPPED_NONPUBLISHED")] += 1
            invalid_distribution[(task.source.family, n, task.source.source_class, reason)] += 1
            for candidate in (COMPACT, LINE):
                aggregate_distribution[(task.source.family, n, task.source.source_class, candidate, "GENERATION_INVALID")] += 1
        elif tx_status == "SCIENTIFICALLY_RECONCILED_LABELABLE":
            if (
                not document["training_rows_committable"]
                or actual_rows != expected_rows
                or set(candidates) != {COMPACT, LINE}
            ):
                raise ReconciliationError("labelable candidate pair is incomplete")
            counters["candidate_pair_retained_events"] += 1
            pair_distribution[(task.source.family, n, task.source.source_class, "RETAINED")] += 1
            for candidate in (COMPACT, LINE):
                candidate_audit = candidates[candidate]
                aggregate = candidate_audit.get("aggregate")
                disposition = str(aggregate["disposition"] if aggregate else "")
                if disposition not in {"RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"}:
                    raise ReconciliationError("candidate disposition changed")
                counters[f"{disposition}_aggregates"] += 1
                aggregate_distribution[(task.source.family, n, task.source.source_class, candidate, disposition)] += 1
                actual_seeds = {
                    int(replica["replica_index"]): int(replica["matched_disturbance_seed"])
                    for replica in candidate_audit["replicas"]
                }
                expected_seeds = {
                    int(job["replica_index"]): int(job["seeds"]["matched_disturbance_seed"])
                    for job in task.replica_jobs(candidate)
                }
                other = LINE if candidate == COMPACT else COMPACT
                other_seeds = {
                    int(job["replica_index"]): int(job["seeds"]["matched_disturbance_seed"])
                    for job in task.replica_jobs(other)
                }
                if actual_seeds != expected_seeds or actual_seeds != other_seeds:
                    raise ReconciliationError("matched candidate streams diverged")

            coverage: Counter[int] = Counter()
            robots: dict[int, set[int]] = defaultdict(set)
            for row in document["rows"]:
                identity = row["scientific_identity"]
                row_id = str(row["scientific_row_id"])
                if row_id != recoverability_scientific_row_id(identity) or row_id in row_ids:
                    raise ReconciliationError("duplicate or invalid scientific row identity")
                row_ids.add(row_id)
                if (
                    identity["study"] != STUDY
                    or identity["split"] != SPLIT
                    or int(identity["team_size"]) != n
                ):
                    raise ReconciliationError("scientific row crossed validation scope")
                candidate = int(row["candidate_topology_id"])
                robot = int(identity["robot_id"])
                if candidate not in (COMPACT, LINE):
                    raise ReconciliationError("unexpected candidate topology")
                if (
                    sha256_document(row["graph_payload"]) != row["graph_fingerprint"]
                    or row["graph_fingerprint"] != identity["graph_fingerprint"]
                ):
                    raise ReconciliationError("row graph fingerprint mismatch")
                disposition = str(row["target_v4_aggregate_disposition"])
                label = int(row["target_v4_aggregate_label"])
                if (disposition == "RECOVERABLE_POSITIVE") != (label == 1):
                    raise ReconciliationError("row label/disposition mismatch")
                coverage[candidate] += 1
                robots[candidate].add(robot)
            if coverage != Counter({COMPACT: n, LINE: n}):
                raise ReconciliationError("candidate row coverage is not N plus N")
            if any(value != set(range(n)) for value in robots.values()):
                raise ReconciliationError("candidate rows do not cover every robot")
        else:
            raise ReconciliationError("unknown candidate-pair transaction status")

        counters["scientific_rows"] += actual_rows
        transaction_descriptors.append({
            "decision_event_id": event_id,
            "relative_staging_path": str(path.relative_to(data_root / "staging")),
            "content_sha256": _sha256_file(path),
            "status": tx_status,
            "scientific_rows": actual_rows,
        })

    if len(source_events) != 300 or any(len(events) != 5 for events in source_events.values()):
        raise ReconciliationError("source/event accounting does not reconcile to 300*5")
    if (
        counters["decision_events"] != 1500
        or counters["candidate_aggregates"] != 3000
        or counters["RECOVERABLE_POSITIVE_aggregates"]
        + counters["VALID_TASK_NEGATIVE_aggregates"]
        + counters["GENERATION_INVALID_aggregates"] != 3000
        or counters["candidate_pair_retained_events"]
        + counters["candidate_pair_dropped_events"] != 1500
    ):
        raise ReconciliationError("validation denominator equations failed")

    candidate_cpu = sum(
        float(unit["cpu_seconds"])
        for item in telemetry for unit in item["candidate_units"]
    )
    return {
        "schema_version": "rvt-phase9g-a1v-validation-reconciliation/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS",
        "run_id": run_id,
        "study": STUDY,
        "split": SPLIT,
        "job_manifest_sha256": JOB_MANIFEST_SHA256,
        "validation_task_manifest_sha256": task_manifest_sha,
        "expected": {
            "source_episodes": 300,
            "decision_events": 1500,
            "candidate_aggregates": 3000,
            "candidate_replica_slots": sum(2 * task.replicas_per_candidate for task in tasks),
        },
        "observed": {
            **dict(counters),
            "source_episodes_completed": len(source_events),
            "unexpected_duplicate_transactions": 0,
            "duplicate_scientific_identities": 0,
            "partial_candidate_pair_publications": 0,
            "unresolved_infrastructure_failures": 0,
            "infrastructure_timeouts": 0,
            "writer_failures": 0,
            "schema_failures": 0,
            "hash_failures": 0,
            "seed_mismatches": 0,
            "seal_violations": 0,
            "unaccounted_events": 0,
        },
        "aggregate_distribution": [
            {
                "family": family,
                "team_size": n,
                "source_class": source_class,
                "candidate_topology_id": candidate,
                "disposition": disposition,
                "count": count,
            }
            for (family, n, source_class, candidate, disposition), count
            in sorted(aggregate_distribution.items())
        ],
        "candidate_pair_distribution": [
            {"family": family, "team_size": n, "source_class": source_class, "state": state, "count": count}
            for (family, n, source_class, state), count in sorted(pair_distribution.items())
        ],
        "invalid_reason_distribution": [
            {"family": family, "team_size": n, "source_class": source_class, "reason": reason, "count": count}
            for (family, n, source_class, reason), count in sorted(invalid_distribution.items())
        ],
        "s3": {"prestart_guard_sha256": guard_sha, **guard["counter_levels"]},
        "transaction_descriptors": transaction_descriptors,
        "operational": {
            "wall_seconds": float(status["execution_summary"]["wall_seconds"]),
            "candidate_cpu_hours": candidate_cpu / 3600.0,
            "maximum_atomic_unit_wall_seconds": status["execution_summary"]["maximum_atomic_unit_wall_seconds"],
            "staging_storage_bytes": sum(
                path.stat().st_size for path in staging.rglob("*") if path.is_file()
            ),
        },
        "train_reference": {"manifest_sha256": TRAIN_MANIFEST, "seal_sha256": TRAIN_SEAL},
        "sealed_domains": {
            "recoverability_train_modifications": 0,
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
            "hyperparameter_trials": 0,
            "checkpoints": 0,
            "optimizer_states": 0,
        },
    }


def finalize(
    data_root: Path,
    run_id: str,
    reconciliation: Mapping[str, Any],
    reconciliation_sha: str,
    run_identity_path: Path,
) -> Mapping[str, Any]:
    started = monotonic()
    final_root = data_root / "final" / DATASET_ID
    building = data_root / "temp" / f"{DATASET_ID}.building"
    if final_root.exists() or building.exists():
        raise ReconciliationError("final or building VALIDATION namespace already exists")
    for subdir in ("shards", "indexes", "transactions/validation", "audits"):
        (building / subdir).mkdir(parents=True, exist_ok=True)

    descriptors = {item["decision_event_id"]: item for item in reconciliation["transaction_descriptors"]}
    source_root = data_root / "staging" / f"{STUDY}-{SPLIT}-recoverability" / "recoverability"
    shard_writer = _ShardWriter(building / "shards", SPLIT)
    row_index = []
    transaction_index = []
    for source_path in sorted(source_root.glob("event-*.json")):
        document = json.loads(source_path.read_text(encoding="ascii"))
        event_id = str(document["decision_event_id"])
        destination = building / "transactions/validation" / source_path.name
        os.link(source_path, destination)
        transaction_index.append({
            **descriptors[event_id],
            "path": f"transactions/validation/{source_path.name}",
        })
        for row in sorted(document["rows"], key=lambda item: item["scientific_row_id"]):
            shard, line = shard_writer.write(row)
            row_index.append({
                "scientific_row_id": row["scientific_row_id"],
                "decision_event_id": event_id,
                "shard": f"shards/{shard}",
                "line": line,
            })
    shard_writer.close()
    row_index_path = building / "indexes/validation-recoverability-row-index.jsonl"
    row_count, row_index_sha = _write_jsonl(row_index_path, row_index)
    tx_index_path = building / "indexes/validation-recoverability-transaction-index.jsonl"
    tx_count, tx_index_sha = _write_jsonl(tx_index_path, transaction_index)

    quality_sha = _atomic_json(
        building / "audits/recoverability_validation_quality_audit.json",
        {
            "schema_version": "rvt-phase9g-a1v-validation-quality-audit/v1",
            "run_id": run_id,
            "class_weighting": "NOT_SELECTED",
            "descriptive_only": True,
            "scientific_rows": reconciliation["observed"]["scientific_rows"],
            "aggregate_dispositions": {
                key: reconciliation["observed"].get(f"{key}_aggregates", 0)
                for key in ("RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE", "GENERATION_INVALID")
            },
            "candidate_pair_retained_events": reconciliation["observed"]["candidate_pair_retained_events"],
            "candidate_pair_dropped_events": reconciliation["observed"]["candidate_pair_dropped_events"],
            "aggregate_distribution": reconciliation["aggregate_distribution"],
            "candidate_pair_distribution": reconciliation["candidate_pair_distribution"],
            "invalid_reason_distribution": reconciliation["invalid_reason_distribution"],
            "s3": reconciliation["s3"],
        },
        "phase9g_a1v_recoverability_validation_quality_audit_sha256",
    )
    source_reconciliation = data_root / "audit" / run_id / "validation_reconciliation.json"
    (building / "audits/validation_reconciliation.json").write_bytes(
        source_reconciliation.read_bytes()
    )
    run_identity, run_identity_sha = _canonical(
        run_identity_path, "phase9g_a1v_validation_run_identity_sha256"
    )
    manifest_sha = _atomic_json(
        building / "dataset_manifest.json",
        {
            "schema_version": "rvt-phase9g-a1v-validation-dataset-manifest/v1",
            "status": "VALID_FROZEN_VALIDATION_ONLY",
            "dataset_id": DATASET_ID,
            "scientific_dataset_lineage_id": run_identity["scientific_dataset_lineage_id"],
            "study": STUDY,
            "splits": [SPLIT],
            "train_included": False,
            "label_branch": "recoverability",
            "run_id": run_id,
            "parent_run_id": run_identity["parent_run_id"],
            "scientific_source_commit": SOURCE_COMMIT,
            "production_image": IMAGE,
            "generation_provenance_root": PROVENANCE,
            "run_identity_sha256": run_identity_sha,
            "job_manifest_sha256": JOB_MANIFEST_SHA256,
            "scientific_row_count": reconciliation["observed"]["scientific_rows"],
            "audit_sidecar_count": reconciliation["observed"]["decision_events"],
            "transaction_count": reconciliation["observed"]["decision_events"],
            "shards": shard_writer.descriptors,
            "row_indexes": [{
                "path": "indexes/validation-recoverability-row-index.jsonl",
                "entry_count": row_count,
                "content_sha256": row_index_sha,
            }],
            "transaction_indexes": [{
                "path": "indexes/validation-recoverability-transaction-index.jsonl",
                "entry_count": tx_count,
                "content_sha256": tx_index_sha,
            }],
            "audit_hashes": {"reconciliation": reconciliation_sha, "quality": quality_sha},
            "train_reference": {"manifest_sha256": TRAIN_MANIFEST, "seal_sha256": TRAIN_SEAL},
            "physical_namespace_separate_from_train": True,
            "mutable_indexes_shared_with_train": False,
            "integrity": {
                "unresolved_infrastructure_failures": 0,
                "unexpected_duplicates": 0,
                "duplicate_scientific_identities": 0,
                "partial_candidate_pair_publications": 0,
                "schema_failures": 0,
                "hash_failures": 0,
                "seed_mismatches": 0,
                "seal_violations": 0,
            },
            "sealed_domains": reconciliation["sealed_domains"],
            "class_weighting": "NOT_SELECTED",
            "completion_state": "COMPLETE",
        },
        "dataset_manifest_sha256",
    )
    seal_sha = _atomic_json(
        building / "DATASET_SEAL.json",
        {
            "schema_version": "rvt-phase9g-a1v-validation-dataset-seal/v1",
            "dataset_manifest_sha256": manifest_sha,
            "sealed_at_utc": _timestamp(),
            "further_staging_writes_permitted": False,
            "recoverability_train_mutation_permitted": False,
            "residual_v2_authorized": False,
            "training_authorized": False,
        },
        "dataset_seal_sha256",
    )
    final_root.parent.mkdir(parents=True, exist_ok=True)
    os.replace(building, final_root)
    staging = data_root / "staging" / f"{STUDY}-{SPLIT}-recoverability"
    for path in staging.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    for path in sorted((path for path in staging.rglob("*") if path.is_dir()), reverse=True):
        path.chmod(0o555)
    staging.chmod(0o555)
    return {
        "schema_version": "rvt-phase9g-a1v-validation-finalization/v1",
        "status": "FINALIZED",
        "run_id": run_id,
        "dataset_path": str(final_root),
        "dataset_manifest_sha256": manifest_sha,
        "dataset_seal_sha256": seal_sha,
        "scientific_row_count": reconciliation["observed"]["scientific_rows"],
        "audit_sidecar_count": reconciliation["observed"]["decision_events"],
        "shard_count": len(shard_writer.descriptors),
        "index_count": 2,
        "finalization_wall_seconds": monotonic() - started,
        "dataset_storage_bytes": sum(path.stat().st_size for path in final_root.rglob("*") if path.is_file()),
        "staging_sealed_read_only": True,
        "train_namespace_modified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-manifest", type=Path, required=True)
    parser.add_argument("--s3-prestart-guard", type=Path, required=True)
    parser.add_argument("--run-identity", type=Path, required=True)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    audit_root = data_root / "audit" / args.run_id
    reconciliation = reconcile(
        args.root.resolve(), data_root, args.run_id, args.task_manifest, args.s3_prestart_guard
    )
    reconciliation_sha = _atomic_json(
        audit_root / "validation_reconciliation.json",
        reconciliation,
        "phase9g_a1v_validation_reconciliation_sha256",
    )
    output = {
        "status": "RECONCILED",
        "reconciliation_sha256": reconciliation_sha,
        "events": reconciliation["observed"]["decision_events"],
        "rows": reconciliation["observed"]["scientific_rows"],
    }
    if args.finalize:
        finalization = finalize(
            data_root, args.run_id, reconciliation, reconciliation_sha, args.run_identity
        )
        finalization_sha = _atomic_json(
            audit_root / "validation_finalization.json",
            finalization,
            "phase9g_a1v_validation_finalization_sha256",
        )
        output.update({
            "finalization_status": finalization["status"],
            "dataset_manifest_sha256": finalization["dataset_manifest_sha256"],
            "dataset_seal_sha256": finalization["dataset_seal_sha256"],
            "finalization_sha256": finalization_sha,
        })
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
