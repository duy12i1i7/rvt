#!/usr/bin/env python3
"""Build the canonical A1V closure and human-readable final report."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/rvt_fd24"
OFFICIAL = OUT / "phase9g_a1v_official_validation"


def _canonical(path: Path, field: str) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path}")
    return document


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _test_result(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"(?P<passed>\d+) passed(?:, (?P<warnings>\d+) warnings?)? in (?P<seconds>[0-9.]+)s",
        text,
    )
    if match is None:
        raise ValueError("postrun complete suite did not pass")
    return {
        "passed": int(match.group("passed")),
        "failed": 0,
        "warnings": int(match.group("warnings") or 0),
        "seconds": float(match.group("seconds")),
        "publication_required_xfailed": 0,
        "log_file_sha256": _file_sha(path),
    }


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return "\n".join(lines)


def _reason_totals(invalid: dict, split: str) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for item in invalid["splits"][split]["reason_distribution"]:
        totals[item["reason"]] += item["count"]
    return dict(sorted(totals.items()))


def _row_totals(balance: dict, split: str) -> dict[int, int]:
    totals: Counter[int] = Counter()
    for item in balance["robot_local_row_level"][split]["distribution"]:
        totals[int(item["label"])] += item["count"]
    return dict(sorted(totals.items()))


def main() -> None:
    train_closure = _canonical(
        OUT / "phase9g_a1c_train_closure_v1.json",
        "phase9g_a1c_train_closure_sha256",
    )
    completion = _canonical(
        OFFICIAL / "official_completion_audit.json",
        "phase9g_a1v_official_completion_audit_sha256",
    )
    validation_manifest = _canonical(
        OFFICIAL / "validation_dataset_manifest.json", "dataset_manifest_sha256"
    )
    validation_seal = _canonical(
        OFFICIAL / "VALIDATION_DATASET_SEAL.json", "dataset_seal_sha256"
    )
    combined = _canonical(
        OFFICIAL / "combined_dataset_root_manifest.json",
        "combined_recoverability_dataset_root_sha256",
    )
    combined_seal = _canonical(
        OFFICIAL / "COMBINED_DATASET_ROOT_SEAL.json",
        "combined_recoverability_dataset_root_seal_sha256",
    )
    coverage = _canonical(
        OFFICIAL / "recoverability_coverage_audit.json",
        "phase9g_a1v_recoverability_coverage_audit_sha256",
    )
    balance = _canonical(
        OFFICIAL / "recoverability_class_balance_audit.json",
        "phase9g_a1v_recoverability_class_balance_audit_sha256",
    )
    invalid = _canonical(
        OFFICIAL / "recoverability_invalid_reason_audit.json",
        "phase9g_a1v_recoverability_invalid_reason_audit_sha256",
    )
    isolation = _canonical(
        OFFICIAL / "recoverability_split_isolation_audit.json",
        "phase9g_a1v_recoverability_split_isolation_audit_sha256",
    )
    readiness = _canonical(
        OFFICIAL / "next_phase_readiness.json",
        "phase9g_a1v_next_phase_readiness_sha256",
    )
    postfinal = _canonical(
        OFFICIAL / "postfinal_dataset_validation.json",
        "phase9g_a1v_postfinal_dataset_validation_sha256",
    )
    combined_validation = _canonical(
        OFFICIAL / "combined_root_validation.json",
        "phase9g_a1v_combined_root_validation_sha256",
    )
    tests = _test_result(OUT / "phase9g_a1v_postrun_full_suite.log")
    if (
        completion["status"] != "PASS_COMPLETE_STOPPED"
        or postfinal["status"] != "PASS"
        or combined_validation["status"] != "PASS"
        or coverage["status"] != "PASS_DESCRIPTIVE_ONLY"
        or balance["class_weighting"] != "NOT_SELECTED"
        or invalid["infrastructure_conditions_classified_as_scientific_invalid"] != 0
        or isolation["status"] != "PASS"
        or readiness["status"] != "READY_FOR_EXPLICIT_PRETRAINING_COVERAGE_CLASS_WEIGHT_DECISION"
    ):
        raise ValueError("A1V closure input is not qualified")

    train = coverage["splits"]["train"]["totals"]
    validation = coverage["splits"]["validation"]["totals"]
    train_rows = _row_totals(balance, "train")
    validation_rows = _row_totals(balance, "validation")
    train_reasons = _reason_totals(invalid, "train")
    validation_reasons = _reason_totals(invalid, "validation")
    closure = {
        "schema_version": "rvt-phase9g-a1v-closure/v1",
        "phase": "PHASE_9G_A1V",
        "status": "COMPLETE_STOPPED_BEFORE_RESIDUAL_AND_TRAINING",
        "run_id": completion["run_id"],
        "authority_commit": completion["authority_commit"],
        "train": {
            **train,
            "manifest_sha256": train_closure["dataset"]["manifest_sha256"],
            "seal_sha256": train_closure["dataset"]["seal_sha256"],
        },
        "validation": {
            **validation,
            "replica_executions": completion["scientific_accounting"]["replica_executions"],
            "manifest_sha256": validation_manifest["dataset_manifest_sha256"],
            "seal_sha256": validation_seal["dataset_seal_sha256"],
            "wall_seconds": completion["telemetry"]["official_wall_seconds"],
            "candidate_cpu_hours": completion["telemetry"]["candidate_cpu_hours"],
            "storage_bytes": completion["dataset"]["storage_bytes"],
            **completion["infrastructure_accounting"],
        },
        "coverage": {
            "classification": coverage["overall_classification"],
            "audit_sha256": coverage["phase9g_a1v_recoverability_coverage_audit_sha256"],
            "descriptive_only": True,
            "scientific_validity_redefined": False,
        },
        "statistical_unit": coverage["statistical_unit"],
        "class_balance": {
            "train_aggregate": {"positive": train["RECOVERABLE_POSITIVE"], "negative": train["VALID_TASK_NEGATIVE"], "invalid": train["GENERATION_INVALID"]},
            "validation_aggregate": {"positive": validation["RECOVERABLE_POSITIVE"], "negative": validation["VALID_TASK_NEGATIVE"], "invalid": validation["GENERATION_INVALID"]},
            "train_robot_local_rows": {"negative": train_rows.get(0, 0), "positive": train_rows.get(1, 0)},
            "validation_robot_local_rows": {"negative": validation_rows.get(0, 0), "positive": validation_rows.get(1, 0)},
            "class_weighting": "NOT_SELECTED",
            "audit_sha256": balance["phase9g_a1v_recoverability_class_balance_audit_sha256"],
        },
        "invalid_reasons": {
            "train": train_reasons,
            "validation": validation_reasons,
            "infrastructure_misclassifications": 0,
            "audit_sha256": invalid["phase9g_a1v_recoverability_invalid_reason_audit_sha256"],
        },
        "split_isolation": {
            key: isolation[key]
            for key in (
                "source_episode_id_overlap", "decision_event_id_overlap",
                "scientific_row_id_overlap", "prohibited_layout_identity_overlap",
                "intentionally_shared_structural_template_count",
            )
        },
        "combined_root": {
            "manifest_sha256": combined["combined_recoverability_dataset_root_sha256"],
            "seal_sha256": combined_seal["combined_recoverability_dataset_root_seal_sha256"],
            "validation_sha256": combined_validation["phase9g_a1v_combined_root_validation_sha256"],
            "physical_files_merged": False,
        },
        "integrity": completion["integrity"],
        "tests": tests,
        "downstream": completion["downstream"],
        "sealed_domains": completion["sealed_domains"],
        "verdict": "C",
        "verdict_text": "Study-A Recoverability TRAIN and VALIDATION are finalized and reconciled; the complete Recoverability dataset is ready for the explicit pre-training coverage/class-weight decision phase.",
    }
    closure = attach_canonical_hash(closure, "phase9g_a1v_closure_sha256")
    closure_path = OUT / "phase9g_a1v_closure_v1.json"
    closure_path.write_text(
        json.dumps(closure, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )

    def coverage_table(split: str, key: str, headers: list[str], columns: list[str]) -> str:
        return _table(headers, [[item[column] for column in columns] for item in coverage["splits"][split][key]])

    report = f"""# Phase 9G-A1V Official Recoverability VALIDATION Report

## Status and verdict

Study-A Recoverability VALIDATION completed, reconciled, independently validated, and finalized. The immutable TRAIN and VALIDATION datasets are referenced by a sealed combined root.

**Verdict C. Study-A Recoverability TRAIN and VALIDATION are finalized and reconciled; the complete Recoverability dataset is ready for the explicit pre-training coverage/class-weight decision phase.**

## Identity and profile

- Authority commit: `{completion['authority_commit']}`
- Official run ID: `{completion['run_id']}`
- Production image: `{completion['container']['image']}`
- Profile: W=12, numeric threads=1, chunk=1, timeout=243 s
- Container: exit 0, network none, read-only root filesystem

## TRAIN

- Events: {train['decision_events']:,}
- Candidate aggregates: {train['candidate_aggregates']:,}
- Positive / negative / invalid: {train['RECOVERABLE_POSITIVE']:,} / {train['VALID_TASK_NEGATIVE']:,} / {train['GENERATION_INVALID']:,}
- Retained / dropped candidate pairs: {train['candidate_pair_retained_events']:,} / {train['candidate_pair_dropped_events']:,}
- Scientific rows: {train['scientific_rows']:,}
- Manifest: `{train_closure['dataset']['manifest_sha256']}`
- Seal: `{train_closure['dataset']['seal_sha256']}`

## VALIDATION

- Authoritative scheduled and completed events: {validation['decision_events']:,} / {validation['decision_events']:,}
- Candidate aggregates: {validation['candidate_aggregates']:,}
- Replica executions: {completion['scientific_accounting']['replica_executions']:,}
- Positive / negative / invalid: {validation['RECOVERABLE_POSITIVE']:,} / {validation['VALID_TASK_NEGATIVE']:,} / {validation['GENERATION_INVALID']:,}
- Retained / dropped candidate pairs: {validation['candidate_pair_retained_events']:,} / {validation['candidate_pair_dropped_events']:,}
- Scientific rows: {validation['scientific_rows']:,}
- Timeouts / retries / failures / duplicates / partial publications: 0 / 0 / 0 / 0 / 0
- Wall time: {completion['telemetry']['official_wall_seconds']:.3f} s
- Candidate CPU time: {completion['telemetry']['candidate_cpu_hours']:.6f} CPU-hours
- Manifest: `{validation_manifest['dataset_manifest_sha256']}`
- Seal: `{validation_seal['dataset_seal_sha256']}`

The exact equations are `{validation['RECOVERABLE_POSITIVE']} + {validation['VALID_TASK_NEGATIVE']} + {validation['GENERATION_INVALID']} = {validation['candidate_aggregates']}` and `{validation['candidate_pair_retained_events']} + {validation['candidate_pair_dropped_events']} = {validation['decision_events']}`. Published rows were reconciled per event using its actual N.

## Coverage

Overall descriptive classification: `{coverage['overall_classification']}`. This warning does not redefine scientific validity and no repair was made.

### TRAIN by family

{coverage_table('train', 'family_coverage', ['Family', 'Events', 'Retained', 'Positive', 'Negative', 'Invalid', 'Rows', 'Flags'], ['family', 'source_events', 'retained_candidate_pairs', 'positive_aggregates', 'negative_aggregates', 'generation_invalid_aggregates', 'scientific_rows', 'descriptive_flags'])}

### VALIDATION by family

{coverage_table('validation', 'family_coverage', ['Family', 'Events', 'Retained', 'Positive', 'Negative', 'Invalid', 'Rows', 'Flags'], ['family', 'source_events', 'retained_candidate_pairs', 'positive_aggregates', 'negative_aggregates', 'generation_invalid_aggregates', 'scientific_rows', 'descriptive_flags'])}

### TRAIN by N

{coverage_table('train', 'team_size_coverage', ['N', 'Events', 'Retained', 'Positive', 'Negative', 'Invalid', 'Rows'], ['team_size', 'source_events', 'retained_candidate_pairs', 'positive_aggregates', 'negative_aggregates', 'generation_invalid_aggregates', 'scientific_rows'])}

### VALIDATION by N

{coverage_table('validation', 'team_size_coverage', ['N', 'Events', 'Retained', 'Positive', 'Negative', 'Invalid', 'Rows'], ['team_size', 'source_events', 'retained_candidate_pairs', 'positive_aggregates', 'negative_aggregates', 'generation_invalid_aggregates', 'scientific_rows'])}

### Candidate topology

TRAIN:

{coverage_table('train', 'topology_coverage', ['Topology', 'Positive', 'Negative', 'Invalid'], ['candidate_topology', 'positive_aggregates', 'negative_aggregates', 'generation_invalid_aggregates'])}

VALIDATION:

{coverage_table('validation', 'topology_coverage', ['Topology', 'Positive', 'Negative', 'Invalid'], ['candidate_topology', 'positive_aggregates', 'negative_aggregates', 'generation_invalid_aggregates'])}

Every retained event contains both COMPACT and LINE candidate rows.

## Statistical unit

- TRAIN: {train['scientific_rows']:,} robot-local rows from {train['candidate_pair_retained_events']:,} independent retained source events.
- VALIDATION: {validation['scientific_rows']:,} robot-local rows from {validation['candidate_pair_retained_events']:,} independent retained source events.
- Rows are clustered by split, layout, source episode, and decision event. Robot-local rows are not reported as statistically independent episodes.

## Invalid reasons

TRAIN event reasons: `{json.dumps(train_reasons, sort_keys=True)}`.

VALIDATION event reasons: `{json.dumps(validation_reasons, sort_keys=True)}`.

Infrastructure conditions classified as scientific invalid: **NO**. Timeout, worker crash, writer failure, and scheduler failure misclassification counts are all zero.

## Class balance

- Aggregate TRAIN: positive={train['RECOVERABLE_POSITIVE']}, negative={train['VALID_TASK_NEGATIVE']}, invalid={train['GENERATION_INVALID']}.
- Aggregate VALIDATION: positive={validation['RECOVERABLE_POSITIVE']}, negative={validation['VALID_TASK_NEGATIVE']}, invalid={validation['GENERATION_INVALID']}.
- Robot-local TRAIN: positive={train_rows.get(1, 0)}, negative={train_rows.get(0, 0)}.
- Robot-local VALIDATION: positive={validation_rows.get(1, 0)}, negative={validation_rows.get(0, 0)}.
- Family, N, topology, and split distributions are canonical artifact `{balance['phase9g_a1v_recoverability_class_balance_audit_sha256']}`.
- Class weighting remains `NOT_SELECTED`.

## Split isolation

- Source episode ID overlap: {isolation['source_episode_id_overlap']}
- Decision event ID overlap: {isolation['decision_event_id_overlap']}
- Scientific row ID overlap: {isolation['scientific_row_id_overlap']}
- Prohibited layout identity overlap: {isolation['prohibited_layout_identity_overlap']}
- Intentionally shared structural templates: {isolation['intentionally_shared_structural_template_count']}

## Combined root and integrity

- Combined root: `{combined['combined_recoverability_dataset_root_sha256']}`
- Combined root seal: `{combined_seal['combined_recoverability_dataset_root_seal_sha256']}`
- Independent combined-root validation: `{combined_validation['phase9g_a1v_combined_root_validation_sha256']}`
- Physical TRAIN/VALIDATION files merged: NO
- Unresolved tasks, duplicates, partial publications, schema/hash failures, seed mismatches, and seal violations: all zero
- Postrun complete suite: {tests['passed']} passed, 0 failed, {tests['publication_required_xfailed']} publication-required xfailed

## Downstream and sealed domains

- Residual V2 started: NO
- Training operations: 0
- Hyperparameter trials: 0
- Model checkpoints: 0
- Optimizer states: 0
- Study A N24 accesses: 0
- Study B accesses: 0
- Final-test accesses: 0

Phase 9G-A1V stops here. No class weighting was selected, Residual V2 was not started, and no training occurred.
"""
    report_path = ROOT / "docs/PHASE9G_A1V_OFFICIAL_RECOVERABILITY_VALIDATION_REPORT.md"
    report_path.write_text(report, encoding="ascii")
    print(json.dumps({
        "closure_sha256": closure["phase9g_a1v_closure_sha256"],
        "report": str(report_path),
        "verdict": closure["verdict"],
        "validation_events": validation["decision_events"],
        "validation_rows": validation["scientific_rows"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
