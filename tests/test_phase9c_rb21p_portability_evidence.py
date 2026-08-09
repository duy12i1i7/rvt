"""RB21P final cross-platform portability and GPU-audit evidence guards."""

from __future__ import annotations

import json
from pathlib import Path

from rvt_swarm.phase8.common import verify_canonical_hash


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "results/rvt_fd24"
PORTABILITY = json.loads((
    RESULT_ROOT / "rb21_cross_platform_numeric_portability_v1.json"
).read_text(encoding="ascii"))
REQUALIFICATION = json.loads((
    RESULT_ROOT / "rb21_portability_requalification_v1.json"
).read_text(encoding="ascii"))


def test_portability_and_requalification_roots_have_valid_self_hashes() -> None:
    assert verify_canonical_hash(
        PORTABILITY, "rb21_cross_platform_numeric_portability_sha256"
    )
    assert verify_canonical_hash(
        REQUALIFICATION, "rb21_portability_requalification_sha256"
    )
    assert REQUALIFICATION["portability_artifact_sha256"] == PORTABILITY[
        "rb21_cross_platform_numeric_portability_sha256"
    ]


def test_verdict_c_requires_every_predeclared_portability_gate() -> None:
    assert PORTABILITY["verdict"] == "C"
    gates = PORTABILITY["acceptance_gates"]
    assert all(
        value is True or value == 0
        for value in gates.values()
    )
    assert PORTABILITY["complete_suite_results"][
        "target_linux_final_image"
    ]["failed"] == 0
    assert PORTABILITY["rb20_semantic_replay"]["semantic_mismatches"] == 0
    assert PORTABILITY["rb20_semantic_replay"][
        "scientific_identity_mismatches"
    ] == 0


def test_repair_keeps_frozen_model_and_layout_contracts() -> None:
    model = PORTABILITY["model_numerics"]
    invariance = model["architecture_schema_invariance"]
    assert model["implementation_repair"] == "NOT_REQUIRED"
    assert invariance["model_code_changed"] is False
    assert invariance["parameter_count_changed"] is False
    assert invariance["tolerance_changed"] is False
    assert model["selected_profile"]["environment"] == {
        "MKL_CBWR": "COMPATIBLE"
    }
    layout = PORTABILITY["layout_portability"]
    assert layout["all_layout_result"]["resolved_authoritative_hash_exact"] == 30
    assert layout["all_layout_result"]["physical_projection_exact"] == 30
    assert layout["rounding_added"] is False
    assert layout["per_layout_special_case"] is False


def test_gpu_is_visible_but_scientific_generation_remains_cpu_authoritative() -> None:
    gpu = PORTABILITY["gpu_audit"]
    assert gpu["hardware"]["exact_model"] == "NVIDIA RTX 5000 Ada Generation"
    assert gpu["docker"]["gpu_access_proven"] is True
    assert gpu["candidate_generation_container"][
        "torch_cuda_is_available"
    ] is False
    assert gpu["cuda_probe_container"]["torch_cuda_is_available"] is True
    diagnostic = PORTABILITY["cuda_model_diagnostic"]
    assert diagnostic["authority"] == "TEST_ONLY_NON_AUTHORITATIVE"
    assert diagnostic["scientific_execution_path_changed"] is False
    assert set(PORTABILITY["gpu_semantic_boundary"].values()) >= {"CPU"}


def test_blocked_evidence_and_sealed_scopes_remain_preserved() -> None:
    assert PORTABILITY["blocked_evidence"] == {
        "artifact_path": (
            "results/rvt_fd24/"
            "rb21_windows_docker_generation_readiness_v1.json"
        ),
        "artifact_self_sha256": (
            "90689f48419bcc738cb6ba37427951bd250629419cf7504464dd6f718f12b1b8"
        ),
        "commit": "96f1811888b5a462dceb905fa74022b78c2988b4",
        "docker_image": (
            "sha256:c730e0726e8d1d9dba781ded3205c5c22131bb35461cbca4f5633e977b4ae0f9"
        ),
        "preserved": True,
        "tag": "rvt-rb21-target-portability-block-v1",
    }
    assert set(PORTABILITY["isolation"].values()) == {0}
    assert REQUALIFICATION["authorization"]["FINAL_TEST"] == (
        "SEALED_NOT_AUTHORIZED"
    )
    assert REQUALIFICATION["authorization"]["STUDY_A_N24_ZERO_SHOT"] == (
        "SEALED_NOT_AUTHORIZED"
    )
    assert REQUALIFICATION["authorization"]["OFFICIAL_GENERATION"] == (
        "NOT_AUTHORIZED_IN_RB21P"
    )
