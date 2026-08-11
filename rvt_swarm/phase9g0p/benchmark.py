"""Diagnostic benchmark runner for the actual Phase 9G0-R producers."""

from __future__ import annotations

import json
import math
import os
import resource
import statistics
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any, Iterable, Mapping, Sequence

from ..phase8.common import attach_canonical_hash, canonical_json_bytes, sha256_document
from ..phase9g0r.compiler import (
    OfficialDecisionEventTask,
    OfficialSourceTask,
    compile_recoverability_tasks,
    compile_source_tasks,
)
from ..phase9g0r.producer import (
    produce_recoverability_candidate,
    produce_residual_state,
    reconcile_recoverability_candidate_results,
    plan_residual_retained_states,
)
from ..phase9g0r.writer import DIAGNOSTIC, CanonicalGenerationWriter
from ..topology_registry import COMPACT, LINE


ADDENDUM_SHA256 = "523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0"
SCIENTIFIC_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
OPERATIONAL_KEYS = frozenset({
    "operational_timing",
    "write",
    "infrastructure_attempts",
    "worker_id",
    "worker_pid",
    "chunk_id",
    "attempt_id",
    "attempt_index",
    "scheduling_metadata",
})


class Phase9G0PBenchmarkError(RuntimeError):
    """A diagnostic workload or result violates the qualification contract."""


def _configure_worker() -> None:
    for name in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"
    import torch

    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass


def _rss_bytes() -> int:
    status = Path("/proc/self/status")
    if status.exists():
        for line in status.read_text(encoding="ascii").splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if os.uname().sysname == "Darwin" else value * 1024


def _recoverability_worker(
    job: tuple[str, OfficialDecisionEventTask, int, str],
) -> Mapping[str, Any]:
    root_value, task, candidate, unit_id = job
    started = perf_counter()
    cpu_started = process_time()
    result = produce_recoverability_candidate(Path(root_value), task, candidate)
    return {
        "scheduler_atomic_unit_id": unit_id,
        "event_id": task.event_id,
        "candidate_topology_id": candidate,
        "worker_pid": os.getpid(),
        "wall_seconds": perf_counter() - started,
        "cpu_seconds": process_time() - cpu_started,
        "peak_rss_bytes": _rss_bytes(),
        "result": result,
    }


def _residual_worker(
    job: tuple[str, OfficialSourceTask, int, int, str],
) -> Mapping[str, Any]:
    root_value, task, robot_id, timestep, unit_id = job
    started = perf_counter()
    cpu_started = process_time()
    result = produce_residual_state(
        Path(root_value),
        task,
        robot_id=robot_id,
        timestep=timestep,
        source_commit=SCIENTIFIC_SOURCE_COMMIT,
        scientific_addendum_sha256=ADDENDUM_SHA256,
    )
    return {
        "scheduler_atomic_unit_id": unit_id,
        "source_job_id": task.job_id,
        "robot_id": robot_id,
        "timestep": timestep,
        "worker_pid": os.getpid(),
        "wall_seconds": perf_counter() - started,
        "cpu_seconds": process_time() - cpu_started,
        "peak_rss_bytes": _rss_bytes(),
        "result": result,
    }


def _load_manifest(path: Path, hash_field: str) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    expected = str(document.get(hash_field, ""))
    body = dict(document)
    body.pop(hash_field, None)
    if len(expected) != 64 or sha256_document(body) != expected:
        raise Phase9G0PBenchmarkError(f"benchmark manifest hash mismatch: {path}")
    return document


def _scientific_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _scientific_projection(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in OPERATIONAL_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_scientific_projection(item) for item in value]
    return value


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise Phase9G0PBenchmarkError("cannot summarize an empty metric")
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def distribution(values: Iterable[float]) -> Mapping[str, Any]:
    materialized = tuple(float(value) for value in values)
    if not materialized:
        return {"n": 0}
    return {
        "n": len(materialized),
        "mean": statistics.fmean(materialized),
        "median": statistics.median(materialized),
        "p90": _percentile(materialized, 0.90),
        "p95": _percentile(materialized, 0.95),
        "max": max(materialized),
    }


def _numeric_environment() -> Mapping[str, Any]:
    import torch

    return {
        "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
        "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
        "NUMEXPR_NUM_THREADS": os.environ.get("NUMEXPR_NUM_THREADS"),
        "torch_intraop_threads_parent": torch.get_num_threads(),
        "torch_interop_threads_parent": torch.get_num_interop_threads(),
        "worker_numeric_threads": 1,
        "nested_oversubscription_permitted": False,
    }


def _aggregate_rss(units: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    by_pid: dict[int, int] = {}
    for unit in units:
        pid = int(unit["worker_pid"])
        by_pid[pid] = max(by_pid.get(pid, 0), int(unit["peak_rss_bytes"]))
    return {
        "worker_count_observed": len(by_pid),
        "peak_aggregate_rss_upper_bound_bytes": sum(by_pid.values()),
        "peak_rss_by_worker_pid_bytes": {
            str(pid): value for pid, value in sorted(by_pid.items())
        },
    }


def _base_result(
    *, branch: str, manifest: Mapping[str, Any], workers: int,
    chunk_size: int, wall_seconds: float, units: Sequence[Mapping[str, Any]],
    planning_seconds: float,
) -> dict[str, Any]:
    total_cpu = sum(float(unit["cpu_seconds"]) for unit in units)
    manifest_hash_field = (
        "phase9g0p_recoverability_benchmark_manifest_sha256"
        if branch == "recoverability"
        else "phase9g0p_residual_benchmark_manifest_sha256"
    )
    return {
        "schema_version": "rvt-phase9g0p-production-benchmark-result/v1",
        "branch": branch,
        "mode": DIAGNOSTIC,
        "official_staging_writes": 0,
        "workers": workers,
        "chunk_size_atomic_units": chunk_size,
        "numeric_environment": _numeric_environment(),
        "benchmark_manifest_sha256": str(manifest[manifest_hash_field]),
        "wall_seconds": wall_seconds,
        "source_planning_seconds": planning_seconds,
        "worker_cpu_seconds": total_cpu,
        "average_worker_cpu_cores": total_cpu / wall_seconds,
        "atomic_unit_latency_seconds": distribution(
            float(unit["wall_seconds"]) for unit in units
        ),
        "memory": _aggregate_rss(units),
        "worker_pids": sorted({int(unit["worker_pid"]) for unit in units}),
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "final_test_accesses": 0,
        },
    }


def run_recoverability(
    root: Path,
    *,
    manifest_path: Path,
    workers: int,
    chunk_size: int,
    diagnostic_root: Path,
) -> Mapping[str, Any]:
    manifest = _load_manifest(
        manifest_path,
        "phase9g0p_recoverability_benchmark_manifest_sha256",
    )
    tasks = {
        task.event_id: task
        for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train"
        )
    }
    jobs = []
    for item in manifest["scheduler_units"]:
        event_id = str(item["event_id"])
        if event_id not in tasks:
            raise Phase9G0PBenchmarkError("manifest event is not an authorized task")
        jobs.append((
            str(root),
            tasks[event_id],
            int(item["candidate_topology_id"]),
            str(item["scheduler_atomic_unit_id"]),
        ))
    started = perf_counter()
    with ProcessPoolExecutor(max_workers=workers, initializer=_configure_worker) as pool:
        units = list(pool.map(_recoverability_worker, jobs, chunksize=chunk_size))
    writer = CanonicalGenerationWriter(diagnostic_root, mode=DIAGNOSTIC)
    by_event: dict[str, dict[int, Mapping[str, Any]]] = {}
    for unit in units:
        by_event.setdefault(str(unit["event_id"]), {})[
            int(unit["candidate_topology_id"])
        ] = unit
    transactions = []
    writer_seconds = []
    row_expansion_seconds = []
    reconciliation_seconds = []
    for event in manifest["events"]:
        event_id = str(event["event_id"])
        pair = by_event.get(event_id, {})
        if set(pair) != {COMPACT, LINE}:
            raise Phase9G0PBenchmarkError("recoverability candidate pair is incomplete")
        reconcile_started = perf_counter()
        transaction = reconcile_recoverability_candidate_results(
            root,
            tasks[event_id],
            pair[COMPACT]["result"],
            pair[LINE]["result"],
            writer=writer,
        )
        reconcile_wall = perf_counter() - reconcile_started
        timing = transaction["audit"]["operational_timing"]
        writer_seconds.append(float(timing["writer_seconds"]))
        row_expansion_seconds.append(float(timing["row_expansion_seconds"]))
        reconciliation_seconds.append(max(
            0.0,
            reconcile_wall
            - float(timing["writer_seconds"])
            - float(timing["row_expansion_seconds"]),
        ))
        transactions.append(transaction)
    wall_seconds = perf_counter() - started
    projection = []
    for event in manifest["events"]:
        event_id = str(event["event_id"])
        projection.append({
            "task": asdict(tasks[event_id]),
            "candidates": [
                _scientific_projection(by_event[event_id][candidate]["result"])
                for candidate in (COMPACT, LINE)
            ],
            "transaction": _scientific_projection(next(
                item for item in transactions
                if item["reconciliation"]["decision_event_id"] == event_id
            )),
        })
    row_count = sum(
        int(item["reconciliation"]["actual_row_count"]) for item in transactions
    )
    replica_seconds = [
        float(value)
        for unit in units
        for value in unit["result"]["operational_timing"]["replica_rollout_seconds"]
    ]
    result = _base_result(
        branch="recoverability",
        manifest=manifest,
        workers=workers,
        chunk_size=chunk_size,
        wall_seconds=wall_seconds,
        units=units,
        planning_seconds=0.0,
    )
    result.update({
        "counts": {
            "events": len(transactions),
            "candidate_aggregates": len(units),
            "replica_executions": sum(
                len(unit["result"]["operational_timing"]["replica_rollout_seconds"])
                for unit in units
            ),
            "prospective_scientific_rows": row_count,
        },
        "throughput": {
            "atomic_units_per_second": len(units) / wall_seconds,
            "prospective_scientific_rows_per_second": row_count / wall_seconds,
            "replica_executions_per_second": sum(
                len(unit["result"]["operational_timing"]["replica_rollout_seconds"])
                for unit in units
            ) / wall_seconds,
            "writer_transactions_per_second": len(transactions) / sum(writer_seconds),
        },
        "stage_seconds": {
            "source_event": distribution(
                unit["result"]["operational_timing"]["source_event_seconds"]
                for unit in units
            ),
            "graph_serialization": distribution(
                unit["result"]["operational_timing"]["graph_serialization_seconds"]
                for unit in units
            ),
            "replica_rollout": distribution(replica_seconds),
            "row_expansion": distribution(row_expansion_seconds),
            "candidate_pair_reconciliation": distribution(reconciliation_seconds),
            "writer": distribution(writer_seconds),
        },
        "scientific_semantic_digest": sha256_document(projection),
        "scientific_semantic_projection": projection,
        "storage": recoverability_storage(transactions, units, manifest_path),
    })
    return attach_canonical_hash(result, "phase9g0p_benchmark_result_sha256")


def run_residual(
    root: Path,
    *,
    manifest_path: Path,
    workers: int,
    chunk_size: int,
    diagnostic_root: Path,
) -> Mapping[str, Any]:
    manifest = _load_manifest(
        manifest_path,
        "phase9g0p_residual_benchmark_manifest_sha256",
    )
    tasks = {
        task.job_id: task
        for task in compile_source_tasks(
            root, study="study_a_zero_shot", split="train"
        )
    }
    planning_started = perf_counter()
    retained_plans = {
        str(item["source_job_id"]): plan_residual_retained_states(
            root, tasks[str(item["source_job_id"])]
        )
        for item in manifest["source_episodes"]
    }
    planning_seconds = perf_counter() - planning_started
    jobs = []
    for item in manifest["scheduler_units"]:
        source_id = str(item["source_job_id"])
        robot_id = int(item["robot_id"])
        timestep = int(item["timestep"])
        if timestep not in retained_plans[source_id][robot_id]:
            raise Phase9G0PBenchmarkError("manifest state violates K=16 retention")
        jobs.append((
            str(root), tasks[source_id], robot_id, timestep,
            str(item["scheduler_atomic_unit_id"]),
        ))
    started = perf_counter()
    with ProcessPoolExecutor(max_workers=workers, initializer=_configure_worker) as pool:
        units = list(pool.map(_residual_worker, jobs, chunksize=chunk_size))
    writer = CanonicalGenerationWriter(diagnostic_root, mode=DIAGNOSTIC)
    writer_seconds = []
    for unit in units:
        result = unit["result"]
        writer_started = perf_counter()
        result["write"] = writer.write_residual_attempt(
            scientific_row_id=str(result["audit"]["scientific_row_id"]),
            disposition=str(result["audit"]["disposition"]),
            row=result["row"],
            audit=result["audit"],
        )
        writer_seconds.append(perf_counter() - writer_started)
    wall_seconds = planning_seconds + perf_counter() - started
    projection = [
        {
            "task": asdict(tasks[str(unit["source_job_id"])]),
            "robot_id": int(unit["robot_id"]),
            "timestep": int(unit["timestep"]),
            "result": _scientific_projection(unit["result"]),
        }
        for unit in sorted(units, key=lambda item: str(item["scheduler_atomic_unit_id"]))
    ]
    timings = [unit["result"]["audit"]["operational_timing"] for unit in units]
    candidate_seconds = [
        float(value) for timing in timings
        for value in timing["candidate_continuation_seconds"]
    ]
    labeled = sum(unit["result"]["row"] is not None for unit in units)
    result = _base_result(
        branch="residual",
        manifest=manifest,
        workers=workers,
        chunk_size=chunk_size,
        wall_seconds=wall_seconds,
        units=units,
        planning_seconds=planning_seconds,
    )
    result.update({
        "counts": {
            "source_episodes_planned": len(retained_plans),
            "retained_state_units": len(units),
            "candidate_evaluations": 9 * len(units),
            "labeled_rows": labeled,
            "no_eligible_audits": len(units) - labeled,
        },
        "throughput": {
            "atomic_units_per_second": len(units) / wall_seconds,
            "prospective_scientific_rows_per_second": labeled / wall_seconds,
            "candidate_evaluations_per_second": 9 * len(units) / wall_seconds,
            "writer_attempts_per_second": len(units) / sum(writer_seconds),
        },
        "stage_seconds": {
            "dense_state_universe_and_k16_retention": distribution([planning_seconds]),
            "source_event": distribution(
                timing["source_event_seconds"] for timing in timings
            ),
            "local_input_graph": distribution(
                timing["local_input_graph_seconds"] for timing in timings
            ),
            "full_nine_candidate_unit": distribution(
                timing["residual_expert_total_seconds"] for timing in timings
            ),
            "per_candidate_continuation": distribution(candidate_seconds),
            "utility_selector_target": distribution(
                timing["utility_selector_target_seconds"] for timing in timings
            ),
            "sidecar_serialization": distribution(
                timing["sidecar_serialization_seconds"] for timing in timings
            ),
            "writer": distribution(writer_seconds),
        },
        "scientific_semantic_digest": sha256_document(projection),
        "scientific_semantic_projection": projection,
        "storage": residual_storage(units, manifest_path),
    })
    return attach_canonical_hash(result, "phase9g0p_benchmark_result_sha256")


def _size(value: Any) -> int:
    return len(canonical_json_bytes(value))


def recoverability_storage(
    transactions: Sequence[Mapping[str, Any]],
    units: Sequence[Mapping[str, Any]],
    manifest_path: Path,
) -> Mapping[str, Any]:
    rows = [
        row for item in transactions for row in item["reconciliation"]["rows"]
    ]
    graphs = [row["graph_payload"] for row in rows]
    candidate_audits = [
        unit["result"]["candidate_audit"] for unit in units
        if unit["result"]["candidate_audit"] is not None
    ]
    replica_audits = [
        replica for audit in candidate_audits for replica in audit.get("replicas", [])
    ]
    pair_metadata = []
    for item in transactions:
        metadata = dict(item["reconciliation"])
        metadata["rows"] = []
        pair_metadata.append(metadata)
    return {
        "recoverability_row_bytes": distribution(_size(row) for row in rows),
        "ego_graph_payload_bytes": distribution(_size(graph) for graph in graphs),
        "candidate_aggregate_audit_bytes": distribution(
            _size(audit) for audit in candidate_audits
        ),
        "replica_audit_bytes": distribution(_size(audit) for audit in replica_audits),
        "pair_transaction_metadata_bytes": distribution(
            _size(item) for item in pair_metadata
        ),
        "benchmark_manifest_bytes": manifest_path.stat().st_size,
    }


def residual_storage(
    units: Sequence[Mapping[str, Any]], manifest_path: Path,
) -> Mapping[str, Any]:
    rows = [unit["result"]["row"] for unit in units if unit["result"]["row"]]
    sidecars = [
        unit["result"]["audit"]["candidate_sidecars"] for unit in units
    ]
    noeligible = [
        unit["result"]["audit"] for unit in units if unit["result"]["row"] is None
    ]
    return {
        "residual_row_bytes": distribution(_size(row) for row in rows),
        "residual_nine_candidate_sidecar_bytes": distribution(
            _size(sidecar) for sidecar in sidecars
        ),
        "no_eligible_audit_bytes": distribution(_size(audit) for audit in noeligible),
        "benchmark_manifest_bytes": manifest_path.stat().st_size,
    }
