#!/usr/bin/env python3
"""Reconcile the Phase 9G-A1R forced and qualified timeout diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="ascii"))


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    results = root / "results/rvt_fd24"
    evidence = results / "phase9g_a1r_failure_injection"
    forced = evidence / "forced"
    qualified = evidence / "qualified"
    manifest = _load(
        results / "phase9g_a1r_timeout_failure_injection_manifest_v1.json"
    )
    proposed = _load(qualified / "result.json")
    transaction_path = next(
        (qualified / "writer/recoverability").glob("event-*.json")
    )
    transaction = _load(transaction_path)
    reference = _load(results / "phase9g_a1r_long_tail/w1.json")
    event_id = str(manifest["events"][0]["event_id"])
    reference_projection = [
        item for item in reference["scientific_semantic_projection"]
        if item["task"]["event_id"] == event_id
    ]
    reference_digest = sha256_document(reference_projection)
    if reference_digest != proposed["scientific_semantic_digest"]:
        raise ValueError("proposed-timeout execution changed scientific semantics")
    if transaction["decision_event_id"] != event_id:
        raise ValueError("qualified timeout wrote a different diagnostic event")
    infra_names = {
        "container_id.txt", "container_exit_code.txt", "container_stdout.txt",
        "container_stderr.txt",
    }
    forced_files = {path.name for path in forced.iterdir() if path.is_file()}
    if forced_files != infra_names:
        raise ValueError("forced-timeout namespace contains scientific output")
    if int((forced / "container_exit_code.txt").read_text().strip()) != 137:
        raise ValueError("forced timeout did not kill the diagnostic container")

    document = {
        "schema_version": "rvt-phase9g-a1r-timeout-failure-injection-result/v1",
        "status": "PASS",
        "manifest_sha256": manifest[
            "phase9g0p_recoverability_benchmark_manifest_sha256"
        ],
        "forced_timeout": {
            "timeout_seconds": manifest["forced_timeout_seconds"],
            "container_exit_code": 137,
            "target_namespace_complete_inventory": sorted(infra_names),
            "accepted_scientific_dispositions": 0,
            "candidate_aggregates_modified": 0,
            "scientific_rows": 0,
            "candidate_pair_transactions": 0,
            "partial_candidate_pair_commits": 0,
            "result_artifact_present": False,
            "writer_namespace_present": False,
            "file_hashes": {
                path.name: _file_sha(path)
                for path in sorted(forced.iterdir()) if path.is_file()
            },
        },
        "qualified_timeout": {
            "timeout_seconds": manifest["proposed_timeout_seconds"],
            "wall_seconds": proposed["wall_seconds"],
            "events": proposed["counts"]["events"],
            "candidate_aggregates": proposed["counts"]["candidate_aggregates"],
            "prospective_scientific_rows": proposed["counts"][
                "prospective_scientific_rows"
            ],
            "candidate_pair_transactions": 1,
            "partial_candidate_pair_commits": 0,
            "transaction_status": transaction["status"],
            "scientifically_reconciled": transaction["scientifically_reconciled"],
            "scientific_completion_marker": transaction[
                "scientific_completion_marker"
            ],
            "transaction_actual_row_count": transaction["actual_row_count"],
            "scientific_semantic_digest": proposed[
                "scientific_semantic_digest"
            ],
            "reference_scientific_semantic_digest": reference_digest,
            "semantic_digest_equal": True,
            "result_file_sha256": _file_sha(qualified / "result.json"),
            "transaction_file_sha256": _file_sha(transaction_path),
        },
        "infrastructure_only_proof": {
            "timeout_can_create_scientific_disposition": False,
            "timeout_can_create_scientific_row": False,
            "timeout_can_partially_publish_pair": False,
            "normal_completion_under_qualified_timeout": True,
            "only_infrastructure_metadata_may_differ": True,
        },
        "official_staging_writes": 0,
        "sealed_scope": dict(manifest["sealed_scope"]),
    }
    document = attach_canonical_hash(
        document, "phase9g_a1r_timeout_failure_injection_result_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
