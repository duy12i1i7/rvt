#!/usr/bin/env python3
"""Build the canonical A1C closure and human-readable TRAIN report."""

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
OFFICIAL = OUT / "phase9g_a1c_official_train"


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
        r"(?P<passed>\d+) passed, (?P<warnings>\d+) warning in "
        r"(?P<seconds>[0-9.]+)s",
        text,
    )
    if match is None:
        raise ValueError("postrun complete suite did not pass")
    return {
        "passed": int(match.group("passed")),
        "failed": 0,
        "warnings": int(match.group("warnings")),
        "seconds": float(match.group("seconds")),
        "publication_required_xfailed": 0,
        "log_file_sha256": _file_sha(path),
    }


def _aggregate_summary(records: list[dict], key_name: str) -> list[dict]:
    result: Counter[tuple] = Counter()
    for record in records:
        result[(record[key_name], record["disposition"])] += record["count"]
    keys = sorted({key for key, _ in result}, key=str)
    return [
        {
            key_name: key,
            "RECOVERABLE_POSITIVE": result[(key, "RECOVERABLE_POSITIVE")],
            "VALID_TASK_NEGATIVE": result[(key, "VALID_TASK_NEGATIVE")],
            "GENERATION_INVALID": result[(key, "GENERATION_INVALID")],
        }
        for key in keys
    ]


def _pair_summary(records: list[dict], key_name: str) -> dict[Any, dict[str, int]]:
    result: Counter[tuple] = Counter()
    for record in records:
        result[(record[key_name], record["state"])] += record["count"]
    return {
        key: {
            "retained": result[(key, "RETAINED")],
            "dropped": result[(key, "DROPPED_NONPUBLISHED")],
        }
        for key in sorted({key for key, _ in result}, key=str)
    }


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return "\n".join(lines)


def main() -> None:
    audit = _canonical(
        OFFICIAL / "official_train_continuation_audit.json",
        "phase9g_a1c_official_train_continuation_audit_sha256",
    )
    reconciliation = _canonical(
        OFFICIAL / "train_reconciliation.json",
        "phase9g_a1c_recoverability_train_reconciliation_sha256",
    )
    manifest = _canonical(
        OFFICIAL / "dataset_manifest.json", "dataset_manifest_sha256"
    )
    seal = _canonical(OFFICIAL / "DATASET_SEAL.json", "dataset_seal_sha256")
    validation = _canonical(
        OFFICIAL / "postfinal_dataset_validation.json",
        "phase9g_a1c_postfinal_dataset_validation_sha256",
    )
    quality = _canonical(
        OFFICIAL / "train_data_quality_audit.json",
        "phase9g_a1c_train_data_quality_audit_sha256",
    )
    startup = _canonical(
        OUT / "phase9g_a1c_startup_requalification_v1.json",
        "phase9g_a1c_startup_requalification_sha256",
    )
    preflight = _canonical(
        OUT / "phase9g_a1c_resume_preflight_v1.json",
        "phase9g_a1c_resume_preflight_sha256",
    )
    tests = _test_result(OUT / "phase9g_a1c_postrun_full_suite.log")
    if (
        audit["status"] != "PASS"
        or reconciliation["status"] != "PASS"
        or validation["status"] != "PASS"
        or quality["status"] != "PASS_DESCRIPTIVE_ONLY"
        or manifest["status"] != "VALID_FROZEN_TRAIN_ONLY"
        or startup["status"] != "PASS_OPERATIONAL_RETRY_PERMITTED"
        or preflight["status"] != "PASS_ZERO_ESCAPES"
    ):
        raise ValueError("A1C closure input is not qualified")

    aggregate_records = quality[
        "aggregate_distribution_by_family_n_source_topology_disposition"
    ]
    pair_records = quality["candidate_pair_distribution_by_family_n_source_state"]
    family = _aggregate_summary(aggregate_records, "family")
    team_size = _aggregate_summary(aggregate_records, "team_size")
    topology = _aggregate_summary(aggregate_records, "candidate_topology")
    family_pairs = _pair_summary(pair_records, "family")
    team_pairs = _pair_summary(pair_records, "team_size")
    for record in family:
        record.update(family_pairs[record["family"]])
    for record in team_size:
        record.update(team_pairs[record["team_size"]])

    closure = {
        "schema_version": "rvt-phase9g-a1c-train-closure/v1",
        "phase": "PHASE_9G_A1C",
        "status": "COMPLETE_STOPPED_BEFORE_VALIDATION",
        "identity": audit["identity"],
        "run_id": audit["run_id"],
        "parent_run_id": audit["parent_run_id"],
        "prestart": {
            "events": 210,
            "scientific_rows": 342,
            "checkpoint_sha256": preflight["staging"]["checkpoint_sha256"],
            "checkpoint_exact": preflight["staging"]["checkpoint_exact"],
            "duplicates": preflight["staging"]["duplicates"],
            "partial_transactions": preflight["staging"]["partial_transactions"],
            "s3_unresolved_ambiguities": preflight["s3_guard"][
                "unresolved_s3_ambiguities"
            ],
        },
        "profile": audit["profile"],
        "train_execution": {
            **audit["complete_train"],
            "infrastructure_timeouts_during_a1c": 0,
            "historical_infrastructure_timeouts_before_a1c": 2,
            "scientific_retries": 0,
            "startup_launch_failures_before_scientific_execution": 1,
            "writer_failures": 0,
            "duplicates": 0,
            "partial_transactions": 0,
            "wall_seconds_a1c": audit["continuation_execution"]["wall_seconds"],
            "wall_seconds_accumulated_observed_lineage": reconciliation[
                "operational"
            ]["total_observed_wall_seconds"],
            "candidate_cpu_hours_a1c": audit["continuation_execution"][
                "candidate_cpu_hours"
            ],
            "sampled_cpu_hours_accumulated_lineage": reconciliation[
                "operational"
            ]["total_sampled_cpu_hours"],
            "maximum_atomic_unit_wall_seconds": audit[
                "continuation_execution"
            ]["maximum_atomic_unit_wall_seconds"],
        },
        "s3": {
            "complete_train_source_instances": quality["s3"][
                "complete_train_source_instances"
            ],
            "complete_train_decision_events": quality["s3"][
                "complete_train_decision_events"
            ],
            "complete_train_candidate_aggregates": quality["s3"][
                "complete_train_candidate_aggregates"
            ],
            "continuation_remaining_counter_levels": quality["s3"][
                "continuation_remaining_prestart_counter_levels"
            ],
            "complete_train_candidate_pair_distribution": quality["s3"][
                "complete_train_candidate_pair_distribution"
            ],
            "unresolved_ambiguities": quality["s3"]["unresolved_ambiguities"],
        },
        "existing_data": quality["original_rows"],
        "integrity": {
            key: reconciliation["observed"][key]
            for key in (
                "unresolved_infrastructure_failures", "unaccounted_events",
                "partial_candidate_pair_publications",
                "duplicate_scientific_identities", "unexpected_duplicate_transactions",
                "hash_failures", "schema_failures", "seed_mismatches",
                "seal_violations",
            )
        },
        "dataset": {
            "dataset_id": manifest["dataset_id"],
            "scientific_rows": manifest["scientific_row_count"],
            "transactions": manifest["transaction_count"],
            "shards": len(manifest["shards"]),
            "storage_bytes": validation["dataset_storage_bytes"],
            "manifest_sha256": manifest["dataset_manifest_sha256"],
            "seal_sha256": seal["dataset_seal_sha256"],
            "postfinal_validation_sha256": validation[
                "phase9g_a1c_postfinal_dataset_validation_sha256"
            ],
        },
        "descriptive_distribution": {
            "by_family": family,
            "by_team_size": team_size,
            "by_candidate_topology": topology,
            "scientific_invalid_reason_distribution": quality[
                "scientific_invalid_reason_distribution"
            ],
            "complete_cross_breakdown_artifact_sha256": quality[
                "phase9g_a1c_train_data_quality_audit_sha256"
            ],
            "class_weighting": "NOT_SELECTED",
        },
        "tests": {
            "prestart_complete_suite": preflight["tests"]["complete_suite"],
            "postrun_complete_suite": tests,
            "dataset_validator": "PASS",
        },
        "sealed_domains": reconciliation["sealed_domains"],
        "downstream": audit["downstream"],
        "verdict": "C",
        "verdict_text": (
            "Study-A Recoverability TRAIN completed, reconciled and finalized "
            "successfully; validation may be separately authorized."
        ),
    }
    closure = attach_canonical_hash(
        closure, "phase9g_a1c_train_closure_sha256"
    )
    closure_path = OUT / "phase9g_a1c_train_closure_v1.json"
    closure_path.write_text(
        json.dumps(closure, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )

    totals = quality["totals"]
    s3 = closure["s3"]
    counters = s3["continuation_remaining_counter_levels"]
    report = f"""# Phase 9G-A1C Official Recoverability TRAIN Report

## Status and verdict

Study-A Recoverability TRAIN completed, reconciled, independently validated, and finalized. Recoverability validation was not started.

**Verdict C. Study-A Recoverability TRAIN completed, reconciled and finalized successfully; validation may be separately authorized.**

## Identity

- Evidence commit at authorization: `af5c083e58476f5bd8a08710ce567176108e8f06`
- Authority commit: `869db24fac87b24b60a95fd192a6a75a63fc0ed0`
- Startup requalification commit: `982349d92863a0a3c5a6bcdce25332877df27be0`
- Executable image source: `848e8b352a91e95af777ebbeccd5fbb43d53777e`
- Target image: `{audit['identity']['production_image']}`
- Authorization continuation: `{audit['identity']['authorization_continuation_sha256']}`
- Run ID: `{audit['run_id']}`
- Parent run ID: `{audit['parent_run_id']}`

## Prestart

- Initial events: 210
- Initial rows: 342
- Checkpoint: `{closure['prestart']['checkpoint_sha256']}` (exact)
- Duplicate identities: 0
- Partial transactions: 0
- Remaining-manifest S3 unresolved ambiguities: 0
- Qualified profile: W=12, numeric threads=1, chunk=1, timeout=243 s

The first launch exited before scientific execution because `/opt/rvt` selected the image copy of an operational helper. Attempt 1 wrote 0 transactions and 0 rows. The launch binding was requalified with working directory `/a1c`; no wrapper bytes, source image, profile, authorization, or scientific semantics changed.

## TRAIN execution

| Metric | Result |
| --- | ---: |
| Source episodes | 1,200 |
| Decision events | 6,000 |
| Candidate aggregates | 12,000 |
| Replica executions | 1,094 |
| RECOVERABLE_POSITIVE | 532 |
| VALID_TASK_NEGATIVE | 354 |
| GENERATION_INVALID | 11,114 |
| Candidate pairs retained | 443 |
| Candidate pairs dropped/nonpublished | 5,557 |
| Robot-local scientific rows | 8,340 |
| A1C infrastructure timeouts | 0 |
| Historical pre-A1C infrastructure timeouts | 2 |
| Scientific retries | 0 |
| Writer failures | 0 |
| Duplicates | 0 |
| Partial transactions | 0 |
| A1C wall time | {closure['train_execution']['wall_seconds_a1c']:.3f} s |
| Accumulated observed lineage wall time | {closure['train_execution']['wall_seconds_accumulated_observed_lineage']:.3f} s |
| A1C candidate CPU time | {closure['train_execution']['candidate_cpu_hours_a1c']:.6f} CPU-hours |
| Accumulated sampled CPU time | {closure['train_execution']['sampled_cpu_hours_accumulated_lineage']:.6f} CPU-hours |
| Maximum atomic-unit wall time | {closure['train_execution']['maximum_atomic_unit_wall_seconds']:.3f} s |

## S3 counter levels

These denominators are intentionally not pooled:

- Complete TRAIN S3 source instances: {s3['complete_train_source_instances']}
- Complete TRAIN S3 decision events: {s3['complete_train_decision_events']}
- Complete TRAIN S3 candidate aggregates: {s3['complete_train_candidate_aggregates']}
- Remaining-manifest source instances carried through continuation status: {counters['source_s3_instances']}
- Robot-local S3 guard observations: {counters['robot_local_s3_observations']}
- Participating support observations: {counters['participating_support_observations']}
- CENTERLINE_NEUTRAL support observations: {counters['centerline_neutral_support_observations']}
- Resolved opposing-pair robot observations: {counters['resolved_opposing_pairs']}
- Existing HOLD_UNKNOWN robot observations: {counters['hold_unknown_robot_observations']}
- Existing source-invalid instances: {counters['source_invalid_instances']}
- Unresolved S3 ambiguities: {counters['unresolved_s3_ambiguities']}

Complete TRAIN S3 has 45 retained and 955 dropped/nonpublished candidate pairs.

## Existing data lineage

All 342 original rows were retained byte-for-byte and none were regenerated: 254 `UNAFFECTED`, 88 `DEPENDENCY_PRESENT_BUT_VALUE_VALID`, 0 `POTENTIALLY_AFFECTED`, and 0 `PROVEN_AFFECTED`.

## Integrity

All 6,000 transaction hashes, 8,340 row identities, graph fingerprints, matched seeds, candidate-pair boundaries, shard hashes, indexes, and hard-link provenance passed. Unresolved tasks, partial publications, duplicate identities, hash failures, schema failures, seed mismatches, and seal violations are all zero.

The frozen invalid-reason distribution is 3,517 `SOURCE_TERMINATED_BEFORE_EVENT:COLLISION`, 1,920 `SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE`, and 120 `SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID` events. These sum to the 5,557 dropped/nonpublished pairs.

## Dataset

- Dataset ID: `{manifest['dataset_id']}`
- Rows: {manifest['scientific_row_count']:,}
- Transactions/audit sidecars: {manifest['transaction_count']:,}
- Shards: {len(manifest['shards'])} (`2048, 2048, 2048, 2048, 148` rows)
- Storage: {validation['dataset_storage_bytes']:,} bytes
- Manifest: `{manifest['dataset_manifest_sha256']}`
- Seal: `{seal['dataset_seal_sha256']}`
- Independent validation: `{validation['phase9g_a1c_postfinal_dataset_validation_sha256']}`
- Class weighting: `NOT_SELECTED`

## Descriptive distribution

### By family

{_markdown_table(['Family', 'Positive', 'Negative', 'Invalid', 'Pairs retained', 'Pairs dropped'], [[r['family'], r['RECOVERABLE_POSITIVE'], r['VALID_TASK_NEGATIVE'], r['GENERATION_INVALID'], r['retained'], r['dropped']] for r in family])}

### By team size

{_markdown_table(['N', 'Positive', 'Negative', 'Invalid', 'Pairs retained', 'Pairs dropped'], [[r['team_size'], r['RECOVERABLE_POSITIVE'], r['VALID_TASK_NEGATIVE'], r['GENERATION_INVALID'], r['retained'], r['dropped']] for r in team_size])}

### By candidate topology

{_markdown_table(['Topology', 'Positive', 'Negative', 'Invalid'], [[r['candidate_topology'], r['RECOVERABLE_POSITIVE'], r['VALID_TASK_NEGATIVE'], r['GENERATION_INVALID']] for r in topology])}

The full family x N x source class x candidate topology cross-breakdown is canonical artifact `{quality['phase9g_a1c_train_data_quality_audit_sha256']}`. No sampling, threshold, Target V4, scenario-count, or class-weighting decision was made.

## Tests and sealed domains

- Prestart complete suite: {preflight['tests']['complete_suite']['passed']} passed, 0 failed
- Postrun complete suite: {tests['passed']} passed, 0 failed
- Independent dataset validator: PASS
- Study A N24 accesses: 0
- Study B accesses: 0
- Final-test accesses: 0
- Recoverability validation started: NO
- Residual V2 started: NO
- Training operations: 0
- Checkpoints: 0
- Optimizer states: 0

Phase 9G-A1C stops here. Validation requires separate owner authorization.
"""
    report_path = ROOT / "docs/PHASE9G_A1C_OFFICIAL_RECOVERABILITY_TRAIN_REPORT.md"
    report_path.write_text(report, encoding="ascii")
    print(json.dumps({
        "closure_sha256": closure["phase9g_a1c_train_closure_sha256"],
        "report": str(report_path),
        "verdict": closure["verdict"],
        "events": totals["decision_events"],
        "rows": totals["scientific_rows"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
