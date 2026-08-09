#!/usr/bin/env python3
"""Derive and freeze the RB21 target worker matrix from W1 resource evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21.rb21_manifest import RB21P_QUALIFIED_IMAGE, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--residual-baseline", type=Path, required=True)
    parser.add_argument("--recoverability-baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--available-cpus", type=int, required=True)
    parser.add_argument("--visible-ram-bytes", type=int, required=True)
    args = parser.parse_args()

    residual = json.loads(args.residual_baseline.read_text(encoding="ascii"))
    recoverability = json.loads(args.recoverability_baseline.read_text(encoding="ascii"))
    baselines = (residual, recoverability)
    if any(row["configuration"]["workers"] != 1 for row in baselines):
        raise SystemExit("worker matrix requires W1 baselines")
    digests = {row["target_benchmark_manifest"] for row in baselines}
    if len(digests) != 1:
        raise SystemExit("W1 branches do not use the same benchmark manifest")

    peak_rss = max(
        int(row["benchmark"]["conservative_peak_total_worker_rss_bytes"])
        for row in baselines)
    ram_headroom_fraction = 0.25
    cpu_headroom = 4
    ram_ceiling = math.floor(
        args.visible_ram_bytes * (1.0 - ram_headroom_fraction) / peak_rss)
    cpu_ceiling = args.available_cpus - cpu_headroom
    safe_ceiling = min(ram_ceiling, cpu_ceiling)
    candidate_sequence = [1, 2, 4, 6, 8, 12, 16]
    matrix = [value for value in candidate_sequence if value <= safe_ceiling]
    if not matrix or matrix[0] != 1:
        raise SystemExit("no safe worker configuration")

    document = {
        "schema_version": "rvt-rb21-target-worker-matrix-predeclaration/v1",
        "status": "FROZEN_BEFORE_WORKER_SCALING_RESULTS",
        "qualified_image": RB21P_QUALIFIED_IMAGE,
        "target_benchmark_manifest": next(iter(digests)),
        "w1_evidence": {
            "residual": residual["rb21_target_benchmark_run_sha256"],
            "recoverability": recoverability["rb21_target_benchmark_run_sha256"],
            "conservative_peak_single_worker_rss_bytes": peak_rss,
        },
        "resource_contract": {
            "available_logical_cpus": args.available_cpus,
            "minimum_cpu_headroom_logical_cpus": cpu_headroom,
            "wsl_visible_ram_bytes": args.visible_ram_bytes,
            "minimum_ram_headroom_fraction": ram_headroom_fraction,
            "ram_available_to_workers_bytes": math.floor(
                args.visible_ram_bytes * (1.0 - ram_headroom_fraction)),
            "ram_worker_ceiling": ram_ceiling,
            "cpu_worker_ceiling": cpu_ceiling,
            "safe_worker_ceiling": safe_ceiling,
        },
        "candidate_sequence_considered": candidate_sequence,
        "declared_worker_matrix": matrix,
        "scaling_workload": {
            "residual_atomic_units_per_configuration": residual["benchmark"][
                "atomic_units"],
            "recoverability_atomic_units_per_configuration": recoverability[
                "benchmark"]["atomic_units"],
            "chunk_size_atomic_units": 1,
            "thread_profile": residual["configuration"]["thread_settings"],
            "run_branches_separately": True,
            "reuse_W1_baselines": True,
        },
        "selection_rule_frozen_before_scaling": {
            "hard_requirements": [
                "identical_scientific_semantic_digest_for_each_branch",
                "observed_peak_RSS_within_75_percent_WSL_RAM_budget",
                "worker_count_not_above_safe_ceiling",
                "no_operational_failure",
            ],
            "throughput_rule": (
                "select the smallest eligible W within 95 percent of the maximum "
                "eligible aggregate throughput"),
            "efficiency_floor_when_available": 0.50,
            "tail_rule": "reject unexplained p95 or maximum latency regression",
            "incremental_gain_preference": "PREFER_SMALLER_W",
        },
        "official_generation_executed": False,
    }
    write_json(
        args.output,
        attach_canonical_hash(document, "rb21_target_worker_matrix_predeclaration_sha256"),
    )


if __name__ == "__main__":
    main()
