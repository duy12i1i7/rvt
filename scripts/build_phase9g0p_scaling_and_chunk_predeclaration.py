#!/usr/bin/env python3
"""Summarize frozen worker scaling and predeclare chunk matrices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


def _load(path: Path) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    field = (
        "phase9g0p_compact_benchmark_result_sha256"
        if "phase9g0p_compact_benchmark_result_sha256" in document
        else "phase9g0p_benchmark_result_sha256"
    )
    expected = str(document[field])
    body = dict(document)
    body.pop(field)
    if sha256_document(body) != expected:
        raise RuntimeError(f"benchmark result hash mismatch: {path}")
    return document


def _write(path: Path, body: Mapping[str, Any], field: str) -> str:
    document = attach_canonical_hash(dict(body), field)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(document[field])


def _entry(document: Mapping[str, Any], baseline_throughput: float) -> Mapping[str, Any]:
    throughput = float(document["throughput"]["atomic_units_per_second"])
    workers = int(document["workers"])
    return {
        "workers": workers,
        "chunk_size": int(document["chunk_size_atomic_units"]),
        "wall_seconds": float(document["wall_seconds"]),
        "atomic_units_per_second": throughput,
        "prospective_scientific_rows_per_second": float(
            document["throughput"]["prospective_scientific_rows_per_second"]
        ),
        "candidate_evaluations_per_second": document["throughput"].get(
            "candidate_evaluations_per_second"
        ),
        "speedup": throughput / baseline_throughput,
        "parallel_efficiency": throughput / baseline_throughput / workers,
        "worker_cpu_seconds": float(document["worker_cpu_seconds"]),
        "average_worker_cpu_cores": float(document["average_worker_cpu_cores"]),
        "peak_aggregate_rss_upper_bound_bytes": int(
            document["memory"]["peak_aggregate_rss_upper_bound_bytes"]
        ),
        "median_unit_latency_seconds": float(
            document["atomic_unit_latency_seconds"]["median"]
        ),
        "p95_unit_latency_seconds": float(
            document["atomic_unit_latency_seconds"]["p95"]
        ),
        "max_unit_latency_seconds": float(
            document["atomic_unit_latency_seconds"]["max"]
        ),
        "writer_throughput_per_second": float(
            document["throughput"][
                "writer_transactions_per_second"
                if document["branch"] == "recoverability"
                else "writer_attempts_per_second"
            ]
        ),
        "scientific_semantic_digest": str(document["scientific_semantic_digest"]),
        "raw_target_result_sha256": str(
            document.get(
                "raw_target_result_sha256",
                document.get("phase9g0p_benchmark_result_sha256"),
            )
        ),
    }


def _branch_summary(
    branch: str,
    w1: Mapping[str, Any],
    scaling: Sequence[Mapping[str, Any]],
    selected_workers: int,
    selection_reason: str,
) -> Mapping[str, Any]:
    all_results = [w1, *scaling]
    baseline = float(w1["throughput"]["atomic_units_per_second"])
    entries = sorted(
        (_entry(document, baseline) for document in all_results),
        key=lambda item: int(item["workers"]),
    )
    digests = {str(item["scientific_semantic_digest"]) for item in entries}
    if len(digests) != 1:
        raise RuntimeError(f"{branch} worker scaling changed scientific semantics")
    selected = next(item for item in entries if item["workers"] == selected_workers)
    maximum = max(entries, key=lambda item: float(item["atomic_units_per_second"]))
    return {
        "branch": branch,
        "entries": entries,
        "semantic_digest_equal_all_workers": True,
        "scientific_semantic_digest": next(iter(digests)),
        "selected_workers": selected_workers,
        "selected_entry": selected,
        "maximum_throughput_workers": int(maximum["workers"]),
        "selected_to_maximum_throughput_ratio": (
            float(selected["atomic_units_per_second"])
            / float(maximum["atomic_units_per_second"])
        ),
        "selection_reason": selection_reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scaling-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    benchmark_root = root / "results/rvt_fd24/phase9g0p_benchmarks"
    recoverability_w1 = _load(benchmark_root / "recoverability_w1_target_v1.json")
    residual_w1 = _load(benchmark_root / "residual_w1_target_v1.json")
    recoverability_scaling = [
        _load(args.scaling_root / f"recoverability_w{workers}_c1.json")
        for workers in (6, 12, 18, 22)
    ]
    residual_scaling = [
        _load(args.scaling_root / f"residual_w{workers}_c1.json")
        for workers in (4, 8, 12, 18, 22)
    ]
    scaling = {
        "schema_version": "rvt-phase9g0p-worker-scaling/v1",
        "worker_matrix_predeclaration_sha256": (
            "982519ec3f3a9f9f78127863364fb8e566d0b0f0c2a59520a7e2d50e71ef01d0"
        ),
        "recoverability": _branch_summary(
            "recoverability",
            recoverability_w1,
            recoverability_scaling,
            12,
            (
                "W=12 has maximum measured throughput; W=18 and W=22 are slower, "
                "less efficient and consume materially more aggregate RSS"
            ),
        ),
        "residual": _branch_summary(
            "residual",
            residual_w1,
            residual_scaling,
            8,
            (
                "W=8 retains at least 99% of maximum measured throughput while "
                "using fewer workers, less RSS and lower p95 latency than W>=12"
            ),
        ),
        "official_staging_writes": 0,
        "study_a_n24_accesses": 0,
        "final_test_accesses": 0,
    }
    scaling_hash = _write(
        benchmark_root / "worker_scaling_target_v1.json",
        scaling,
        "phase9g0p_worker_scaling_sha256",
    )
    chunks = {
        "schema_version": "rvt-phase9g0p-chunk-matrix-predeclaration/v1",
        "predeclared_before_chunk_benchmark_results": True,
        "worker_scaling_sha256": scaling_hash,
        "recoverability": {
            "selected_workers": 12,
            "chunk_matrix_atomic_units": [1, 2, 4],
            "atomic_unit": (
                "one source event x one candidate topology x all frozen replicas"
            ),
            "candidate_pair_publication_remains_event_level_all_or_none": True,
        },
        "residual": {
            "selected_workers": 8,
            "chunk_matrix_atomic_units": [1, 2, 3],
            "atomic_unit": "one retained robot state x all nine candidates",
            "nine_candidate_unit_is_never_split": True,
        },
        "selection_rule": (
            "select the smallest chunk within 2% of maximum throughput unless a "
            "larger chunk materially improves scheduler overhead without tail, "
            "load-balance, resume-granularity or retry-blast-radius regression"
        ),
        "scientific_semantic_digest_must_equal_selected_worker_chunk1": True,
        "official_staging_writes": 0,
    }
    chunk_hash = _write(
        root / "results/rvt_fd24/phase9g0p_chunk_matrix_predeclaration_v1.json",
        chunks,
        "phase9g0p_chunk_matrix_predeclaration_sha256",
    )
    print(json.dumps({"worker_scaling": scaling_hash, "chunk_matrix": chunk_hash}))


if __name__ == "__main__":
    main()
