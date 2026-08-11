#!/usr/bin/env python3
"""Build the target audit and final held readiness artifact for Phase 9G0-R."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


def _load_hash(results: Path, name: str, field: str) -> str:
    document = json.loads((results / name).read_text(encoding="ascii"))
    expected = str(document.pop(field))
    if sha256_document(document) != expected:
        raise ValueError(f"canonical artifact hash mismatch: {name}")
    return expected


def _write(
    results: Path, name: str, body: Mapping[str, Any], field: str,
) -> str:
    document = attach_canonical_hash(dict(body), field)
    (results / name).write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(document[field])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    results = root / "results/rvt_fd24"

    references = {
        "scientific_addendum": _load_hash(
            results,
            "phase9_predata_generation_scientific_addendum_v1.json",
            "phase9_predata_generation_scientific_addendum_sha256",
        ),
        "generator_contract": _load_hash(
            results,
            "phase9_official_generator_contract_v2.json",
            "phase9_official_generator_contract_sha256",
        ),
        "generation_provenance": _load_hash(
            results,
            "phase9_current_generation_provenance_v2.json",
            "phase9_current_generation_provenance_sha256",
        ),
        "command_plan": _load_hash(
            results,
            "phase9_official_command_plan_v2.json",
            "phase9_official_command_plan_sha256",
        ),
        "command_resolution": _load_hash(
            results,
            "phase9g0r_command_plan_resolution_v1.json",
            "phase9g0r_command_plan_resolution_sha256",
        ),
        "structural_canary": _load_hash(
            results,
            "phase9g0r_structural_canary_v1.json",
            "phase9g0r_structural_canary_sha256",
        ),
        "rb20_replay": _load_hash(
            results,
            "phase9g0r_rb20_official_path_replay_v1.json",
            "phase9g0r_rb20_official_path_replay_sha256",
        ),
        "preflight": _load_hash(
            results,
            "phase9g0r_preflight_v1.json",
            "phase9g0r_preflight_sha256",
        ),
        "matched_randomness": _load_hash(
            results,
            "phase9g0r_matched_randomness_regression_v1.json",
            "phase9g0r_matched_randomness_regression_sha256",
        ),
        "count_reconciliation": _load_hash(
            results,
            "phase9g0r_count_reconciliation_v1.json",
            "phase9g0r_count_reconciliation_sha256",
        ),
        "performance": _load_hash(
            results,
            "phase9g0r_performance_classification_v1.json",
            "phase9g0r_performance_classification_sha256",
        ),
    }

    target = {
        "schema_version": "rvt-phase9g0r-target-exact-image-validation/v1",
        "target_host": "100.71.102.9",
        "target_account": "avis\\avis",
        "reached": True,
        "wrong_prior_address_used_as_evidence": False,
        "qualified_base_image": {
            "digest": "sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b",
            "present_on_target": True,
        },
        "superseding_image": {
            "digest": "sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c",
            "tag": "rvt-phase9g0r:8cf6448-v2",
            "base_digest": "sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b",
            "source_commit": "8cf64481cd17b2c44f7007d3722a8110e53cae46",
            "git_head_exact": True,
            "rvt_source_commit_environment_exact": True,
            "appledouble_files": 0,
            "source_tree_writable_by_runtime_user": True,
        },
        "rejected_intermediate_image": {
            "digest": "sha256:b06dc8cbf1fb06329059102b9945ea173ecad404e48226db6a4971cdb62e87b6",
            "accepted_as_qualified": False,
            "failure_class": "IMAGE_CONSTRUCTION_ONLY",
            "failures": 112,
            "causes": [
                "macOS AppleDouble metadata entered the build context",
                "source tree was not writable by the runtime user",
                "inherited Git metadata was not advanced to the new source commit",
            ],
        },
        "validation": {
            "post_repair_regression_subset": {"passed": 149, "failed": 0},
            "complete_exact_image_suite": {
                "passed": 3034,
                "failed": 0,
                "xfailed": 0,
                "warnings": 1,
                "seconds": 360.95,
            },
            "final_evidence_tests_inside_exact_image": {
                "passed": 6,
                "failed": 0,
                "xfailed": 0,
            },
        },
        "scientific_path": "CPU_AUTHORITATIVE_UNCHANGED",
        "official_generation_executed": False,
        "training_executed": False,
        "credential_persisted": False,
        "status": "PASS",
    }
    target_hash = _write(
        results,
        "phase9g0r_target_exact_image_validation_v1.json",
        target,
        "phase9g0r_target_exact_image_validation_sha256",
    )

    readiness = {
        "schema_version": "rvt-phase9-generation-readiness/v4",
        "status": "PRE_DATA_BINDING_CLOSED_PRODUCTION_PROFILE_REQUALIFICATION_REQUIRED",
        "verdict": "C",
        "owner_addendum": {
            "sha256": references["scientific_addendum"],
            "frozen_decisions": 6,
            "official_rows_before_addendum": 0,
            "prospective_before_official_labels": True,
        },
        "closure_references": {**references, "target_validation": target_hash},
        "executable_binding": {
            "source_commit": "8cf64481cd17b2c44f7007d3722a8110e53cae46",
            "docker_image": "sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c",
            "real_recoverability_producer": True,
            "real_residual_producer": True,
            "canonical_staging_writer": True,
            "command_plan_resolutions": 8,
            "command_plan_executed": False,
            "official_execution_authorized": False,
        },
        "scientific_gates": {
            "unresolved_owner_decisions": [],
            "f1_through_f10_compiled": True,
            "study_a_train_validation_compiled": True,
            "study_b_train_validation_including_n24_compiled": True,
            "study_a_n24_sealed": True,
            "final_test_sealed": True,
            "matched_randomness_groups": 21000,
            "matched_randomness_mismatches": 0,
            "residual_retention_k": 16,
            "residual_strict_upper_bound": 520960,
            "residual_cap": 536000,
        },
        "tests": {
            "focused_required_regressions": {
                "passed": 133, "failed": 0, "xfailed": 0
            },
            "local_complete_suite": {
                "passed": 3040,
                "failed": 0,
                "xfailed": 0,
                "warnings": 1,
                "seconds": 395.59,
            },
            "target_complete_exact_image_suite": {
                "passed": 3034,
                "failed": 0,
                "xfailed": 0,
                "warnings": 1,
                "seconds": 360.95,
            },
            "target_final_evidence_tests": {
                "passed": 6,
                "failed": 0,
                "xfailed": 0,
            },
            "publication_required_xfailed": 0,
        },
        "performance": {
            "classification": "RB21_PRODUCTION_PATH_REQUALIFICATION_REQUIRED",
            "rb21_w12_profile_authoritative": False,
            "full_worker_scaling_executed": False,
            "scientific_semantic_change": False,
        },
        "isolation": {
            "official_run_ids": 0,
            "official_staging_writes": 0,
            "official_recoverability_rows": 0,
            "official_residual_rows": 0,
            "official_shards": 0,
            "training_operations": 0,
            "checkpoints": 0,
            "optimizer_states": 0,
            "study_a_n24_accesses": 0,
            "final_test_accesses": 0,
        },
        "next_gate": (
            "Run scoped RB21 performance requalification for the real production "
            "path, then obtain a new narrow authorization artifact before any "
            "official STAGING execution."
        ),
    }
    readiness_hash = _write(
        results,
        "phase9_generation_readiness_v4.json",
        readiness,
        "phase9_generation_readiness_v4_sha256",
    )
    print(json.dumps({
        "target_validation": target_hash,
        "readiness_v4": readiness_hash,
        "verdict": "C",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
