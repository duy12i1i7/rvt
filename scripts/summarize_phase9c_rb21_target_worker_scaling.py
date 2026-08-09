#!/usr/bin/env python3
"""Validate RB21 target worker scaling and select the production worker count."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21.rb21_manifest import write_json


def _load(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="ascii"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--w1-residual", type=Path, required=True)
    parser.add_argument("--w1-recoverability", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    matrix = _load(args.matrix)
    w1 = {
        "residual": _load(args.w1_residual),
        "recoverability": _load(args.w1_recoverability),
    }
    runs = {}
    for workers in matrix["declared_worker_matrix"]:
        runs[workers] = (w1 if workers == 1 else {
            kind: _load(args.run_directory / f"worker-w{workers}-{kind}.json")
            for kind in ("residual", "recoverability")
        })

    baseline_digests = {
        kind: row["benchmark"]["scientific_semantic_digest"]
        for kind, row in w1.items()
    }
    rows = []
    for workers, branches in runs.items():
        residual = branches["residual"]
        recoverability = branches["recoverability"]
        if any(branch["configuration"]["workers"] != workers
               for branch in branches.values()):
            raise SystemExit(f"W{workers} artifact has wrong worker count")
        if any(branch["configuration"]["chunk_size_atomic_units"] != 1
               for branch in branches.values()):
            raise SystemExit(f"W{workers} scaling artifact has nonbaseline chunk")
        total_wall = sum(float(branch["benchmark"]["wall_seconds"])
                         for branch in branches.values())
        total_cpu = sum(float(branch["benchmark"]["aggregate_cpu_seconds"])
                        for branch in branches.values())
        total_units = sum(int(branch["benchmark"]["atomic_units"])
                          for branch in branches.values())
        digest_equal = all(
            branch["benchmark"]["scientific_semantic_digest"]
            == baseline_digests[kind] for kind, branch in branches.items())
        rows.append({
            "workers": workers,
            "residual_run_sha256": residual["rb21_target_benchmark_run_sha256"],
            "recoverability_run_sha256": recoverability[
                "rb21_target_benchmark_run_sha256"],
            "wall_seconds_sequential_branches": total_wall,
            "atomic_units": total_units,
            "throughput_atomic_units_per_second": total_units / total_wall,
            "residual_expert_decisions_per_second": (
                residual["benchmark"]["atomic_units"]
                / residual["benchmark"]["wall_seconds"]),
            "residual_candidate_evaluations_per_second": (
                residual["distributions"]["residual"]["candidate_evaluations"]
                / residual["benchmark"]["wall_seconds"]),
            "recoverability_atomic_units_per_second": (
                recoverability["benchmark"]["atomic_units"]
                / recoverability["benchmark"]["wall_seconds"]),
            "recoverability_replica_rollouts_per_second": (
                recoverability["distributions"]["recoverability"]["replica_rollouts"]
                / recoverability["benchmark"]["wall_seconds"]),
            "aggregate_cpu_seconds": total_cpu,
            "allocated_worker_cpu_utilization_percent": (
                100.0 * total_cpu / total_wall / workers),
            "host_24_cpu_utilization_percent": 100.0 * total_cpu / total_wall / 24,
            "peak_aggregate_worker_rss_bytes": max(
                int(branch["benchmark"]["conservative_peak_total_worker_rss_bytes"])
                for branch in branches.values()),
            "residual_atomic_latency_seconds": residual["distributions"][
                "residual"]["atomic_unit_wall_seconds"],
            "recoverability_atomic_latency_seconds": recoverability["distributions"][
                "recoverability"]["atomic_unit_wall_seconds"],
            "residual_scientific_semantic_digest": residual["benchmark"][
                "scientific_semantic_digest"],
            "recoverability_scientific_semantic_digest": recoverability["benchmark"][
                "scientific_semantic_digest"],
            "scientific_semantic_digests_equal_to_W1": digest_equal,
            "gpu_utilization_percent_before_after": sorted({
                sample["utilization_percent"]
                for branch in branches.values()
                for observation in (branch["observations_before"],
                                    branch["observations_after"])
                for sample in observation["gpu"]["gpus"]
            }),
        })

    baseline_throughput = rows[0]["throughput_atomic_units_per_second"]
    for row in rows:
        row["speedup"] = row["throughput_atomic_units_per_second"] / baseline_throughput
        row["parallel_efficiency"] = row["speedup"] / row["workers"]
    eligible = [row for row in rows
                if row["scientific_semantic_digests_equal_to_W1"]
                and row["parallel_efficiency"] >= matrix[
                    "selection_rule_frozen_before_scaling"][
                        "efficiency_floor_when_available"]]
    if not eligible:
        raise SystemExit("no worker configuration satisfies semantic/efficiency gates")
    maximum = max(row["throughput_atomic_units_per_second"] for row in eligible)
    selected = min(
        row["workers"] for row in eligible
        if row["throughput_atomic_units_per_second"] >= 0.95 * maximum)
    selected_row = next(row for row in rows if row["workers"] == selected)
    document = {
        "schema_version": "rvt-rb21-target-worker-scaling/v1",
        "qualified_target_measurement": True,
        "worker_matrix_predeclaration": matrix[
            "rb21_target_worker_matrix_predeclaration_sha256"],
        "rows": rows,
        "all_semantic_digests_equal": all(
            row["scientific_semantic_digests_equal_to_W1"] for row in rows),
        "selected_worker_count": selected,
        "selected_row": selected_row,
        "selection_rule_applied": matrix["selection_rule_frozen_before_scaling"],
        "selection_rationale": (
            "smallest semantically valid, efficiency-qualified W within 95 percent "
            "of maximum eligible aggregate throughput"),
        "writer_throughput_reference": "QUALIFIED_SEPARATELY_FOR_EVERY_DECLARED_W",
        "official_generation_executed": False,
    }
    write_json(
        args.output,
        attach_canonical_hash(document, "rb21_target_worker_scaling_sha256"),
    )


if __name__ == "__main__":
    main()
