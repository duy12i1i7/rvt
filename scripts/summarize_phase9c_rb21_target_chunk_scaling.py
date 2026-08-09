#!/usr/bin/env python3
"""Validate chunk invariance and select per-branch RB21 target chunk sizes."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21.rb21_manifest import write_json


def _load(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="ascii"))


def _load_balance(results) -> Mapping[str, Any]:
    counts = list(Counter(int(row["pid"]) for row in results).values())
    mean = statistics.fmean(counts)
    return {
        "workers_observed": len(counts),
        "atomic_units_per_worker_minimum": min(counts),
        "atomic_units_per_worker_maximum": max(counts),
        "atomic_units_per_worker_mean": mean,
        "atomic_units_per_worker_population_stdev": statistics.pstdev(counts),
        "coefficient_of_variation": statistics.pstdev(counts) / mean,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--chunk-one-residual", type=Path, required=True)
    parser.add_argument("--chunk-one-recoverability", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    declaration = _load(args.declaration)
    workers = declaration["selected_worker_count"]
    chunks = declaration["declared_chunk_sizes_atomic_units"]
    branches = {}
    selections = {}
    for kind in ("residual", "recoverability"):
        rows = []
        baseline_digest = None
        for chunk in chunks:
            if chunk == 1:
                path = (args.chunk_one_residual if kind == "residual"
                        else args.chunk_one_recoverability)
            else:
                path = args.run_directory / f"chunk-c{chunk}-{kind}.json"
            run = _load(path)
            if run["configuration"]["workers"] != workers:
                raise SystemExit(f"chunk C{chunk} {kind} has wrong worker count")
            if run["configuration"]["chunk_size_atomic_units"] != chunk:
                raise SystemExit(f"chunk C{chunk} {kind} has wrong chunk size")
            digest = run["benchmark"]["scientific_semantic_digest"]
            if baseline_digest is None:
                baseline_digest = digest
            results = run["benchmark"]["results"]
            wall = float(run["benchmark"]["wall_seconds"])
            cpu = float(run["benchmark"]["aggregate_cpu_seconds"])
            rows.append({
                "chunk_size_atomic_units": chunk,
                "run_sha256": run["rb21_target_benchmark_run_sha256"],
                "wall_seconds": wall,
                "throughput_atomic_units_per_second": (
                    run["benchmark"]["atomic_units"] / wall),
                "parallel_noncompute_wall_proxy_seconds": max(
                    0.0, wall - cpu / workers),
                "atomic_unit_latency_seconds": run["distributions"][kind][
                    "atomic_unit_wall_seconds"],
                "peak_aggregate_worker_rss_bytes": run["benchmark"][
                    "conservative_peak_total_worker_rss_bytes"],
                "load_balance": _load_balance(results),
                "resume_granularity": "ATOMIC_SCIENTIFIC_UNIT_IDENTITY",
                "maximum_retry_blast_radius_atomic_units": chunk,
                "scientific_semantic_digest": digest,
                "semantic_digest_equal_to_chunk_one": digest == baseline_digest,
            })
        maximum = max(row["throughput_atomic_units_per_second"] for row in rows)
        eligible = [row for row in rows
                    if row["semantic_digest_equal_to_chunk_one"]
                    and row["throughput_atomic_units_per_second"] >= 0.95 * maximum]
        if not eligible:
            raise SystemExit(f"no eligible {kind} chunk")
        selected = min(row["chunk_size_atomic_units"] for row in eligible)
        branches[kind] = rows
        selections[kind] = selected

    document = {
        "schema_version": "rvt-rb21-target-chunk-scaling/v1",
        "chunk_matrix_predeclaration": declaration[
            "rb21_target_chunk_matrix_predeclaration_sha256"],
        "selected_worker_count": workers,
        "branches": branches,
        "all_semantic_digests_equal": all(
            row["semantic_digest_equal_to_chunk_one"]
            for rows in branches.values() for row in rows),
        "selected_residual_chunk_size_atomic_units": selections["residual"],
        "selected_recoverability_chunk_size_atomic_units": selections[
            "recoverability"],
        "selection_rule_applied": declaration[
            "selection_rule_frozen_before_chunk_results"],
        "selection_rationale": (
            "smallest semantically invariant chunk within 95 percent of each branch's "
            "maximum throughput, limiting load imbalance and retry blast radius"),
        "official_generation_executed": False,
    }
    write_json(
        args.output,
        attach_canonical_hash(document, "rb21_target_chunk_scaling_sha256"),
    )


if __name__ == "__main__":
    main()
