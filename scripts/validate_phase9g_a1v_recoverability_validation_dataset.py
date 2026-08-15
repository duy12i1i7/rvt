#!/usr/bin/env python3
"""Independently validate the finalized A1V Recoverability VALIDATION dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import attach_canonical_hash, canonical_json_bytes, sha256_document
from rvt_swarm.phase9g0r.contracts import recoverability_scientific_row_id


DATASET_ID = "phase9g-a1-study-a-validation-recoverability-v1"
TRAIN_DATASET_ID = "phase9g-a1-study-a-train-recoverability-v1"
STUDY = "study_a_zero_shot"
TRAIN_MANIFEST = "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
TRAIN_SEAL = "5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5"


class DatasetValidationError(RuntimeError):
    """A finalized VALIDATION artifact violates its publication contract."""


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
        raise DatasetValidationError(f"canonical hash mismatch: {path}")
    return document


def _jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("rb") as stream:
        for number, line in enumerate(stream):
            if not line.endswith(b"\n"):
                raise DatasetValidationError(f"unterminated JSONL line: {path}:{number}")
            record = json.loads(line)
            if line != canonical_json_bytes(record) + b"\n":
                raise DatasetValidationError(f"noncanonical JSONL line: {path}:{number}")
            records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    final = data_root / "final" / DATASET_ID
    train = data_root / "final" / TRAIN_DATASET_ID
    staging = data_root / "staging" / f"{STUDY}-validation-recoverability"
    audit = data_root / "audit" / args.run_id

    manifest = _canonical(final / "dataset_manifest.json", "dataset_manifest_sha256")
    seal = _canonical(final / "DATASET_SEAL.json", "dataset_seal_sha256")
    train_manifest = _canonical(train / "dataset_manifest.json", "dataset_manifest_sha256")
    train_seal = _canonical(train / "DATASET_SEAL.json", "dataset_seal_sha256")
    reconciliation = _canonical(
        final / "audits/validation_reconciliation.json",
        "phase9g_a1v_validation_reconciliation_sha256",
    )
    quality = _canonical(
        final / "audits/recoverability_validation_quality_audit.json",
        "phase9g_a1v_recoverability_validation_quality_audit_sha256",
    )
    if (
        manifest["status"] != "VALID_FROZEN_VALIDATION_ONLY"
        or manifest["dataset_id"] != DATASET_ID
        or manifest["study"] != STUDY
        or manifest["splits"] != ["validation"]
        or manifest["train_included"] is not False
        or manifest["class_weighting"] != "NOT_SELECTED"
        or manifest["completion_state"] != "COMPLETE"
        or manifest["physical_namespace_separate_from_train"] is not True
        or manifest["mutable_indexes_shared_with_train"] is not False
    ):
        raise DatasetValidationError("VALIDATION manifest scope or completion changed")
    if (
        seal["dataset_manifest_sha256"] != manifest["dataset_manifest_sha256"]
        or seal["further_staging_writes_permitted"] is not False
        or seal["recoverability_train_mutation_permitted"] is not False
        or seal["residual_v2_authorized"] is not False
        or seal["training_authorized"] is not False
    ):
        raise DatasetValidationError("VALIDATION dataset seal is inconsistent")
    if (
        train_manifest["dataset_manifest_sha256"] != TRAIN_MANIFEST
        or train_seal["dataset_seal_sha256"] != TRAIN_SEAL
        or manifest["train_reference"]
        != {"manifest_sha256": TRAIN_MANIFEST, "seal_sha256": TRAIN_SEAL}
    ):
        raise DatasetValidationError("immutable TRAIN reference changed")
    if reconciliation["status"] != "PASS" or quality["descriptive_only"] is not True:
        raise DatasetValidationError("reconciliation or descriptive audit is invalid")

    for descriptor in list(manifest["shards"]) + list(manifest["row_indexes"]) + list(manifest["transaction_indexes"]):
        path = final / descriptor["path"]
        if not path.is_file() or _file_sha(path) != descriptor["content_sha256"]:
            raise DatasetValidationError(f"published file hash mismatch: {path}")

    shard_rows: dict[str, tuple[dict[str, Any], str, int]] = {}
    shard_counts = []
    for descriptor in manifest["shards"]:
        path = final / descriptor["path"]
        records = _jsonl(path)
        if len(records) != int(descriptor["row_count"]):
            raise DatasetValidationError("shard row count differs from manifest")
        shard_counts.append(len(records))
        for line, row in enumerate(records):
            row_id = str(row["scientific_row_id"])
            identity = row["scientific_identity"]
            if row_id != recoverability_scientific_row_id(identity) or row_id in shard_rows:
                raise DatasetValidationError("duplicate or invalid final row identity")
            if identity["study"] != STUDY or identity["split"] != "validation":
                raise DatasetValidationError("final row crossed VALIDATION scope")
            if (
                sha256_document(row["graph_payload"]) != row["graph_fingerprint"]
                or row["graph_fingerprint"] != identity["graph_fingerprint"]
            ):
                raise DatasetValidationError("final row graph fingerprint mismatch")
            shard_rows[row_id] = (row, descriptor["path"], line)

    transaction_index = _jsonl(final / manifest["transaction_indexes"][0]["path"])
    if len(transaction_index) != 1500:
        raise DatasetValidationError("transaction index is not the 1500-event universe")
    transaction_ids = set()
    transaction_row_event: dict[str, str] = {}
    status_counts: Counter[str] = Counter()
    hardlink_matches = 0
    for descriptor in transaction_index:
        event_id = str(descriptor["decision_event_id"])
        if event_id in transaction_ids:
            raise DatasetValidationError("duplicate transaction index identity")
        transaction_ids.add(event_id)
        final_path = final / descriptor["path"]
        staging_path = data_root / "staging" / descriptor["relative_staging_path"]
        if not final_path.is_file() or not staging_path.is_file():
            raise DatasetValidationError("transaction provenance path is missing")
        if not os.path.samefile(final_path, staging_path):
            raise DatasetValidationError("final transaction is not linked to STAGING")
        hardlink_matches += 1
        if _file_sha(final_path) != descriptor["content_sha256"]:
            raise DatasetValidationError("transaction index content hash mismatch")
        document = _canonical(final_path, "canonical_record_sha256")
        if document["decision_event_id"] != event_id:
            raise DatasetValidationError("transaction index/event identity mismatch")
        if int(document["actual_row_count"]) != len(document["rows"]):
            raise DatasetValidationError("transaction row count mismatch")
        if len(document["rows"]) not in (0, int(document["expected_row_count"])):
            raise DatasetValidationError("partial candidate-pair publication")
        status_counts[str(document["status"])] += 1
        for row in document["rows"]:
            row_id = str(row["scientific_row_id"])
            if row_id in transaction_row_event:
                raise DatasetValidationError("row appears in multiple transactions")
            transaction_row_event[row_id] = event_id
            if row_id not in shard_rows or shard_rows[row_id][0] != row:
                raise DatasetValidationError("transaction/shard row payload mismatch")

    row_index = _jsonl(final / manifest["row_indexes"][0]["path"])
    row_index_ids = set()
    for item in row_index:
        row_id = str(item["scientific_row_id"])
        if row_id in row_index_ids or row_id not in shard_rows:
            raise DatasetValidationError("invalid row-index identity")
        row_index_ids.add(row_id)
        _, shard, line = shard_rows[row_id]
        if (
            item["shard"] != shard
            or int(item["line"]) != line
            or item["decision_event_id"] != transaction_row_event[row_id]
        ):
            raise DatasetValidationError("row-index location or event binding mismatch")
    if row_index_ids != set(shard_rows) or set(transaction_row_event) != set(shard_rows):
        raise DatasetValidationError("final row universes do not reconcile")
    if len(shard_rows) != manifest["scientific_row_count"]:
        raise DatasetValidationError("manifest scientific-row count mismatch")
    if any(manifest["integrity"].values()) or any(manifest["sealed_domains"].values()):
        raise DatasetValidationError("manifest reports integrity or sealed-domain activity")

    writable_files = sum(
        bool(path.stat().st_mode & 0o222) for path in staging.rglob("*") if path.is_file()
    )
    if writable_files:
        raise DatasetValidationError("sealed VALIDATION STAGING contains writable files")
    train_row_ids = {
        str(item["scientific_row_id"])
        for item in _jsonl(train / "indexes/train-recoverability-row-index.jsonl")
    }
    train_event_ids = {
        str(item["decision_event_id"])
        for item in _jsonl(train / "indexes/train-recoverability-transaction-index.jsonl")
    }
    if train_row_ids & set(shard_rows) or train_event_ids & transaction_ids:
        raise DatasetValidationError("TRAIN/VALIDATION scientific identity overlap")

    report = {
        "schema_version": "rvt-phase9g-a1v-postfinal-dataset-validation/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS",
        "dataset_id": DATASET_ID,
        "dataset_manifest_sha256": manifest["dataset_manifest_sha256"],
        "dataset_seal_sha256": seal["dataset_seal_sha256"],
        "train_manifest_sha256": TRAIN_MANIFEST,
        "train_seal_sha256": TRAIN_SEAL,
        "validated": {
            "transactions": len(transaction_ids),
            "transaction_hardlink_matches": hardlink_matches,
            "scientific_rows": len(shard_rows),
            "unique_scientific_row_ids": len(shard_rows),
            "row_index_entries": len(row_index),
            "shards": len(shard_counts),
            "shard_row_counts": shard_counts,
            "row_identity_failures": 0,
            "graph_fingerprint_failures": 0,
            "transaction_hash_failures": 0,
            "published_file_hash_failures": 0,
            "partial_pair_publications": 0,
            "duplicates": 0,
            "schema_failures": 0,
            "seed_mismatches": reconciliation["observed"]["seed_mismatches"],
            "seal_violations": 0,
        },
        "split_isolation": {
            "train_validation_scientific_row_id_overlap": 0,
            "train_validation_decision_event_id_overlap": 0,
            "separate_final_namespaces": True,
            "shared_mutable_indexes": False,
        },
        "transaction_status_distribution": dict(sorted(status_counts.items())),
        "staging": {
            "directory_mode_octal": oct(staging.stat().st_mode & 0o777),
            "writable_files": writable_files,
            "partial_files": len(tuple(staging.rglob("*.partial"))),
        },
        "dataset_storage_bytes": sum(path.stat().st_size for path in final.rglob("*") if path.is_file()),
        "class_weighting": "NOT_SELECTED",
        "residual_started": False,
        "training_operations": 0,
        "hyperparameter_trials": 0,
    }
    report = attach_canonical_hash(report, "phase9g_a1v_postfinal_dataset_validation_sha256")
    output = audit / "postfinal_dataset_validation.json"
    output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": report["status"],
        "hash": report["phase9g_a1v_postfinal_dataset_validation_sha256"],
        "transactions": len(transaction_ids),
        "rows": len(shard_rows),
        "storage_bytes": report["dataset_storage_bytes"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
