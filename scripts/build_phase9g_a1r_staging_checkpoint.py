#!/usr/bin/env python3
"""Build a canonical read-only checkpoint of stopped official STAGING."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


STUDY = "study_a_zero_shot"
SPLITS = ("train", "validation")
RUN_ID = "phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
COMPACT = 5
LINE = 2


class StagingCheckpointError(RuntimeError):
    """The stopped official STAGING checkpoint is not internally consistent."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256_document(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_artifact(path: Path, field: str) -> tuple[Mapping[str, Any], str]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or _sha256_document(body) != expected:
        raise StagingCheckpointError(f"canonical artifact mismatch: {path.name}")
    return document, expected


def _load_manifest(root: Path) -> Mapping[str, Any]:
    path = root / "results/rvt_fd24/datasets/phase9_job_manifest.json"
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop("job_manifest_sha256", ""))
    if _sha256_document(body) != expected:
        raise StagingCheckpointError("authoritative job manifest hash mismatch")
    return document


def _write(path: Path, body: Mapping[str, Any]) -> str:
    body = dict(body)
    digest = _sha256_document(body)
    body["phase9g_a1r_staging_checkpoint_sha256"] = digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(body, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    data_root = args.data_root.resolve()
    authorization, authorization_sha256 = _canonical_artifact(
        data_root / "authorization/phase9g_a1_owner_authorization_v1.json",
        "phase9g_a1_owner_authorization_sha256",
    )
    run, run_sha256 = _canonical_artifact(
        data_root / "authorization/phase9g_a1_recoverability_run_identity_v1.json",
        "phase9g_a1_recoverability_run_identity_sha256",
    )
    operational, operational_sha256 = _canonical_artifact(
        data_root / "authorization/phase9g0p_operational_production_contract_v2.json",
        "phase9g0p_operational_contract_sha256",
    )
    stop, stop_sha256 = _canonical_artifact(
        data_root / "audit" / RUN_ID / "operational_stop.json",
        "phase9g_a1_operational_stop_sha256",
    )
    if run["run_id"] != RUN_ID or stop["run_identity"]["run_id"] != RUN_ID:
        raise StagingCheckpointError("official run identity changed")
    if run["authorization"]["sha256"] != authorization_sha256:
        raise StagingCheckpointError("run authorization binding changed")
    if run["operational_profile"]["sha256"] != operational_sha256:
        raise StagingCheckpointError("run operational contract binding changed")
    if run["production_image"] != stop["production_image"]:
        raise StagingCheckpointError("production image binding changed")
    if run["scientific_source_commit"] != stop["scientific_source_commit"]:
        raise StagingCheckpointError("scientific source binding changed")

    manifest = _load_manifest(root)
    source_jobs = {
        str(job["job_id"]): job
        for job in manifest["source_episode_jobs"]
        if job.get("study") == STUDY
        and job.get("split") in SPLITS
        and not bool(job.get("sealed"))
    }
    event_jobs = {
        str(job["job_id"]): job
        for job in manifest["decision_event_jobs"]
        if str(job["source_episode_job_id"]) in source_jobs
        and not bool(job.get("sealed"))
    }

    transaction_descriptors = []
    completed_event_ids = []
    completed_atomic_unit_ids = []
    scientific_row_ids = []
    invalid_reasons: Counter[str] = Counter()
    pair_statuses: Counter[str] = Counter()
    row_id_set = set()
    partial_files = []
    staging_bytes = 0
    for split in SPLITS:
        staging_root = data_root / "staging" / f"{STUDY}-{split}-recoverability"
        if staging_root.exists() and os.access(staging_root, os.W_OK):
            raise StagingCheckpointError(f"{split} STAGING is writable during inspection")
        partial_files.extend(str(path) for path in staging_root.rglob("*.partial"))
        transaction_root = staging_root / "recoverability"
        for path in sorted(transaction_root.glob("event-*.json")):
            staging_bytes += path.stat().st_size
            document = json.loads(path.read_text(encoding="ascii"))
            body = dict(document)
            expected_record_hash = str(body.pop("canonical_record_sha256", ""))
            if _sha256_document(body) != expected_record_hash:
                raise StagingCheckpointError(f"transaction hash mismatch: {path.name}")
            event_id = str(document["decision_event_id"])
            if event_id not in event_jobs or event_id in completed_event_ids:
                raise StagingCheckpointError("unexpected or duplicate decision event")
            event = event_jobs[event_id]
            source = source_jobs[str(event["source_episode_job_id"])]
            if source["split"] != split or int(source["team_size"]) == 24:
                raise StagingCheckpointError("transaction crossed a sealed scope")
            expected_rows = 2 * int(source["team_size"])
            actual_rows = int(document["actual_row_count"])
            if actual_rows not in (0, expected_rows) or actual_rows != len(
                document["rows"]
            ):
                raise StagingCheckpointError("partial candidate-pair publication")
            if not bool(document["scientific_completion_marker"]):
                raise StagingCheckpointError("incomplete transaction became durable")
            status = str(document["status"])
            pair_statuses[status] += 1
            if status == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID":
                if actual_rows != 0 or document["training_rows_committable"]:
                    raise StagingCheckpointError("invalid transaction emitted rows")
                if not document["audit"].get("source_terminated_before_event"):
                    raise StagingCheckpointError(
                        "generation-invalid transaction lacks frozen source termination"
                    )
                termination = document["audit"].get("termination")
                if not isinstance(termination, Mapping) or not termination.get("cause"):
                    raise StagingCheckpointError("invalid source termination is unclassified")
                invalid_reasons[f"SOURCE_TERMINATED_BEFORE_EVENT:{termination['cause']}"] += 2
            elif status == "SCIENTIFICALLY_RECONCILED_LABELABLE":
                if actual_rows != expected_rows or not document[
                    "training_rows_committable"
                ]:
                    raise StagingCheckpointError("labelable transaction is incomplete")
            else:
                raise StagingCheckpointError("unresolved transaction is durable")

            for row in document["rows"]:
                row_id = str(row["scientific_row_id"])
                if row_id in row_id_set:
                    raise StagingCheckpointError("duplicate scientific row identity")
                row_id_set.add(row_id)
                if _sha256_document(row["scientific_identity"]) != row_id:
                    raise StagingCheckpointError("scientific row identity hash mismatch")
                if _sha256_document(row["graph_payload"]) != row[
                    "graph_fingerprint"
                ]:
                    raise StagingCheckpointError("graph fingerprint mismatch")
                scientific_row_ids.append(row_id)

            completed_event_ids.append(event_id)
            for candidate in (COMPACT, LINE):
                completed_atomic_unit_ids.append(_sha256_document({
                    "event_id": event_id,
                    "candidate_topology_id": candidate,
                }))
            transaction_descriptors.append({
                "decision_event_id": event_id,
                "split": split,
                "candidate_pair_status": status,
                "scientific_row_count": actual_rows,
                "relative_path": str(path.relative_to(data_root)),
                "file_sha256": _sha256_file(path),
                "canonical_record_sha256": expected_record_hash,
            })

    if partial_files:
        raise StagingCheckpointError("partial writer files remain in STAGING")
    if len(completed_event_ids) != 127 or len(completed_atomic_unit_ids) != 254:
        raise StagingCheckpointError("completed event/atomic-unit count changed")
    if len(scientific_row_ids) != 318:
        raise StagingCheckpointError("scientific row count is not 318")
    if sum(invalid_reasons.values()) != 216:
        raise StagingCheckpointError("generation-invalid aggregate count is not 216")

    completed_event_ids.sort()
    completed_atomic_unit_ids.sort()
    scientific_row_ids.sort()
    transaction_descriptors.sort(key=lambda item: item["decision_event_id"])
    checkpoint_preimage = {
        "run_id": RUN_ID,
        "transaction_descriptors": transaction_descriptors,
        "completed_atomic_unit_ids": completed_atomic_unit_ids,
        "scientific_row_ids": scientific_row_ids,
    }
    report = {
        "schema_version": "rvt-phase9g-a1r-staging-checkpoint/v1",
        "status": "PASS_READ_ONLY",
        "run_id": RUN_ID,
        "source_commit": run["scientific_source_commit"],
        "docker_image": run["production_image"],
        "authorization": {
            "artifact": "phase9g_a1_owner_authorization_v1.json",
            "sha256": authorization_sha256,
            "scope": authorization["scope_status"],
        },
        "scientific_provenance_root": run["generation_provenance_root"],
        "operational_contract": {
            "artifact": "phase9g0p_operational_production_contract_v2.json",
            "sha256": operational_sha256,
            "recoverability_profile": operational["profiles"]["recoverability"],
        },
        "run_identity_sha256": run_sha256,
        "operational_stop_sha256": stop_sha256,
        "job_manifest_sha256": manifest["job_manifest_sha256"],
        "staging_read_only_during_inspection": True,
        "staging_checkpoint_preimage_sha256": _sha256_document(checkpoint_preimage),
        "transaction_count": len(transaction_descriptors),
        "completed_candidate_pair_count": len(completed_event_ids),
        "completed_atomic_unit_count": len(completed_atomic_unit_ids),
        "scientific_row_count": len(scientific_row_ids),
        "duplicate_scientific_row_identities": 0,
        "partial_candidate_pair_publications": 0,
        "partial_writer_files": 0,
        "staging_storage_bytes": staging_bytes,
        "candidate_pair_status_distribution": dict(sorted(pair_statuses.items())),
        "generation_invalid_aggregate_reason_distribution": dict(
            sorted(invalid_reasons.items())
        ),
        "infrastructure_converted_to_generation_invalid": False,
        "completed_event_ids": completed_event_ids,
        "completed_atomic_unit_ids": completed_atomic_unit_ids,
        "scientific_row_ids": scientific_row_ids,
        "transaction_descriptors": transaction_descriptors,
        "sealed_domains": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "training_operations": 0,
        },
    }
    digest = _write(args.output, report)
    print(json.dumps({
        "status": report["status"],
        "events": report["transaction_count"],
        "atomic_units": report["completed_atomic_unit_count"],
        "rows": report["scientific_row_count"],
        "invalid_reasons": report["generation_invalid_aggregate_reason_distribution"],
        "checkpoint_preimage_sha256": report[
            "staging_checkpoint_preimage_sha256"
        ],
        "sha256": digest,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
