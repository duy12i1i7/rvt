"""Process benchmark harness for complete RB-21 atomic work units."""

from __future__ import annotations

import json
import math
import multiprocessing as mp
import os
import resource
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple, Union

from ..phase8.common import canonical_json_bytes
from ..phase9c_rb import policies as source_policies
from ..phase9c_rb.binding import build_binding, load_execution_specification
from ..phase9c_rb.counterfactual import execute_candidate, snapshot
from ..phase9c_rb.residual_expert_v2 import (
    canonical_result_digest,
    evaluate_residual_expert_v2,
)
from ..phase9c_rb.session import SimulatorEpisodeSession, build_event_plan
from ..runtime_configuration import DEFAULT_RUNTIME_CONFIG
from .rb21_units import (
    RecoverabilityAtomicUnit,
    ResidualAtomicUnit,
    ThreadSettings,
    scientific_semantic_digest,
)

AtomicUnit = Union[ResidualAtomicUnit, RecoverabilityAtomicUnit]

_WORKER_THREAD_SETTINGS = ThreadSettings()


def _max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Darwin reports bytes; Linux reports KiB.
    return value if os.uname().sysname == "Darwin" else value * 1024


def _worker_init(settings: Mapping[str, int]) -> None:
    global _WORKER_THREAD_SETTINGS
    _WORKER_THREAD_SETTINGS = ThreadSettings(**dict(settings))
    _WORKER_THREAD_SETTINGS.apply()


def _load_contracts(root: Path) -> Tuple[Mapping[str, Any], ...]:
    result_root = root / "results/rvt_fd24"
    names = (
        "executable_scientific_protocol_v1.json",
        "target_v4_execution_contract_v1.json",
        "source_policy_contracts_v1.json",
    )
    return tuple(json.loads((result_root / name).read_text(encoding="ascii"))
                 for name in names)


def _session_for_unit(root: Path, unit: AtomicUnit) -> SimulatorEpisodeSession:
    protocol, target, contracts = _load_contracts(root)
    case = unit.case
    specification = load_execution_specification(
        root / "results/rvt_fd24", case.split, case.layout_id)
    binding = build_binding(
        specification, team_size=case.team_size, source_policy=case.source_policy,
        protocol=protocol, target_contract=target, source_policy_contracts=contracts)
    event_plan = (build_event_plan(binding, contracts)
                  if case.source_policy == source_policies.S0 else ())
    policy = source_policies.build_source_policy(
        case.source_policy, contracts=contracts,
        seed=int(case.seeds["data_sampling"]),
        horizon_seconds=binding.horizon_seconds, team_size=case.team_size,
        family_id=case.family, runtime_config=DEFAULT_RUNTIME_CONFIG,
        event_plan=event_plan)
    session = SimulatorEpisodeSession(
        binding, protocol=protocol, target_contract=target,
        seeds={
            "initial_condition": int(case.seeds["initial_condition"]),
            "communication": int(case.seeds["communication"]),
            "dynamic_obstacle": int(case.seeds["dynamic_obstacle"]),
        },
        source_policy=policy,
        episode_id=f"rb21-diagnostic:{case.case_id}",
    )
    while session.termination is None and session.control_step < unit.decision_step:
        session.step()
    if session.termination is not None and session.control_step < unit.decision_step:
        raise RuntimeError(
            f"{case.case_id} terminated before predeclared step {unit.decision_step}")
    return session


def _thread_observation() -> Mapping[str, int]:
    return _WORKER_THREAD_SETTINGS.apply()


def run_residual_atomic_unit(root: Path, unit: ResidualAtomicUnit) -> Dict[str, Any]:
    """Run all nine candidates in one worker call; no horizon enters from RB-21."""
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    session = _session_for_unit(root, unit)
    scientific_start = time.perf_counter()
    result = evaluate_residual_expert_v2(session, unit.robot_id)
    reduction_seconds = max(0.0, result.seconds - sum(c.seconds for c in result.candidates))
    disposition = "LABELED" if result.target is not None else "NO_ELIGIBLE_ACTION"
    scientific = {
        "atomic_unit_id": unit.atomic_unit_id,
        "unit_kind": unit.unit_kind,
        "case_id": unit.case.case_id,
        "decision_step": unit.decision_step,
        "robot_id": unit.robot_id,
        "candidate_indices": list(unit.candidate_indices),
        "candidate_count": len(result.candidates),
        "snapshot_sha256": result.snapshot_hash,
        "robot_view_sha256": result.robot_view_hash,
        "candidate_lattice_sha256": result.candidate_lattice_hash,
        "result_digest": canonical_result_digest(result),
        "selected_candidate_index": result.selected_index,
        "selected_residual_world": result.selected_residual,
        "target_world": (None if result.target is None else
                         list(result.target.residual_target_world_acceleration)),
        "selector_error": result.selector_error,
        "disposition": disposition,
        "candidate_records": [{
            "candidate_index": candidate.candidate_index,
            "candidate_sha256": candidate.canonical_hash,
            "delta_u_world": list(candidate.delta_u_world),
            "utilities": dict(candidate.utilities),
            "termination_cause": candidate.trace.termination_cause,
            "control_intervals": candidate.trace.control_intervals,
            "matched_stream_identity": [list(value)
                                        for value in candidate.trace.matched_stream_identity],
        } for candidate in result.candidates],
    }
    serialization_start = time.perf_counter()
    serialized = canonical_json_bytes(scientific)
    serialization_seconds = time.perf_counter() - serialization_start
    return {
        **scientific,
        "wall_seconds": time.perf_counter() - wall_start,
        "scientific_seconds": time.perf_counter() - scientific_start,
        "candidate_seconds": [candidate.seconds for candidate in result.candidates],
        "candidate_control_intervals": [candidate.trace.control_intervals
                                        for candidate in result.candidates],
        "selector_target_reduction_seconds": reduction_seconds,
        "serialization_seconds": serialization_seconds,
        "serialized_bytes": len(serialized),
        "cpu_seconds": time.process_time() - cpu_start,
        "max_rss_bytes": _max_rss_bytes(),
        "pid": os.getpid(),
        "thread_settings": _thread_observation(),
    }


def run_recoverability_atomic_unit(
        root: Path, unit: RecoverabilityAtomicUnit) -> Dict[str, Any]:
    """Run one candidate with every frozen replica before returning to the scheduler."""
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    session = _session_for_unit(root, unit)
    source = snapshot(session)
    replicas = []
    replica_seconds = []
    for replica_index in unit.replica_indices:
        started = time.perf_counter()
        result = execute_candidate(
            source, unit.candidate_topology, replica_index=replica_index,
            disturbance_seed=int(unit.case.seeds["dynamic_obstacle"]),
        )
        replica_seconds.append(time.perf_counter() - started)
        replicas.append(asdict(result))
    aggregation_start = time.perf_counter()
    aggregate = (None if any(item["disposition"] == "GENERATION_INVALID"
                             for item in replicas)
                 else int(all(item["label"] == 1 for item in replicas)))
    aggregation_seconds = time.perf_counter() - aggregation_start
    scientific = {
        "atomic_unit_id": unit.atomic_unit_id,
        "unit_kind": unit.unit_kind,
        "case_id": unit.case.case_id,
        "decision_step": unit.decision_step,
        "candidate_topology": unit.candidate_topology,
        "replica_indices": list(unit.replica_indices),
        "replica_count": len(replicas),
        "decision_snapshot_sha256": source.canonical_hash,
        "replicas": replicas,
        "aggregate_label": aggregate,
    }
    serialization_start = time.perf_counter()
    serialized = canonical_json_bytes(scientific)
    serialization_seconds = time.perf_counter() - serialization_start
    return {
        **scientific,
        "wall_seconds": time.perf_counter() - wall_start,
        "replica_seconds": replica_seconds,
        "replica_control_steps": [item["control_steps"] for item in replicas],
        "aggregation_seconds": aggregation_seconds,
        "serialization_seconds": serialization_seconds,
        "serialized_bytes": len(serialized),
        "cpu_seconds": time.process_time() - cpu_start,
        "max_rss_bytes": _max_rss_bytes(),
        "pid": os.getpid(),
        "thread_settings": _thread_observation(),
    }


def _run_one(args: Tuple[str, AtomicUnit, int, int, int]) -> Dict[str, Any]:
    root, unit, worker_count, chunk_size, attempt_index = args
    result = (run_residual_atomic_unit(Path(root), unit)
              if isinstance(unit, ResidualAtomicUnit)
              else run_recoverability_atomic_unit(Path(root), unit))
    result.update({
        "worker_count": worker_count,
        "chunk_size": chunk_size,
        "attempt_index": attempt_index,
        "worker_id": result["pid"],
    })
    return result


def run_process_benchmark(root: Path, units: Sequence[AtomicUnit], *, workers: int,
                          chunk_size: int, thread_settings: ThreadSettings,
                          attempt_index: int = 0) -> Dict[str, Any]:
    if workers < 1 or chunk_size < 1:
        raise ValueError("workers and chunk size must be positive")
    if not units:
        raise ValueError("a benchmark needs at least one complete atomic unit")
    started = time.perf_counter()
    arguments = [(str(root.resolve()), unit, workers, chunk_size, attempt_index)
                 for unit in units]
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(
            max_workers=workers, mp_context=context, initializer=_worker_init,
            initargs=(asdict(thread_settings),)) as executor:
        results = list(executor.map(_run_one, arguments, chunksize=chunk_size))
    elapsed = time.perf_counter() - started
    cpu_seconds = sum(float(result["cpu_seconds"]) for result in results)
    pids = {int(result["pid"]) for result in results}
    peak_worker_rss = {
        str(pid): max(int(result["max_rss_bytes"]) for result in results
                      if int(result["pid"]) == pid)
        for pid in pids
    }
    return {
        "workers": workers,
        "chunk_size_atomic_units": chunk_size,
        "thread_settings": asdict(thread_settings),
        "atomic_units": len(units),
        "wall_seconds": elapsed,
        "throughput_atomic_units_per_second": len(units) / elapsed,
        "aggregate_cpu_seconds": cpu_seconds,
        "cpu_utilization_percent_of_one_core": 100.0 * cpu_seconds / elapsed,
        "peak_worker_rss_bytes_by_pid": peak_worker_rss,
        "conservative_peak_total_worker_rss_bytes": sum(peak_worker_rss.values()),
        "scientific_semantic_digest": scientific_semantic_digest(results),
        "results": results,
    }


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("no values")
    rank = max(1, math.ceil(quantile * len(ordered)))
    return ordered[rank - 1]


def distribution(values: Iterable[float]) -> Dict[str, Any]:
    sequence = [float(value) for value in values]
    if not sequence:
        return {"count": 0, "mean": None, "median": None, "p90": None,
                "p95": None, "maximum": None, "p99": "NOT_REPORTED"}
    return {
        "count": len(sequence),
        "mean": statistics.fmean(sequence),
        "median": statistics.median(sequence),
        "p90": _percentile(sequence, 0.90),
        "p95": _percentile(sequence, 0.95),
        "maximum": max(sequence),
        "p99": "NOT_REPORTED_SAMPLE_COUNT_INSUFFICIENT",
    }


def scaling_projection(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []
    baseline = next(row for row in rows if int(row["workers"]) == 1)
    baseline_throughput = float(baseline["throughput_atomic_units_per_second"])
    output = []
    for row in rows:
        workers = int(row["workers"])
        speedup = float(row["throughput_atomic_units_per_second"]) / baseline_throughput
        output.append({**dict(row), "speedup": speedup,
                       "parallel_efficiency": speedup / workers})
    return output
