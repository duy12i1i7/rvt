"""RB21-TARGET Windows/Docker negative qualification evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rvt_swarm.phase8.common import canonical_json_bytes


ROOT = Path(__file__).resolve().parents[1]
RESULT = json.loads((
    ROOT / "results/rvt_fd24/rb21_windows_docker_generation_readiness_v1.json"
).read_text(encoding="ascii"))


def test_target_readiness_artifact_has_a_valid_canonical_self_hash() -> None:
    body = {
        key: value for key, value in RESULT.items()
        if key != "rb21_windows_docker_generation_readiness_sha256"
    }
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == RESULT[
        "rb21_windows_docker_generation_readiness_sha256"
    ]


def test_phase15_semantic_failure_forces_verdict_b_and_no_later_benchmark() -> None:
    gate = RESULT["gate_result"]
    assert gate["verdict"] == "B"
    assert gate["failed_gate"].startswith("PHASE_15")
    assert gate["mandatory_action"] == "STOP_NO_SCIENCE_CHANGE"
    assert gate["later_phases_executed"] is False
    assert gate["official_environment_tuple_declared"] is False
    assert all(
        value == "NOT_RUN_MANDATORY_PHASE15_STOP"
        for key, value in RESULT["benchmark_execution"].items()
        if key in {
            "capacity_projection",
            "chunk_matrix",
            "failure_resume_matrix",
            "single_worker_baseline",
            "storage_projection",
            "worker_matrix",
        }
    )


def test_container_failure_is_recorded_without_rewriting_science() -> None:
    validation = RESULT["semantic_validation"]
    assert validation["host_reference"]["failed"] == 0
    assert validation["target_critical_suite"]["failed"] == 0
    assert validation["target_exact_stack_full_suite"] == {
        "failed": 3,
        "passed": 2967,
        "publication_required_xfailed": 0,
        "warnings": 1,
        "wall_seconds": 341.78,
        "xfailed": 0,
        "xpassed": 0,
    }
    assert {item["type"] for item in validation["mismatches"]} == {
        "MODEL_BATCH_ISOLATION",
        "MODEL_CANDIDATE_ISOLATION",
        "CROSS_PLATFORM_LAYOUT_COMPILATION",
    }


def test_no_sealed_or_official_work_was_executed() -> None:
    isolation = RESULT["isolation"]
    assert set(isolation.values()) == {0}
    assert RESULT["authorization"]["STUDY_A_N24_ZERO_SHOT"] == (
        "SEALED_NOT_AUTHORIZED"
    )
    assert RESULT["authorization"]["FINAL_TEST"] == "SEALED_NOT_AUTHORIZED"
    assert RESULT["benchmark_execution"]["official_command_plan"] == (
        "NOT_PREPARED_SEMANTIC_GATE_FAILED"
    )


def test_generation_source_is_immutable_and_versions_are_pinned() -> None:
    container = RESULT["container"]
    assert container["source_runtime_writable_by_worker"] is False
    assert container["source_runtime_owner"] == "root:root"
    assert "@sha256:" in container["base_image"]
    assert container["python_version"] == "3.9.6"
    assert container["numpy_version"] == "2.0.2"
    assert container["torch_version"] == "2.8.0+cpu"
    for value in container["thread_environment"].values():
        assert value == 1
