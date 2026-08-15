#!/usr/bin/env python3
"""Bind official A1V execution telemetry, final datasets, and stop state."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Any

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


RUN_ID = "phase9g-a1v-study-a-validation-recoverability-20260815T163005Z"
IMAGE = "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
AUTHORITY_COMMIT = "b5e5de5"
TRAIN_MANIFEST = "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
TRAIN_SEAL = "5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5"


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(path: Path, field: str) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path}")
    return document


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--running-phase9-containers", type=int, required=True)
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    audit = data_root / "audit" / args.run_id
    train = data_root / "final/phase9g-a1-study-a-train-recoverability-v1"
    validation = data_root / "final/phase9g-a1-study-a-validation-recoverability-v1"
    combined = data_root / "final/phase9g-a1-study-a-recoverability-train-validation-root-v1"
    validation_staging = data_root / "staging/study_a_zero_shot-validation-recoverability"

    status = _canonical(audit / "validation-status.json", "phase9g_a1v_validation_status_sha256")
    reconciliation = _canonical(audit / "validation_reconciliation.json", "phase9g_a1v_validation_reconciliation_sha256")
    finalization = _canonical(audit / "validation_finalization.json", "phase9g_a1v_validation_finalization_sha256")
    postfinal = _canonical(audit / "postfinal_dataset_validation.json", "phase9g_a1v_postfinal_dataset_validation_sha256")
    combined_validation = _canonical(audit / "combined_root_validation.json", "phase9g_a1v_combined_root_validation_sha256")
    train_manifest = _canonical(train / "dataset_manifest.json", "dataset_manifest_sha256")
    train_seal = _canonical(train / "DATASET_SEAL.json", "dataset_seal_sha256")
    validation_manifest = _canonical(validation / "dataset_manifest.json", "dataset_manifest_sha256")
    validation_seal = _canonical(validation / "DATASET_SEAL.json", "dataset_seal_sha256")
    combined_manifest = _canonical(combined / "dataset_root_manifest.json", "combined_recoverability_dataset_root_sha256")
    combined_seal = _canonical(combined / "DATASET_ROOT_SEAL.json", "combined_recoverability_dataset_root_seal_sha256")
    inspect = json.loads((audit / "official-validation-container-inspect.json").read_text(encoding="ascii"))[0]
    telemetry_path = audit / "validation-operational-telemetry.jsonl"
    telemetry = [json.loads(line) for line in telemetry_path.read_text(encoding="ascii").splitlines() if line.strip()]
    candidate_walls = [float(unit["wall_seconds"]) for event in telemetry for unit in event["candidate_units"]]
    candidate_cpu = [float(unit["cpu_seconds"]) for event in telemetry for unit in event["candidate_units"]]
    writer_walls = [float(event["candidate_pair_reconciliation_wall_seconds"]) for event in telemetry]

    observed = reconciliation["observed"]
    if (
        status["state"] != "COMPLETE"
        or status["execution_summary"]["events"] != 1500
        or len(telemetry) != 1500
        or observed["decision_events"] != 1500
        or observed["candidate_aggregates"] != 3000
        or observed["scientific_rows"] != 2294
        or finalization["status"] != "FINALIZED"
        or postfinal["status"] != "PASS"
        or combined_validation["status"] != "PASS"
        or train_manifest["dataset_manifest_sha256"] != TRAIN_MANIFEST
        or train_seal["dataset_seal_sha256"] != TRAIN_SEAL
        or inspect["State"]["ExitCode"] != 0
        or inspect["Image"] != IMAGE
        or inspect["HostConfig"]["NetworkMode"] != "none"
        or inspect["HostConfig"]["ReadonlyRootfs"] is not True
        or inspect["HostConfig"]["NanoCpus"] != 12_000_000_000
        or args.running_phase9_containers != 0
    ):
        raise ValueError("official completion state differs from A1V contract")
    integrity_fields = (
        "unexpected_duplicate_transactions", "duplicate_scientific_identities",
        "partial_candidate_pair_publications", "unresolved_infrastructure_failures",
        "infrastructure_timeouts", "writer_failures", "schema_failures",
        "hash_failures", "seed_mismatches", "seal_violations", "unaccounted_events",
    )
    if any(observed[field] for field in integrity_fields):
        raise ValueError("official reconciliation reports an integrity failure")
    writable_validation_files = sum(
        bool(path.stat().st_mode & 0o222)
        for path in validation_staging.rglob("*") if path.is_file()
    )
    if writable_validation_files or (validation_staging.stat().st_mode & 0o777) != 0o555:
        raise ValueError("VALIDATION STAGING is not sealed read-only")

    report = {
        "schema_version": "rvt-phase9g-a1v-official-completion-audit/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS_COMPLETE_STOPPED",
        "run_id": args.run_id,
        "authority_commit": AUTHORITY_COMMIT,
        "container": {
            "image": inspect["Image"],
            "exit_code": inspect["State"]["ExitCode"],
            "network_mode": inspect["HostConfig"]["NetworkMode"],
            "read_only_root_filesystem": inspect["HostConfig"]["ReadonlyRootfs"],
            "nano_cpus": inspect["HostConfig"]["NanoCpus"],
            "running_phase9_containers_at_closure": args.running_phase9_containers,
            "inspect_file_sha256": _file_sha(audit / "official-validation-container-inspect.json"),
        },
        "profile": {
            "workers": 12,
            "numeric_threads_per_worker": 1,
            "chunk_size_atomic_units": 1,
            "infrastructure_timeout_seconds": 243,
        },
        "scientific_accounting": {
            "source_episodes": observed["source_episodes_completed"],
            "decision_events": observed["decision_events"],
            "candidate_aggregates": observed["candidate_aggregates"],
            "replica_executions": observed["replica_executions"],
            "RECOVERABLE_POSITIVE": observed["RECOVERABLE_POSITIVE_aggregates"],
            "VALID_TASK_NEGATIVE": observed["VALID_TASK_NEGATIVE_aggregates"],
            "GENERATION_INVALID": observed["GENERATION_INVALID_aggregates"],
            "candidate_pair_retained_events": observed["candidate_pair_retained_events"],
            "candidate_pair_dropped_events": observed["candidate_pair_dropped_events"],
            "scientific_rows": observed["scientific_rows"],
        },
        "infrastructure_accounting": {
            "timeouts": observed["infrastructure_timeouts"],
            "retries": observed["infrastructure_retries"],
            "failure_attempts": observed["infrastructure_failure_attempts"],
            "writer_failures": observed["writer_failures"],
            "duplicates": observed["unexpected_duplicate_transactions"],
            "partial_publications": observed["partial_candidate_pair_publications"],
            "unresolved_failures": observed["unresolved_infrastructure_failures"],
        },
        "telemetry": {
            "target_path": f"/rvt-data/audit/{args.run_id}/validation-operational-telemetry.jsonl",
            "records": len(telemetry),
            "file_size_bytes": telemetry_path.stat().st_size,
            "file_sha256": _file_sha(telemetry_path),
            "candidate_atomic_units": len(candidate_walls),
            "candidate_wall_seconds": {
                "median": median(candidate_walls),
                "p90": _percentile(candidate_walls, 0.90),
                "p95": _percentile(candidate_walls, 0.95),
                "max": max(candidate_walls),
            },
            "writer_wall_seconds": {
                "median": median(writer_walls),
                "p90": _percentile(writer_walls, 0.90),
                "p95": _percentile(writer_walls, 0.95),
                "max": max(writer_walls),
            },
            "candidate_cpu_hours": sum(candidate_cpu) / 3600.0,
            "official_wall_seconds": status["execution_summary"]["wall_seconds"],
        },
        "dataset": {
            "manifest_sha256": validation_manifest["dataset_manifest_sha256"],
            "seal_sha256": validation_seal["dataset_seal_sha256"],
            "reconciliation_sha256": reconciliation["phase9g_a1v_validation_reconciliation_sha256"],
            "finalization_sha256": finalization["phase9g_a1v_validation_finalization_sha256"],
            "postfinal_validation_sha256": postfinal["phase9g_a1v_postfinal_dataset_validation_sha256"],
            "storage_bytes": postfinal["dataset_storage_bytes"],
            "staging_mode_octal": oct(validation_staging.stat().st_mode & 0o777),
            "staging_writable_files": writable_validation_files,
        },
        "combined_root": {
            "manifest_sha256": combined_manifest["combined_recoverability_dataset_root_sha256"],
            "seal_sha256": combined_seal["combined_recoverability_dataset_root_seal_sha256"],
            "validation_sha256": combined_validation["phase9g_a1v_combined_root_validation_sha256"],
        },
        "train_immutable": {
            "manifest_sha256": train_manifest["dataset_manifest_sha256"],
            "seal_sha256": train_seal["dataset_seal_sha256"],
            "modified": False,
        },
        "integrity": {field: observed[field] for field in integrity_fields},
        "downstream": {
            "residual_v2_started": False,
            "training_operations": 0,
            "hyperparameter_trials": 0,
            "model_checkpoints": 0,
            "optimizer_states": 0,
        },
        "sealed_domains": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
        },
    }
    report = attach_canonical_hash(report, "phase9g_a1v_official_completion_audit_sha256")
    output = audit / "official_completion_audit.json"
    output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": report["status"],
        "hash": report["phase9g_a1v_official_completion_audit_sha256"],
        "events": report["scientific_accounting"]["decision_events"],
        "rows": report["scientific_accounting"]["scientific_rows"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
