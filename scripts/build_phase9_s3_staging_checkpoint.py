#!/usr/bin/env python3
"""Bind the read-only 342-row STAGING prefix before S3 analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    data_root = args.data_root.resolve()
    stop = _canonical(
        root / "results/rvt_fd24/phase9g_a1r_continuation_stop_audit_v1.json",
        "phase9g_a1r_continuation_stop_audit_sha256",
    )
    a1r = _canonical(
        root / "results/rvt_fd24/phase9g_a1r_staging_checkpoint_v1.json",
        "phase9g_a1r_staging_checkpoint_sha256",
    )
    staging = data_root / "staging/study_a_zero_shot-train-recoverability"
    validation = data_root / "staging/study_a_zero_shot-validation-recoverability"
    if os.access(staging, os.W_OK):
        raise ValueError("official STAGING must be read-only")
    paths = sorted((staging / "recoverability").glob("event-*.json"))
    partials = sorted(staging.rglob("*.partial"))
    if len(paths) != 210 or partials:
        raise ValueError("official transaction prefix is not exact")

    row_ids: list[str] = []
    descriptors = []
    events = set()
    for path in paths:
        record = _canonical(path, "canonical_record_sha256")
        event_id = str(record["decision_event_id"])
        if event_id in events:
            raise ValueError("duplicate candidate-pair identity")
        events.add(event_id)
        if (
            not record["scientifically_reconciled"]
            or not record["scientific_completion_marker"]
            or int(record["actual_row_count"]) != len(record["rows"])
        ):
            raise ValueError("incomplete transaction is durable")
        local_rows = [str(row["scientific_row_id"]) for row in record["rows"]]
        for row in record["rows"]:
            if _sha(row["scientific_identity"]) != row["scientific_row_id"]:
                raise ValueError("scientific row identity mismatch")
        row_ids.extend(local_rows)
        descriptors.append({
            "decision_event_id": event_id,
            "status": record["status"],
            "scientific_row_count": len(local_rows),
            "scientific_row_ids": local_rows,
            "file_name": path.name,
            "file_size_bytes": path.stat().st_size,
            "file_sha256": _file_sha(path),
            "canonical_record_sha256": record["canonical_record_sha256"],
        })
    if len(row_ids) != 342 or len(set(row_ids)) != 342:
        raise ValueError("342 unique scientific rows are required")
    if set(row_ids) != set(stop["data_integrity"]["scientific_row_ids"]):
        raise ValueError("live row IDs differ from the A1R stop audit")

    report = {
        "schema_version": "rvt-phase9-s3-staging-checkpoint/v1",
        "status": "PASS_READ_ONLY_PREFIX_BOUND",
        "phase": "PHASE_9G_A1S3",
        "a1r_commit": "a943ca391fb5feb5c8e90a693f763cc47c4d4e2b",
        "run_lineage": {
            "parent_run_id": stop["parent_run_id"],
            "continuation_run_id": stop["run_id"],
        },
        "scientific_binding": {
            "source_commit": stop["scientific_source_commit"],
            "production_image": stop["production_image"],
            "scientific_provenance_root": a1r["scientific_provenance_root"],
            "job_manifest_sha256": a1r["job_manifest_sha256"],
            "owner_authorization_sha256": a1r["authorization"]["sha256"],
            "a1r_operational_amendment_sha256": (
                "1821badc6b09c2417a3fff98bb2f97673a69cdeff002b9ac1a64fac927d806e8"
            ),
        },
        "prefix": {
            "train_events": len(paths),
            "candidate_aggregates": 2 * len(paths),
            "scientific_rows": len(row_ids),
            "initial_rows": 318,
            "post_timeout_rows": 24,
            "duplicate_scientific_identities": 0,
            "partial_candidate_pair_publications": 0,
            "validation_started": validation.exists(),
            "staging_read_only": True,
            "staging_storage_bytes": sum(path.stat().st_size for path in paths),
        },
        "scientific_row_ids": sorted(row_ids),
        "candidate_pair_transactions": descriptors,
        "upstream_evidence": {
            "a1r_stop_audit_sha256": stop[
                "phase9g_a1r_continuation_stop_audit_sha256"
            ],
            "initial_a1r_checkpoint_sha256": a1r[
                "phase9g_a1r_staging_checkpoint_sha256"
            ],
        },
        "sealed_domains": dict(stop["sealed_domains"]),
    }
    if report["prefix"]["validation_started"]:
        raise ValueError("Recoverability validation must not be started")
    if any(report["sealed_domains"].values()):
        raise ValueError("sealed-domain counter is nonzero")
    report["phase9_s3_staging_checkpoint_sha256"] = _sha(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "events": len(paths), "rows": len(row_ids),
        "phase9_s3_staging_checkpoint_sha256": report[
            "phase9_s3_staging_checkpoint_sha256"
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
