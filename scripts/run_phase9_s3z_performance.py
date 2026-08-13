#!/usr/bin/env python3
"""Run the predeclared Recoverability-only A1S3Z target benchmark."""

from __future__ import annotations

import argparse
import json
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from time import perf_counter

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0p.benchmark import (
    _configure_worker,
    _recoverability_worker,
    _scientific_projection,
    distribution,
)
from rvt_swarm.phase9g0p.executor import _bounded_ordered_results
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.phase9g0r.producer import reconcile_recoverability_candidate_results
from rvt_swarm.phase9g0r.writer import DIAGNOSTIC, CanonicalGenerationWriter
from rvt_swarm.topology_registry import COMPACT, LINE


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = _canonical(
        args.manifest, "phase9_s3z_performance_manifest_sha256")
    profile = manifest["profile"]
    if profile != {
        "workers": 12,
        "numeric_threads_per_worker": 1,
        "chunk_size_atomic_units": 1,
        "infrastructure_timeout_seconds": 243,
    }:
        raise ValueError("predeclared Recoverability profile changed")
    tasks_by_id = {
        task.event_id: task for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train")
    }
    tasks = [tasks_by_id[item["decision_event_id"]] for item in manifest["events"]]
    classes = {
        item["decision_event_id"]: item["classification"]
        for item in manifest["events"]
    }
    jobs = [
        (
            str(root), task, candidate,
            sha256_document({
                "event_id": task.event_id,
                "candidate_topology_id": candidate,
            }),
        )
        for task in tasks for candidate in (COMPACT, LINE)
    ]
    started = perf_counter()
    with ProcessPoolExecutor(
        max_workers=profile["workers"], initializer=_configure_worker,
    ) as pool:
        results = list(_bounded_ordered_results(
            pool, _recoverability_worker, jobs,
            workers=profile["workers"],
            timeout_seconds=profile["infrastructure_timeout_seconds"],
        ))
    scheduler_wall = perf_counter() - started

    reconciliations = []
    with tempfile.TemporaryDirectory(prefix="phase9-s3z-performance-") as temporary:
        writer = CanonicalGenerationWriter(Path(temporary), mode=DIAGNOSTIC)
        for index, task in enumerate(tasks):
            pair = results[2 * index:2 * index + 2]
            by_candidate = {
                int(item["candidate_topology_id"]): item["result"] for item in pair
            }
            reconcile_started = perf_counter()
            transaction = reconcile_recoverability_candidate_results(
                root, task, by_candidate[COMPACT], by_candidate[LINE], writer=writer)
            reconciliations.append({
                "event_id": task.event_id,
                "classification": classes[task.event_id],
                "wall_seconds": perf_counter() - reconcile_started,
                "status": transaction["reconciliation"]["status"],
                "prospective_rows": transaction["reconciliation"]["actual_row_count"],
                "official_counter_delta": transaction["write"]["official_counter_delta"],
            })

    units = [
        {
            "scheduler_atomic_unit_id": item["scheduler_atomic_unit_id"],
            "event_id": item["event_id"],
            "classification": classes[item["event_id"]],
            "candidate_topology_id": item["candidate_topology_id"],
            "wall_seconds": item["wall_seconds"],
            "cpu_seconds": item["cpu_seconds"],
            "peak_rss_bytes": item["peak_rss_bytes"],
            "source_event_seconds": item["result"]["operational_timing"][
                "source_event_seconds"],
            "replica_rollout_seconds": item["result"]["operational_timing"][
                "replica_rollout_seconds"],
            "disposition": item["result"]["disposition"],
        }
        for item in results
    ]
    maximum = max(item["wall_seconds"] for item in units)
    timeout = float(profile["infrastructure_timeout_seconds"])
    scientific_projection = [
        _scientific_projection(item["result"]) for item in results
    ]
    report = {
        "schema_version": "rvt-phase9-s3z-performance-result/v1",
        "mode": "NON_OFFICIAL_RECOVERABILITY_DIAGNOSTIC",
        "manifest_sha256": manifest["phase9_s3z_performance_manifest_sha256"],
        "source_commit": args.source_commit,
        "image": args.image,
        "profile": profile,
        "scheduler_wall_seconds": scheduler_wall,
        "candidate_aggregate_wall_seconds": distribution(
            item["wall_seconds"] for item in units),
        "source_event_wall_seconds": distribution(
            item["source_event_seconds"] for item in units),
        "per_replica_rollout_wall_seconds": distribution(
            value for item in units for value in item["replica_rollout_seconds"]),
        "candidate_pair_reconciliation_wall_seconds": distribution(
            item["wall_seconds"] for item in reconciliations),
        "units": units,
        "reconciliations": reconciliations,
        "scientific_semantic_digest": sha256_document(scientific_projection),
        "timeouts": 0,
        "failures": 0,
        "maximum_timeout_utilization": maximum / timeout,
        "performance_classification": (
            "RECOVERABILITY_PROFILE_REMAINS_QUALIFIED"
            if maximum < timeout and all(
                item["official_counter_delta"] == 0 for item in reconciliations
            ) else "RECOVERABILITY_SCOPED_REQUALIFICATION_REQUIRED"
        ),
        "official_staging_mounted": False,
        "official_staging_writes": 0,
        "residual_operations": 0,
        "sealed_scope": manifest["sealed_scope"],
    }
    report = attach_canonical_hash(report, "phase9_s3z_performance_result_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "classification": report["performance_classification"],
        "candidate_aggregates": len(units),
        "median": report["candidate_aggregate_wall_seconds"]["median"],
        "p95": report["candidate_aggregate_wall_seconds"]["p95"],
        "max": report["candidate_aggregate_wall_seconds"]["max"],
        "timeout_utilization": report["maximum_timeout_utilization"],
        "hash": report["phase9_s3z_performance_result_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
