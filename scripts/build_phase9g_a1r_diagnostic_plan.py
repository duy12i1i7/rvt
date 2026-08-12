#!/usr/bin/env python3
"""Predeclare the isolated Phase 9G-A1R timeout diagnostic replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash


OLD_TIMEOUT_SECONDS = 60.0
DIAGNOSTIC_WATCHDOG_MULTIPLIER = 5.0
PRODUCTION_IMAGE = (
    "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    timeout = json.loads(
        (root / "results/rvt_fd24/phase9g_a1r_timeout_unit_v1.json")
        .read_text(encoding="ascii")
    )
    unit = dict(timeout["timed_out_unit"])
    watchdog = OLD_TIMEOUT_SECONDS * DIAGNOSTIC_WATCHDOG_MULTIPLIER
    document = {
        "schema_version": "rvt-phase9g-a1r-timeout-diagnostic-plan/v1",
        "mode": "NON_OFFICIAL_DIAGNOSTIC",
        "official_staging_writes_permitted": 0,
        "production_image": PRODUCTION_IMAGE,
        "scientific_source_commit": "8cf64481cd17b2c44f7007d3722a8110e53cae46",
        "qualified_closure_commit": "6bcfc0e058603abf41d8cc26ad9586dc34941784",
        "stop_evidence_commit": "f5d81ac46a71c8f6ef5351ca3e993496e34e9cc4",
        "target_host": "100.71.102.9",
        "numeric_threads": 1,
        "isolated_workers": 1,
        "repeat_count": 2,
        "diagnostic_watchdog_seconds": watchdog,
        "watchdog_derivation": {
            "formula": "old_timeout_seconds * diagnostic_multiplier",
            "old_timeout_seconds": OLD_TIMEOUT_SECONDS,
            "diagnostic_multiplier": DIAGNOSTIC_WATCHDOG_MULTIPLIER,
            "result_seconds": watchdog,
            "production_authority": False,
            "purpose": (
                "distinguish a terminating long tail from a hang without "
                "preselecting a replacement production timeout"
            ),
        },
        "scientific_atomic_unit": unit,
        "required_comparisons": [
            "scientific_semantic_digest",
            "replica_output_digest",
            "target_v4_input_digest",
            "target_v4_output_digest",
        ],
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    document = attach_canonical_hash(
        document, "phase9g_a1r_timeout_diagnostic_plan_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
