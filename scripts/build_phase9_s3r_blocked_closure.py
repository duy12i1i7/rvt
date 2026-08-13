#!/usr/bin/env python3
"""Build canonical A1S3R Verdict-A artifacts from read-only diagnostics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


PREVIOUS_EVIDENCE_COMMIT = "2d21f402ec286bde0f44494f612a2b83e2087184"
PREVIOUS_REPORT_COMMIT = "5b0a439b739cdfd229aa1f124bdb4ed01bc65126"
SCIENTIFIC_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
OLD_IMAGE = "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def _write(path: Path, document: dict, field: str) -> dict:
    document = attach_canonical_hash(document, field)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return document


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "results/rvt_fd24"
    checkpoint = _canonical(
        out / "phase9_s3_staging_checkpoint_v1.json",
        "phase9_s3_staging_checkpoint_sha256",
    )
    previous_population = _canonical(
        out / "phase9_s3_population_audit_v1.json",
        "phase9_s3_population_audit_closure_sha256",
    )
    owner_reference = _canonical(
        out / "phase9_s3r_owner_rule_audit_reference_v1.json",
        "phase9_s3r_owner_rule_audit_sha256",
    )
    owner_docker = _canonical(
        out / "phase9_s3r_owner_rule_audit_docker_v1.json",
        "phase9_s3r_owner_rule_audit_sha256",
    )
    existing_reference = _canonical(
        out / "phase9_s3_existing_data_requalification_reference_v1.json",
        "phase9_s3r_existing_data_requalification_sha256",
    )
    existing_docker = _canonical(
        out / "phase9_s3_existing_data_requalification_docker_v1.json",
        "phase9_s3r_existing_data_requalification_sha256",
    )
    if (
        owner_reference["semantic_projection_sha256"]
        != owner_docker["semantic_projection_sha256"]
    ):
        raise ValueError("owner-rule reference/Docker semantic projections differ")
    if (
        existing_reference["semantic_projection_sha256"]
        != existing_docker["semantic_projection_sha256"]
    ):
        raise ValueError("existing-data reference/Docker projections differ")
    if checkpoint["prefix"]["scientific_rows"] != 342:
        raise ValueError("official STAGING checkpoint is not the retained prefix")
    if owner_reference["centerline_degeneracy"]["affected_observation_count"] != 4:
        raise ValueError("centerline-degeneracy evidence changed")

    mandatory_provenance = {
        "official_generation_had_begun_before_discovery": True,
        "official_rows_already_existed": 342,
        "dependency_audit_potentially_affected_rows": 0,
        "dependency_audit_proven_affected_rows": 0,
        "blocked_s3_transaction_committed_scientific_rows": 0,
        "owner_decision_basis": (
            "local physical geometry and anonymous support semantics only"
        ),
        "target_v4_outcomes_used_to_select_rule": False,
        "model_performance_used_to_select_rule": False,
        "class_balance_used_to_select_rule": False,
        "downstream_results_used_to_select_rule": False,
        "historical_scientific_roots_rewritten": False,
        "binding": "additive",
    }
    addendum = _write(
        out / "phase9_s3_opposing_boundary_scientific_addendum_v1.json",
        {
            "schema_version": "rvt-s3-opposing-boundary-pairing/v1",
            "phase": "PHASE_9G_A1S3R",
            "status": "OWNER_RULE_FROZEN_BUT_NOT_EXECUTABLE",
            "identity": {
                "previous_s3_evidence_commit": PREVIOUS_EVIDENCE_COMMIT,
                "previous_s3_report_commit": PREVIOUS_REPORT_COMMIT,
                "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
                "qualified_pre_repair_image": OLD_IMAGE,
            },
            "owner_rule": {
                "scope": "anonymous S3 support pairing only",
                "local_frame": {
                    "c": "authoritative local corridor/reference center point at S3",
                    "t": "authoritative oriented local corridor tangent or mission tangent",
                    "n": "authoritative local normal associated with t",
                    "new_independent_frame_definition_permitted": False,
                },
                "signed_coordinate": "d_k = dot(p_k-c,n)",
                "negative_side": "d_k < 0",
                "positive_side": "d_k > 0",
                "negative_selection": "d_neg = max({d_k | d_k < 0})",
                "positive_selection": "d_pos = min({d_k | d_k > 0})",
                "width": "S3_width = d_pos-d_neg",
                "same_side_pair_permitted": False,
                "abs_previous_width_permitted": False,
                "clamp_permitted": False,
                "numerical_epsilon": None,
                "independence": [
                    "family identity", "team size", "robot ID",
                    "candidate topology", "Target V4 outcome",
                    "recoverability label", "future trajectory",
                    "worker", "chunk", "retry", "token enumeration order",
                ],
            },
            "mandatory_provenance": mandatory_provenance,
            "newly_exposed_ambiguity": {
                "code": "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED",
                "description": (
                    "Authorized F6 S3 observations contain the anonymous circle-0 "
                    "central-blocker token exactly on the authoritative mission "
                    "reference centerline: d_k is +0.0 and is neither d_k<0 nor d_k>0."
                ),
                "affected_observations": 4,
                "existing_geometry_epsilon": None,
                "existing_boundary_on_centerline_validity_rule": None,
                "owner_instruction_requires_stop": True,
                "new_tolerance_invented": False,
            },
            "scientific_status": {
                "pairing_rule_non_degenerate_domain_closed": True,
                "total_s3_pairing_contract_closed": False,
                "implementation_authorized": False,
                "required_next_input": (
                    "owner rule for an anonymous support whose authoritative signed "
                    "coordinate is exactly zero, including whether circle centers are "
                    "passage-boundary candidates"
                ),
            },
            "sealed_scope": dict(owner_reference["sealed_scope"]),
        },
        "phase9_s3_opposing_boundary_scientific_addendum_sha256",
    )

    execution = _write(
        out / "phase9_s3_pairing_execution_contract_v1.json",
        {
            "schema_version": "rvt-phase9-s3-pairing-execution-contract/v1",
            "status": "NOT_EXECUTABLE_CENTERLINE_DEGENERACY_UNDERSPECIFIED",
            "scientific_addendum_sha256": addendum[
                "phase9_s3_opposing_boundary_scientific_addendum_sha256"
            ],
            "proposed_non_degenerate_pipeline": [
                "authoritative anonymous local support set",
                "existing authoritative local corridor/reference frame c,t,n",
                "signed free-space-facing support coordinates d_k",
                "nearest strictly negative and strictly positive coordinates",
                "width d_pos-d_neg",
            ],
            "unresolved_totality_input": "d_k == 0.0",
            "runtime_files_changed": [],
            "controller_changed": False,
            "safety_changed": False,
            "geometry_changed": False,
            "event_timing_changed": False,
            "target_v4_changed": False,
            "matched_randomness_changed": False,
            "row_identity_contract_changed": False,
            "graph_schema_changed": False,
            "model_changed": False,
            "executable_repair_implemented": False,
        },
        "phase9_s3_pairing_execution_contract_sha256",
    )

    instance_records = owner_reference["instance_records"]
    instance_counts = {
        "valid_negative_side_support": sum(
            record["valid_negative_side_support"] > 0 for record in instance_records
        ),
        "valid_positive_side_support": sum(
            record["valid_positive_side_support"] > 0 for record in instance_records
        ),
        "both_sides": sum(record["both_sides"] > 0 for record in instance_records),
        "missing_side": sum(
            record["robot_observation_count"] > 0
            and record["both_sides"] < record["robot_observation_count"]
            for record in instance_records
        ),
        "centerline_degenerate": sum(
            record["centerline_degenerate_support_count"] > 0
            for record in instance_records
        ),
    }
    population = _write(
        out / "phase9_s3_population_requalification_v1.json",
        {
            "schema_version": "rvt-phase9-s3-population-requalification/v1",
            "status": "BLOCKED_CENTERLINE_DEGENERACY",
            "mode": "NON_OFFICIAL_AUTHORIZED_READ_ONLY_DIAGNOSTIC",
            "raw_evidence": {
                "reference": {
                    "canonical_sha256": owner_reference[
                        "phase9_s3r_owner_rule_audit_sha256"
                    ],
                    "file_sha256": _file_sha(
                        out / "phase9_s3r_owner_rule_audit_reference_v1.json"
                    ),
                },
                "qualified_docker": {
                    "canonical_sha256": owner_docker[
                        "phase9_s3r_owner_rule_audit_sha256"
                    ],
                    "file_sha256": _file_sha(
                        out / "phase9_s3r_owner_rule_audit_docker_v1.json"
                    ),
                    "image": OLD_IMAGE,
                },
            },
            "semantic_projection_sha256": owner_reference[
                "semantic_projection_sha256"
            ],
            "reference_docker_semantic_exact": True,
            "source_instance_count": 250,
            "instance_counts": instance_counts,
            "robot_observation_distribution": owner_reference["population"],
            "by_split_family_team_size_layout": owner_reference[
                "by_split_family_team_size_layout"
            ],
            "previous_negative_explanation": {
                "negative_source_instances": previous_population[
                    "source_instance_distribution"
                ]["negative"],
                "negative_robot_observations": previous_population[
                    "systematic_sign_audit"
                ]["negative_observation_count"],
                "all_were_same_compiled_boundary_pairs": previous_population[
                    "systematic_sign_audit"
                ]["all_negative_pairs_from_same_compiled_boundary_side"],
                "owner_rule_prohibits_that_pair": True,
                "f3_f4_special_case_logic": False,
            },
            "centerline_degeneracy": owner_reference["centerline_degeneracy"],
            "tie_audit": owner_reference["tie_audit"],
            "scientific_stop": dict(owner_reference["scientific_stop"]),
            "official_staging_writes": 0,
            "sealed_scope": dict(owner_reference["sealed_scope"]),
        },
        "phase9_s3_population_requalification_sha256",
    )

    token = _write(
        out / "phase9_s3_token_order_invariance_v1.json",
        {
            "schema_version": "rvt-phase9-s3-token-order-invariance/v1",
            "status": "DIAGNOSTIC_OWNER_RULE_PROJECTION_PASS",
            "scientific_addendum_sha256": addendum[
                "phase9_s3_opposing_boundary_scientific_addendum_sha256"
            ],
            "observations_tested": owner_reference["token_order_audit"][
                "observations_tested"
            ],
            "orders_per_observation": owner_reference["token_order_audit"][
                "orders_per_observation"
            ],
            "orders": ["runtime", "canonical_identity", "reversed"],
            "semantic_projection_mismatches": 0,
            "physically_distinct_equal_distance_ties": 0,
            "equivalent_representation_tie_observations": owner_reference[
                "tie_audit"
            ]["equal_distance_observation_count"],
            "translation_invariance": {
                "formula": "dot((p+a)-(c+a),n)=dot(p-c,n)",
                "exact_algebraic": True,
            },
            "rotation_invariance": {
                "formula": "dot(R(p-c),Rn)=dot(p-c,n) for orthonormal R",
                "diagnostic_transform_contract": "rotate p,c,t,n consistently",
                "physical_width_preserved": True,
            },
            "historical_implementation": {
                "scalar_token_permutation_susceptibility": False,
                "actual_defect": (
                    "same physical boundary crossed signs of the robot-relative "
                    "mission normal; token permutation did not repair the pair"
                ),
            },
            "executable_new_path_tested": False,
            "reason": "No executable path may be implemented before degeneracy closure.",
        },
        "phase9_s3_token_order_invariance_sha256",
    )

    existing = _write(
        out / "phase9_s3_existing_data_requalification_v1.json",
        {
            "schema_version": "rvt-phase9-s3-existing-data-requalification/v1",
            "status": "RETAIN_ALL_342",
            "staging_checkpoint_sha256": checkpoint[
                "phase9_s3_staging_checkpoint_sha256"
            ],
            "raw_evidence": {
                "reference": existing_reference[
                    "phase9_s3r_existing_data_requalification_sha256"
                ],
                "qualified_docker": existing_docker[
                    "phase9_s3r_existing_data_requalification_sha256"
                ],
            },
            "semantic_projection_sha256": existing_reference[
                "semantic_projection_sha256"
            ],
            "reference_docker_semantic_exact": True,
            "row_count": 342,
            "row_classification_counts": existing_reference[
                "row_classification_counts"
            ],
            "dependent_transaction_count": existing_reference[
                "dependent_transaction_count"
            ],
            "dependent_row_count": existing_reference["dependent_row_count"],
            "source_replay_count": existing_reference["source_replay_count"],
            "s3_call_count": existing_reference["s3_call_count"],
            "physical_pair_difference_count": 0,
            "decision_difference_count": 0,
            "centerline_degenerate_support_count": 0,
            "width_bit_difference_count": existing_reference[
                "width_bit_difference_count"
            ],
            "maximum_width_absolute_difference_meters": existing_reference[
                "maximum_width_absolute_difference_meters"
            ],
            "semantic_conclusion": existing_reference["semantic_conclusion"],
            "official_data_action": "RETAIN_ALL_342",
            "rows_rebuilt": 0,
            "row_ids_changed": 0,
            "provenance_payloads_rewritten": 0,
            "official_staging_writes": 0,
            "sealed_scope": dict(existing_reference["sealed_scope"]),
        },
        "phase9_s3_existing_data_requalification_sha256",
    )

    blocked = owner_reference["blocked_case_robot_8"]
    blocked_replay = _write(
        out / "phase9_s3_blocked_task_replay_v1.json",
        {
            "schema_version": "rvt-phase9-s3-blocked-task-replay/v1",
            "status": "NOT_RUN_SCIENTIFIC_GATE_BLOCKED",
            "original_failure": {
                "source_task_id": blocked["source_task_id"],
                "robot_id": blocked["robot_id"],
                "historical_selected_supports": [
                    "corridor-0-left-4", "corridor-0-left-3"
                ],
                "historical_selected_physical_components": [
                    "corridor-0-left", "corridor-0-left"
                ],
                "historical_width_meters": -0.6143634774571596,
            },
            "owner_rule_failure_call_diagnostic": {
                "local_frame": blocked["local_frame_diagnostic"],
                "support_table": blocked["support_table"],
                "selection": blocked["selection"],
                "conclusion": (
                    "The exact old failure call has only positive physical-boundary "
                    "supports in the owner frame and therefore routes to the existing "
                    "missing-side UNKNOWN behavior; no width is fabricated."
                ),
            },
            "physical_aperture_meters": 1.361,
            "executable_repaired_source_available": False,
            "candidate_replica_replay_executed": False,
            "scientific_disposition": None,
            "official_rows_committed": 0,
            "stop_reason": "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED",
        },
        "phase9_s3_blocked_task_replay_sha256",
    )

    production = _write(
        out / "phase9_s3_production_impact_v1.json",
        {
            "schema_version": "rvt-phase9-s3-production-impact/v1",
            "status": "NOT_MEASURED_SCIENTIFIC_GATE_BLOCKED",
            "profile": {
                "workers": 12,
                "numeric_threads": 1,
                "chunk": 1,
                "infrastructure_timeout_seconds": 243,
            },
            "runtime_source_changed": False,
            "production_path_diagnostics_run": 0,
            "performance_requalification_run": False,
            "profile_classification": "SUSPENDED_NOT_REQUALIFIED_FOR_S3R",
            "timeout_changed": False,
            "reason": (
                "Performance measurement cannot qualify a scientifically incomplete "
                "executable path."
            ),
        },
        "phase9_s3_production_impact_sha256",
    )

    image = _write(
        out / "phase9_s3_new_image_qualification_v1.json",
        {
            "schema_version": "rvt-phase9-s3-new-image-qualification/v1",
            "status": "NOT_BUILT_SCIENTIFIC_GATE_BLOCKED",
            "old_image": OLD_IMAGE,
            "new_image": None,
            "source_commit_for_new_image": None,
            "dockerfile_environment_lineage": None,
            "target_exact_commit_verification": False,
            "reason": "No executable scientific repair was permitted.",
        },
        "phase9_s3_new_image_qualification_sha256",
    )

    readiness = _write(
        out / "phase9_s3_recoverability_resume_readiness_v1.json",
        {
            "schema_version": "rvt-phase9-s3-recoverability-resume-readiness/v1",
            "readiness": "BLOCKED_SCIENTIFIC_OWNER_DECISION",
            "verdict": "A",
            "verdict_text": (
                "The owner pairing rule reveals another still-unfrozen scientific ambiguity."
            ),
            "blocking_code": "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED",
            "scientific_addendum_sha256": addendum[
                "phase9_s3_opposing_boundary_scientific_addendum_sha256"
            ],
            "pairing_execution_contract_sha256": execution[
                "phase9_s3_pairing_execution_contract_sha256"
            ],
            "population_requalification_sha256": population[
                "phase9_s3_population_requalification_sha256"
            ],
            "token_order_invariance_sha256": token[
                "phase9_s3_token_order_invariance_sha256"
            ],
            "existing_data_requalification_sha256": existing[
                "phase9_s3_existing_data_requalification_sha256"
            ],
            "blocked_task_replay_sha256": blocked_replay[
                "phase9_s3_blocked_task_replay_sha256"
            ],
            "production_impact_sha256": production[
                "phase9_s3_production_impact_sha256"
            ],
            "new_image_qualification_sha256": image[
                "phase9_s3_new_image_qualification_sha256"
            ],
            "official_data_action": "RETAIN_ALL_342",
            "resume_authorization_prepared": False,
            "resume_authorization_executed": False,
            "resume_lineage": {
                "completed_train_events": 210,
                "total_train_events": 6000,
                "completed_rows": 342,
                "completed_transactions_preserved": True,
                "unresolved_tasks_scheduled": False,
            },
            "official_operations": {
                "generation_resumes": 0,
                "validation_starts": 0,
                "residual_starts": 0,
                "training_operations": 0,
                "official_staging_writes": 0,
            },
            "sealed_scope": dict(checkpoint["sealed_domains"]),
        },
        "phase9_s3_recoverability_resume_readiness_sha256",
    )
    _write(
        out / "phase9_s3r_scientific_closure_v1.json",
        {
            "schema_version": "rvt-phase9-s3r-scientific-closure/v1",
            "status": "STOPPED_FOR_OWNER_SCIENTIFIC_DECISION",
            "classification": "S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED",
            "verdict": "A",
            "readiness_sha256": readiness[
                "phase9_s3_recoverability_resume_readiness_sha256"
            ],
            "source_code_changed": False,
            "new_image_built": False,
            "official_data_action": "RETAIN_ALL_342",
            "isolation": {
                "official_generation_resumed": False,
                "recoverability_validation_started": False,
                "residual_v2_started": False,
                "training_operations": 0,
                "study_a_n24_accesses": 0,
                "study_b_accesses": 0,
                "final_test_accesses": 0,
                "official_staging_writes": 0,
            },
        },
        "phase9_s3r_scientific_closure_sha256",
    )


if __name__ == "__main__":
    main()
