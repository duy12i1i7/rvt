#!/usr/bin/env python3
"""Build additive authority for the train-only A1C continuation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import JOB_MANIFEST_SHA256, compile_recoverability_tasks


EVIDENCE_COMMIT = "af5c083e58476f5bd8a08710ce567176108e8f06"
SOURCE_COMMIT = "848e8b352a91e95af777ebbeccd5fbb43d53777e"
IMAGE = "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
RUN_ID = "phase9g-a1c-study-a-train-recoverability-continuation-20260813T112333Z"
PARENT_RUN_ID = (
    "phase9g-a1r-study-a-train-validation-recoverability-continuation-"
    "20260812T061720Z"
)
DATASET_LINEAGE_ID = "phase9g-a1-study-a-train-validation-recoverability-v1"
CREATED_AT = "2026-08-13T11:23:33Z"
OWNER_INSTRUCTION_SHA256 = (
    "76654c8fe141500f401cbb8e87866751f19e1b568560b1c76ca5bdba083f9f61"
)
CHECKPOINT_SHA256 = "72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f"
PROVENANCE_V3_SHA256 = "9f209cd4b5ae591b2f576a085bcbdb6b7d30a7f3fecb9840d6e0eb56bb03adc8"
S3_OPPOSING_SHA256 = "a5e7fa9ce92ba7fb449a76406da47cc00dd4a39ddee2e108a62a969589b5f6d3"
S3_CENTERLINE_SHA256 = "d216217b3a3dfead5e3249cbf57317a71aa1c479acc840994eec9ff1616da23b"
S3_READINESS_SHA256 = "a7118241538639b4da657f5aceff89bdfe9c64be62f22a21221b221016637d6c"
A1R_AMENDMENT_SHA256 = "1821badc6b09c2417a3fff98bb2f97673a69cdeff002b9ac1a64fac927d806e8"


ROOTS = (
    ("rb19_current_generation_provenance_v1.json", "rb19_current_generation_provenance_sha256"),
    ("rb20_clean_detached_reproduction_v1.json", "rb20_clean_detached_reproduction_sha256"),
    ("rb21_portability_requalification_v1.json", "rb21_portability_requalification_sha256"),
    ("rb21_cross_platform_numeric_portability_v1.json", "rb21_cross_platform_numeric_portability_sha256"),
    ("phase9_predata_generation_scientific_addendum_v1.json", "phase9_predata_generation_scientific_addendum_sha256"),
    ("phase9g0p_operational_production_contract_v2.json", "phase9g0p_operational_contract_sha256"),
    ("phase9g_a1r_operational_contract_amendment_v1.json", "phase9g_a1r_operational_contract_amendment_sha256"),
    ("phase9_s3_geometry_authority_v1.json", "phase9_s3_geometry_authority_sha256"),
    ("phase9_s3_opposing_boundary_scientific_addendum_v1.json", "phase9_s3_opposing_boundary_scientific_addendum_sha256"),
    ("phase9_s3_exact_centerline_scientific_addendum_v1.json", "phase9_s3_exact_centerline_scientific_addendum_sha256"),
    ("phase9_s3_final_resume_readiness_v1.json", "phase9_s3_final_resume_readiness_sha256"),
    ("phase9_current_generation_provenance_v3.json", "phase9_current_generation_provenance_v3_sha256"),
    ("phase9_generation_readiness_v5.json", "phase9_generation_readiness_v5_sha256"),
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="ascii"))


def _canonical(path: Path, field: str) -> dict[str, Any]:
    document = _load(path)
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, body: dict[str, Any], field: str) -> dict[str, Any]:
    document = attach_canonical_hash(body, field)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "results/rvt_fd24"

    validated = []
    for name, field in ROOTS:
        path = out / name
        document = _canonical(path, field)
        validated.append({
            "artifact": name,
            "canonical_hash_field": field,
            "canonical_sha256": document[field],
            "file_sha256": _file_sha256(path),
        })

    expected_hashes = {
        "phase9_predata_generation_scientific_addendum_v1.json": "523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0",
        "phase9g0p_operational_production_contract_v2.json": "1a4e0fcbe49b94c3375125d0ef8421e7129b801491cec309e49ce4bc24adcc12",
        "phase9g_a1r_operational_contract_amendment_v1.json": A1R_AMENDMENT_SHA256,
        "phase9_s3_opposing_boundary_scientific_addendum_v1.json": S3_OPPOSING_SHA256,
        "phase9_s3_exact_centerline_scientific_addendum_v1.json": S3_CENTERLINE_SHA256,
        "phase9_s3_final_resume_readiness_v1.json": S3_READINESS_SHA256,
        "phase9_current_generation_provenance_v3.json": PROVENANCE_V3_SHA256,
    }
    actual = {item["artifact"]: item["canonical_sha256"] for item in validated}
    for name, expected in expected_hashes.items():
        if actual.get(name) != expected:
            raise ValueError(f"authoritative root changed: {name}")

    checkpoint_path = out / "phase9g_a1c_staging_precheck_v1.json"
    checkpoint = _canonical(checkpoint_path, "phase9_s3_staging_checkpoint_sha256")
    transaction_ids = {
        item["decision_event_id"] for item in checkpoint["candidate_pair_transactions"]
    }
    train_tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="train"
    )
    train_ids = {task.event_id for task in train_tasks}
    if checkpoint["prefix"]["train_events"] != 210 or len(transaction_ids) != 210:
        raise ValueError("A1C initial completed-event count changed")
    if checkpoint["prefix"]["scientific_rows"] != 342:
        raise ValueError("A1C initial scientific-row count changed")
    if checkpoint["phase9_s3_staging_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ValueError("A1C STAGING checkpoint changed")
    if not transaction_ids <= train_ids:
        raise ValueError("STAGING contains an out-of-scope event")

    root_validation = _write(
        out / "phase9g_a1c_current_root_validation_v1.json",
        {
            "schema_version": "rvt-phase9g-a1c-current-root-validation/v1",
            "phase": "PHASE_9G_A1C",
            "status": "PASS",
            "evidence_commit": EVIDENCE_COMMIT,
            "executable_source_commit": SOURCE_COMMIT,
            "production_image": IMAGE,
            "validated_roots": validated,
            "current_scientific_provenance_root": PROVENANCE_V3_SHA256,
            "historical_roots_rewritten": False,
            "sealed_scope": {
                "study_a_n24_accesses": 0,
                "study_b_accesses": 0,
                "final_test_accesses": 0,
                "residual_operations": 0,
                "training_operations": 0,
            },
        },
        "phase9g_a1c_current_root_validation_sha256",
    )

    scope = _write(
        out / "phase9g_a1c_authorization_scope_study_a_zero_shot-train-recoverability_v1.json",
        {
            "schema_version": "rvt-phase9g-a1c-authorization-scope/v1",
            "phase": "PHASE_9G_A1C",
            "authorization_class": "AUTHORIZED_STUDY_A_RECOVERABILITY_TRAIN_CONTINUATION_ONLY",
            "owner_authorization_timestamp_utc": CREATED_AT,
            "binding": {
                "study": "study_a_zero_shot",
                "split": "train",
                "branch": "recoverability",
                "source_commit": SOURCE_COMMIT,
                "docker_image": IMAGE,
                "scientific_addendum_sha256": S3_CENTERLINE_SHA256,
                "generation_provenance_root": PROVENANCE_V3_SHA256,
            },
            "official_generation_execution_authorized": True,
            "broad_authorization": False,
            "scientific_outcomes_present": False,
            "sealed_exclusions": [
                "recoverability_validation", "residual_v2", "training",
                "study_a_n24_zero_shot", "study_b", "final_test",
            ],
        },
        "phase9_authorization_scope_sha256",
    )

    authorization = _write(
        out / "phase9g_a1c_owner_authorization_continuation_v1.json",
        {
            "schema_version": "rvt-phase9g-a1c-owner-authorization-continuation/v1",
            "phase": "PHASE_9G_A1C",
            "created_at_utc": CREATED_AT,
            "authorization_source": {
                "kind": "EXPLICIT_OWNER_INSTRUCTION_IN_CURRENT_TASK",
                "instruction_file_sha256": OWNER_INSTRUCTION_SHA256,
            },
            "authorized_scope": {
                "study": "study_a_zero_shot",
                "splits": ["train"],
                "branch": "recoverability",
                "operation": "OFFICIAL_STAGING_CONTINUATION_AND_TRAIN_FINALIZATION",
            },
            "scope_artifact": {
                "artifact": (
                    "phase9g_a1c_authorization_scope_study_a_zero_shot-"
                    "train-recoverability_v1.json"
                ),
                "sha256": scope["phase9_authorization_scope_sha256"],
            },
            "bindings": {
                "evidence_commit": EVIDENCE_COMMIT,
                "executable_source_commit": SOURCE_COMMIT,
                "production_image": IMAGE,
                "scientific_provenance_root": PROVENANCE_V3_SHA256,
                "job_manifest_sha256": JOB_MANIFEST_SHA256,
                "s3_opposing_boundary_addendum_sha256": S3_OPPOSING_SHA256,
                "s3_exact_centerline_addendum_sha256": S3_CENTERLINE_SHA256,
                "s3_final_resume_readiness_sha256": S3_READINESS_SHA256,
                "a1r_operational_amendment_sha256": A1R_AMENDMENT_SHA256,
                "initial_staging_checkpoint_sha256": CHECKPOINT_SHA256,
            },
            "qualified_profile": {
                "workers": 12,
                "numeric_threads_per_worker": 1,
                "chunk_size_atomic_units": 1,
                "infrastructure_timeout_seconds": 243,
            },
            "operational_wrappers": {
                name: _file_sha256(root / "scripts" / name)
                for name in (
                    "run_phase9g_a1r_recoverability_continuation.py",
                    "run_phase9g_a1c_recoverability_train_continuation.py",
                    "audit_phase9g_a1c_s3_prestart.py",
                    "finalize_phase9g_a1c_recoverability_train.py",
                )
            },
            "existing_data_action": "RETAIN_ALL_342",
            "scope_status": {
                "RECOVERABILITY_TRAIN": "AUTHORIZED_CONTINUATION",
                "RECOVERABILITY_VALIDATION": "NOT_AUTHORIZED_YET",
                "RESIDUAL_V2": "NOT_AUTHORIZED",
                "TRAINING": "NOT_AUTHORIZED",
                "STUDY_A_N24": "SEALED_NOT_AUTHORIZED",
                "STUDY_B": "NOT_AUTHORIZED",
                "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
            },
            "broadens_scientific_scope": False,
            "scientific_outcomes_present_in_authorization": False,
        },
        "phase9g_a1c_owner_authorization_continuation_sha256",
    )

    run = _write(
        out / "phase9g_a1c_continuation_run_identity_v1.json",
        {
            "schema_version": "rvt-phase9g-a1c-continuation-run-identity/v1",
            "phase": "PHASE_9G_A1C",
            "created_at_utc": CREATED_AT,
            "run_id": RUN_ID,
            "parent_run_id": PARENT_RUN_ID,
            "original_run_id": "phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z",
            "identity_class": "OPERATIONAL_SUCCESSOR_CONTINUATION_NOT_SCIENTIFIC",
            "successor_required_reason": "qualified image and executable-source binding changed after S3Z",
            "scientific_dataset_lineage_id": DATASET_LINEAGE_ID,
            "logically_independent_dataset": False,
            "same_staging_namespace_as_parent": True,
            "scientific_row_identity_includes_run_id": False,
            "writer_namespace": "staging/study_a_zero_shot-train-recoverability",
            "authorization_continuation_sha256": authorization[
                "phase9g_a1c_owner_authorization_continuation_sha256"
            ],
            "authorization_scope_sha256": scope["phase9_authorization_scope_sha256"],
            "current_root_validation_sha256": root_validation[
                "phase9g_a1c_current_root_validation_sha256"
            ],
            "initial_staging_checkpoint": {
                "artifact": checkpoint_path.name,
                "sha256": CHECKPOINT_SHA256,
                "completed_train_events": 210,
                "scientific_rows": 342,
            },
            "frozen_train_universe": {
                "source_episodes": 1200,
                "decision_events": 6000,
                "candidate_aggregates": 12000,
                "initial_unresolved_events": 5790,
            },
            "resume_semantics": {
                "completed_event_transactions_rescheduled": 0,
                "existing_rows_reemitted": 0,
                "scientific_retry_count": 0,
                "operational_continuation_only": True,
            },
            "required_order": ["train", "stop_before_validation"],
            "sealed_scope": {
                "recoverability_validation_operations": 0,
                "residual_operations": 0,
                "training_operations": 0,
                "study_a_n24_accesses": 0,
                "study_b_accesses": 0,
                "final_test_accesses": 0,
            },
        },
        "phase9g_a1c_continuation_run_identity_sha256",
    )
    print(json.dumps({
        "root_validation": root_validation["phase9g_a1c_current_root_validation_sha256"],
        "scope": scope["phase9_authorization_scope_sha256"],
        "authorization": authorization["phase9g_a1c_owner_authorization_continuation_sha256"],
        "run_identity": run["phase9g_a1c_continuation_run_identity_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
