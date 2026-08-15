#!/usr/bin/env python3
"""Independently validate the immutable A1V TRAIN+VALIDATION reference root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


TRAIN_ID = "phase9g-a1-study-a-train-recoverability-v1"
VALIDATION_ID = "phase9g-a1-study-a-validation-recoverability-v1"
COMBINED_ID = "phase9g-a1-study-a-recoverability-train-validation-root-v1"


def _canonical(path: Path, field: str) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path}")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    audit = data_root / "audit" / args.run_id
    train_root = data_root / "final" / TRAIN_ID
    validation_root = data_root / "final" / VALIDATION_ID
    combined_root = data_root / "final" / COMBINED_ID

    train_manifest = _canonical(train_root / "dataset_manifest.json", "dataset_manifest_sha256")
    train_seal = _canonical(train_root / "DATASET_SEAL.json", "dataset_seal_sha256")
    validation_manifest = _canonical(validation_root / "dataset_manifest.json", "dataset_manifest_sha256")
    validation_seal = _canonical(validation_root / "DATASET_SEAL.json", "dataset_seal_sha256")
    combined = _canonical(combined_root / "dataset_root_manifest.json", "combined_recoverability_dataset_root_sha256")
    combined_seal = _canonical(combined_root / "DATASET_ROOT_SEAL.json", "combined_recoverability_dataset_root_seal_sha256")
    generation = _canonical(audit / "validation_generation_audit.json", "phase9g_a1v_validation_generation_audit_sha256")
    coverage = _canonical(audit / "recoverability_coverage_audit.json", "phase9g_a1v_recoverability_coverage_audit_sha256")
    balance = _canonical(audit / "recoverability_class_balance_audit.json", "phase9g_a1v_recoverability_class_balance_audit_sha256")
    invalid = _canonical(audit / "recoverability_invalid_reason_audit.json", "phase9g_a1v_recoverability_invalid_reason_audit_sha256")
    isolation = _canonical(audit / "recoverability_split_isolation_audit.json", "phase9g_a1v_recoverability_split_isolation_audit_sha256")
    readiness = _canonical(audit / "next_phase_readiness.json", "phase9g_a1v_next_phase_readiness_sha256")
    postfinal = _canonical(audit / "postfinal_dataset_validation.json", "phase9g_a1v_postfinal_dataset_validation_sha256")

    expected_splits = {
        "train": {
            "dataset_id": TRAIN_ID,
            "manifest_sha256": train_manifest["dataset_manifest_sha256"],
            "seal_sha256": train_seal["dataset_seal_sha256"],
            "scientific_rows": 8340,
            "retained_source_events": 443,
        },
        "validation": {
            "dataset_id": VALIDATION_ID,
            "manifest_sha256": validation_manifest["dataset_manifest_sha256"],
            "seal_sha256": validation_seal["dataset_seal_sha256"],
            "scientific_rows": 2294,
            "retained_source_events": 120,
        },
    }
    if (
        combined["status"] != "COMPLETE_REFERENTIAL_ROOT"
        or combined["splits"] != expected_splits
        or combined["physical_files_merged"] is not False
        or combined["mutable_namespace"] is not False
        or combined["class_weighting"] != "NOT_SELECTED"
        or any(combined["sealed_domains"].values())
    ):
        raise ValueError("combined root scope or split references changed")
    if combined["generation_audits"] != {
        "validation_generation": generation["phase9g_a1v_validation_generation_audit_sha256"],
        "coverage": coverage["phase9g_a1v_recoverability_coverage_audit_sha256"],
        "class_balance": balance["phase9g_a1v_recoverability_class_balance_audit_sha256"],
        "invalid_reasons": invalid["phase9g_a1v_recoverability_invalid_reason_audit_sha256"],
        "split_isolation": isolation["phase9g_a1v_recoverability_split_isolation_audit_sha256"],
    }:
        raise ValueError("combined root audit references changed")
    if (
        combined_seal["combined_recoverability_dataset_root_sha256"]
        != combined["combined_recoverability_dataset_root_sha256"]
        or any(combined_seal[key] for key in (
            "train_dataset_mutation_permitted",
            "validation_dataset_mutation_permitted",
            "residual_v2_authorized",
            "training_authorized",
            "class_weighting_selected",
        ))
    ):
        raise ValueError("combined root seal is inconsistent")
    if (
        generation["status"] != "PASS"
        or any(generation["infrastructure"].values())
        or any(generation["sealed_domains"].values())
        or coverage["status"] != "PASS_DESCRIPTIVE_ONLY"
        or coverage["class_weighting"] != "NOT_SELECTED"
        or balance["status"] != "PASS_DESCRIPTIVE_ONLY"
        or balance["class_weighting"] != "NOT_SELECTED"
        or invalid["status"] != "PASS_SCIENTIFIC_INFRASTRUCTURE_SEPARATION"
        or invalid["infrastructure_conditions_classified_as_scientific_invalid"] != 0
        or isolation["status"] != "PASS"
        or any(isolation[key] for key in (
            "source_episode_id_overlap",
            "decision_event_id_overlap",
            "scientific_row_id_overlap",
            "prohibited_layout_identity_overlap",
        ))
        or postfinal["status"] != "PASS"
    ):
        raise ValueError("one closure audit failed")
    if (
        readiness["status"] != "READY_FOR_EXPLICIT_PRETRAINING_COVERAGE_CLASS_WEIGHT_DECISION"
        or readiness["combined_dataset_root_sha256"]
        != combined["combined_recoverability_dataset_root_sha256"]
        or readiness["combined_dataset_root_seal_sha256"]
        != combined_seal["combined_recoverability_dataset_root_seal_sha256"]
        or readiness["class_weighting"] != "NOT_SELECTED"
        or readiness["residual_v2_started"] is not False
        or any(readiness[key] for key in (
            "training_operations", "hyperparameter_trials", "model_checkpoints",
            "optimizer_states", "study_a_n24_accesses", "study_b_accesses",
            "final_test_accesses",
        ))
    ):
        raise ValueError("next-phase readiness crossed an authorization boundary")
    files = tuple(path for path in combined_root.rglob("*") if path.is_file())
    if len(files) != 2 or (combined_root.stat().st_mode & 0o777) != 0o555:
        raise ValueError("combined root is not a minimal read-only reference root")
    if any(path.stat().st_mode & 0o222 for path in files):
        raise ValueError("combined root contains a writable file")

    report = {
        "schema_version": "rvt-phase9g-a1v-combined-root-validation/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS",
        "combined_dataset_root_sha256": combined["combined_recoverability_dataset_root_sha256"],
        "combined_dataset_root_seal_sha256": combined_seal["combined_recoverability_dataset_root_seal_sha256"],
        "train_manifest_sha256": train_manifest["dataset_manifest_sha256"],
        "train_seal_sha256": train_seal["dataset_seal_sha256"],
        "validation_manifest_sha256": validation_manifest["dataset_manifest_sha256"],
        "validation_seal_sha256": validation_seal["dataset_seal_sha256"],
        "referential_files": len(files),
        "directory_mode_octal": oct(combined_root.stat().st_mode & 0o777),
        "writable_files": 0,
        "split_identity_overlaps": 0,
        "scientific_invalid_infrastructure_misclassifications": 0,
        "class_weighting": "NOT_SELECTED",
        "residual_started": False,
        "training_operations": 0,
        "sealed_domain_accesses": 0,
    }
    report = attach_canonical_hash(report, "phase9g_a1v_combined_root_validation_sha256")
    output = audit / "combined_root_validation.json"
    output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": report["status"],
        "hash": report["phase9g_a1v_combined_root_validation_sha256"],
        "combined_root": report["combined_dataset_root_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
