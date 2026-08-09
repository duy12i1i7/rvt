#!/usr/bin/env python3
"""Freeze the complete-atomic-unit chunk matrix after worker selection."""

import argparse
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21.rb21_manifest import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-scaling", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scaling = json.loads(args.worker_scaling.read_text(encoding="ascii"))
    if not scaling["all_semantic_digests_equal"]:
        raise SystemExit("cannot declare chunks after worker semantic mismatch")
    document = {
        "schema_version": "rvt-rb21-target-chunk-matrix-predeclaration/v1",
        "status": "FROZEN_BEFORE_CHUNK_RESULTS",
        "worker_scaling": scaling["rb21_target_worker_scaling_sha256"],
        "selected_worker_count": scaling["selected_worker_count"],
        "declared_chunk_sizes_atomic_units": [1, 2, 4, 8],
        "branches_benchmarked_separately": ["residual", "recoverability"],
        "chunk_one_reuses_selected_worker_scaling_measurement": True,
        "atomic_boundaries": {
            "residual": "ONE_DECISION_ONE_ROBOT_ALL_NINE_CANDIDATES",
            "recoverability": "ONE_DECISION_ONE_TOPOLOGY_ALL_FROZEN_REPLICAS",
            "candidate_split": "PROHIBITED",
            "replica_split": "PROHIBITED",
        },
        "selection_rule_frozen_before_chunk_results": {
            "hard_requirements": [
                "scientific_semantic_digest_equal_to_chunk_one",
                "no_operational_failure",
                "peak_RSS_within_selected_worker_RAM_budget",
            ],
            "throughput_near_equal_fraction": 0.95,
            "selection": (
                "for each branch choose the smallest eligible chunk within 95 percent "
                "of that branch's maximum throughput"),
            "priority": [
                "scientific_identity", "reasonable_throughput", "tail_load_balance",
                "small_retry_blast_radius", "atomic_resume_granularity", "RAM_safety",
            ],
        },
        "official_generation_executed": False,
    }
    write_json(
        args.output,
        attach_canonical_hash(document, "rb21_target_chunk_matrix_predeclaration_sha256"),
    )


if __name__ == "__main__":
    main()
