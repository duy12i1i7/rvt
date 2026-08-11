"""Canonical final evidence for the held Phase 9G0-R closure."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from rvt_swarm.phase8.common import sha256_document


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"
IMAGE = "sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c"
SOURCE = "8cf64481cd17b2c44f7007d3722a8110e53cae46"


CANONICAL = (
    ("phase9_official_generator_contract_v2.json",
     "phase9_official_generator_contract_sha256"),
    ("phase9_current_generation_provenance_v2.json",
     "phase9_current_generation_provenance_sha256"),
    ("phase9_official_command_plan_v2.json",
     "phase9_official_command_plan_sha256"),
    ("phase9g0r_command_plan_resolution_v1.json",
     "phase9g0r_command_plan_resolution_sha256"),
    ("phase9g0r_target_exact_image_validation_v1.json",
     "phase9g0r_target_exact_image_validation_sha256"),
    ("phase9_generation_readiness_v4.json",
     "phase9_generation_readiness_v4_sha256"),
)


def _load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


def test_every_final_artifact_and_scope_has_a_valid_canonical_hash() -> None:
    for name, field in CANONICAL:
        document = _load(name)
        expected = document.pop(field)
        assert sha256_document(document) == expected
    scopes = sorted(RESULTS.glob("phase9_authorization_scope_*_v2.json"))
    assert len(scopes) == 8
    for path in scopes:
        document = json.loads(path.read_text(encoding="ascii"))
        expected = document.pop("phase9_authorization_scope_sha256")
        assert sha256_document(document) == expected


def test_generator_contract_binds_real_producers_and_no_final_writer() -> None:
    contract = _load("phase9_official_generator_contract_v2.json")
    assert contract["provenance_class"] == "OFFICIAL_SCIENTIFIC_PRODUCER"
    assert contract["executable_source_commit"] == SOURCE
    assert contract["container"]["superseding_execution_image"] == IMAGE
    assert contract["recoverability"]["publication_unit"].startswith(
        "one reconciled 2*N"
    )
    assert contract["residual"]["candidate_count"] == 9
    assert contract["writer"]["direct_final_writer"] is False
    assert contract["official_generation_executed"] is False


def test_all_eight_commands_resolve_but_remain_held() -> None:
    plan = _load("phase9_official_command_plan_v2.json")
    launches = plan["launch_specifications"]
    assert len(launches) == 8
    assert plan["executed"] is False
    assert plan["docker_image"] == IMAGE
    assert plan["study_a_n24_command"] == "NOT_CREATED_SEALED"
    assert plan["final_test_command"] == "NOT_CREATED_SEALED"
    for launch in launches:
        assert launch["execution_authorized"] is False
        assert launch["executed"] is False
        command = shlex.split(launch["official_command"])
        assert "/opt/rvt/scripts/run_phase9_official_generation.py" in command
        assert "--job-manifest-sha256" in command
        assert "--authorization-scope-sha256" in command
        scope = _load(launch["authorization_scope_artifact"])
        assert scope["broad_authorization"] is False
        assert scope["official_generation_execution_authorized"] is False
    resolution = _load("phase9g0r_command_plan_resolution_v1.json")
    assert resolution["resolution_count"] == 8
    assert resolution["scientific_commands_executed"] == 0
    assert all(
        item["scientific_execution"] is False
        and item["official_generation_execution_authorized"] is False
        for item in resolution["resolutions"]
    )


def test_target_validation_uses_the_correct_host_and_exact_image() -> None:
    target = _load("phase9g0r_target_exact_image_validation_v1.json")
    assert target["target_host"] == "100.71.102.9"
    assert target["reached"] is True
    assert target["superseding_image"]["digest"] == IMAGE
    assert target["superseding_image"]["source_commit"] == SOURCE
    assert target["superseding_image"]["git_head_exact"] is True
    assert target["superseding_image"]["appledouble_files"] == 0
    assert target["validation"]["complete_exact_image_suite"]["passed"] == 3034
    assert target["validation"]["complete_exact_image_suite"]["failed"] == 0
    assert target["credential_persisted"] is False


def test_readiness_is_verdict_c_with_complete_isolation() -> None:
    readiness = _load("phase9_generation_readiness_v4.json")
    assert readiness["verdict"] == "C"
    assert readiness["owner_addendum"]["frozen_decisions"] == 6
    assert readiness["scientific_gates"]["unresolved_owner_decisions"] == []
    assert readiness["scientific_gates"]["matched_randomness_mismatches"] == 0
    assert readiness["scientific_gates"]["residual_strict_upper_bound"] == 520960
    assert readiness["performance"]["classification"] == (
        "RB21_PRODUCTION_PATH_REQUALIFICATION_REQUIRED"
    )
    assert readiness["executable_binding"]["official_execution_authorized"] is False
    assert set(readiness["isolation"].values()) == {0}


def test_final_report_records_exactly_the_selected_verdict() -> None:
    report = (
        ROOT / "docs/PHASE9G0_R_PRE_DATA_OFFICIAL_GENERATION_CLOSURE.md"
    ).read_text(encoding="ascii")
    assert "**C. The pre-data scientific addendum" in report
    assert "Commands executed: **NO**" in report
    assert "100.71.102.9" in report
