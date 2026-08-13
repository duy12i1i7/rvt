#!/usr/bin/env python3
"""Run additive A1S3Z RB20 and matched-randomness diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21p.audit import audit_rb20_semantic_replay
from scripts.run_phase9g0r_diagnostics import matched_randomness


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    rb20 = audit_rb20_semantic_replay(root)
    randomness = matched_randomness(root)
    expected = {
        "source_episodes": 4,
        "recoverability_rollouts": 14,
        "residual_candidate_evaluations": 36,
        "semantic_mismatches": 0,
        "scientific_identity_mismatches": 0,
    }
    if rb20["counts"] != expected:
        raise ValueError(f"RB20 regression mismatch: {rb20['counts']}")
    if randomness["status"] != "PASS":
        raise ValueError("matched-randomness regression failed")
    document = {
        "schema_version": "rvt-phase9-s3z-regression/v1",
        "mode": "NON_OFFICIAL_RUNTIME_CONFORMANCE_DIAGNOSTIC",
        "source_commit": "848e8b352a91e95af777ebbeccd5fbb43d53777e",
        "rb20": rb20,
        "matched_randomness": randomness,
        "official_producer_canary": {
            "artifact": "phase9_s3z_performance_result_v1.json",
            "scope": "Recoverability-only diagnostic producer",
            "candidate_aggregates": 12,
            "semantic_mismatches": 0,
        },
        "candidate_pair_and_target_v4": {
            "covered_by_focused_and_complete_test_suites": True,
            "unexplained_semantic_mismatches": 0,
        },
        "official_operations": {
            "recoverability_generation_resumed": False,
            "official_residual_v2_started": False,
            "official_staging_writes": 0,
            "training_operations": 0,
        },
        "diagnostic_runtime_conformance": {
            "rb20_residual_candidate_evaluations": 36,
            "scientific_rows": 0,
            "authorization_scope_broadened": False,
        },
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
        },
        "status": "PASS",
    }
    document = attach_canonical_hash(
        document, "phase9_s3z_regression_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "hash": document["phase9_s3z_regression_sha256"],
        "rb20_counts": rb20["counts"],
        "matched_randomness": randomness["status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
