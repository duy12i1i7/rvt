"""Phase 9G-A1S3R fail-fast tests for the centerline-degeneracy stop."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase8e.protocol import s3_local_geometric_decision
from rvt_swarm.phase9g0r.compiler import compile_source_tasks
from rvt_swarm.phase9g0r.producer import build_source_session
from scripts.audit_phase9_s3r_owner_rule import _observation


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _canonical(name: str, field: str) -> dict:
    document = json.loads((RESULTS / name).read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop(field)
    assert sha256_document(body) == expected
    return document


def test_all_s3r_artifacts_are_canonical() -> None:
    artifacts = {
        "phase9_s3r_owner_rule_audit_reference_v1.json": (
            "phase9_s3r_owner_rule_audit_sha256"
        ),
        "phase9_s3r_owner_rule_audit_docker_v1.json": (
            "phase9_s3r_owner_rule_audit_sha256"
        ),
        "phase9_s3_existing_data_requalification_reference_v1.json": (
            "phase9_s3r_existing_data_requalification_sha256"
        ),
        "phase9_s3_existing_data_requalification_docker_v1.json": (
            "phase9_s3r_existing_data_requalification_sha256"
        ),
        "phase9_s3_opposing_boundary_scientific_addendum_v1.json": (
            "phase9_s3_opposing_boundary_scientific_addendum_sha256"
        ),
        "phase9_s3_pairing_execution_contract_v1.json": (
            "phase9_s3_pairing_execution_contract_sha256"
        ),
        "phase9_s3_population_requalification_v1.json": (
            "phase9_s3_population_requalification_sha256"
        ),
        "phase9_s3_token_order_invariance_v1.json": (
            "phase9_s3_token_order_invariance_sha256"
        ),
        "phase9_s3_existing_data_requalification_v1.json": (
            "phase9_s3_existing_data_requalification_sha256"
        ),
        "phase9_s3_blocked_task_replay_v1.json": (
            "phase9_s3_blocked_task_replay_sha256"
        ),
        "phase9_s3_production_impact_v1.json": (
            "phase9_s3_production_impact_sha256"
        ),
        "phase9_s3_new_image_qualification_v1.json": (
            "phase9_s3_new_image_qualification_sha256"
        ),
        "phase9_s3_recoverability_resume_readiness_v1.json": (
            "phase9_s3_recoverability_resume_readiness_sha256"
        ),
        "phase9_s3r_scientific_closure_v1.json": (
            "phase9_s3r_scientific_closure_sha256"
        ),
    }
    for name, field in artifacts.items():
        _canonical(name, field)


def test_owner_rule_and_mandatory_provenance_are_frozen_additively() -> None:
    addendum = _canonical(
        "phase9_s3_opposing_boundary_scientific_addendum_v1.json",
        "phase9_s3_opposing_boundary_scientific_addendum_sha256",
    )
    assert addendum["schema_version"] == "rvt-s3-opposing-boundary-pairing/v1"
    rule = addendum["owner_rule"]
    assert rule["signed_coordinate"] == "d_k = dot(p_k-c,n)"
    assert rule["negative_selection"] == "d_neg = max({d_k | d_k < 0})"
    assert rule["positive_selection"] == "d_pos = min({d_k | d_k > 0})"
    assert rule["width"] == "S3_width = d_pos-d_neg"
    assert rule["abs_previous_width_permitted"] is False
    assert rule["numerical_epsilon"] is None
    provenance = addendum["mandatory_provenance"]
    assert provenance["official_generation_had_begun_before_discovery"] is True
    assert provenance["official_rows_already_existed"] == 342
    assert provenance["dependency_audit_potentially_affected_rows"] == 0
    assert provenance["dependency_audit_proven_affected_rows"] == 0
    assert provenance["blocked_s3_transaction_committed_scientific_rows"] == 0
    assert provenance["historical_scientific_roots_rewritten"] is False
    assert not any(
        provenance[key] for key in (
            "target_v4_outcomes_used_to_select_rule",
            "model_performance_used_to_select_rule",
            "class_balance_used_to_select_rule",
            "downstream_results_used_to_select_rule",
        )
    )


def test_reference_and_qualified_docker_find_the_same_exact_degeneracy() -> None:
    reference = _canonical(
        "phase9_s3r_owner_rule_audit_reference_v1.json",
        "phase9_s3r_owner_rule_audit_sha256",
    )
    docker = _canonical(
        "phase9_s3r_owner_rule_audit_docker_v1.json",
        "phase9_s3r_owner_rule_audit_sha256",
    )
    assert reference["semantic_projection_sha256"] == docker[
        "semantic_projection_sha256"
    ] == "34173283767f4b9cf09f3af5627bc0ab41f71ce81c1f36ae8b5be260c1950241"
    assert reference["centerline_degeneracy"]["affected_observation_count"] == 4
    assert docker["centerline_degeneracy"]["affected_observation_count"] == 4
    for artifact in (reference, docker):
        for observation in artifact["centerline_degeneracy"]["observations"]:
            assert observation["family"] == "F6"
            assert observation["team_size"] == 16
            assert observation["centerline_degenerate_supports"] == ["circle-0"]
            row = next(
                row for row in observation["support_table"]
                if row["owner_side"] == "CENTERLINE_DEGENERATE"
            )
            assert row["participates_in_existing_s3_lookahead"] is True
            assert row["signed_center_coordinate_meters"] == 0.0
            assert row["signed_center_float_hex"] == "0x0.0p+0"


def test_exact_authorized_f6_source_reproduces_centerline_zero() -> None:
    source_id = (
        "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F6/"
        "b63e08eeaacad624c27080a2468e751d06f2e2817a24242efab159864ce670c9/"
        "N16/S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR/episode-1"
    )
    task = next(
        task for task in compile_source_tasks(
            ROOT, study="study_a_zero_shot", split="train"
        ) if task.job_id == source_id
    )
    session = build_source_session(ROOT, task)
    for _ in range(3):
        session.step()
    observation = _observation(session, session.robots[14])
    assert observation["centerline_degenerate_supports"] == ["circle-0"]
    row = next(
        row for row in observation["support_table"]
        if row["source_key"] == "circle-0"
    )
    assert row["owner_side"] == "CENTERLINE_DEGENERATE"
    assert row["signed_center_coordinate_meters"] == 0.0


def test_frozen_s3_totality_has_no_centerline_degeneracy_input_or_rule() -> None:
    parameters = inspect.signature(s3_local_geometric_decision).parameters
    assert "centerline_degenerate_support" not in parameters
    assert "geometric_epsilon" not in parameters
    contracts = json.loads(
        (RESULTS / "source_policy_contracts_v1.json").read_text(encoding="ascii")
    )["policies"]["S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR"]
    serialized = json.dumps(contracts, sort_keys=True).lower()
    assert "centerline" not in serialized
    assert "epsilon" not in serialized


def test_blocked_f3_call_is_missing_opposite_side_not_absolute_width() -> None:
    replay = _canonical(
        "phase9_s3_blocked_task_replay_v1.json",
        "phase9_s3_blocked_task_replay_sha256",
    )
    old = replay["original_failure"]
    assert old["historical_selected_physical_components"] == [
        "corridor-0-left", "corridor-0-left"
    ]
    assert old["historical_width_meters"] == -0.6143634774571596
    selection = replay["owner_rule_failure_call_diagnostic"]["selection"]
    assert selection["valid_negative_side_support"] is False
    assert selection["valid_positive_side_support"] is True
    assert selection["width_meters"] is None
    assert replay["candidate_replica_replay_executed"] is False
    assert replay["official_rows_committed"] == 0


def test_all_250_population_requalification_is_generic_and_stopped() -> None:
    population = _canonical(
        "phase9_s3_population_requalification_v1.json",
        "phase9_s3_population_requalification_sha256",
    )
    assert population["source_instance_count"] == 250
    assert population["robot_observation_distribution"]["observation_count"] == 2270
    assert population["robot_observation_distribution"]["centerline_degenerate"] == 4
    assert population["robot_observation_distribution"][
        "physically_distinct_equal_distance_tie"
    ] == 0
    assert population["previous_negative_explanation"] == {
        "all_were_same_compiled_boundary_pairs": True,
        "f3_f4_special_case_logic": False,
        "negative_robot_observations": 48,
        "negative_source_instances": 20,
        "owner_rule_prohibits_that_pair": True,
    }
    assert population["scientific_stop"] == {
        "executable_repair_permitted": False,
        "reason": "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED",
        "required": True,
    }


def test_token_order_projection_is_invariant_but_not_executable() -> None:
    token = _canonical(
        "phase9_s3_token_order_invariance_v1.json",
        "phase9_s3_token_order_invariance_sha256",
    )
    assert token["observations_tested"] == 2270
    assert token["orders_per_observation"] == 3
    assert token["semantic_projection_mismatches"] == 0
    assert token["physically_distinct_equal_distance_ties"] == 0
    assert token["translation_invariance"]["exact_algebraic"] is True
    assert token["rotation_invariance"]["physical_width_preserved"] is True
    assert token["executable_new_path_tested"] is False


def test_all_342_rows_retain_exact_identity_and_semantics() -> None:
    existing = _canonical(
        "phase9_s3_existing_data_requalification_v1.json",
        "phase9_s3_existing_data_requalification_sha256",
    )
    assert existing["row_count"] == 342
    assert existing["row_classification_counts"] == {
        "DEPENDENCY_PRESENT_BUT_VALUE_VALID": 88,
        "POTENTIALLY_AFFECTED": 0,
        "PROVEN_AFFECTED": 0,
        "UNAFFECTED": 254,
    }
    assert existing["s3_call_count"] == 6485
    assert existing["physical_pair_difference_count"] == 0
    assert existing["decision_difference_count"] == 0
    assert existing["centerline_degenerate_support_count"] == 0
    assert existing["official_data_action"] == "RETAIN_ALL_342"
    assert existing["rows_rebuilt"] == 0
    assert existing["row_ids_changed"] == 0
    assert existing["provenance_payloads_rewritten"] == 0


def test_no_runtime_repair_image_performance_or_resume_was_performed() -> None:
    execution = _canonical(
        "phase9_s3_pairing_execution_contract_v1.json",
        "phase9_s3_pairing_execution_contract_sha256",
    )
    image = _canonical(
        "phase9_s3_new_image_qualification_v1.json",
        "phase9_s3_new_image_qualification_sha256",
    )
    production = _canonical(
        "phase9_s3_production_impact_v1.json",
        "phase9_s3_production_impact_sha256",
    )
    readiness = _canonical(
        "phase9_s3_recoverability_resume_readiness_v1.json",
        "phase9_s3_recoverability_resume_readiness_sha256",
    )
    assert execution["runtime_files_changed"] == []
    assert execution["executable_repair_implemented"] is False
    assert image["new_image"] is None
    assert production["performance_requalification_run"] is False
    assert production["profile"]["infrastructure_timeout_seconds"] == 243
    assert readiness["readiness"] == "BLOCKED_SCIENTIFIC_OWNER_DECISION"
    assert readiness["blocking_code"] == (
        "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED"
    )
    assert readiness["official_data_action"] == "RETAIN_ALL_342"
    assert not any(readiness["official_operations"].values())
    assert not any(readiness["sealed_scope"].values())


def test_pre_repair_runtime_files_remain_byte_identical_to_s3_authority_audit() -> None:
    authority = _canonical(
        "phase9_s3_geometry_authority_v1.json",
        "phase9_s3_geometry_authority_sha256",
    )
    for source in authority["relevant_sources"]:
        if source["classification"] != "CURRENT_AUTHORITATIVE":
            continue
        path = ROOT / source["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["file_sha256"]


def test_final_closure_is_verdict_a_and_fully_isolated() -> None:
    closure = _canonical(
        "phase9_s3r_scientific_closure_v1.json",
        "phase9_s3r_scientific_closure_sha256",
    )
    assert closure["classification"] == (
        "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED"
    )
    assert closure["verdict"] == "A"
    assert closure["source_code_changed"] is False
    assert closure["new_image_built"] is False
    assert closure["official_data_action"] == "RETAIN_ALL_342"
    assert not any(closure["isolation"].values())
