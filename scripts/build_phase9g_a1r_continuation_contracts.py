#!/usr/bin/env python3
"""Build additive A1R contract, authorization and successor run identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks


RUN_ID = (
    "phase9g-a1r-study-a-train-validation-recoverability-continuation-"
    "20260812T061720Z"
)
PARENT_RUN_ID = (
    "phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
)
IMAGE = "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
SCIENTIFIC_SOURCE = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
WRAPPER_COMMIT = "96dfab986082d2a987f488634e7c32f192aa37cd"
CREATED_AT = "2026-08-12T06:17:20Z"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="ascii"))


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict, hash_field: str) -> dict:
    result = attach_canonical_hash(value, hash_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "results/rvt_fd24"
    old_contract = _load(out / "phase9g0p_operational_production_contract_v2.json")
    old_auth = _load(out / "phase9g_a1_owner_authorization_v1.json")
    parent_run = _load(out / "phase9g_a1_recoverability_run_identity_v1.json")
    checkpoint = _load(out / "phase9g_a1r_staging_checkpoint_v1.json")
    timeout = _load(out / "phase9g_a1r_timeout_derivation_v1.json")
    failure = _load(out / "phase9g_a1r_timeout_failure_injection_result_v1.json")
    wrapper_path = root / "scripts/run_phase9g_a1r_recoverability_continuation.py"
    old_hash = old_contract["phase9g0p_operational_contract_sha256"]
    if old_hash != "1a4e0fcbe49b94c3375125d0ef8421e7129b801491cec309e49ce4bc24adcc12":
        raise ValueError("historical operational contract changed")
    if failure["status"] != "PASS":
        raise ValueError("timeout failure injection has not passed")

    train_tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="train"
    )
    validation_tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="validation"
    )
    completed = frozenset(checkpoint["completed_event_ids"])
    train_ids = {task.event_id for task in train_tasks}
    if not completed <= train_ids or len(completed) != 127:
        raise ValueError("stopped prefix does not bind the train universe")

    amendment = {
        "schema_version": "rvt-phase9g-a1r-operational-contract-amendment/v1",
        "phase": "PHASE_9G_A1R",
        "amendment_scope": "RECOVERABILITY_ONLY",
        "parent_contract": {
            "artifact": "phase9g0p_operational_production_contract_v2.json",
            "sha256": old_hash,
            "status": "SUPERSEDED_FOR_RECOVERABILITY_TIMEOUT_ONLY",
        },
        "unchanged_scientific_bindings": {
            "scientific_source_commit": SCIENTIFIC_SOURCE,
            "scientific_addendum_sha256": old_contract["common"][
                "scientific_addendum_sha256"
            ],
            "recoverability_row_binding_sha256": old_contract["common"][
                "recoverability_row_binding_sha256"
            ],
            "production_image": IMAGE,
            "writer": old_contract["common"]["writer"],
            "writer_parent_process_only": True,
            "gpu_generation": False,
        },
        "recoverability_profile": {
            "profile_id": "PROFILE_RECOVERABILITY_A1R_V1",
            "workers": 12,
            "numeric_threads": 1,
            "chunk_size_atomic_units": 1,
            "infrastructure_timeout_seconds": timeout[
                "new_qualified_timeout_seconds"
            ],
            "old_infrastructure_timeout_seconds": timeout[
                "old_timeout_seconds"
            ],
        },
        "field_changes": [
            {
                "field": "profiles.recoverability.infrastructure_timeout_seconds",
                "old": 60.0,
                "new": timeout["new_qualified_timeout_seconds"],
                "classification": "OPERATIONAL_INFRASTRUCTURE_ONLY",
            },
            {
                "field": "common.resume.scheduler_selection",
                "old": "canonical duplicate replay is a no-op",
                "new": (
                    "exclude durable completed candidate-pair event identities "
                    "before scheduling; schedule unresolved identities only"
                ),
                "classification": "OPERATIONAL_EXACT_RESUME_ENFORCEMENT",
            },
        ],
        "preserved_fields": {
            "workers": 12,
            "numeric_threads": 1,
            "chunk_size_atomic_units": 1,
            "candidate_scheduler_atomic_unit": (
                "one candidate aggregate containing all replicas"
            ),
            "candidate_pair_publication_boundary": "one complete decision event",
        },
        "continuation_wrapper": {
            "artifact": "run_phase9g_a1r_recoverability_continuation.py",
            "file_sha256": _file_sha(wrapper_path),
            "qualification_commit": WRAPPER_COMMIT,
            "scientific_functions_reused_from_image": [
                "produce_recoverability_candidate",
                "reconcile_recoverability_candidate_results",
                "CanonicalGenerationWriter.write_recoverability_transaction",
            ],
        },
        "evidence": {
            "timeout_derivation_sha256": timeout[
                "phase9g_a1r_timeout_derivation_sha256"
            ],
            "failure_injection_sha256": failure[
                "phase9g_a1r_timeout_failure_injection_result_sha256"
            ],
            "scientific_semantic_equality": True,
            "resume_identity_tests": "tests/test_phase9g_a1r_continuation.py",
        },
        "residual_profile_changed": False,
        "frozen_science_changed": False,
        "official_resume_permitted_after_preflight": True,
    }
    amendment = _write(
        out / "phase9g_a1r_operational_contract_amendment_v1.json",
        amendment,
        "phase9g_a1r_operational_contract_amendment_sha256",
    )

    statement = {
        "phase": "PHASE_9G_A1R",
        "authorization": (
            "operational-only Recoverability timeout requalification and exact "
            "official Study-A train then validation continuation"
        ),
        "preserve_existing_staging_rows": 318,
        "prohibited": [
            "Residual V2", "training", "Study A N24", "Study B", "final test",
        ],
    }
    auth = {
        "schema_version": "rvt-phase9g-a1r-authorization-continuation/v1",
        "phase": "PHASE_9G_A1R",
        "created_at_utc": CREATED_AT,
        "authorization_source": {
            "kind": "EXPLICIT_OWNER_INSTRUCTION_IN_CURRENT_TASK",
            "semantic_statement": statement,
            "semantic_statement_sha256": sha256_document(statement),
        },
        "parent_authorization": {
            "artifact": "phase9g_a1_owner_authorization_v1.json",
            "sha256": old_auth["phase9g_a1_owner_authorization_sha256"],
            "binds_old_operational_contract": True,
        },
        "operational_amendment_sha256": amendment[
            "phase9g_a1r_operational_contract_amendment_sha256"
        ],
        "authorized_scope": {
            "study": "study_a_zero_shot",
            "splits": ["train", "validation"],
            "branch": "recoverability",
            "operation": "OFFICIAL_STAGING_CONTINUATION",
            "train_before_validation": True,
        },
        "scope_artifacts": {
            "train": {
                "artifact": (
                    "phase9g_a1_authorization_scope_study_a_zero_shot-train-"
                    "recoverability_v1.json"
                ),
                "sha256": "77319fcfd8822f56763ed09b7e9c71c3dcc851ea810165d301acacc2388d773a",
            },
            "validation": {
                "artifact": (
                    "phase9g_a1_authorization_scope_study_a_zero_shot-validation-"
                    "recoverability_v1.json"
                ),
                "sha256": "9a1e7d7fee28d74c8411e1b162066e34ed08b4e52156d859afe71088ad869c6b",
            },
        },
        "bindings": {
            "scientific_source_commit": SCIENTIFIC_SOURCE,
            "production_image": IMAGE,
            "generation_provenance_root": parent_run["generation_provenance_root"],
            "scientific_addendum_sha256": old_contract["common"][
                "scientific_addendum_sha256"
            ],
            "job_manifest_sha256": (
                "801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3"
            ),
        },
        "scope_status": {
            "RECOVERABILITY_STUDY_A_TRAIN_VALIDATION": "AUTHORIZED_CONTINUATION",
            "RESIDUAL_V2": "NOT_AUTHORIZED_IN_PHASE_9G_A1R",
            "TRAINING": "NOT_AUTHORIZED",
            "STUDY_A_N24": "SEALED_NOT_AUTHORIZED",
            "STUDY_B": "NOT_AUTHORIZED",
            "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
        },
        "broadens_parent_scientific_scope": False,
        "scientific_outcomes_present_in_authorization": False,
    }
    auth = _write(
        out / "phase9g_a1r_authorization_continuation_v1.json",
        auth,
        "phase9g_a1r_authorization_continuation_sha256",
    )

    run = {
        "schema_version": "rvt-phase9g-a1r-continuation-run-identity/v1",
        "phase": "PHASE_9G_A1R",
        "created_at_utc": CREATED_AT,
        "identity_class": "OPERATIONAL_SUCCESSOR_CONTINUATION_NOT_SCIENTIFIC",
        "run_id": RUN_ID,
        "parent_run_id": PARENT_RUN_ID,
        "parent_run_identity_sha256": parent_run[
            "phase9g_a1_recoverability_run_identity_sha256"
        ],
        "successor_required_reason": (
            "parent run identity immutably binds the superseded 60 s profile"
        ),
        "scientific_dataset_lineage_id": (
            "phase9g-a1-study-a-train-validation-recoverability-v1"
        ),
        "logically_independent_dataset": False,
        "scientific_row_identity_includes_run_id": False,
        "same_staging_namespace_as_parent": True,
        "writer_namespaces": parent_run["writer_namespaces"],
        "authorization_continuation_sha256": auth[
            "phase9g_a1r_authorization_continuation_sha256"
        ],
        "operational_amendment_sha256": amendment[
            "phase9g_a1r_operational_contract_amendment_sha256"
        ],
        "source_commit": SCIENTIFIC_SOURCE,
        "production_image": IMAGE,
        "initial_staging_checkpoint": {
            "artifact": "phase9g_a1r_staging_checkpoint_v1.json",
            "sha256": checkpoint["phase9g_a1r_staging_checkpoint_sha256"],
            "checkpoint_preimage_sha256": checkpoint[
                "staging_checkpoint_preimage_sha256"
            ],
            "completed_train_events": len(completed),
            "completed_train_candidate_aggregates": checkpoint[
                "completed_atomic_unit_count"
            ],
            "scientific_rows": checkpoint["scientific_row_count"],
        },
        "frozen_universe": {
            "train_events": len(train_tasks),
            "train_candidate_aggregates": 2 * len(train_tasks),
            "validation_events": len(validation_tasks),
            "validation_candidate_aggregates": 2 * len(validation_tasks),
            "total_events": len(train_tasks) + len(validation_tasks),
            "total_candidate_aggregates": 2 * (
                len(train_tasks) + len(validation_tasks)
            ),
            "initial_unresolved_train_events": len(train_tasks) - len(completed),
        },
        "resume_semantics": {
            "schedule_only_unresolved_event_identities": True,
            "existing_rows_reemitted": 0,
            "completed_candidate_pair_transactions_rescheduled": 0,
            "timed_out_atomic_unit_eligible_for_exact_retry": True,
            "scientific_retry_count": 0,
            "infrastructure_continuation": True,
        },
        "operational_profile": amendment["recoverability_profile"],
        "required_order": ["train", "validation", "stop"],
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
        "state_at_creation": "CREATED_NOT_STARTED",
    }
    _write(
        out / "phase9g_a1r_continuation_run_identity_v1.json",
        run,
        "phase9g_a1r_continuation_run_identity_sha256",
    )


if __name__ == "__main__":
    main()
