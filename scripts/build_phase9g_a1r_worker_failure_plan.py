#!/usr/bin/env python3
"""Predeclare deterministic diagnostic replay of the A1R worker exception."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    identity = json.loads(args.identity.read_text(encoding="ascii"))
    unit = dict(identity["failed_atomic_unit"])
    document = {
        "schema_version": "rvt-phase9g-a1r-worker-failure-diagnostic-plan/v1",
        "mode": "NON_OFFICIAL_DIAGNOSTIC",
        "official_staging_writes_permitted": 0,
        "production_image": (
            "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
        ),
        "scientific_source_commit": "8cf64481cd17b2c44f7007d3722a8110e53cae46",
        "workers": 1,
        "numeric_threads": 1,
        "diagnostic_watchdog_seconds": 243.0,
        "watchdog_is_production_qualification": False,
        "failed_atomic_unit": unit,
        "replays": [
            {"replay_index": 1, "candidate_topology_id": 5},
            {"replay_index": 2, "candidate_topology_id": 5},
            {"replay_index": 3, "candidate_topology_id": 2},
        ],
        "expected_observation": {
            "exception_class": "ValueError",
            "exception_message": "S3 measured width must be finite and nonnegative",
            "source_stage_before_candidate_result": True,
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
        document, "phase9g_a1r_worker_failure_diagnostic_plan_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
