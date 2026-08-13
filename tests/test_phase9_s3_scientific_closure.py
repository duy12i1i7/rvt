"""Fail-fast evidence tests for Phase 9G-A1S3 scientific closure."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.phase9g0r.producer import build_source_session
from scripts.diagnose_phase9_s3_width import EVENT_ID, _selector_projection


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _canonical(name: str, field: str) -> dict:
    document = json.loads((RESULTS / name).read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop(field)
    assert sha256_document(body) == expected
    return document


def test_all_closure_artifacts_are_canonical() -> None:
    artifacts = {
        "phase9_s3_staging_checkpoint_v1.json": (
            "phase9_s3_staging_checkpoint_sha256"
        ),
        "phase9_s3_width_derivation_reference_v1.json": (
            "phase9_s3_width_derivation_sha256"
        ),
        "phase9_s3_width_derivation_docker_v1.json": (
            "phase9_s3_width_derivation_sha256"
        ),
        "phase9_s3_width_derivation_v1.json": (
            "phase9_s3_width_derivation_closure_sha256"
        ),
        "phase9_s3_geometry_authority_v1.json": (
            "phase9_s3_geometry_authority_sha256"
        ),
        "phase9_s3_population_audit_reference_v1.json": (
            "phase9_s3_population_audit_sha256"
        ),
        "phase9_s3_population_audit_docker_v1.json": (
            "phase9_s3_population_audit_sha256"
        ),
        "phase9_s3_population_audit_v1.json": (
            "phase9_s3_population_audit_closure_sha256"
        ),
        "phase9_s3_staging_dependency_audit_v1.json": (
            "phase9_s3_staging_dependency_audit_sha256"
        ),
        "phase9_s3_official_data_impact_v1.json": (
            "phase9_s3_official_data_impact_sha256"
        ),
        "phase9_s3_owner_decision_required_v1.json": (
            "phase9_s3_owner_decision_required_sha256"
        ),
        "phase9_s3_expanded_preflight_coverage_v1.json": (
            "phase9_s3_expanded_preflight_coverage_sha256"
        ),
        "phase9_s3_scientific_closure_v1.json": (
            "phase9_s3_scientific_closure_sha256"
        ),
        "phase9_s3_generation_readiness_v1.json": (
            "phase9_s3_generation_readiness_sha256"
        ),
    }
    for name, field in artifacts.items():
        _canonical(name, field)


def test_width_trace_is_binary64_exact_and_not_orientation_sign_defect() -> None:
    width = _canonical(
        "phase9_s3_width_derivation_v1.json",
        "phase9_s3_width_derivation_closure_sha256",
    )
    measured = width["direct_operands"]["measured_width"]
    assert measured == {
        "binary64_big_endian_hex": "bfe3a8dd98712174",
        "coordinate_frame": "ego-relative mission lateral projection",
        "data_type": "IEEE-754 binary64 / Python float",
        "float_hex": "-0x1.3a8dd98712174p-1",
        "signed": True,
        "source_contract": "LocalGeometricSelectorPolicy.observe left+right",
        "unit": "meters",
        "value": -0.6143634774571596,
    }
    selected = width["selected_supports"]
    assert selected["left"]["source_key"] == "corridor-0-left-4"
    assert selected["right"]["source_key"] == "corridor-0-left-3"
    assert selected["same_compiled_boundary_side"] is True
    ordering = width["representational_ordering_tests"]
    assert ordering["bit_equal"] is True
    assert ordering["sign_changed"] is False
    rotation = width["rigid_layout_rotation_test"]
    assert rotation["rotation_degrees"] == 90
    assert rotation["bit_equal"] is True
    assert rotation["sign_changed"] is False
    assert width["cross_platform_classification"] == {
        "binary64_exact": True,
        "portability_framework_routing_required": False,
        "result": "SAME_EXACT_NEGATIVE_RESULT",
        "semantic_projection_exact": True,
    }


def test_historical_blocked_source_evidence_is_preserved() -> None:
    task = next(
        task for task in compile_recoverability_tasks(
            ROOT, study="study_a_zero_shot", split="train"
        ) if task.event_id == EVENT_ID
    )
    assert task.source.family == "F3"
    assert task.source.team_size == 12
    assert task.resolved_control_step == 90
    width = _canonical(
        "phase9_s3_width_derivation_v1.json",
        "phase9_s3_width_derivation_closure_sha256",
    )
    assert width["failure_call"]["session_control_step"] == 3
    assert width["direct_operands"]["measured_width"]["value"] < 0.0


def test_positive_straight_control_keeps_unsigned_span() -> None:
    tokens = (
        ((1.0, 1.05), 0.35, "straight-left"),
        ((1.0, -1.05), 0.35, "straight-right"),
    )
    _, left, right, width = _selector_projection(
        tokens, (1.0, 0.0), (0.0, 1.0), 2.0
    )
    assert left["source_key"] == "straight-left"
    assert right["source_key"] == "straight-right"
    assert width == pytest.approx(1.4)
    reversed_width = _selector_projection(
        tuple(reversed(tokens)), (1.0, 0.0), (0.0, -1.0), 2.0
    )[3]
    assert struct.pack(">d", reversed_width) == struct.pack(">d", width)


def test_population_covers_curved_families_and_multiple_team_sizes() -> None:
    population = _canonical(
        "phase9_s3_population_audit_v1.json",
        "phase9_s3_population_audit_closure_sha256",
    )
    assert population["source_instance_distribution"] == {
        "count": 250,
        "negative": 20,
        "positive": 56,
        "source_terminated_before_diagnostic": 5,
        "unknown_no_paired_width": 169,
        "zero": 0,
    }
    observations = population["robot_observation_distribution"]
    assert observations["count"] == 2270
    assert observations["negative"] == 48
    assert observations["positive"] == 293
    assert observations["zero"] == 0
    negatives = population["negative_observations"]
    assert {record["family"] for record in negatives} == {"F3", "F4"}
    assert {record["team_size"] for record in negatives} >= {8, 12, 16}
    assert all(record["same_compiled_boundary_side"] for record in negatives)
    assert all(
        record["all_compiled_passage_widths_positive"] for record in negatives
    )
    systematic = population["systematic_sign_audit"]
    assert systematic["orientation_sign_reversal_defect"] is False
    assert systematic["same_boundary_component_mispairing_defect"] is True


def test_case_iv_follows_from_frozen_authority_gap() -> None:
    authority = _canonical(
        "phase9_s3_geometry_authority_v1.json",
        "phase9_s3_geometry_authority_sha256",
    )
    assert authority["classification"] == "CASE_IV"
    assert authority["width_semantics"]["category"] == (
        "UNSIGNED_LOCAL_FREE_SPACE_SPAN"
    )
    assert authority["width_semantics"][
        "negative_value_mathematically_permitted"
    ] is False
    assert authority["runtime_information_loss"][
        "component_identity_available_to_s3"
    ] is False
    assert authority["case_evaluation"]["CASE_IV"]["selected"] is True
    assert authority["case_evaluation"]["CASE_I"]["selected"] is False
    classifications = {
        source["classification"] for source in authority["relevant_sources"]
    }
    assert classifications == {
        "CURRENT_AUTHORITATIVE", "HISTORICAL", "DIAGNOSTIC"
    }
    assert authority["superseded_rule_adopted"] is False


def test_existing_342_rows_are_exactly_partitioned_and_preserved() -> None:
    impact = _canonical(
        "phase9_s3_official_data_impact_v1.json",
        "phase9_s3_official_data_impact_sha256",
    )
    assert impact["scientific_rows"] == 342
    assert impact["classification_counts"] == {
        "DEPENDENCY_PRESENT_BUT_VALUE_VALID": 88,
        "POTENTIALLY_AFFECTED": 0,
        "PROVEN_AFFECTED": 0,
        "UNAFFECTED": 254,
    }
    assert impact["negative_width_in_committed_dependency_cone"] is False
    assert impact["current_preservation"] == {
        "rows_compacted": 0,
        "rows_deduplicated": 0,
        "rows_deleted": 0,
        "rows_regenerated": 0,
        "rows_rewritten": 0,
        "staging_remains_read_only": True,
    }
    assert impact["data_action"] == "OWNER_DECISION_REQUIRED"


def test_owner_decision_has_three_unimplemented_scientific_alternatives() -> None:
    owner = _canonical(
        "phase9_s3_owner_decision_required_v1.json",
        "phase9_s3_owner_decision_required_sha256",
    )
    assert owner["classification"] == "CASE_IV"
    assert len(owner["alternatives"]) == 3
    assert all(
        item["scientific_interpretation_changes"] is True
        for item in owner["alternatives"]
    )
    assert all(
        item["current_official_rows_proven_affected"] == 0
        for item in owner["alternatives"]
    )
    assert owner["recommended_option"]["implemented"] is False


def test_generation_readiness_is_blocked_until_owner_decision() -> None:
    readiness = _canonical(
        "phase9_s3_generation_readiness_v1.json",
        "phase9_s3_generation_readiness_sha256",
    )
    assert readiness["readiness"] == "BLOCKED_SCIENTIFIC_OWNER_DECISION"
    assert readiness["may_resume_official_recoverability"] is False
    assert readiness["staging_rows"] == 342
    assert readiness["staging_read_only"] is True
    assert readiness["new_image"] is None
    assert not any(readiness["official_operations"].values())
    assert not any(readiness["sealed_scope"].values())


def test_phase_closure_is_verdict_a_with_zero_downstream_operations() -> None:
    closure = _canonical(
        "phase9_s3_scientific_closure_v1.json",
        "phase9_s3_scientific_closure_sha256",
    )
    assert closure["classification"] == "CASE_IV"
    assert closure["data_action"] == "OWNER_DECISION_REQUIRED"
    assert closure["verdict"] == "A"
    assert closure["repair"]["implemented"] is False
    assert closure["repair"][
        "executable_conformance_repair_available_from_frozen_authority"
    ] is False
    assert closure["timeout_and_performance"]["qualified_timeout_seconds"] == 243
    assert closure["timeout_and_performance"]["reopened"] is False
    assert not any(closure["isolation"].values())
