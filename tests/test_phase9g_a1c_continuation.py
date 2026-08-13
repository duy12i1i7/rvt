"""Operational authority and exact-prefix tests for Phase 9G-A1C."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from scripts.run_phase9g_a1c_recoverability_train_continuation import (
    ContinuationError,
    validate_exact_checkpoint,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _canonical(name: str, field: str) -> dict:
    document = json.loads((RESULTS / name).read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop(field)
    assert sha256_document(body) == expected
    return document


def test_a1c_authorization_is_train_only_and_fail_closed() -> None:
    document = _canonical(
        "phase9g_a1c_owner_authorization_continuation_v1.json",
        "phase9g_a1c_owner_authorization_continuation_sha256",
    )
    assert document["authorized_scope"]["splits"] == ["train"]
    assert document["authorized_scope"]["branch"] == "recoverability"
    assert document["existing_data_action"] == "RETAIN_ALL_342"
    assert document["scope_status"] == {
        "RECOVERABILITY_TRAIN": "AUTHORIZED_CONTINUATION",
        "RECOVERABILITY_VALIDATION": "NOT_AUTHORIZED_YET",
        "RESIDUAL_V2": "NOT_AUTHORIZED",
        "TRAINING": "NOT_AUTHORIZED",
        "STUDY_A_N24": "SEALED_NOT_AUTHORIZED",
        "STUDY_B": "NOT_AUTHORIZED",
        "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
    }
    assert document["broadens_scientific_scope"] is False


def test_a1c_run_identity_preserves_dataset_and_exact_resume_boundary() -> None:
    document = _canonical(
        "phase9g_a1c_continuation_run_identity_v1.json",
        "phase9g_a1c_continuation_run_identity_sha256",
    )
    assert document["logically_independent_dataset"] is False
    assert document["same_staging_namespace_as_parent"] is True
    assert document["scientific_row_identity_includes_run_id"] is False
    assert document["initial_staging_checkpoint"] == {
        "artifact": "phase9g_a1c_staging_precheck_v1.json",
        "sha256": "72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f",
        "completed_train_events": 210,
        "scientific_rows": 342,
    }
    assert document["resume_semantics"]["existing_rows_reemitted"] == 0
    assert document["required_order"] == ["train", "stop_before_validation"]


def test_remaining_s3_guard_has_explicit_nonconflated_counter_levels() -> None:
    document = _canonical(
        "phase9g_a1c_s3_prestart_guard_reference_v1.json",
        "phase9g_a1c_s3_prestart_guard_sha256",
    )
    counters = document["counter_levels"]
    assert document["status"] == "PASS"
    assert document["scope"]["remaining_s3_source_instances"] == 194
    assert document["scope"]["remaining_s3_event_identities"] == 970
    assert counters["source_s3_instances"] == 194
    assert counters["robot_local_s3_observations"] == 1766
    assert counters["participating_support_observations"] == 3921
    assert counters["resolved_opposing_pairs"] == 248
    assert counters["hold_unknown_robot_observations"] == 1518
    assert counters["unresolved_s3_ambiguities"] == 0
    assert document["scientific_writes"] == 0


def _checkpoint_fixture(root: Path) -> tuple[Path, dict]:
    row_ids = [f"row-{index:03d}" for index in range(342)]
    body = {
        "schema_version": "test",
        "writer_mode": "OFFICIAL_STAGING",
        "decision_event_id": "event-a",
        "scientifically_reconciled": True,
        "scientific_completion_marker": True,
        "rows": [{"scientific_row_id": value} for value in row_ids],
        "actual_row_count": 342,
    }
    document = attach_canonical_hash(body, "canonical_record_sha256")
    path = root / "recoverability/event-a.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="ascii")
    checkpoint = {
        "candidate_pair_transactions": [{
            "decision_event_id": "event-a",
            "file_name": path.name,
            "canonical_record_sha256": document["canonical_record_sha256"],
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "scientific_row_ids": row_ids,
        }],
        "scientific_row_ids": row_ids,
    }
    return path, checkpoint


def test_exact_checkpoint_accepts_only_byte_identical_original_rows(tmp_path: Path) -> None:
    path, checkpoint = _checkpoint_fixture(tmp_path)
    assert validate_exact_checkpoint(tmp_path, checkpoint) == frozenset({"event-a"})
    path.write_text(path.read_text(encoding="ascii") + " ", encoding="ascii")
    with pytest.raises(ContinuationError, match="file hash"):
        validate_exact_checkpoint(tmp_path, checkpoint)


def test_current_roots_and_staging_checkpoint_are_canonical() -> None:
    root = _canonical(
        "phase9g_a1c_current_root_validation_v1.json",
        "phase9g_a1c_current_root_validation_sha256",
    )
    checkpoint = _canonical(
        "phase9g_a1c_staging_precheck_v1.json",
        "phase9_s3_staging_checkpoint_sha256",
    )
    assert root["status"] == "PASS"
    assert root["historical_roots_rewritten"] is False
    assert checkpoint["prefix"]["train_events"] == 210
    assert checkpoint["prefix"]["scientific_rows"] == 342
    assert checkpoint["prefix"]["partial_candidate_pair_publications"] == 0


def test_attempt1_startup_requalification_has_no_scientific_effect() -> None:
    document = _canonical(
        "phase9g_a1c_startup_requalification_v1.json",
        "phase9g_a1c_startup_requalification_sha256",
    )
    assert document["status"] == "PASS_OPERATIONAL_RETRY_PERMITTED"
    assert document["attempt"]["classification"] == (
        "OPERATIONAL_DEPLOYMENT_IMPORT_BINDING"
    )
    assert document["scientific_effect"] == {
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
        "checkpoint_sha256": (
            "72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f"
        ),
    }
    assert document["repair"]["module_before"]["status_hash_field_present"] is False
    assert document["repair"]["module_after"]["status_hash_field_present"] is True
    assert document["repair"]["scientific_source_image_changed"] is False
    assert document["repair"]["operational_wrapper_bytes_changed"] is False


def test_official_train_completion_reconciles_and_stops_before_validation() -> None:
    audit = _canonical(
        "phase9g_a1c_official_train/official_train_continuation_audit.json",
        "phase9g_a1c_official_train_continuation_audit_sha256",
    )
    reconciliation = _canonical(
        "phase9g_a1c_official_train/train_reconciliation.json",
        "phase9g_a1c_recoverability_train_reconciliation_sha256",
    )
    assert audit["status"] == "PASS"
    assert audit["complete_train"] == {
        "source_episodes": 1200,
        "events": 6000,
        "candidate_aggregates": 12000,
        "replica_executions": 1094,
        "scientific_rows": 8340,
        "candidate_pair_retained_events": 443,
        "candidate_pair_dropped_events": 5557,
        "candidate_dispositions": {
            "GENERATION_INVALID": 11114,
            "RECOVERABLE_POSITIVE": 532,
            "VALID_TASK_NEGATIVE": 354,
        },
    }
    observed = reconciliation["observed"]
    assert observed["unresolved_infrastructure_failures"] == 0
    assert observed["unexpected_duplicate_transactions"] == 0
    assert observed["duplicate_scientific_identities"] == 0
    assert observed["partial_candidate_pair_publications"] == 0
    assert observed["hash_failures"] == 0
    assert observed["schema_failures"] == 0
    assert observed["seed_mismatches"] == 0
    assert observed["seal_violations"] == 0
    assert audit["downstream"] == {
        "recoverability_validation_started": False,
        "residual_v2_started": False,
        "training_operations": 0,
    }


def test_final_train_dataset_manifest_and_independent_validation_pass() -> None:
    manifest = _canonical(
        "phase9g_a1c_official_train/dataset_manifest.json",
        "dataset_manifest_sha256",
    )
    seal = _canonical(
        "phase9g_a1c_official_train/DATASET_SEAL.json",
        "dataset_seal_sha256",
    )
    validation = _canonical(
        "phase9g_a1c_official_train/postfinal_dataset_validation.json",
        "phase9g_a1c_postfinal_dataset_validation_sha256",
    )
    assert manifest["status"] == "VALID_FROZEN_TRAIN_ONLY"
    assert manifest["splits"] == ["train"]
    assert manifest["validation_included"] is False
    assert manifest["scientific_row_count"] == 8340
    assert manifest["transaction_count"] == 6000
    assert sum(item["row_count"] for item in manifest["shards"]) == 8340
    assert seal["dataset_manifest_sha256"] == manifest["dataset_manifest_sha256"]
    assert seal["further_staging_writes_permitted"] is False
    assert seal["recoverability_validation_authorized"] is False
    assert validation["status"] == "PASS"
    assert validation["validated"]["transaction_hardlink_matches"] == 6000
    assert validation["validated"]["unique_scientific_row_ids"] == 8340
    assert all(value == 0 for value in manifest["integrity"].values())
    assert all(value == 0 for value in manifest["sealed_domains"].values())


def test_descriptive_quality_audit_uses_exact_repository_dispositions() -> None:
    quality = _canonical(
        "phase9g_a1c_official_train/train_data_quality_audit.json",
        "phase9g_a1c_train_data_quality_audit_sha256",
    )
    assert quality["status"] == "PASS_DESCRIPTIVE_ONLY"
    assert quality["totals"] == {
        "source_episodes": 1200,
        "decision_events": 6000,
        "candidate_aggregates": 12000,
        "RECOVERABLE_POSITIVE": 532,
        "VALID_TASK_NEGATIVE": 354,
        "GENERATION_INVALID": 11114,
        "candidate_pair_retained_events": 443,
        "candidate_pair_dropped_nonpublished_events": 5557,
        "scientific_rows": 8340,
    }
    reasons = {}
    for record in quality["scientific_invalid_reason_distribution"]:
        reasons[record["reason"]] = reasons.get(record["reason"], 0) + record["count"]
    assert reasons == {
        "SOURCE_TERMINATED_BEFORE_EVENT:COLLISION": 3517,
        "SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE": 1920,
        "SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID": 120,
    }
    assert quality["s3"]["complete_train_source_instances"] == 200
    assert quality["s3"]["complete_train_decision_events"] == 1000
    assert quality["s3"]["unresolved_ambiguities"] == 0
    assert quality["class_weighting"] == "NOT_SELECTED"
    assert quality["descriptive_only"] is True
