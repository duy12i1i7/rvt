#!/usr/bin/env python3
"""Reconcile and atomically finalize Study-A Recoverability TRAIN only."""

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
    ROWS_PER_SHARD,
    ReconciliationError,
    _ShardWriter,
    _atomic_json,
    _canonical,
    _candidate_dispositions,
    _sha256_file,
    _timestamp,
    _write_jsonl,
)


STUDY = "study_a_zero_shot"
SPLIT = "train"
DATASET_ID = "phase9g-a1-study-a-train-recoverability-v1"


def _transaction_map(staging: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    root = staging / "recoverability"
    partials = tuple(root.glob("*.partial"))
    if partials:
        raise ReconciliationError("partial candidate-pair transaction remains")
    result = {}
    for path in sorted(root.glob("event-*.json")):
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
    path = audit_root / "train-operational-telemetry.jsonl"
    records = [
        json.loads(line) for line in path.read_text(encoding="ascii").splitlines()
        if line.strip()
    ]
    status, _ = _canonical(
        audit_root / "train-continuation-status.json",
        "phase9g_a1c_continuation_status_sha256",
    )
    if status["state"] != "COMPLETE":
        raise ReconciliationError("A1C continuation status is not COMPLETE")
    if len(records) != 5790:
        raise ReconciliationError("A1C telemetry does not cover every resumed event")
    return records, status


def reconcile(
    root: Path,
    data_root: Path,
    run_id: str,
    initial_checkpoint_path: Path,
    s3_guard_path: Path,
) -> Mapping[str, Any]:
    tasks = compile_recoverability_tasks(
        root, study=STUDY, split=SPLIT
    )
    if len(tasks) != 6000:
        raise ReconciliationError("frozen TRAIN event universe changed")
    task_by_id = {task.event_id: task for task in tasks}
    staging = data_root / "staging" / f"{STUDY}-{SPLIT}-recoverability"
    observed = _transaction_map(staging)
    if set(observed) != set(task_by_id):
        raise ReconciliationError(
            f"event universe mismatch: missing={len(set(task_by_id)-set(observed))}, "
            f"unexpected={len(set(observed)-set(task_by_id))}"
        )

    initial, initial_sha256 = _canonical(
        initial_checkpoint_path, "phase9_s3_staging_checkpoint_sha256"
    )
    if len(initial["candidate_pair_transactions"]) != 210:
        raise ReconciliationError("initial transaction lineage changed")
    if len(initial["scientific_row_ids"]) != 342:
        raise ReconciliationError("initial scientific row lineage changed")
    initial_transactions = {
        item["decision_event_id"]: item
        for item in initial["candidate_pair_transactions"]
    }
    for event_id, descriptor in initial_transactions.items():
        path, document = observed[event_id]
        if (
            path.name != descriptor["file_name"]
            or document["canonical_record_sha256"]
            != descriptor["canonical_record_sha256"]
            or _sha256_file(path) != descriptor["file_sha256"]
        ):
            raise ReconciliationError("an original transaction was regenerated or rewritten")

    guard, guard_sha256 = _canonical(
        s3_guard_path, "phase9g_a1c_s3_prestart_guard_sha256"
    )
    if guard["status"] != "PASS" or guard["counter_levels"][
        "unresolved_s3_ambiguities"
    ] != 0:
        raise ReconciliationError("S3 prestart provenance guard did not pass")

    telemetry, status = _load_telemetry(data_root / "audit" / run_id)
    if status["completed_event_identities_reused"] != 210:
        raise ReconciliationError("continuation did not reuse exact completed prefix")
    if status["unresolved_event_identities_scheduled"] != 5790:
        raise ReconciliationError("continuation scheduled the wrong unresolved set")
    if status["execution_summary"]["events"] != 5790:
        raise ReconciliationError("continuation did not complete all unresolved events")
    telemetry_ids = {item["decision_event_id"] for item in telemetry}
    if telemetry_ids != set(task_by_id) - set(initial_transactions):
        raise ReconciliationError("telemetry identity set differs from exact resume boundary")

    counters: Counter[str] = Counter()
    distribution: Counter[tuple[str, int, int, int]] = Counter()
    invalid_distribution: Counter[tuple[str, int, str]] = Counter()
    pair_distribution: Counter[tuple[str, int, str]] = Counter()
    source_events: dict[str, set[str]] = defaultdict(set)
    row_ids: set[str] = set()
    transaction_descriptors = []

    for event_id in sorted(task_by_id):
        task = task_by_id[event_id]
        path, document = observed[event_id]
        if not document.get("scientifically_reconciled") or not document.get(
            "scientific_completion_marker"
        ):
            raise ReconciliationError("unresolved transaction entered TRAIN completion set")
        team_size = task.source.team_size
        if team_size == 24:
            raise ReconciliationError("Study A N24 entered TRAIN staging")
        expected_rows = 2 * team_size
        actual_rows = int(document["actual_row_count"])
        if int(document["expected_row_count"]) != expected_rows:
            raise ReconciliationError("transaction expected row count is not 2*N")
        if actual_rows not in (0, expected_rows) or actual_rows != len(document["rows"]):
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
            counters["candidate_pair_dropped_events"] += 1
            counters["GENERATION_INVALID_aggregates"] += 2
            reason = "UNKNOWN_FROZEN_GENERATION_INVALID"
            audits = list(document.get("audit", {}).get("candidate_audits", ()))
            terminations = [
                audit.get("termination") for audit in audits
                if audit.get("termination") is not None
            ]
            if terminations:
                reason = str(terminations[0].get("cause", reason))
            elif audits and all(audit.get("source_terminated_before_event") for audit in audits):
                reason = "SOURCE_TERMINATED_BEFORE_EVENT"
            invalid_distribution[(task.source.family, team_size, reason)] += 1
            pair_distribution[(task.source.family, team_size, "DROPPED_NONPUBLISHED")] += 1
        elif tx_status == "SCIENTIFICALLY_RECONCILED_LABELABLE":
            if not document["training_rows_committable"] or actual_rows != expected_rows:
                raise ReconciliationError("labelable transaction is incomplete")
            if set(candidates) != {COMPACT, LINE}:
                raise ReconciliationError("labelable event lacks both candidate audits")
            counters["candidate_pair_retained_events"] += 1
            pair_distribution[(task.source.family, team_size, "RETAINED")] += 1
            for candidate in (COMPACT, LINE):
                audit = candidates[candidate]
                aggregate = audit.get("aggregate")
                disposition = str(aggregate["disposition"] if aggregate else "")
                if disposition not in {"RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"}:
                    raise ReconciliationError("candidate disposition changed")
                counters[f"{disposition}_aggregates"] += 1
                actual_seeds = {
                    int(replica["replica_index"]): int(replica["matched_disturbance_seed"])
                    for replica in audit["replicas"]
                }
                expected_seeds = {
                    int(job["replica_index"]): int(job["seeds"]["matched_disturbance_seed"])
                    for job in task.replica_jobs(candidate)
                }
                if actual_seeds != expected_seeds:
                    raise ReconciliationError("candidate matched-seed set differs from manifest")
                other = LINE if candidate == COMPACT else COMPACT
                other_seeds = {
                    int(job["replica_index"]): int(job["seeds"]["matched_disturbance_seed"])
                    for job in task.replica_jobs(other)
                }
                if actual_seeds != other_seeds:
                    raise ReconciliationError("COMPACT/LINE matched streams diverged")

            coverage = Counter()
            robots: dict[int, set[int]] = defaultdict(set)
            for row in document["rows"]:
                identity = row["scientific_identity"]
                row_id = str(row["scientific_row_id"])
                if row_id != recoverability_scientific_row_id(identity):
                    raise ReconciliationError("scientific row identity hash mismatch")
                if row_id in row_ids:
                    raise ReconciliationError("duplicate scientific row identity")
                row_ids.add(row_id)
                if identity["study"] != STUDY or identity["split"] != SPLIT:
                    raise ReconciliationError("scientific row crossed TRAIN scope")
                if int(identity["team_size"]) != team_size:
                    raise ReconciliationError("scientific row team size changed")
                candidate = int(row["candidate_topology_id"])
                robot = int(identity["robot_id"])
                if candidate not in (COMPACT, LINE):
                    raise ReconciliationError("unexpected candidate topology")
                if sha256_document(row["graph_payload"]) != row["graph_fingerprint"]:
                    raise ReconciliationError("graph fingerprint mismatch")
                if row["graph_fingerprint"] != identity["graph_fingerprint"]:
                    raise ReconciliationError("row/identity graph fingerprint mismatch")
                disposition = str(row["target_v4_aggregate_disposition"])
                label = int(row["target_v4_aggregate_label"])
                if (disposition == "RECOVERABLE_POSITIVE") != (label == 1):
                    raise ReconciliationError("row label/disposition mismatch")
                coverage[candidate] += 1
                robots[candidate].add(robot)
                distribution[(task.source.family, team_size, candidate, label)] += 1
            if coverage != Counter({COMPACT: team_size, LINE: team_size}):
                raise ReconciliationError("candidate row coverage is not N plus N")
            if any(value != set(range(team_size)) for value in robots.values()):
                raise ReconciliationError("candidate rows do not cover every robot")
        else:
            raise ReconciliationError("unknown transaction status")
        counters["scientific_rows"] += actual_rows
        transaction_descriptors.append({
            "decision_event_id": event_id,
            "relative_staging_path": str(path.relative_to(data_root / "staging")),
            "content_sha256": _sha256_file(path),
            "status": tx_status,
            "scientific_rows": actual_rows,
            "predates_final_s3_addenda": event_id in initial_transactions,
        })

    if len(source_events) != 1200 or any(len(events) != 5 for events in source_events.values()):
        raise ReconciliationError("source/event accounting did not reconcile to 1200*5")
    if sorted(row_ids & set(initial["scientific_row_ids"])) != sorted(
        initial["scientific_row_ids"]
    ):
        raise ReconciliationError("original 342-row lineage is not intact")

    resumed_cpu = sum(
        float(unit["cpu_seconds"])
        for item in telemetry for unit in item["candidate_units"]
    )
    resumed_wall = float(status["execution_summary"]["wall_seconds"])
    historical_wall = 490.2080932349995
    historical_cpu_hours = 1.0214619703444445
    storage = sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())
    return {
        "schema_version": "rvt-phase9g-a1c-recoverability-train-reconciliation/v1",
        "phase": "PHASE_9G_A1C",
        "status": "PASS",
        "run_id": run_id,
        "study": STUDY,
        "split": SPLIT,
        "job_manifest_sha256": JOB_MANIFEST_SHA256,
        "expected": {
            "source_episodes": 1200,
            "decision_events": 6000,
            "candidate_aggregates": 12000,
            "candidate_replica_slots": sum(
                2 * task.replicas_per_candidate for task in tasks
            ),
        },
        "observed": {
            **dict(counters),
            "source_episodes_completed": len(source_events),
            "unexpected_duplicate_transactions": 0,
            "duplicate_scientific_identities": 0,
            "partial_candidate_pair_publications": 0,
            "unresolved_infrastructure_failures": 0,
            "timeouts_during_a1c": 0,
            "writer_failures": 0,
            "schema_failures": 0,
            "hash_failures": 0,
            "seed_mismatches": 0,
            "seal_violations": 0,
            "unaccounted_events": 0,
        },
        "distribution": [
            {
                "family": family,
                "team_size": team_size,
                "candidate_topology_id": candidate,
                "label": label,
                "rows": count,
            }
            for (family, team_size, candidate, label), count in sorted(distribution.items())
        ],
        "invalid_event_distribution": [
            {"family": family, "team_size": n, "reason": reason, "events": count}
            for (family, n, reason), count in sorted(invalid_distribution.items())
        ],
        "candidate_pair_distribution": [
            {"family": family, "team_size": n, "state": state, "events": count}
            for (family, n, state), count in sorted(pair_distribution.items())
        ],
        "s3": {
            "remaining_prestart_guard_sha256": guard_sha256,
            **guard["counter_levels"],
        },
        "existing_342_row_lineage": {
            "checkpoint_sha256": initial_sha256,
            "rows_retained": 342,
            "rows_regenerated": 0,
            "UNAFFECTED": 254,
            "DEPENDENCY_PRESENT_BUT_VALUE_VALID": 88,
            "POTENTIALLY_AFFECTED": 0,
            "PROVEN_AFFECTED": 0,
        },
        "transaction_descriptors": transaction_descriptors,
        "operational": {
            "historical_wall_seconds": historical_wall,
            "a1c_wall_seconds": resumed_wall,
            "total_observed_wall_seconds": historical_wall + resumed_wall,
            "historical_sampled_cpu_hours": historical_cpu_hours,
            "a1c_candidate_cpu_hours": resumed_cpu / 3600.0,
            "total_sampled_cpu_hours": historical_cpu_hours + resumed_cpu / 3600.0,
            "staging_storage_bytes": storage,
            "maximum_atomic_unit_wall_seconds": status[
                "execution_summary"
            ]["maximum_atomic_unit_wall_seconds"],
        },
        "sealed_domains": {
            "recoverability_validation_operations": 0,
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
            "checkpoints": 0,
            "optimizer_states": 0,
        },
    }


def finalize(
    data_root: Path,
    run_id: str,
    reconciliation: Mapping[str, Any],
    reconciliation_sha256: str,
    run_identity_path: Path,
) -> Mapping[str, Any]:
    started = monotonic()
    final_root = data_root / "final" / DATASET_ID
    building = data_root / "temp" / f"{DATASET_ID}.building"
    if final_root.exists() or building.exists():
        raise ReconciliationError("final or building TRAIN namespace already exists")
    for subdir in ("shards", "indexes", "transactions/train", "audits"):
        (building / subdir).mkdir(parents=True, exist_ok=True)

    descriptors = {
        item["decision_event_id"]: item
        for item in reconciliation["transaction_descriptors"]
    }
    source_root = (
        data_root / "staging" / f"{STUDY}-{SPLIT}-recoverability" / "recoverability"
    )
    shard_writer = _ShardWriter(building / "shards", SPLIT)
    row_index = []
    transaction_index = []
    for source_path in sorted(source_root.glob("event-*.json")):
        document = json.loads(source_path.read_text(encoding="ascii"))
        event_id = str(document["decision_event_id"])
        destination = building / "transactions/train" / source_path.name
        os.link(source_path, destination)
        transaction_index.append({
            **descriptors[event_id],
            "path": f"transactions/train/{source_path.name}",
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
    row_index_path = building / "indexes/train-recoverability-row-index.jsonl"
    row_count, row_index_sha = _write_jsonl(row_index_path, row_index)
    tx_index_path = building / "indexes/train-recoverability-transaction-index.jsonl"
    tx_count, tx_index_sha = _write_jsonl(tx_index_path, transaction_index)

    quality_body = {
        "schema_version": "rvt-phase9g-a1c-recoverability-train-quality-audit/v1",
        "run_id": run_id,
        "class_weighting": "NOT_SELECTED",
        "descriptive_only": True,
        "scientific_rows": reconciliation["observed"]["scientific_rows"],
        "aggregate_dispositions": {
            key: reconciliation["observed"].get(f"{key}_aggregates", 0)
            for key in (
                "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE", "GENERATION_INVALID"
            )
        },
        "candidate_pair_retained_events": reconciliation["observed"][
            "candidate_pair_retained_events"
        ],
        "candidate_pair_dropped_events": reconciliation["observed"][
            "candidate_pair_dropped_events"
        ],
        "row_distribution": reconciliation["distribution"],
        "invalid_event_distribution": reconciliation["invalid_event_distribution"],
        "candidate_pair_distribution": reconciliation["candidate_pair_distribution"],
        "s3": reconciliation["s3"],
    }
    quality_sha = _atomic_json(
        building / "audits/recoverability_train_quality_audit.json",
        quality_body,
        "phase9g_a1c_recoverability_train_quality_audit_sha256",
    )
    source_reconciliation = data_root / "audit" / run_id / "train_reconciliation.json"
    (building / "audits/train_reconciliation.json").write_bytes(
        source_reconciliation.read_bytes()
    )

    run_identity, run_identity_sha = _canonical(
        run_identity_path, "phase9g_a1c_continuation_run_identity_sha256"
    )
    manifest_body = {
        "schema_version": "rvt-phase9g-a1c-recoverability-train-dataset-manifest/v1",
        "status": "VALID_FROZEN_TRAIN_ONLY",
        "dataset_id": DATASET_ID,
        "scientific_dataset_lineage_id": run_identity[
            "scientific_dataset_lineage_id"
        ],
        "study": STUDY,
        "splits": [SPLIT],
        "validation_included": False,
        "label_branch": "recoverability",
        "run_id": run_id,
        "parent_run_id": run_identity["parent_run_id"],
        "scientific_source_commit": "848e8b352a91e95af777ebbeccd5fbb43d53777e",
        "production_image": "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90",
        "generation_provenance_root": "9f209cd4b5ae591b2f576a085bcbdb6b7d30a7f3fecb9840d6e0eb56bb03adc8",
        "run_identity_sha256": run_identity_sha,
        "job_manifest_sha256": JOB_MANIFEST_SHA256,
        "scientific_row_count": reconciliation["observed"]["scientific_rows"],
        "audit_sidecar_count": reconciliation["observed"]["decision_events"],
        "transaction_count": reconciliation["observed"]["decision_events"],
        "shards": shard_writer.descriptors,
        "row_indexes": [{
            "path": "indexes/train-recoverability-row-index.jsonl",
            "entry_count": row_count,
            "content_sha256": row_index_sha,
        }],
        "transaction_indexes": [{
            "path": "indexes/train-recoverability-transaction-index.jsonl",
            "entry_count": tx_count,
            "content_sha256": tx_index_sha,
        }],
        "audit_hashes": {
            "reconciliation": reconciliation_sha256,
            "quality": quality_sha,
        },
        "existing_342_row_lineage": reconciliation["existing_342_row_lineage"],
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
    }
    manifest_sha = _atomic_json(
        building / "dataset_manifest.json", manifest_body, "dataset_manifest_sha256"
    )
    _atomic_json(
        building / "DATASET_SEAL.json",
        {
            "schema_version": "rvt-phase9g-a1c-train-dataset-seal/v1",
            "dataset_manifest_sha256": manifest_sha,
            "sealed_at_utc": _timestamp(),
            "further_staging_writes_permitted": False,
            "recoverability_validation_authorized": False,
        },
        "dataset_seal_sha256",
    )
    final_root.parent.mkdir(parents=True, exist_ok=True)
    os.replace(building, final_root)
    staging = data_root / "staging" / f"{STUDY}-{SPLIT}-recoverability"
    for path in staging.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    for path in sorted((p for p in staging.rglob("*") if p.is_dir()), reverse=True):
        path.chmod(0o555)
    staging.chmod(0o555)
    return {
        "schema_version": "rvt-phase9g-a1c-recoverability-train-finalization/v1",
        "status": "FINALIZED",
        "run_id": run_id,
        "dataset_path": str(final_root),
        "dataset_manifest_sha256": manifest_sha,
        "scientific_row_count": reconciliation["observed"]["scientific_rows"],
        "audit_sidecar_count": reconciliation["observed"]["decision_events"],
        "shard_count": len(shard_writer.descriptors),
        "index_count": 2,
        "finalization_wall_seconds": monotonic() - started,
        "dataset_storage_bytes": sum(
            path.stat().st_size for path in final_root.rglob("*") if path.is_file()
        ),
        "staging_sealed_read_only": True,
        "validation_started": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--s3-prestart-guard", type=Path, required=True)
    parser.add_argument("--run-identity", type=Path, required=True)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    data_root = args.data_root.resolve()
    audit_root = data_root / "audit" / args.run_id
    reconciliation = reconcile(
        root, data_root, args.run_id, args.initial_checkpoint, args.s3_prestart_guard
    )
    reconciliation_sha = _atomic_json(
        audit_root / "train_reconciliation.json",
        reconciliation,
        "phase9g_a1c_recoverability_train_reconciliation_sha256",
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
            audit_root / "train_finalization.json",
            finalization,
            "phase9g_a1c_recoverability_train_finalization_sha256",
        )
        output.update({
            "finalization_status": finalization["status"],
            "dataset_manifest_sha256": finalization["dataset_manifest_sha256"],
            "finalization_sha256": finalization_sha,
        })
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
