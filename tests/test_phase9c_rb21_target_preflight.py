"""RB21 target authorization rejects every predeclared operational mismatch."""

from pathlib import Path

from rvt_swarm.phase9c_rb21.rb21_manifest import (
    RB19_PROVENANCE_ROOT,
    RB20_REPRODUCTION_HASH,
    RB21P_QUALIFIED_IMAGE,
    RB21P_REQUALIFICATION_ROOT,
    RB21P_SOURCE_CHECKPOINT,
    TARGET_V4_HASH,
)
from rvt_swarm.phase9c_rb21.rb21_target_preflight import (
    IMAGE_SOURCE_COMMIT,
    build_target_operational_preflight,
    run_target_negative_matrix,
)


ROOT = Path(__file__).resolve().parents[1]


def _documents():
    environment = {
        "qualification_result": "QUALIFIED",
        "windows": {"hostname": "AVIS"},
        "wsl": {"cpus": 24},
        "docker": {"image_digest": RB21P_QUALIFIED_IMAGE},
    }
    contract = {
        "qualified_docker_image": RB21P_QUALIFIED_IMAGE,
        "scientific_source_checkpoint": RB21P_SOURCE_CHECKPOINT,
        "qualified_image_source_commit": IMAGE_SOURCE_COMMIT,
        "references": {
            "rb19_current_provenance_root": RB19_PROVENANCE_ROOT,
            "rb20_reproduction": RB20_REPRODUCTION_HASH,
            "target_v4": TARGET_V4_HASH,
            "rb21p_portability_root": RB21P_REQUALIFICATION_ROOT,
        },
        "process_worker_count": 8,
        "nested_thread_settings": {
            "OMP_NUM_THREADS": 1,
            "MKL_NUM_THREADS": 1,
            "OPENBLAS_NUM_THREADS": 1,
            "NUMEXPR_NUM_THREADS": 1,
            "torch_num_threads": 1,
            "torch_num_interop_threads": 1,
        },
        "residual_chunk_size_atomic_units": 1,
        "recoverability_chunk_size_atomic_units": 1,
        "infrastructure_timeout_seconds": 900,
        "timeout_classification": "INFRASTRUCTURE_FAILURE",
        "timeout_changes_scientific_horizon": False,
        "resume_granularity": "ATOMIC_SCIENTIFIC_UNIT_IDENTITY",
        "semantic_retries": 0,
        "writer_mode": "STAGING_VALIDATE_ATOMIC_PROMOTION",
        "partial_staging_is_completed_dataset": False,
    }
    authorization = {
        "RECOVERABILITY_GENERATION": "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION",
        "RESIDUAL_V2_GENERATION": "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION",
        "STUDY_A_TRAIN_VALIDATION": "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION",
        "STUDY_A_N24_ZERO_SHOT": "SEALED_NOT_AUTHORIZED",
        "STUDY_B": "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION",
        "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
    }
    job = {
        "h4_classification": "H4_OPERATIONALLY_FEASIBLE",
        "low_vs_production_scientific_projection_equal": True,
        "study_a_n24_command": "NOT_CREATED_SEALED",
        "final_test_command": "NOT_CREATED_SEALED",
        "isolation": {
            "official_recoverability_rows": 0,
            "official_residual_rows": 0,
            "official_scientific_shards": 0,
            "checkpoints": 0,
            "optimizer_states": 0,
            "training_operations": 0,
            "study_a_n24_runtime_accesses": 0,
            "final_test_runtime_accesses": 0,
        },
    }
    return environment, contract, authorization, job


def test_positive_target_preflight_passes_without_broad_authorization() -> None:
    environment, contract, authorization, job = _documents()
    result = build_target_operational_preflight(
        ROOT, environment, contract, authorization, job)
    assert result["status"] == "PASS"
    assert result["failures"] == []


def test_target_negative_matrix_has_zero_escapes() -> None:
    environment, contract, authorization, job = _documents()
    result = run_target_negative_matrix(
        ROOT, environment, contract, authorization, job)
    assert result["case_count"] == 15
    assert result["escapes"] == 0
    assert all(row["failed_checks"] for row in result["cases"])
