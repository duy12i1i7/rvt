#!/usr/bin/env python3
"""Freeze the additive exact-centerline S3 owner decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "results/rvt_fd24/phase9_s3_exact_centerline_scientific_addendum_v1.json"
    document = {
        "schema_version": "rvt-s3-exact-centerline-support/v1",
        "phase": "PHASE_9G_A1S3Z",
        "binding": "ADDITIVE_DO_NOT_REWRITE_HISTORICAL_ROOTS",
        "identity": {
            "a1r_evidence_commit": "a943ca391fb5feb5c8e90a693f763cc47c4d4e2b",
            "a1s3_evidence_commit": "2d21f402ec286bde0f44494f612a2b83e2087184",
            "a1s3_report_commit": "5b0a439b739cdfd229aa1f124bdb4ed01bc65126",
            "a1s3r_evidence_commit": "7079a23bab9a5eed4c4e864988c0139d937009d4",
            "a1s3r_report_commit": "eb71541eb8d611c350aa856f9da28165757f3e6c",
            "prior_owner_rule": "rvt-s3-opposing-boundary-pairing/v1",
            "qualified_pre_repair_image": (
                "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
            ),
            "official_staging_checkpoint_sha256": (
                "72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f"
            ),
        },
        "owner_rule": {
            "signed_coordinate": "d_k = dot(p_k-c,n)",
            "exact_zero_classification": "CENTERLINE_NEUTRAL",
            "positive_zero_classification": "CENTERLINE_NEUTRAL",
            "negative_zero_classification": "CENTERLINE_NEUTRAL",
            "signbit_used_for_zero_side_assignment": False,
            "negative_side": "finite d_k < 0.0",
            "positive_side": "finite d_k > 0.0",
            "centerline_neutral_eligible_for_d_neg": False,
            "centerline_neutral_eligible_for_d_pos": False,
            "numerical_epsilon": None,
            "isclose_permitted": False,
            "rounding_permitted": False,
            "clamping_permitted": False,
            "snapping_permitted": False,
            "perturbation_permitted": False,
            "nonfinite_handling": "use existing fail-closed numerical validity guards",
        },
        "physical_scene_rule": {
            "scope": "S3 opposing-boundary pairing only",
            "centerline_neutral_means_ignore_object": False,
            "physical_primitive_removed": False,
            "collision_geometry_changed": False,
            "safety_geometry_changed": False,
            "controller_observation_changed": False,
            "target_v4_physical_execution_changed": False,
        },
        "pairing_after_classification": {
            "negative_selection": "d_neg = max({d_k | d_k < 0})",
            "positive_selection": "d_pos = min({d_k | d_k > 0})",
            "width": "S3_width = d_pos-d_neg",
            "same_side_pair_permitted": False,
            "missing_side": (
                "use existing authoritative HOLD_UNKNOWN/source-validity disposition; "
                "fail closed if no existing rule applies"
            ),
            "tie": (
                "use frozen canonical physical identity; fail closed as "
                "S3_SUPPORT_TIE_UNDERSPECIFIED if a physically distinct tie affects execution"
            ),
        },
        "mandatory_provenance": {
            "official_generation_had_begun_before_discovery": True,
            "official_rows_already_existed": 342,
            "existing_row_classification": {
                "UNAFFECTED": 254,
                "DEPENDENCY_PRESENT_BUT_VALUE_VALID": 88,
                "POTENTIALLY_AFFECTED": 0,
                "PROVEN_AFFECTED": 0,
            },
            "four_exact_zero_cases_discovered_during_pre_resume_qualification": True,
            "owner_rule_basis": "local geometric meaning only",
            "model_results_used": False,
            "class_balance_used": False,
            "target_v4_success_rate_used": False,
            "downstream_evaluation_used": False,
            "official_staging_read_only_during_qualification": True,
            "historical_roots_rewritten": False,
        },
        "authorization": {
            "implementation_authorized": True,
            "official_generation_resume_authorized": False,
            "scope_if_separately_authorized_later": (
                "Study A Recoverability TRAIN continuation only"
            ),
        },
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    document = attach_canonical_hash(
        document, "phase9_s3_exact_centerline_scientific_addendum_sha256")
    output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(document["phase9_s3_exact_centerline_scientific_addendum_sha256"])


if __name__ == "__main__":
    main()
