#!/usr/bin/env python3
"""Independently validate the finalized A1C Recoverability TRAIN dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import (
    attach_canonical_hash,
    canonical_json_bytes,
    sha256_document,
)
from rvt_swarm.phase9g0r.contracts import recoverability_scientific_row_id


DATASET_ID = "phase9g-a1-study-a-train-recoverability-v1"
STUDY = "study_a_zero_shot"


class DatasetValidationError(RuntimeError):
    """A finalized TRAIN artifact violates its publication contract."""


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
    staging = data_root / "staging" / f"{STUDY}-train-recoverability"
    audit = data_root / "audit" / args.run_id

    manifest = _canonical(final / "dataset_manifest.json", "dataset_manifest_sha256")
    seal = _canonical(final / "DATASET_SEAL.json", "dataset_seal_sha256")
    reconciliation = _canonical(
        final / "audits/train_reconciliation.json",
        "phase9g_a1c_recoverability_train_reconciliation_sha256",
    )
    quality = _canonical(
        final / "audits/recoverability_train_quality_audit.json",
        "phase9g_a1c_recoverability_train_quality_audit_sha256",
    )
    if (
        manifest["status"] != "VALID_FROZEN_TRAIN_ONLY"
        or manifest["dataset_id"] != DATASET_ID
        or manifest["study"] != STUDY
        or manifest["splits"] != ["train"]
        or manifest["validation_included"] is not False
        or manifest["class_weighting"] != "NOT_SELECTED"
        or manifest["completion_state"] != "COMPLETE"
    ):
        raise DatasetValidationError("TRAIN manifest scope or completion changed")
    if (
        seal["dataset_manifest_sha256"] != manifest["dataset_manifest_sha256"]
        or seal["further_staging_writes_permitted"] is not False
        or seal["recoverability_validation_authorized"] is not False
    ):
        raise DatasetValidationError("TRAIN dataset seal is inconsistent")
    if reconciliation["status"] != "PASS" or quality["descriptive_only"] is not True:
        raise DatasetValidationError("reconciliation or descriptive audit is invalid")
    if quality["class_weighting"] != "NOT_SELECTED":
        raise DatasetValidationError("class weighting was selected")

    file_descriptors = (
        list(manifest["shards"])
        + list(manifest["row_indexes"])
        + list(manifest["transaction_indexes"])
    )
    for descriptor in file_descriptors:
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
            if row_id != recoverability_scientific_row_id(identity):
                raise DatasetValidationError("final shard row identity mismatch")
            if row_id in shard_rows:
                raise DatasetValidationError("duplicate final shard row identity")
            if identity["study"] != STUDY or identity["split"] != "train":
                raise DatasetValidationError("final shard row crossed TRAIN scope")
            if sha256_document(row["graph_payload"]) != row["graph_fingerprint"]:
                raise DatasetValidationError("final shard graph fingerprint mismatch")
            if row["graph_fingerprint"] != identity["graph_fingerprint"]:
                raise DatasetValidationError("final shard identity graph mismatch")
            shard_rows[row_id] = (row, descriptor["path"], line)

    transaction_index = _jsonl(
        final / manifest["transaction_indexes"][0]["path"]
    )
    if len(transaction_index) != 6000:
        raise DatasetValidationError("transaction index is not the 6000-event universe")
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
            raise DatasetValidationError("partial candidate-pair publication in final")
        status_counts[str(document["status"])] += 1
        for row in document["rows"]:
            row_id = str(row["scientific_row_id"])
            if row_id in transaction_row_event:
                raise DatasetValidationError("row appears in multiple transactions")
            transaction_row_event[row_id] = event_id
            if row_id not in shard_rows or shard_rows[row_id][0] != row:
                raise DatasetValidationError("transaction/shard row payload mismatch")

    row_index = _jsonl(final / manifest["row_indexes"][0]["path"])
    if len(row_index) != len(shard_rows):
        raise DatasetValidationError("row index cardinality mismatch")
    row_index_ids = set()
    for item in row_index:
        row_id = str(item["scientific_row_id"])
        if row_id in row_index_ids:
            raise DatasetValidationError("duplicate row index identity")
        row_index_ids.add(row_id)
        if row_id not in shard_rows:
            raise DatasetValidationError("row index points outside final shards")
        _, shard, line = shard_rows[row_id]
        if (
            item["shard"] != shard
            or int(item["line"]) != line
            or item["decision_event_id"] != transaction_row_event[row_id]
        ):
            raise DatasetValidationError("row index location or event binding mismatch")
    if row_index_ids != set(shard_rows) or set(transaction_row_event) != set(shard_rows):
        raise DatasetValidationError("final row universes do not reconcile")

    initial = manifest["existing_342_row_lineage"]
    if initial != reconciliation["existing_342_row_lineage"] or initial != {
        "checkpoint_sha256": "72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f",
        "rows_retained": 342,
        "rows_regenerated": 0,
        "UNAFFECTED": 254,
        "DEPENDENCY_PRESENT_BUT_VALUE_VALID": 88,
        "POTENTIALLY_AFFECTED": 0,
        "PROVEN_AFFECTED": 0,
    }:
        raise DatasetValidationError("original 342-row lineage differs from authority")
    if any(value != 0 for value in manifest["integrity"].values()):
        raise DatasetValidationError("manifest reports an integrity failure")
    if any(value != 0 for value in manifest["sealed_domains"].values()):
        raise DatasetValidationError("manifest reports sealed-domain activity")
    if (data_root / "staging/study_a_zero_shot-validation-recoverability").exists():
        raise DatasetValidationError("Recoverability validation was started")
    writable_staging_files = sum(
        bool(path.stat().st_mode & 0o222) for path in staging.rglob("*") if path.is_file()
    )
    if writable_staging_files:
        raise DatasetValidationError("sealed TRAIN STAGING contains writable files")

    report = {
        "schema_version": "rvt-phase9g-a1c-postfinal-dataset-validation/v1",
        "phase": "PHASE_9G_A1C",
        "status": "PASS",
        "dataset_id": DATASET_ID,
        "dataset_manifest_sha256": manifest["dataset_manifest_sha256"],
        "dataset_seal_sha256": seal["dataset_seal_sha256"],
        "reconciliation_sha256": reconciliation[
            "phase9g_a1c_recoverability_train_reconciliation_sha256"
        ],
        "quality_audit_sha256": quality[
            "phase9g_a1c_recoverability_train_quality_audit_sha256"
        ],
        "validated": {
            "transactions": len(transaction_ids),
            "transaction_hardlink_matches": hardlink_matches,
            "scientific_rows": len(shard_rows),
            "unique_scientific_row_ids": len(shard_rows),
            "row_index_entries": len(row_index),
            "shards": len(shard_counts),
            "shard_row_counts": shard_counts,
            "canonical_transaction_records": len(transaction_ids),
            "canonical_jsonl_rows": len(shard_rows),
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
        "transaction_status_distribution": dict(sorted(status_counts.items())),
        "existing_342_row_lineage": initial,
        "staging": {
            "directory_mode_octal": oct(staging.stat().st_mode & 0o777),
            "writable_files": writable_staging_files,
            "partial_files": len(tuple(staging.rglob("*.partial"))),
        },
        "dataset_storage_bytes": sum(
            path.stat().st_size for path in final.rglob("*") if path.is_file()
        ),
        "sealed_domains": manifest["sealed_domains"],
        "class_weighting": "NOT_SELECTED",
        "validation_started": False,
        "residual_started": False,
        "training_operations": 0,
    }
    report = attach_canonical_hash(
        report, "phase9g_a1c_postfinal_dataset_validation_sha256"
    )
    output = audit / "postfinal_dataset_validation.json"
    output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": report["status"],
        "hash": report["phase9g_a1c_postfinal_dataset_validation_sha256"],
        "transactions": len(transaction_ids),
        "rows": len(shard_rows),
        "storage_bytes": report["dataset_storage_bytes"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
