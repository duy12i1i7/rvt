#!/usr/bin/env python3
"""Validate canonical Phase 9D-R artifacts and their cross-document decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import sha256_document


FAMILIES = [f"F{index}" for index in range(1, 11)]
TEAM_SIZES = [5, 6, 8, 12, 16]
TOPOLOGIES = ["COMPACT", "LINE"]
INPUT_COMMIT = "6ce4a37f195875e6568e2bbed2d1e2dfea103946"
FILES = {
    "input_integrity": (
        "phase9d_recoverability_input_integrity_v1.json",
        "phase9d_r_dataset_readonly_audit_sha256",
    ),
    "coverage_cube": (
        "phase9d_recoverability_coverage_cube_v1.json",
        "phase9d_recoverability_coverage_cube_sha256",
    ),
    "missing_cells": (
        "phase9d_recoverability_missing_cells_v1.json",
        "phase9d_recoverability_missing_cells_sha256",
    ),
    "invalid_reasons": (
        "phase9d_recoverability_invalid_reason_matrix_v1.json",
        "phase9d_recoverability_invalid_reason_matrix_sha256",
    ),
    "split_consistency": (
        "phase9d_recoverability_split_consistency_v1.json",
        "phase9d_recoverability_split_consistency_sha256",
    ),
    "class_balance": (
        "phase9d_recoverability_class_balance_v1.json",
        "phase9d_recoverability_class_balance_sha256",
    ),
    "h1_requirements": (
        "phase9d_h1_requirement_map_v1.json",
        "phase9d_h1_requirement_map_sha256",
    ),
    "h1_identifiability": (
        "phase9d_h1_identifiability_v1.json",
        "phase9d_h1_identifiability_sha256",
    ),
    "statistical_unit": (
        "phase9d_recoverability_statistical_unit_v1.json",
        "phase9d_recoverability_statistical_unit_sha256",
    ),
    "class_weight": (
        "phase9d_recoverability_class_weight_decision_v1.json",
        "phase9d_recoverability_class_weight_decision_sha256",
    ),
    "adequacy": (
        "phase9d_recoverability_dataset_adequacy_v1.json",
        "phase9d_recoverability_dataset_adequacy_sha256",
    ),
    "residual": (
        "phase9d_residual_go_no_go_v1.json",
        "phase9d_residual_go_no_go_sha256",
    ),
    "training": (
        "phase9d_training_readiness_v1.json",
        "phase9d_training_readiness_sha256",
    ),
    "closure": ("phase9d_r_closure_v1.json", "phase9d_r_closure_sha256"),
}


class Phase9DRValidationError(RuntimeError):
    """A Phase 9D-R artifact violates its frozen decision contract."""


def _canonical(path: Path, field: str) -> tuple[dict[str, Any], str]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise Phase9DRValidationError(f"canonical hash mismatch: {path}")
    return document, expected


def validate(root: Path) -> dict[str, Any]:
    results = root / "results/rvt_fd24"
    documents = {}
    hashes = {}
    for name, (filename, field) in FILES.items():
        documents[name], hashes[name] = _canonical(results / filename, field)

    integrity = documents["input_integrity"]
    if (
        integrity["status"] != "PASS"
        or integrity["execution_mode"] != "READ_ONLY"
        or integrity["official_dataset_mutations"] != 0
        or any(integrity["split_isolation"].values())
    ):
        raise Phase9DRValidationError("input integrity or split isolation changed")
    for split in ("train", "validation"):
        audit = integrity["datasets"][split]["integrity"]
        failure_fields = (
            "published_file_hash_failures",
            "transaction_hash_failures",
            "row_identity_failures",
            "graph_fingerprint_failures",
            "candidate_pair_reconciliation_failures",
            "matched_seed_mismatches",
            "partial_pair_publications",
            "duplicate_scientific_row_ids",
            "rollout_invalid_replicas",
            "staging_writable_files",
        )
        if any(audit[field] for field in failure_fields):
            raise Phase9DRValidationError(f"{split} integrity failure is nonzero")

    coverage = documents["coverage_cube"]
    if (
        coverage["authorized_families"] != FAMILIES
        or coverage["authorized_team_sizes"] != TEAM_SIZES
        or coverage["candidate_topologies"] != TOPOLOGIES
        or coverage["splits"] != ["TRAIN", "VALIDATION"]
        or coverage["zero_cells_hidden"] is not False
        or len(coverage["cells"]) != 200
    ):
        raise Phase9DRValidationError("coverage axes or complete cell count changed")
    identities = set()
    for cell in coverage["cells"]:
        identity = (
            cell["split"], cell["family"], cell["team_size"], cell["candidate_topology"]
        )
        if identity in identities:
            raise Phase9DRValidationError("duplicate coverage cell")
        identities.add(identity)
        if (
            cell["candidate_aggregates"]
            != cell["positive_aggregates"]
            + cell["negative_aggregates"]
            + cell["generation_invalid_aggregates"]
            or cell["scheduled_source_decision_events"]
            != cell["retained_candidate_pairs"] + cell["dropped_candidate_pairs"]
        ):
            raise Phase9DRValidationError("coverage denominator equation failed")

    missing = documents["missing_cells"]
    if (
        missing["status"] != "COVERAGE_STRUCTURALLY_MISSING"
        or missing["authoritative_structurally_missing_family_cell_count"] != 11
        or missing["contributing_zero_retained_family_n_cell_count"] != 28
        or missing["unscheduled_family_n_topology_cells"]
        or missing["unexpected_executable_or_manifest_gap_count"] != 0
        or missing["unknown_cause_count"] != 0
    ):
        raise Phase9DRValidationError("missing-cell classification changed")
    if any(
        cell["classification"] != "EXPECTED_FROM_FROZEN_SCIENCE"
        for cell in missing["authoritative_structurally_missing_family_cells"]
    ):
        raise Phase9DRValidationError("missing-cell cause classification changed")

    invalid = documents["invalid_reasons"]
    if (
        invalid["status"] != "PASS_SCIENTIFIC_INFRASTRUCTURE_SEPARATION"
        or invalid["infrastructure_misclassification_count"] != 0
        or len(invalid["cells"]) != 100
    ):
        raise Phase9DRValidationError("invalid-reason matrix changed")

    consistency = documents["split_consistency"]
    if (
        consistency["significance_tests_performed"] is not False
        or consistency["robot_rows_treated_as_independent"] is not False
        or consistency["joint_category_distribution"]["jensen_shannon_divergence_base2"] > 0.15
    ):
        raise Phase9DRValidationError("split consistency contract changed")

    balance = documents["class_balance"]
    if (
        balance["aggregate_level"]["train"]["positive"] != 532
        or balance["aggregate_level"]["train"]["negative"] != 354
        or balance["aggregate_level"]["validation"]["positive"] != 154
        or balance["aggregate_level"]["validation"]["negative"] != 86
        or balance["sampling_or_resampling_change"] != "NONE"
    ):
        raise Phase9DRValidationError("class-balance authority changed")

    requirements = documents["h1_requirements"]
    gate_status = {row["gate"]: row["status"] for row in requirements["label_audit_gates"]}
    if requirements["failed_predeclared_gates"] != [4] or gate_status[4] != "FAIL":
        raise Phase9DRValidationError("predeclared H1 label gate result changed")
    if requirements["post_hoc_minimum_rules_added"]:
        raise Phase9DRValidationError("post-hoc minimum support rule was added")
    mask = requirements["supervised_training_and_evaluation_mask"]
    if (
        mask["included_dispositions"] != ["RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"]
        or mask["excluded_dispositions"] != ["GENERATION_INVALID"]
        or mask["generation_invalid_mapped_to_label_zero"] is not False
    ):
        raise Phase9DRValidationError("supervised invalid-event mask changed")

    identifiability = documents["h1_identifiability"]
    if (
        identifiability["status"] != "NOT_IDENTIFIABLE_UNDER_CURRENT_FROZEN_GATE"
        or any(
            row["classification"] != "NOT_IDENTIFIABLE_FROM_CURRENT_DATA"
            for row in identifiability["comparisons"]
        )
    ):
        raise Phase9DRValidationError("H1 identifiability changed")

    statistical = documents["statistical_unit"]
    if (
        statistical["n_dependent_weighting_intended"] is not False
        or statistical["raw_row_mean_permitted"] is not False
        or statistical["robot_local_rows_statistically_independent"] is not False
        or any(
            row["frozen_event_averaged_effective_event_weight"] != 1.0
            for row in statistical["team_size_weight_audit"]
        )
    ):
        raise Phase9DRValidationError("statistical-unit or loss reduction changed")

    class_weight = documents["class_weight"]
    if (
        class_weight["decision"] != "NONE_UNWEIGHTED_BCE"
        or class_weight["oversampling"]
        or class_weight["undersampling"]
        or class_weight["family_weighting"]
        or class_weight["team_size_weighting"]
        or class_weight["synthetic_rows"]
    ):
        raise Phase9DRValidationError("class-weight decision changed")

    if documents["adequacy"]["classification"] != "RECOVERABILITY_DATASET_INADEQUATE_FOR_FROZEN_H1":
        raise Phase9DRValidationError("dataset adequacy changed")
    if documents["residual"]["decision"] != "HOLD_RESIDUAL_PENDING_RECOVERABILITY_SCIENTIFIC_DECISION":
        raise Phase9DRValidationError("Residual go/no-go changed")
    if documents["training"]["decision"] != "RECOVERABILITY_TRAINING_BLOCKED":
        raise Phase9DRValidationError("training readiness changed")

    closure = documents["closure"]
    if (
        closure["input_closure_commit"] != INPUT_COMMIT
        or closure["status"] != "COMPLETE_STOPPED_BEFORE_RESIDUAL_AND_TRAINING"
        or closure["verdict"] != "C"
        or any(closure["isolation"].values())
    ):
        raise Phase9DRValidationError("closure identity or isolation changed")
    for name, value in closure["artifact_hashes"].items():
        if name not in hashes or hashes[name] != value:
            raise Phase9DRValidationError(f"closure artifact binding changed: {name}")

    report_path = root / "docs/PHASE9D_R_RECOVERABILITY_DATASET_ADEQUACY_REPORT.md"
    report = report_path.read_text(encoding="ascii")
    if report.count("**C.") != 1 or "DO NOT START" in report:
        raise Phase9DRValidationError("final report verdict changed")
    return {
        "status": "PASS",
        "validated_artifact_count": len(documents),
        "closure_sha256": hashes["closure"],
        "verdict": "C",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(validate(args.root.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
