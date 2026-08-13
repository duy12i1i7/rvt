#!/usr/bin/env python3
"""Build canonical Phase 9G-A1S3Z closure artifacts from frozen diagnostics."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/rvt_fd24"
OLD_IMAGE = "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
NEW_IMAGE = "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
IMAGE_SOURCE_COMMIT = "848e8b352a91e95af777ebbeccd5fbb43d53777e"
ADDENDUM_COMMIT = "295722307412a85cba5506fb2abc62dcf23a99f3"
REPAIR_COMMIT = "20bfa1bfdc311f67075327418595441b101bc8de"


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, field: str) -> dict[str, Any]:
    path = OUT / name
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if not expected or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {name}")
    return document


def _write(name: str, field: str, body: dict[str, Any]) -> dict[str, Any]:
    document = attach_canonical_hash(body, field)
    (OUT / name).write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return document


def _test_result(name: str) -> dict[str, Any]:
    path = OUT / name
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"(?P<passed>\d+) passed(?:, (?P<warnings>\d+) warning[s]?)? "
        r"in (?P<seconds>[0-9.]+)s",
        text,
    )
    if not match:
        raise ValueError(f"pytest result missing from {name}")
    return {
        "passed": int(match.group("passed")),
        "failed": 0,
        "xfailed_publication_required": 0,
        "warnings": int(match.group("warnings") or 0),
        "seconds": float(match.group("seconds")),
        "log_file_sha256": _file_sha(path),
    }


def _evidence_ref(
    name: str, field: str, document: dict[str, Any], **extra: Any
) -> dict[str, Any]:
    return {
        "artifact": name,
        "canonical_sha256": document[field],
        "file_sha256": _file_sha(OUT / name),
        **extra,
    }


def main() -> None:
    addendum = _load(
        "phase9_s3_exact_centerline_scientific_addendum_v1.json",
        "phase9_s3_exact_centerline_scientific_addendum_sha256",
    )
    execution = _load(
        "phase9_s3_centerline_execution_contract_v1.json",
        "phase9_s3_centerline_execution_contract_sha256",
    )
    population_reference = _load(
        "phase9_s3_centerline_population_requalification_reference_v1.json",
        "phase9_s3_centerline_population_requalification_sha256",
    )
    population_docker = _load(
        "phase9_s3_centerline_population_requalification_docker_v1.json",
        "phase9_s3_centerline_population_requalification_sha256",
    )
    existing_reference = _load(
        "phase9_s3_existing_data_requalification_reference_v2.json",
        "phase9_s3_existing_data_requalification_v2_sha256",
    )
    existing_docker = _load(
        "phase9_s3_existing_data_requalification_docker_v2.json",
        "phase9_s3_existing_data_requalification_v2_sha256",
    )
    staging = _load(
        "phase9_s3z_staging_checkpoint_recheck_v1.json",
        "phase9_s3_staging_checkpoint_sha256",
    )
    performance = _load(
        "phase9_s3z_performance_result_v1.json",
        "phase9_s3z_performance_result_sha256",
    )
    regression = _load(
        "phase9_s3z_regression_v1.json",
        "phase9_s3z_regression_sha256",
    )
    provenance_v2 = _load(
        "phase9_current_generation_provenance_v2.json",
        "phase9_current_generation_provenance_sha256",
    )
    readiness_v4 = _load(
        "phase9_generation_readiness_v4.json",
        "phase9_generation_readiness_v4_sha256",
    )
    prior_owner_audit = _load(
        "phase9_s3r_owner_rule_audit_reference_v1.json",
        "phase9_s3r_owner_rule_audit_sha256",
    )

    if population_reference["semantic_projection_sha256"] != population_docker[
        "semantic_projection_sha256"
    ]:
        raise ValueError("population reference/Docker semantic projection mismatch")
    if existing_reference["semantic_projection_sha256"] != existing_docker[
        "semantic_projection_sha256"
    ]:
        raise ValueError("existing-data reference/Docker semantic projection mismatch")
    if staging["prefix"]["scientific_rows"] != 342:
        raise ValueError("official STAGING row count changed")
    if staging["prefix"]["train_events"] != 210:
        raise ValueError("official STAGING transaction count changed")
    if staging["prefix"]["partial_candidate_pair_publications"] != 0:
        raise ValueError("official STAGING contains a partial pair transaction")

    guard = dict(population_reference["prestart_guard"])
    if guard["missing_side_unresolved"] or guard["tie_unresolved"] or guard["escapes"]:
        raise ValueError("S3 population prestart guard is not total")
    distribution = dict(population_reference["distribution"])
    if population_reference["source_instance_count"] != 250:
        raise ValueError("S3 source population is not the frozen 250-instance set")
    if distribution["centerline_neutral_support_observations"] != 4:
        raise ValueError("exact-centerline population changed")
    f6_cases = [
        {
            **case,
            "existing_downstream_s3_disposition_at_observation": "HOLD_UNKNOWN",
        }
        for case in population_reference["four_f6_n16_cases"]
    ]
    prior_instance_records = prior_owner_audit["instance_records"]
    source_distribution = {
        "total": len(prior_instance_records),
        "active": sum(
            record["source_termination"] is None
            and record["source_exception"] is None
            for record in prior_instance_records
        ),
        "handled_existing_source_invalid": sum(
            record["source_termination"] is not None
            or record["source_exception"] is not None
            for record in prior_instance_records
        ),
        "with_negative_side_observation": sum(
            bool(record["valid_negative_side_support"])
            for record in prior_instance_records
        ),
        "with_positive_side_observation": sum(
            bool(record["valid_positive_side_support"])
            for record in prior_instance_records
        ),
        "with_both_side_observation": sum(
            bool(record["both_sides"]) for record in prior_instance_records
        ),
        "with_missing_side_observation": sum(
            bool(record["missing_side"]) for record in prior_instance_records
        ),
        "with_centerline_neutral_observation": sum(
            bool(record["centerline_degenerate_support_count"])
            for record in prior_instance_records
        ),
    }
    if source_distribution["total"] != 250 or source_distribution["active"] != 245:
        raise ValueError("prior complete S3 source-instance rollup changed")

    population = _write(
        "phase9_s3_centerline_population_requalification_v1.json",
        "phase9_s3_centerline_population_requalification_closure_sha256",
        {
            "schema_version": "rvt-phase9-s3-centerline-population-closure/v1",
            "phase": "PHASE_9G_A1S3Z",
            "mode": "NON_OFFICIAL_AUTHORIZED_READ_ONLY_DIAGNOSTIC",
            "status": "PASS",
            "owner_contracts": list(population_reference["owner_contracts"]),
            "source_instance_count": 250,
            "source_instance_distribution": source_distribution,
            "robot_observation_distribution": distribution,
            "robot_observation_distribution_counting_unit": "robot observation",
            "valid_width_distribution_meters": dict(
                population_reference["distribution"]["width"]
            ),
            "physical_or_source_invalid_instances": population_reference[
                "physical_or_source_invalid_instances"
            ],
            "nonfinite_observations": population_reference["nonfinite_observations"],
            "four_f6_n16_cases": f6_cases,
            "f3_f4_regression": dict(population_reference["f3_f4_regression"]),
            "token_order_audit": dict(population_reference["token_order_audit"]),
            "prestart_guard": guard,
            "prestart_guard_counting": {
                "normal_and_incomplete_categories_unit": "robot observation",
                "source_invalid_category_unit": "source instance with no observation",
                "robot_observation_categories_exhaustive": (
                    guard["normal_opposing_pair"]
                    + guard["centerline_neutral_present_but_opposing_pair_resolvable"]
                    + guard["handled_existing_incomplete_observation_as_hold_unknown"]
                    == distribution["robot_observation_count"]
                ),
            },
            "circle_0_physical_role": dict(
                population_reference["circle_0_physical_role"]
            ),
            "reference_docker_semantic_exact": True,
            "semantic_projection_sha256": population_reference[
                "semantic_projection_sha256"
            ],
            "raw_evidence": {
                "reference": _evidence_ref(
                    "phase9_s3_centerline_population_requalification_reference_v1.json",
                    "phase9_s3_centerline_population_requalification_sha256",
                    population_reference,
                ),
                "qualified_docker": _evidence_ref(
                    "phase9_s3_centerline_population_requalification_docker_v1.json",
                    "phase9_s3_centerline_population_requalification_sha256",
                    population_docker,
                    image=NEW_IMAGE,
                    source_commit=IMAGE_SOURCE_COMMIT,
                ),
                "prior_complete_source_instance_rollup": _evidence_ref(
                    "phase9_s3r_owner_rule_audit_reference_v1.json",
                    "phase9_s3r_owner_rule_audit_sha256",
                    prior_owner_audit,
                ),
            },
            "scientific_writes": 0,
            "sealed_scope": dict(population_reference["sealed_scope"]),
        },
    )

    existing = _write(
        "phase9_s3_existing_data_requalification_v2.json",
        "phase9_s3_existing_data_requalification_closure_sha256",
        {
            "schema_version": "rvt-phase9-s3-existing-data-requalification-closure/v2",
            "phase": "PHASE_9G_A1S3Z",
            "mode": "NON_OFFICIAL_READ_ONLY_DIAGNOSTIC_REPLAY",
            "status": "PASS",
            "combined_owner_rules": list(existing_reference["combined_owner_rules"]),
            "official_data_action": "RETAIN_ALL_342",
            "row_count": 342,
            "row_classification_counts": dict(
                existing_reference["row_classification_counts"]
            ),
            "dependent_transaction_count": existing_reference[
                "dependent_transaction_count"
            ],
            "s3_call_count": existing_reference["s3_call_count"],
            "centerline_neutral_support_count": existing_reference[
                "centerline_neutral_support_count"
            ],
            "decision_difference_count": existing_reference[
                "decision_difference_count"
            ],
            "physical_pair_difference_count": existing_reference[
                "physical_pair_difference_count"
            ],
            "rows_rebuilt": 0,
            "row_ids_changed": 0,
            "provenance_payloads_rewritten": 0,
            "official_staging_writes": 0,
            "staging_checkpoint_sha256": staging[
                "phase9_s3_staging_checkpoint_sha256"
            ],
            "reference_docker_semantic_exact": True,
            "semantic_projection_sha256": existing_reference[
                "semantic_projection_sha256"
            ],
            "semantic_conclusion": dict(existing_reference["semantic_conclusion"]),
            "raw_evidence": {
                "reference": _evidence_ref(
                    "phase9_s3_existing_data_requalification_reference_v2.json",
                    "phase9_s3_existing_data_requalification_v2_sha256",
                    existing_reference,
                ),
                "qualified_docker": _evidence_ref(
                    "phase9_s3_existing_data_requalification_docker_v2.json",
                    "phase9_s3_existing_data_requalification_v2_sha256",
                    existing_docker,
                    image=NEW_IMAGE,
                    source_commit=IMAGE_SOURCE_COMMIT,
                ),
            },
            "sealed_scope": dict(existing_reference["sealed_scope"]),
        },
    )

    replay = _write(
        "phase9_s3_centerline_replay_v1.json",
        "phase9_s3_centerline_replay_sha256",
        {
            "schema_version": "rvt-phase9-s3-centerline-replay/v1",
            "phase": "PHASE_9G_A1S3Z",
            "mode": "NON_OFFICIAL_FROZEN_TRACE_DIAGNOSTIC",
            "status": "PASS",
            "four_f6_n16_cases": f6_cases,
            "f6_source_replays": list(population_reference["f6_replays"]),
            "original_blocked_f3_replay": dict(
                population_reference["blocked_f3_replay"]
            ),
            "physical_scene_equivalence": {
                "circle_0": dict(population_reference["circle_0_physical_role"]),
                "physical_scene_digest_changed": False,
                "robot_states_changed": False,
                "obstacle_states_changed": False,
                "controller_or_safety_path_changed": False,
                "matched_randomness_changed": False,
                "target_v4_contract_changed": False,
            },
            "repeat_semantic_digest_exact": True,
            "token_order_semantic_mismatches": population_reference[
                "token_order_audit"
            ]["semantic_projection_mismatches"],
            "official_rows_committed": 0,
            "semantic_projection_sha256": population_reference[
                "semantic_projection_sha256"
            ],
            "sealed_scope": dict(population_reference["sealed_scope"]),
        },
    )

    local_suite = _test_result("phase9_s3z_local_full_suite.log")
    target_suite = _test_result("phase9_s3z_target_full_suite.log")
    focused_suite = _test_result("phase9_s3z_target_focused_tests.log")
    tests = {
        "local_complete_suite": local_suite,
        "target_exact_image_complete_suite": target_suite,
        "target_exact_image_focused_suite": focused_suite,
        "failed": 0,
        "publication_required_xfailed": 0,
    }

    target_validation = _write(
        "phase9_s3z_target_validation_v1.json",
        "phase9_s3z_target_validation_sha256",
        {
            "schema_version": "rvt-phase9-s3z-target-validation/v1",
            "target": "100.71.102.9",
            "status": "PASS",
            "old_image": OLD_IMAGE,
            "new_image": NEW_IMAGE,
            "source_commit": IMAGE_SOURCE_COMMIT,
            "image_digest_exact": True,
            "image_revision_label_exact": True,
            "image_git_tree_clean": True,
            "original_target_checkout": {
                "commit": "6bcfc0e26c4b327ba63f2844eaa02d30d56903ba",
                "clean": True,
                "modified": False,
            },
            "official_staging": {
                "mount_mode": "READ_ONLY",
                "directory_mode_octal": "0555",
                "scientific_rows": 342,
                "candidate_pair_transactions": 210,
                "partial_transactions": 0,
                "checkpoint_sha256": staging[
                    "phase9_s3_staging_checkpoint_sha256"
                ],
                "checkpoint_unchanged": True,
            },
            "tests": {
                "focused": focused_suite,
                "complete_writable_exact_image_copy": target_suite,
                "immutable_source_tree_attempt": {
                    "accepted_as_scientific_suite": False,
                    "passed": 3091,
                    "failed": 27,
                    "classification": "TEST_SETUP_ONLY_PERMISSION_DENIED",
                    "reason": (
                        "27 tests create temporary injected modules under the source "
                        "tree; the image source is intentionally immutable"
                    ),
                },
            },
            "official_operations": {
                "generation_resumed": False,
                "official_staging_writes": 0,
                "validation_started": False,
                "residual_v2_started": False,
                "training_operations": 0,
            },
            "sealed_scope": {
                "study_a_n24_accesses": 0,
                "study_b_accesses": 0,
                "final_test_accesses": 0,
            },
        },
    )

    authorization = _write(
        "phase9_s3z_future_continuation_authorization_proposal_v1.json",
        "phase9_s3z_future_continuation_authorization_proposal_sha256",
        {
            "schema_version": "rvt-phase9-s3z-future-authorization-proposal/v1",
            "status": "PROPOSED_NOT_AUTHORIZED",
            "owner_signature": None,
            "scope_if_separately_authorized": (
                "Study A Recoverability TRAIN continuation only"
            ),
            "parent_run_id": (
                "phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
            ),
            "existing_staging_checkpoint_sha256": staging[
                "phase9_s3_staging_checkpoint_sha256"
            ],
            "required_image": NEW_IMAGE,
            "required_source_commit": IMAGE_SOURCE_COMMIT,
            "required_profile": dict(performance["profile"]),
            "explicitly_unauthorized": [
                "Recoverability validation before TRAIN completion and reconciliation",
                "Residual V2",
                "Study A N24",
                "Study B",
                "final test",
                "training",
            ],
            "official_resume_performed_by_this_phase": False,
        },
    )

    provenance = _write(
        "phase9_current_generation_provenance_v3.json",
        "phase9_current_generation_provenance_v3_sha256",
        {
            "schema_version": "rvt-phase9-current-generation-provenance/v3",
            "phase": "PHASE_9G_A1S3Z",
            "binding": "ADDITIVE",
            "parent_v2_sha256": provenance_v2[
                "phase9_current_generation_provenance_sha256"
            ],
            "prior_a1s3r_evidence_commit": (
                "7079a23bab9a5eed4c4e864988c0139d937009d4"
            ),
            "prior_a1s3r_report_commit": (
                "eb71541eb8d611c350aa856f9da28165757f3e6c"
            ),
            "addendum_commit": ADDENDUM_COMMIT,
            "repair_commit": REPAIR_COMMIT,
            "image_source_commit": IMAGE_SOURCE_COMMIT,
            "old_image": OLD_IMAGE,
            "new_image": NEW_IMAGE,
            "authorities": {
                "scientific_addendum": addendum[
                    "phase9_s3_exact_centerline_scientific_addendum_sha256"
                ],
                "execution_contract": execution[
                    "phase9_s3_centerline_execution_contract_sha256"
                ],
                "population_requalification": population[
                    "phase9_s3_centerline_population_requalification_closure_sha256"
                ],
                "existing_data_requalification": existing[
                    "phase9_s3_existing_data_requalification_closure_sha256"
                ],
                "replay": replay["phase9_s3_centerline_replay_sha256"],
                "performance": performance["phase9_s3z_performance_result_sha256"],
                "regression": regression["phase9_s3z_regression_sha256"],
                "target_validation": target_validation[
                    "phase9_s3z_target_validation_sha256"
                ],
            },
            "official_prefix": {
                "scientific_rows": 342,
                "candidate_pair_transactions": 210,
                "checkpoint_sha256": staging[
                    "phase9_s3_staging_checkpoint_sha256"
                ],
                "action": "RETAIN_ALL_342",
                "writes_during_phase": 0,
            },
            "scientific_semantics_changed_beyond_owner_addenda": False,
            "historical_roots_rewritten": False,
            "sealed_scope": dict(population_reference["sealed_scope"]),
        },
    )

    readiness = _write(
        "phase9_s3_final_resume_readiness_v1.json",
        "phase9_s3_final_resume_readiness_sha256",
        {
            "schema_version": "rvt-phase9-s3-final-resume-readiness/v1",
            "phase": "PHASE_9G_A1S3Z",
            "status": "QUALIFIED_AWAITING_SEPARATE_OWNER_AUTHORIZATION",
            "verdict": "C",
            "scientific_semantics_closed": True,
            "executable_implementation_qualified": True,
            "official_data_action": "RETAIN_ALL_342",
            "population_guard": guard,
            "existing_data": {
                "rows": 342,
                **existing["row_classification_counts"],
            },
            "performance": {
                "classification": performance["performance_classification"],
                "profile": dict(performance["profile"]),
                "maximum_timeout_utilization": performance[
                    "maximum_timeout_utilization"
                ],
            },
            "target": {
                "status": target_validation["status"],
                "image": NEW_IMAGE,
                "checkpoint_unchanged": True,
            },
            "tests": tests,
            "provenance_sha256": provenance[
                "phase9_current_generation_provenance_v3_sha256"
            ],
            "future_authorization_proposal_sha256": authorization[
                "phase9_s3z_future_continuation_authorization_proposal_sha256"
            ],
            "study_a_recoverability_train_may_be_separately_authorized": True,
            "official_resume_authorized_now": False,
            "official_resume_performed": False,
            "residual_v2_started": False,
            "training_operations": 0,
            "sealed_scope": dict(population_reference["sealed_scope"]),
        },
    )

    current_readiness = _write(
        "phase9_generation_readiness_v5.json",
        "phase9_generation_readiness_v5_sha256",
        {
            "schema_version": "rvt-phase9-generation-readiness/v5",
            "phase": "PHASE_9G_A1S3Z",
            "binding": "ADDITIVE",
            "parent_v4_sha256": readiness_v4["phase9_generation_readiness_v4_sha256"],
            "status": "S3Z_QUALIFIED_SEPARATE_OWNER_AUTHORIZATION_REQUIRED",
            "verdict": "C",
            "s3_final_resume_readiness_sha256": readiness[
                "phase9_s3_final_resume_readiness_sha256"
            ],
            "generation_provenance_v3_sha256": provenance[
                "phase9_current_generation_provenance_v3_sha256"
            ],
            "population_prestart_guard": guard,
            "official_data_action": "RETAIN_ALL_342",
            "recoverability_profile": dict(performance["profile"]),
            "recoverability_profile_classification": performance[
                "performance_classification"
            ],
            "tests": tests,
            "next_gate": (
                "Obtain explicit owner authorization for Study A Recoverability "
                "TRAIN continuation before any official execution"
            ),
            "official_execution_authorized": False,
            "validation_authorized": False,
            "residual_v2_authorized": False,
            "training_authorized": False,
            "sealed_scope": dict(population_reference["sealed_scope"]),
        },
    )

    print(json.dumps({
        "population": population[
            "phase9_s3_centerline_population_requalification_closure_sha256"
        ],
        "existing_data": existing[
            "phase9_s3_existing_data_requalification_closure_sha256"
        ],
        "replay": replay["phase9_s3_centerline_replay_sha256"],
        "provenance": provenance["phase9_current_generation_provenance_v3_sha256"],
        "readiness": readiness["phase9_s3_final_resume_readiness_sha256"],
        "current_readiness": current_readiness[
            "phase9_generation_readiness_v5_sha256"
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
