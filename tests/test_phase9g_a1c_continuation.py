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
