"""RB-21 artifacts, scoped authorization and target-environment hard stop."""

from __future__ import annotations

import hashlib
import json
import pathlib

from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase9c_rb21.rb21_preflight import operational_checks

ROOT = pathlib.Path("results/rvt_fd24")


def _load(name):
    return json.loads((ROOT / name).read_text())


ENV = _load("rb21_target_environment_qualification_v1.json")
CONTRACT = _load("rb21_operational_execution_contract_v1.json")
AUTH = _load("rb21_authorization_scope_v1.json")
JOB = _load("rb21_operational_job_manifest_v1.json")
PREFLIGHT = _load("rb21_operational_preflight_v1.json")
READINESS = _load("rb21_generation_readiness_v1.json")
FAILURE = _load("rb21_resume_failure_qualification_v1.json")


def _assert_hash(document, field):
    body = {key: value for key, value in document.items() if key != field}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == document[field]


def test_all_rb21_artifacts_hash_canonically() -> None:
    for file_name, field in (
        ("rb21_target_environment_qualification_v1.json",
         "target_environment_qualification_sha256"),
        ("rb21_benchmark_manifest_v1.json", "rb21_benchmark_manifest_sha256"),
        ("rb21_performance_benchmark_v1.json", "rb21_performance_benchmark_sha256"),
        ("rb21_worker_chunk_scaling_v1.json", "rb21_worker_chunk_scaling_sha256"),
        ("rb21_storage_capacity_v1.json", "rb21_storage_capacity_sha256"),
        ("rb21_resume_failure_qualification_v1.json",
         "rb21_resume_failure_qualification_sha256"),
        ("rb21_operational_execution_contract_v1.json",
         "rb21_operational_execution_contract_sha256"),
        ("rb21_authorization_scope_v1.json", "rb21_authorization_scope_sha256"),
        ("rb21_operational_job_manifest_v1.json",
         "rb21_operational_job_manifest_sha256"),
        ("rb21_operational_preflight_v1.json", "rb21_operational_preflight_sha256"),
        ("rb21_generation_readiness_v1.json", "rb21_generation_readiness_sha256"),
    ):
        _assert_hash(_load(file_name), field)


def test_target_environment_hard_stop_leaves_no_guessed_values() -> None:
    assert ENV["qualification_result"] == "TARGET_ENVIRONMENT_NOT_QUALIFIED"
    assert ENV["declared_official_environment_id"] is None
    for field in ("process_worker_count", "residual_chunk_size_atomic_units",
                  "recoverability_chunk_size_atomic_units",
                  "infrastructure_timeout_seconds"):
        assert CONTRACT[field] == "PENDING_TARGET_ENVIRONMENT"
    assert READINESS["verdict"] == "D"


def test_authorization_is_scoped_and_sealed_domains_remain_closed() -> None:
    scopes = AUTH["scopes"]
    assert set(scopes) == {
        "RECOVERABILITY_GENERATION", "RESIDUAL_V2_GENERATION",
        "STUDY_A_TRAIN_VALIDATION", "STUDY_A_N24_ZERO_SHOT", "STUDY_B",
        "FINAL_TEST",
    }
    assert all("AUTHORIZED" not in status or status.startswith("NOT_AUTHORIZED")
               or status.startswith("SEALED_NOT_AUTHORIZED")
               for status in scopes.values())
    assert scopes["STUDY_A_N24_ZERO_SHOT"] == "SEALED_NOT_AUTHORIZED"
    assert scopes["FINAL_TEST"] == "SEALED_NOT_AUTHORIZED"
    assert JOB["study_a_n24_command"] == "NOT_CREATED_SEALED"
    assert JOB["final_test_command"] == "NOT_CREATED_SEALED"
    assert JOB["official_commands"] == []


def test_preflight_science_passes_and_operations_block_only_on_pending_values() -> None:
    assert PREFLIGHT["scientific_preflight_status"] == "PASS"
    assert PREFLIGHT["scientific_failures"] == []
    assert PREFLIGHT["operational_failures"] == [
        "target_environment", "worker_count", "chunk_sizes", "timeout"]
    assert PREFLIGHT["negative_matrix"]["escapes"] == 0
    assert PREFLIGHT["negative_matrix"]["case_count"] >= 13


def test_abrupt_worker_and_between_chunk_failures_preserve_atomic_completion() -> None:
    before = FAILURE["worker_dies_before_complete"]
    after = FAILURE["worker_dies_after_compute_before_ack"]
    between = FAILURE["process_terminates_between_chunks"]
    assert before["exit_code"] != 0 and before["accepted_as_complete"] is False
    assert after["exit_code"] != 0 and after["accepted_as_complete"] is False
    assert between["exit_code"] != 0
    assert between["first_unit_complete"] is True
    assert between["unscheduled_second_unit_complete"] is False
    assert between["resume_rechecks_atomic_unit_ids"] is True
    assert FAILURE["partial_write_accepted"] is False
    assert FAILURE["duplicate_retry_submission"] == "DUPLICATE_IDEMPOTENT"


def test_positive_operational_shape_can_validate_without_changing_science() -> None:
    scientific = {"status": "PASS"}
    environment = {**ENV, "qualification_result": "QUALIFIED"}
    contract = {**CONTRACT, "process_worker_count": 2,
                "residual_chunk_size_atomic_units": 2,
                "recoverability_chunk_size_atomic_units": 2,
                "infrastructure_timeout_seconds": 900}
    checks = operational_checks(scientific, environment, contract, AUTH["scopes"], JOB)
    assert all(check["passed"] for check in checks), checks


def test_no_official_rows_shards_training_or_model_state_were_created() -> None:
    assert set(READINESS["isolation"].values()) == {0}
    assert READINESS["official_phase9_generation_executed"] is False
    assert AUTH["official_generation_authorized"] is False
    assert AUTH["residual_branch_enabled"] is False
    assert READINESS["capacity_projection"]["residual_stored_rows_cap"] == 536000
    assert READINESS["capacity_projection"]["residual_candidate_evaluations"] == 4824000
