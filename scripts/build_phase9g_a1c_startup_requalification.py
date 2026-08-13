#!/usr/bin/env python3
"""Freeze the A1C attempt-1 packaging failure and launch-binding repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/rvt_fd24"
RAW = OUT / "phase9g_a1c_attempt1_startup_failure"


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    status = json.loads(
        (RAW / "train-continuation-status.json").read_text(encoding="ascii")
    )
    body = dict(status)
    expected = str(body.pop("phase9g_a1c_continuation_status_sha256", ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError("attempt-1 status canonical hash mismatch")
    before = json.loads(
        (RAW / "module-provenance-before.json").read_text(encoding="ascii")
    )
    after = json.loads(
        (RAW / "module-provenance-after.json").read_text(encoding="ascii")
    )
    stderr = (RAW / "container.stderr.log").read_text(encoding="utf-8")
    if (
        status["events_completed_this_continuation"] != 0
        or status["official_transactions_written_this_continuation"] != 0
        or "unexpected keyword argument 'status_hash_field'" not in stderr
        or before["module_file"]
        != "/opt/rvt/scripts/run_phase9g_a1r_recoverability_continuation.py"
        or before["status_hash_field_present"] is not False
        or after["module_file"]
        != "/a1c/scripts/run_phase9g_a1r_recoverability_continuation.py"
        or after["status_hash_field_present"] is not True
    ):
        raise ValueError("startup failure or repaired module provenance changed")

    artifact = {
        "schema_version": "rvt-phase9g-a1c-startup-requalification/v1",
        "phase": "PHASE_9G_A1C",
        "status": "PASS_OPERATIONAL_RETRY_PERMITTED",
        "attempt": {
            "number": 1,
            "container": "phase9g-a1c-recoverability-train-attempt-1-failed",
            "exit_code": 1,
            "classification": "OPERATIONAL_DEPLOYMENT_IMPORT_BINDING",
            "root_cause": (
                "working directory /opt/rvt preceded /a1c on sys.path, so the "
                "image copy of the helper module was imported"
            ),
            "exception": "TypeError: execute_unresolved() got an unexpected keyword argument 'status_hash_field'",
            "failure_point": "after authority/checkpoint validation and before execute_unresolved",
        },
        "scientific_effect": {
            "scientific_units_started": 0,
            "candidate_aggregates_started": 0,
            "scientific_transactions_written": 0,
            "scientific_rows_written": 0,
            "scientific_retries": 0,
            "scientific_semantics_changed": False,
            "staging_transactions_after_failure": 210,
            "staging_rows_after_failure": 342,
            "partial_transactions_after_failure": 0,
            "checkpoint_unchanged": True,
            "checkpoint_sha256": "72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f",
        },
        "repair": {
            "classification": "LAUNCH_BINDING_ONLY",
            "working_directory": {
                "old": "/opt/rvt",
                "new": "/a1c",
            },
            "deployed_package_marker": {
                "path": "/a1c/scripts/__init__.py",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "content_bytes": 0,
                "existing_repository_file": True,
            },
            "module_before": before,
            "module_after": after,
            "scientific_source_image_changed": False,
            "operational_wrapper_bytes_changed": False,
            "authorization_scope_changed": False,
            "profile_changed": False,
        },
        "raw_evidence": {
            path.name: {"file_sha256": _file_sha(path), "bytes": path.stat().st_size}
            for path in sorted(RAW.iterdir()) if path.is_file()
        },
        "required_retry_preconditions": {
            "exact_checkpoint_revalidation": True,
            "resolve_only_under_repaired_working_directory": True,
            "same_run_id": True,
            "same_unresolved_identity_set": True,
            "workers": 12,
            "numeric_threads": 1,
            "chunk_size": 1,
            "timeout_seconds": 243,
        },
        "sealed_scope": {
            "recoverability_validation_operations": 0,
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    artifact = attach_canonical_hash(
        artifact, "phase9g_a1c_startup_requalification_sha256"
    )
    path = OUT / "phase9g_a1c_startup_requalification_v1.json"
    path.write_text(
        json.dumps(artifact, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(artifact["phase9g_a1c_startup_requalification_sha256"])


if __name__ == "__main__":
    main()
