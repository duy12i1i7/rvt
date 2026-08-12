#!/usr/bin/env python3
"""Replay one exact Recoverability atomic unit in a diagnostic namespace."""

from __future__ import annotations

import argparse
import json
import os
import resource
import signal
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
from typing import Any, Mapping


for _name in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

from rvt_swarm.phase8.common import (  # noqa: E402
    attach_canonical_hash,
    canonical_json_bytes,
    sha256_document,
)
from rvt_swarm.phase9g0p.benchmark import (  # noqa: E402
    _rss_bytes,
    _scientific_projection,
)
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks  # noqa: E402
from rvt_swarm.phase9g0r.producer import produce_recoverability_candidate  # noqa: E402
from rvt_swarm.phase9c_rb import counterfactual  # noqa: E402


class DiagnosticWatchdogExpired(RuntimeError):
    """The diagnostic ceiling expired before scientific completion."""


def _load_plan(path: Path) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    expected = str(document["phase9g_a1r_timeout_diagnostic_plan_sha256"])
    body = dict(document)
    body.pop("phase9g_a1r_timeout_diagnostic_plan_sha256")
    if sha256_document(body) != expected:
        raise ValueError("diagnostic plan hash mismatch")
    if document["mode"] != "NON_OFFICIAL_DIAGNOSTIC":
        raise ValueError("only the diagnostic namespace is permitted")
    if int(document["official_staging_writes_permitted"]) != 0:
        raise ValueError("diagnostic plan permits an official write")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--replay-index", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import torch

    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    root = args.root.resolve()
    plan = _load_plan(args.plan.resolve())
    unit = dict(plan["scientific_atomic_unit"])
    tasks = {
        task.event_id: task
        for task in compile_recoverability_tasks(
            root, study=str(unit["study"]), split=str(unit["split"])
        )
    }
    event_id = str(unit["decision_event_id"])
    if event_id not in tasks:
        raise ValueError("predeclared event is absent from the canonical compiler")
    task = tasks[event_id]
    candidate = int(unit["candidate_topology_id"])

    target_observations: list[dict[str, Any]] = []
    original_target = counterfactual.evaluate_target_v4

    def timed_target(summary):
        started = perf_counter()
        result = original_target(summary)
        target_observations.append({
            "wall_seconds": perf_counter() - started,
            "input": asdict(summary),
            "output": asdict(result),
        })
        return result

    counterfactual.evaluate_target_v4 = timed_target

    def expire(_signum, _frame):
        raise DiagnosticWatchdogExpired(
            "atomic unit exceeded the predeclared diagnostic watchdog"
        )

    watchdog = float(plan["diagnostic_watchdog_seconds"])
    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, watchdog)
    started = perf_counter()
    cpu_started = process_time()
    usage_started = resource.getrusage(resource.RUSAGE_SELF)
    try:
        result = produce_recoverability_candidate(root, task, candidate)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        counterfactual.evaluate_target_v4 = original_target
    wall_seconds = perf_counter() - started
    cpu_seconds = process_time() - cpu_started
    usage = resource.getrusage(resource.RUSAGE_SELF)

    serialization_started = perf_counter()
    serialized = canonical_json_bytes(result)
    serialization_seconds = perf_counter() - serialization_started
    scientific = _scientific_projection(result)
    replicas = []
    if result["candidate_audit"] is not None:
        replicas = list(result["candidate_audit"].get("replicas", ()))

    target_inputs = [item["input"] for item in target_observations]
    target_outputs = [item["output"] for item in target_observations]
    document = {
        "schema_version": "rvt-phase9g-a1r-timeout-diagnostic-replay/v1",
        "mode": "NON_OFFICIAL_DIAGNOSTIC",
        "replay_index": args.replay_index,
        "diagnostic_plan_sha256": plan[
            "phase9g_a1r_timeout_diagnostic_plan_sha256"
        ],
        "scientific_atomic_unit_id": unit["scientific_atomic_unit_id"],
        "event_id": event_id,
        "candidate_topology_id": candidate,
        "completion_disposition": result["disposition"],
        "source_terminated_before_event": result["source_terminated_before_event"],
        "scientific_semantic_digest": sha256_document(scientific),
        "replica_output_digest": sha256_document(_scientific_projection(replicas)),
        "target_v4_input_digest": sha256_document(target_inputs),
        "target_v4_output_digest": sha256_document(target_outputs),
        "target_v4_observations": target_observations,
        "timing": {
            "atomic_unit_wall_seconds": wall_seconds,
            "process_cpu_seconds": cpu_seconds,
            "average_cpu_cores": cpu_seconds / wall_seconds,
            "source_event_seconds": result["operational_timing"][
                "source_event_seconds"
            ],
            "graph_serialization_seconds": result["operational_timing"][
                "graph_serialization_seconds"
            ],
            "replica_rollout_seconds": result["operational_timing"][
                "replica_rollout_seconds"
            ],
            "target_v4_evaluation_seconds": [
                item["wall_seconds"] for item in target_observations
            ],
            "result_serialization_seconds": serialization_seconds,
        },
        "resources": {
            "peak_rss_bytes": _rss_bytes(),
            "minor_page_faults_delta": usage.ru_minflt - usage_started.ru_minflt,
            "major_page_faults_delta": usage.ru_majflt - usage_started.ru_majflt,
            "involuntary_context_switches_delta": (
                usage.ru_nivcsw - usage_started.ru_nivcsw
            ),
        },
        "serialized_result_bytes": len(serialized),
        "diagnostic_watchdog_seconds": watchdog,
        "official_staging_writes": 0,
        "sealed_scope": dict(plan["sealed_scope"]),
    }
    document = attach_canonical_hash(
        document, "phase9g_a1r_timeout_diagnostic_replay_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "atomic_unit_wall_seconds": wall_seconds,
        "completion_disposition": result["disposition"],
        "replay_index": args.replay_index,
        "scientific_semantic_digest": document["scientific_semantic_digest"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
