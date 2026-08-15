#!/usr/bin/env python3
"""Build validation-only authority and immutable A1V execution manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import (
    JOB_MANIFEST_SHA256,
    compile_recoverability_tasks,
    compile_source_tasks,
)


EVIDENCE_COMMIT = "2f47af531b6b584d9b36c9a38681d20305783e9b"
SOURCE_COMMIT = "848e8b352a91e95af777ebbeccd5fbb43d53777e"
IMAGE = "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
PROVENANCE = "9f209cd4b5ae591b2f576a085bcbdb6b7d30a7f3fecb9840d6e0eb56bb03adc8"
SCIENTIFIC_ADDENDUM = "d216217b3a3dfead5e3249cbf57317a71aa1c479acc840994eec9ff1616da23b"
OPERATIONAL_AMENDMENT = "1821badc6b09c2417a3fff98bb2f97673a69cdeff002b9ac1a64fac927d806e8"
TRAIN_MANIFEST = "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
TRAIN_SEAL = "5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5"
TRAIN_CLOSURE = "10a3c7a6b9058bfc0d513dc2a0c598c6aa0c4ffde9dfd92641fe44f139988e88"
OWNER_INSTRUCTION = "d27c8768e00e10fae8c3d2ce48406d61d751b88ce01ccbb43a16696d15434112"
RUN_ID = "phase9g-a1v-study-a-validation-recoverability-20260815T163005Z"
PARENT_RUN_ID = "phase9g-a1c-study-a-train-recoverability-continuation-20260813T112333Z"
CREATED_AT = "2026-08-15T16:30:05Z"
DATASET_LINEAGE = "phase9g-a1-study-a-train-validation-recoverability-v1"


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(path: Path, field: str) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path}")
    return document


def _write(path: Path, body: Mapping[str, Any], field: str) -> dict[str, Any]:
    document = attach_canonical_hash(dict(body), field)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return document


def _counts(values: list[Any]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(Counter(values).items(), key=lambda x: str(x[0]))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "results/rvt_fd24"
    train = out / "phase9g_a1c_official_train"

    train_manifest = _canonical(train / "dataset_manifest.json", "dataset_manifest_sha256")
    train_seal = _canonical(train / "DATASET_SEAL.json", "dataset_seal_sha256")
    train_closure = _canonical(
        out / "phase9g_a1c_train_closure_v1.json",
        "phase9g_a1c_train_closure_sha256",
    )
    if (
        train_manifest["dataset_manifest_sha256"] != TRAIN_MANIFEST
        or train_seal["dataset_seal_sha256"] != TRAIN_SEAL
        or train_closure["phase9g_a1c_train_closure_sha256"] != TRAIN_CLOSURE
        or train_manifest["scientific_row_count"] != 8340
        or train_manifest["transaction_count"] != 6000
        or train_manifest["completion_state"] != "COMPLETE"
        or train_manifest["validation_included"] is not False
        or train_seal["dataset_manifest_sha256"] != TRAIN_MANIFEST
        or train_seal["further_staging_writes_permitted"] is not False
        or any(train_manifest["integrity"].values())
    ):
        raise ValueError("authoritative TRAIN closure changed")

    sources = compile_source_tasks(root, study="study_a_zero_shot", split="validation")
    tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="validation"
    )
    if len(sources) != 300 or len(tasks) != 1500:
        raise ValueError("authoritative VALIDATION universe changed")
    if any(task.source.team_size == 24 for task in tasks):
        raise ValueError("Study A N24 entered VALIDATION compilation")
    source_ids = {source.job_id for source in sources}
    if len(source_ids) != 300 or len({task.event_id for task in tasks}) != 1500:
        raise ValueError("duplicate VALIDATION scientific identity")

    train_precheck = _write(
        out / "phase9g_a1v_train_seal_precheck_v1.json",
        {
            "schema_version": "rvt-phase9g-a1v-train-seal-precheck/v1",
            "phase": "PHASE_9G_A1V",
            "status": "PASS_IMMUTABLE",
            "train_dataset_id": train_manifest["dataset_id"],
            "train_manifest_sha256": TRAIN_MANIFEST,
            "train_seal_sha256": TRAIN_SEAL,
            "train_closure_sha256": TRAIN_CLOSURE,
            "train_accounting": {
                "source_episodes": 1200,
                "decision_events": 6000,
                "candidate_aggregates": 12000,
                "RECOVERABLE_POSITIVE": 532,
                "VALID_TASK_NEGATIVE": 354,
                "GENERATION_INVALID": 11114,
                "candidate_pair_retained_events": 443,
                "candidate_pair_dropped_events": 5557,
                "scientific_rows": 8340,
                "duplicate_scientific_identities": 0,
                "partial_candidate_pair_publications": 0,
                "unresolved_infrastructure_failures": 0,
            },
            "train_namespace_mutation_authorized": False,
            "validation_rows_append_to_train": False,
            "validated_files": {
                "manifest_file_sha256": _file_sha(train / "dataset_manifest.json"),
                "seal_file_sha256": _file_sha(train / "DATASET_SEAL.json"),
            },
        },
        "phase9g_a1v_train_seal_precheck_sha256",
    )

    validation_manifest = _write(
        out / "phase9g_a1v_validation_task_manifest_v1.json",
        {
            "schema_version": "rvt-phase9g-a1v-validation-task-manifest/v1",
            "phase": "PHASE_9G_A1V",
            "status": "FROZEN_PREEXECUTION",
            "study": "study_a_zero_shot",
            "split": "validation",
            "branch": "recoverability",
            "job_manifest_sha256": JOB_MANIFEST_SHA256,
            "source_episodes": len(sources),
            "decision_events": len(tasks),
            "candidate_aggregates": 2 * len(tasks),
            "candidate_replica_slots": sum(
                2 * task.replicas_per_candidate for task in tasks
            ),
            "robot_local_row_capacity": sum(
                2 * task.source.team_size for task in tasks
            ),
            "family_source_counts": _counts([source.family for source in sources]),
            "family_event_counts": _counts([task.source.family for task in tasks]),
            "team_size_source_counts": _counts([source.team_size for source in sources]),
            "team_size_event_counts": _counts([task.source.team_size for task in tasks]),
            "replicas_per_candidate_event_counts": _counts(
                [task.replicas_per_candidate for task in tasks]
            ),
            "source_class_counts": _counts([source.source_class for source in sources]),
            "source_task_ids": sorted(source_ids),
            "decision_event_tasks": [
                {
                    "decision_event_id": task.event_id,
                    "source_task_id": task.source.job_id,
                    "family": task.source.family,
                    "layout_id": task.source.layout_id,
                    "layout_sha256": task.source.layout_sha256,
                    "layout_source_split": task.source.layout_source_split,
                    "team_size": task.source.team_size,
                    "source_class": task.source.source_class,
                    "episode_index": task.source.episode_index,
                    "event_slot_index": task.event_slot_index,
                    "resolved_control_step": task.resolved_control_step,
                    "replicas_per_candidate": task.replicas_per_candidate,
                    "candidate_replica_jobs": list(task.candidate_replica_jobs),
                }
                for task in tasks
            ],
            "sealed_domains": {
                "study_a_n24_tasks": 0,
                "study_b_tasks": 0,
                "final_test_tasks": 0,
            },
        },
        "phase9g_a1v_validation_task_manifest_sha256",
    )

    scope = _write(
        out / "phase9g_a1v_authorization_scope_study_a_zero_shot-validation-recoverability_v1.json",
        {
            "schema_version": "rvt-phase9g-a1v-authorization-scope/v1",
            "phase": "PHASE_9G_A1V",
            "authorization_class": "AUTHORIZED_STUDY_A_RECOVERABILITY_VALIDATION_ONLY",
            "binding": {
                "study": "study_a_zero_shot",
                "split": "validation",
                "branch": "recoverability",
                "source_commit": SOURCE_COMMIT,
                "docker_image": IMAGE,
                "scientific_addendum_sha256": SCIENTIFIC_ADDENDUM,
                "generation_provenance_root": PROVENANCE,
            },
            "official_generation_execution_authorized": True,
            "broad_authorization": False,
            "scientific_outcomes_present": False,
            "sealed_exclusions": [
                "recoverability_train_modification",
                "residual_v2",
                "training",
                "hyperparameter_search",
                "class_weight_selection",
                "study_a_n24_zero_shot",
                "study_b",
                "final_test",
            ],
        },
        "phase9_authorization_scope_sha256",
    )

    authorization = _write(
        out / "phase9g_a1v_owner_authorization_v1.json",
        {
            "schema_version": "rvt-phase9g-a1v-owner-authorization/v1",
            "phase": "PHASE_9G_A1V",
            "created_at_utc": CREATED_AT,
            "authorization_source": {
                "kind": "EXPLICIT_OWNER_INSTRUCTION_IN_CURRENT_TASK",
                "instruction_file_sha256": OWNER_INSTRUCTION,
            },
            "authorized_scope": {
                "study": "study_a_zero_shot",
                "splits": ["validation"],
                "branch": "recoverability",
                "operation": "OFFICIAL_VALIDATION_STAGING_AND_FINALIZATION",
            },
            "authorization_scope_sha256": scope["phase9_authorization_scope_sha256"],
            "bindings": {
                "evidence_commit": EVIDENCE_COMMIT,
                "executable_source_commit": SOURCE_COMMIT,
                "production_image": IMAGE,
                "scientific_provenance_root": PROVENANCE,
                "scientific_addendum_sha256": SCIENTIFIC_ADDENDUM,
                "job_manifest_sha256": JOB_MANIFEST_SHA256,
                "operational_amendment_sha256": OPERATIONAL_AMENDMENT,
                "train_manifest_sha256": TRAIN_MANIFEST,
                "train_seal_sha256": TRAIN_SEAL,
                "train_closure_sha256": TRAIN_CLOSURE,
                "train_seal_precheck_sha256": train_precheck[
                    "phase9g_a1v_train_seal_precheck_sha256"
                ],
                "validation_task_manifest_sha256": validation_manifest[
                    "phase9g_a1v_validation_task_manifest_sha256"
                ],
            },
            "qualified_profile": {
                "workers": 12,
                "numeric_threads_per_worker": 1,
                "chunk_size_atomic_units": 1,
                "infrastructure_timeout_seconds": 243,
            },
            "scope_status": {
                "RECOVERABILITY_TRAIN_MODIFICATION": "NOT_AUTHORIZED",
                "RECOVERABILITY_VALIDATION": "AUTHORIZED",
                "RESIDUAL_V2": "NOT_AUTHORIZED",
                "TRAINING": "NOT_AUTHORIZED",
                "HYPERPARAMETER_SEARCH": "NOT_AUTHORIZED",
                "CLASS_WEIGHT_SELECTION": "NOT_AUTHORIZED",
                "STUDY_A_N24": "SEALED_NOT_AUTHORIZED",
                "STUDY_B": "NOT_AUTHORIZED",
                "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
            },
            "broadens_scientific_scope": False,
            "scientific_outcomes_present_in_authorization": False,
        },
        "phase9g_a1v_owner_authorization_sha256",
    )

    run = _write(
        out / "phase9g_a1v_validation_run_identity_v1.json",
        {
            "schema_version": "rvt-phase9g-a1v-validation-run-identity/v1",
            "phase": "PHASE_9G_A1V",
            "created_at_utc": CREATED_AT,
            "run_id": RUN_ID,
            "parent_run_id": PARENT_RUN_ID,
            "identity_class": "OFFICIAL_DISTINCT_VALIDATION_RUN",
            "scientific_dataset_lineage_id": DATASET_LINEAGE,
            "writer_namespace": "staging/study_a_zero_shot-validation-recoverability",
            "final_dataset_id": "phase9g-a1-study-a-validation-recoverability-v1",
            "train_namespace": "final/phase9g-a1-study-a-train-recoverability-v1",
            "train_namespace_mutable": False,
            "shared_mutable_indexes_with_train": False,
            "authorization_sha256": authorization[
                "phase9g_a1v_owner_authorization_sha256"
            ],
            "authorization_scope_sha256": scope["phase9_authorization_scope_sha256"],
            "validation_task_manifest_sha256": validation_manifest[
                "phase9g_a1v_validation_task_manifest_sha256"
            ],
            "frozen_validation_universe": {
                "source_episodes": len(sources),
                "decision_events": len(tasks),
                "candidate_aggregates": 2 * len(tasks),
                "candidate_replica_slots": sum(
                    2 * task.replicas_per_candidate for task in tasks
                ),
            },
            "sealed_scope": {
                "recoverability_train_modifications": 0,
                "residual_operations": 0,
                "training_operations": 0,
                "hyperparameter_trials": 0,
                "study_a_n24_accesses": 0,
                "study_b_accesses": 0,
                "final_test_accesses": 0,
            },
        },
        "phase9g_a1v_validation_run_identity_sha256",
    )
    print(json.dumps({
        "run_id": RUN_ID,
        "train_precheck": train_precheck["phase9g_a1v_train_seal_precheck_sha256"],
        "task_manifest": validation_manifest["phase9g_a1v_validation_task_manifest_sha256"],
        "scope": scope["phase9_authorization_scope_sha256"],
        "authorization": authorization["phase9g_a1v_owner_authorization_sha256"],
        "run_identity": run["phase9g_a1v_validation_run_identity_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
