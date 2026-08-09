#!/usr/bin/env python3
"""Run one predeclared RB21 target benchmark configuration."""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21.rb21_bench import distribution, run_process_benchmark
from rvt_swarm.phase9c_rb21.rb21_manifest import write_json
from rvt_swarm.phase9c_rb21.rb21_units import (
    DiagnosticCase,
    RecoverabilityAtomicUnit,
    ResidualAtomicUnit,
    ThreadSettings,
    scientific_semantic_projection,
)


EXPECTED_IMAGE = (
    "sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b")
THREAD_ENVIRONMENT = (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def _command(args: Sequence[str]) -> str | None:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _gpu_observation() -> Mapping[str, Any]:
    query = _command([
        "nvidia-smi",
        "--query-gpu=name,uuid,memory.total,memory.used,utilization.gpu,driver_version",
        "--format=csv,noheader,nounits",
    ])
    if query is None:
        return {"visible": False, "query": None}
    rows = []
    for line in query.splitlines():
        values = [value.strip() for value in line.split(",")]
        rows.append({
            "name": values[0],
            "uuid": values[1],
            "memory_total_mib": int(values[2]),
            "memory_used_mib": int(values[3]),
            "utilization_percent": int(values[4]),
            "driver_version": values[5],
        })
    return {"visible": True, "gpus": rows}


def _case(document: Mapping[str, Any]) -> DiagnosticCase:
    return DiagnosticCase(
        case_id=str(document["case_id"]),
        split=str(document["split"]),
        layout_id=str(document["layout_id"]),
        family=str(document["family"]),
        team_size=int(document["team_size"]),
        source_policy=str(document["source_policy"]),
        seeds={str(key): int(value) for key, value in document["seeds"].items()},
        decision_steps=tuple(int(value) for value in document["decision_steps"]),
        robot_ids=tuple(int(value) for value in document["robot_ids"]),
        structural_roles=tuple(str(value) for value in document["structural_roles"]),
    )


def _units(manifest: Mapping[str, Any], kind: str) -> list:
    cases = {item["case_id"]: _case(item) for item in manifest["cases"]}
    units = []
    if kind in ("residual", "all"):
        for item in manifest["residual_atomic_units"]:
            case = cases[item["case"]["case_id"]]
            units.append(ResidualAtomicUnit(
                case=case,
                decision_step=int(item["decision_step"]),
                robot_id=int(item["robot_id"]),
                candidate_indices=tuple(int(value) for value in item["candidate_indices"]),
            ))
    if kind in ("recoverability", "all"):
        for item in manifest["recoverability_atomic_units"]:
            case = cases[item["case"]["case_id"]]
            units.append(RecoverabilityAtomicUnit(
                case=case,
                decision_step=int(item["decision_step"]),
                candidate_topology=int(item["candidate_topology"]),
                replica_indices=tuple(int(value) for value in item["replica_indices"]),
            ))
    return units


def _values(results: Iterable[Mapping[str, Any]], key: str) -> list:
    return [float(row[key]) for row in results]


def _nested_values(results: Iterable[Mapping[str, Any]], key: str) -> list:
    return [float(value) for row in results for value in row[key]]


def _kind_summary(results: Sequence[Mapping[str, Any]], kind: str) -> Dict[str, Any]:
    selected = [row for row in results if row["unit_kind"] == kind]
    if not selected:
        return {"atomic_units": 0}
    summary: Dict[str, Any] = {
        "atomic_units": len(selected),
        "atomic_unit_wall_seconds": distribution(_values(selected, "wall_seconds")),
        "serialization_seconds": distribution(_values(selected, "serialization_seconds")),
        "serialized_bytes": distribution(_values(selected, "serialized_bytes")),
        "max_rss_bytes": distribution(_values(selected, "max_rss_bytes")),
    }
    if kind == "RESIDUAL":
        summary.update({
            "candidate_continuation_seconds": distribution(
                _nested_values(selected, "candidate_seconds")),
            "candidate_rollout_control_intervals": distribution(
                _nested_values(selected, "candidate_control_intervals")),
            "utility_selection_target_seconds": distribution(
                _values(selected, "selector_target_reduction_seconds")),
            "dispositions": {
                disposition: sum(row["disposition"] == disposition for row in selected)
                for disposition in ("LABELED", "NO_ELIGIBLE_ACTION")
            },
            "candidate_evaluations": sum(int(row["candidate_count"]) for row in selected),
        })
    else:
        summary.update({
            "replica_rollout_seconds": distribution(
                _nested_values(selected, "replica_seconds")),
            "replica_rollout_control_steps": distribution(
                _nested_values(selected, "replica_control_steps")),
            "aggregation_seconds": distribution(_values(selected, "aggregation_seconds")),
            "replica_rollouts": sum(int(row["replica_count"]) for row in selected),
        })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--kind", choices=("residual", "recoverability", "all"),
                        required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--chunk-size", type=int, required=True)
    parser.add_argument("--attempt-index", type=int, default=0)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="ascii"))
    if manifest["qualified_target_image"] != EXPECTED_IMAGE:
        raise SystemExit("benchmark manifest does not name the qualified image")
    units = _units(manifest, args.kind)
    expected = manifest["sample_counts"]
    expected_count = {
        "residual": expected["residual_atomic_units"],
        "recoverability": expected["recoverability_atomic_units"],
        "all": expected["residual_atomic_units"] + expected["recoverability_atomic_units"],
    }[args.kind]
    if len(units) != expected_count:
        raise SystemExit("manifest reconstruction changed atomic-unit count")

    settings = ThreadSettings()
    for name in THREAD_ENVIRONMENT:
        os.environ[name] = "1"
    before = {
        "environment": {name: os.environ.get(name) for name in THREAD_ENVIRONMENT},
        "torch": settings.apply(),
        "gpu": _gpu_observation(),
    }
    benchmark = run_process_benchmark(
        args.root,
        units,
        workers=args.workers,
        chunk_size=args.chunk_size,
        thread_settings=settings,
        attempt_index=args.attempt_index,
    )
    after = {"gpu": _gpu_observation()}
    results = benchmark["results"]
    document = {
        "schema_version": "rvt-rb21-target-benchmark-run/v1",
        "provenance_class": "OPERATIONAL_BENCHMARK_ONLY",
        "run_id": args.run_id,
        "qualified_image_expected": EXPECTED_IMAGE,
        "qualified_image_observed_by_host_wrapper": os.environ.get(
            "RVT_QUALIFIED_IMAGE_OBSERVED", "NOT_SET"),
        "target_benchmark_manifest": manifest[
            "rb21_target_benchmark_manifest_sha256"],
        "container": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "root_source_commit": _command(["git", "-C", str(args.root), "rev-parse", "HEAD"]),
        },
        "configuration": {
            "kind": args.kind,
            "workers": args.workers,
            "chunk_size_atomic_units": args.chunk_size,
            "thread_settings": asdict(settings),
            "attempt_index": args.attempt_index,
        },
        "observations_before": before,
        "observations_after": after,
        "benchmark": benchmark,
        "distributions": {
            "all_atomic_unit_wall_seconds": distribution(_values(results, "wall_seconds")),
            "residual": _kind_summary(results, "RESIDUAL"),
            "recoverability": _kind_summary(results, "RECOVERABILITY"),
        },
        "scientific_semantic_projection": scientific_semantic_projection(results),
        "official_generation_executed": False,
        "study_a_n24_accesses": 0,
        "final_test_accesses": 0,
    }
    document = attach_canonical_hash(document, "rb21_target_benchmark_run_sha256")
    write_json(args.output, document)


if __name__ == "__main__":
    main()
