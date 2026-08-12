#!/usr/bin/env python3
"""Observe one predeclared A1R source exception without scientific writes."""

from __future__ import annotations

import argparse
import json
import os
import resource
import signal
import traceback
from pathlib import Path
from time import perf_counter, process_time


for _name in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document  # noqa: E402
from rvt_swarm.phase9g0p.benchmark import _rss_bytes  # noqa: E402
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks  # noqa: E402
from rvt_swarm.phase9g0r.producer import produce_recoverability_candidate  # noqa: E402
from rvt_swarm.phase9c_rb import policies  # noqa: E402


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if sha256_document(body) != expected:
        raise ValueError("diagnostic plan hash mismatch")
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
    plan = _canonical(
        args.plan,
        "phase9g_a1r_worker_failure_diagnostic_plan_sha256",
    )
    spec = next(
        item for item in plan["replays"]
        if int(item["replay_index"]) == args.replay_index
    )
    unit = plan["failed_atomic_unit"]
    root = args.root.resolve()
    tasks = {
        task.event_id: task
        for task in compile_recoverability_tasks(
            root, study=unit["study"], split=unit["split"]
        )
    }
    task = tasks[unit["decision_event_id"]]
    candidate = int(spec["candidate_topology_id"])
    original = policies.s3_local_geometric_decision
    calls = []

    def observed_s3(committed_topology, **kwargs):
        observation = {
            "committed_topology": committed_topology,
            **kwargs,
        }
        calls.append(observation)
        return original(committed_topology, **kwargs)

    policies.s3_local_geometric_decision = observed_s3
    watchdog = float(plan["diagnostic_watchdog_seconds"])

    def expire(_signum, _frame):
        raise TimeoutError("diagnostic watchdog expired")

    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, watchdog)
    started = perf_counter()
    cpu_started = process_time()
    usage_started = resource.getrusage(resource.RUSAGE_SELF)
    result = None
    caught = None
    caught_traceback = None
    try:
        result = produce_recoverability_candidate(root, task, candidate)
    except BaseException as exc:
        caught = exc
        caught_traceback = traceback.format_exc()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        policies.s3_local_geometric_decision = original
    wall = perf_counter() - started
    usage = resource.getrusage(resource.RUSAGE_SELF)
    invalid_calls = [
        call for call in calls
        if call["measured_width_meters"] is not None
        and float(call["measured_width_meters"]) < 0.0
    ]
    document = {
        "schema_version": "rvt-phase9g-a1r-worker-failure-diagnostic-replay/v1",
        "mode": "NON_OFFICIAL_DIAGNOSTIC",
        "replay_index": args.replay_index,
        "candidate_topology_id": candidate,
        "decision_event_id": task.event_id,
        "scientific_atomic_unit_id": sha256_document({
            "event_id": task.event_id,
            "candidate_topology_id": candidate,
        }),
        "termination": {
            "kind": "EXCEPTION" if caught is not None else "RETURNED_RESULT",
            "exception_class": type(caught).__name__ if caught is not None else None,
            "exception_message": str(caught) if caught is not None else None,
            "traceback": caught_traceback,
        },
        "candidate_result_created": result is not None,
        "scientific_disposition_created": (
            result is not None and result.get("disposition") is not None
        ),
        "s3_call_count_before_termination": len(calls),
        "negative_measured_width_call_count": len(invalid_calls),
        "first_negative_measured_width_call": invalid_calls[0] if invalid_calls else None,
        "timing": {
            "wall_seconds": wall,
            "cpu_seconds": process_time() - cpu_started,
        },
        "resources": {
            "peak_rss_bytes": _rss_bytes(),
            "minor_page_faults_delta": usage.ru_minflt - usage_started.ru_minflt,
            "major_page_faults_delta": usage.ru_majflt - usage_started.ru_majflt,
        },
        "official_staging_writes": 0,
        "sealed_scope": plan["sealed_scope"],
    }
    document = attach_canonical_hash(
        document, "phase9g_a1r_worker_failure_diagnostic_replay_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "candidate_topology_id": candidate,
        "exception_class": document["termination"]["exception_class"],
        "exception_message": document["termination"]["exception_message"],
        "negative_width": (
            invalid_calls[0]["measured_width_meters"] if invalid_calls else None
        ),
        "wall_seconds": wall,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
