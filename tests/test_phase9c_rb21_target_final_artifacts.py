"""Final RB21 target evidence is canonical, linked, and remains isolated."""

import json
import math
from pathlib import Path

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase9c_rb21.rb21_manifest import (
    RB19_PROVENANCE_ROOT,
    RB20_REPRODUCTION_HASH,
    RB21P_PORTABILITY_ARTIFACT_HASH,
    RB21P_QUALIFIED_IMAGE,
    RB21P_REQUALIFICATION_ROOT,
    RB21P_SOURCE_CHECKPOINT,
    TARGET_V4_HASH,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


ARTIFACTS = (
    ("rb21_target_environment_qualification_v2.json",
     "rb21_target_environment_qualification_v2_sha256"),
    ("rb21_target_single_worker_benchmark_v1.json",
     "rb21_target_single_worker_benchmark_sha256"),
    ("rb21_target_storage_capacity_v2.json",
     "rb21_target_storage_capacity_v2_sha256"),
    ("rb21_target_writer_qualification_v1.json",
     "rb21_target_writer_qualification_sha256"),
    ("rb21_target_resume_failure_qualification_v2.json",
     "rb21_target_resume_failure_qualification_v2_sha256"),
    ("rb21_target_timeout_derivation_v1.json",
     "rb21_target_timeout_derivation_sha256"),
    ("rb21_target_capacity_estimate_v1.json",
     "rb21_target_capacity_estimate_sha256"),
    ("rb21_target_h4_result_v1.json", "rb21_target_h4_result_sha256"),
    ("rb21_target_gpu_generation_observation_v1.json",
     "rb21_target_gpu_generation_observation_sha256"),
    ("rb21_target_authorization_scope_v2.json",
     "rb21_target_authorization_scope_v2_sha256"),
    ("rb21_target_operational_execution_contract_v2.json",
     "rb21_target_operational_execution_contract_v2_sha256"),
    ("rb21_target_official_command_plan_v1.json",
     "rb21_target_official_command_plan_sha256"),
    ("rb21_target_operational_job_manifest_v2.json",
     "rb21_target_operational_job_manifest_v2_sha256"),
    ("rb21_target_operational_preflight_v2.json",
     "rb21_target_operational_preflight_v2_sha256"),
    ("rb21_target_generation_readiness_v2.json",
     "rb21_target_generation_readiness_v2_sha256"),
)


def test_all_final_target_artifacts_have_valid_canonical_hashes() -> None:
    for name, field in ARTIFACTS:
        assert verify_canonical_hash(_load(name), field), name


def test_readiness_root_links_every_final_artifact() -> None:
    readiness = _load("rb21_target_generation_readiness_v2.json")
    linked = set(readiness["artifacts"].values())
    for name, field in ARTIFACTS[:-1]:
        assert _load(name)[field] in linked, name
    assert readiness["verdict"] == "C"
    assert readiness["scientific_source_checkpoint"] == RB21P_SOURCE_CHECKPOINT
    assert readiness["qualified_docker_image"] == RB21P_QUALIFIED_IMAGE
    assert readiness["scientific_semantics_changed"] is False


def test_environment_and_contract_pin_authoritative_provenance() -> None:
    environment = _load("rb21_target_environment_qualification_v2.json")
    contract = _load("rb21_target_operational_execution_contract_v2.json")
    assert environment["qualification_result"] == "QUALIFIED"
    assert environment["windows"]["hostname"] == "AVIS"
    assert environment["wsl"]["cpus"] == 24
    assert environment["docker"]["image_digest"] == RB21P_QUALIFIED_IMAGE
    assert contract["scientific_source_checkpoint"] == RB21P_SOURCE_CHECKPOINT
    assert contract["qualified_docker_image"] == RB21P_QUALIFIED_IMAGE
    assert contract["references"]["rb19_current_provenance_root"] == (
        RB19_PROVENANCE_ROOT)
    assert contract["references"]["rb20_reproduction"] == RB20_REPRODUCTION_HASH
    assert contract["references"]["target_v4"] == TARGET_V4_HASH
    assert contract["references"]["rb21p_portability_artifact"] == (
        RB21P_PORTABILITY_ARTIFACT_HASH)
    assert contract["references"]["rb21p_portability_root"] == (
        RB21P_REQUALIFICATION_ROOT)


def test_selected_worker_thread_and_chunk_configuration_is_measured() -> None:
    worker = _load("rb21_target_worker_scaling_v1.json")
    chunk = _load("rb21_target_chunk_scaling_v1.json")
    contract = _load("rb21_target_operational_execution_contract_v2.json")
    assert worker["all_semantic_digests_equal"] is True
    assert chunk["all_semantic_digests_equal"] is True
    assert worker["selected_worker_count"] == 12
    assert contract["process_worker_count"] == 12
    assert set(contract["nested_thread_settings"].values()) == {1}
    assert chunk["selected_recoverability_chunk_size_atomic_units"] == 1
    assert chunk["selected_residual_chunk_size_atomic_units"] == 1
    assert contract["recoverability_chunk_size_atomic_units"] == 1
    assert contract["residual_chunk_size_atomic_units"] == 1


def test_timeout_is_derived_from_tail_and_is_infrastructure_only() -> None:
    timeout = _load("rb21_target_timeout_derivation_v1.json")
    expected = 3.0 * max(timeout["scaled_worst_case_seconds"].values()) + 60.0
    assert math.isclose(timeout["unrounded_safety_bound_seconds"], expected)
    assert 900.0 < expected < 1200.0
    assert timeout["selected_timeout_seconds"] == 1200
    assert timeout["historical_1800_seconds_authoritative"] is False
    assert timeout["classification"] == "INFRASTRUCTURE_FAILURE"
    assert timeout["changes_scientific_horizon"] is False
    assert timeout["emits_target_row"] is False
    assert timeout["timeout_probe"]["target_v4_evaluated_from_timeout"] is False


def test_storage_and_capacity_use_frozen_upper_bounds() -> None:
    storage = _load("rb21_target_storage_capacity_v2.json")
    capacity = _load("rb21_target_capacity_estimate_v1.json")
    projection = storage["projection"]
    assert projection["scientific_payload_bytes"] == 3_377_407_600
    assert projection["audit_payload_bytes"] == 6_533_802_400
    assert projection["index_and_manifest_bytes"] == 235_473_190
    assert projection["staging_plus_final_plus_resume_plus_temporary_upper_bytes"] == (
        23_032_970_842)
    assert storage["headroom_ratio"] > 44.0
    assert storage["qualification_result"] == "PASS"
    assert capacity["recoverability"]["atomic_units"] == 30_600
    assert capacity["recoverability"]["replica_rollouts"] == 42_840
    assert capacity["residual_v2"]["expert_decisions_upper_cap"] == 536_000
    assert capacity["residual_v2"]["candidate_evaluations_upper_bound"] == 4_824_000
    assert capacity["recoverability"]["estimated_wall_days"] < 1.08
    assert 25.47 < capacity["residual_v2"]["estimated_wall_days_upper_bound"] < 25.48


def test_writer_and_resume_failure_gates_pass() -> None:
    writer = _load("rb21_target_writer_qualification_v1.json")
    resume = _load("rb21_target_resume_failure_qualification_v2.json")
    assert writer["selected_worker_count"] == 12
    assert writer["selected_measurement"]["all_commits_validate"] is True
    assert writer["writer_is_throughput_bottleneck"] is False
    assert writer["writer_to_scientific_rate_ratio"] > 250.0
    assert resume["qualification_result"] == "PASS"
    assert resume["semantic_retries"] == 0
    assert resume["duplicate_scientific_rows"] == 0
    assert resume["changed_scientific_identities"] == 0
    assert resume["partial_records_accepted_as_complete"] == 0


def test_h4_and_authorization_are_explicitly_scoped() -> None:
    h4 = _load("rb21_target_h4_result_v1.json")
    authorization = _load("rb21_target_authorization_scope_v2.json")
    scopes = authorization["scopes"]
    assert h4["classification"] == "H4_OPERATIONAL_RISK_BUT_FEASIBLE"
    assert scopes["RECOVERABILITY_GENERATION"].startswith("AUTHORIZED_ON_EXPLICIT")
    assert scopes["RESIDUAL_V2_GENERATION"].startswith("AUTHORIZED_ON_EXPLICIT")
    assert scopes["STUDY_A_TRAIN_VALIDATION"].startswith("AUTHORIZED_ON_EXPLICIT")
    assert scopes["STUDY_B"].startswith("AUTHORIZED_ON_EXPLICIT")
    assert scopes["STUDY_A_N24_ZERO_SHOT"] == "SEALED_NOT_AUTHORIZED"
    assert scopes["FINAL_TEST"] == "SEALED_NOT_AUTHORIZED"
    assert authorization["owner_instruction_required"] is True


def test_preflight_passes_and_all_negative_cases_are_rejected() -> None:
    preflight = _load("rb21_target_operational_preflight_v2.json")
    assert preflight["status"] == "PASS"
    assert preflight["failures"] == []
    assert preflight["negative_matrix"]["case_count"] == 15
    assert preflight["negative_matrix"]["escapes"] == 0
    assert all(row["rejected"] for row in preflight["negative_matrix"]["cases"])


def test_command_plan_is_prepared_unexecuted_and_has_no_sealed_commands() -> None:
    plan = _load("rb21_target_official_command_plan_v1.json")
    assert plan["prepared"] is True
    assert plan["executed"] is False
    assert plan["commands_begin_in"] == "STAGING"
    assert len(plan["launch_specifications"]) == 8
    assert all(spec["job_selector"]["split"] in {"train", "validation"}
               for spec in plan["launch_specifications"])
    assert all(spec["job_selector"]["sealed"] is False
               for spec in plan["launch_specifications"])
    assert plan["study_a_n24_command"] == "NOT_CREATED_SEALED"
    assert plan["final_test_command"] == "NOT_CREATED_SEALED"


def test_phase_ends_with_zero_generation_training_and_sealed_access() -> None:
    readiness = _load("rb21_target_generation_readiness_v2.json")
    assert set(readiness["isolation"].values()) == {0}
    assert readiness["command_plan_prepared"] is True
    assert readiness["command_plan_executed"] is False
    assert all(value == "PASS" or str(value).startswith("PASS_") or value == 0
               for value in readiness["acceptance_gates"].values())
