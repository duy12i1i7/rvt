#!/usr/bin/env python3
"""Resume only unresolved official Recoverability candidate-pair identities."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Mapping, Sequence

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0p.benchmark import _configure_worker, _recoverability_worker
from rvt_swarm.phase9g0p.executor import _bounded_ordered_results
from rvt_swarm.phase9g0r.compiler import (
    JOB_MANIFEST_SHA256,
    OfficialDecisionEventTask,
    compile_recoverability_tasks,
)
from rvt_swarm.phase9g0r.preflight import validate_authorization_scope
from rvt_swarm.phase9g0r.producer import reconcile_recoverability_candidate_results
from rvt_swarm.phase9g0r.writer import CanonicalGenerationWriter, OFFICIAL_STAGING
from rvt_swarm.topology_registry import COMPACT, LINE


class ContinuationError(RuntimeError):
    """The operational continuation binding or durable prefix is invalid."""


def canonical_artifact(path: Path, hash_field: str) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(hash_field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ContinuationError(f"canonical artifact mismatch: {path.name}")
    return document


def _canonical_record(path: Path) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop("canonical_record_sha256", ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ContinuationError(f"staging transaction hash mismatch: {path.name}")
    return document


def completed_event_ids(
    writer_root: Path,
    tasks: Sequence[OfficialDecisionEventTask],
) -> frozenset[str]:
    task_ids = {task.event_id for task in tasks}
    transaction_root = writer_root.resolve() / "recoverability"
    partials = tuple(transaction_root.glob("*.partial")) if transaction_root.exists() else ()
    if partials:
        raise ContinuationError("partial candidate-pair transaction is present")
    completed: set[str] = set()
    if not transaction_root.exists():
        return frozenset()
    for path in sorted(transaction_root.glob("event-*.json")):
        record = _canonical_record(path)
        event_id = str(record.get("decision_event_id", ""))
        if event_id not in task_ids:
            raise ContinuationError("staging contains an out-of-scope event identity")
        if event_id in completed:
            raise ContinuationError("duplicate durable event identity")
        if record.get("writer_mode") != OFFICIAL_STAGING:
            raise ContinuationError("durable prefix contains a non-official transaction")
        if record.get("scientifically_reconciled") is not True:
            raise ContinuationError("durable prefix contains an unresolved transaction")
        if record.get("scientific_completion_marker") is not True:
            raise ContinuationError("durable prefix lacks a completion marker")
        rows = list(record.get("rows", ()))
        if int(record.get("actual_row_count", -1)) != len(rows):
            raise ContinuationError("durable transaction row count mismatch")
        completed.add(event_id)
    return frozenset(completed)


def unresolved_tasks(
    tasks: Sequence[OfficialDecisionEventTask], completed: Iterable[str]
) -> tuple[OfficialDecisionEventTask, ...]:
    completed_set = frozenset(completed)
    return tuple(task for task in tasks if task.event_id not in completed_set)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _atomic_write(path: Path, body: Mapping[str, Any], hash_field: str) -> None:
    document = attach_canonical_hash(dict(body), hash_field)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    temporary.replace(path)


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("a", encoding="ascii") as stream:
        stream.write(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def execute_unresolved(
    root: Path,
    tasks: Sequence[OfficialDecisionEventTask],
    writer: CanonicalGenerationWriter,
    *,
    workers: int,
    timeout_seconds: float,
    telemetry_path: Path,
    status_path: Path,
    status: dict[str, Any],
) -> Mapping[str, Any]:
    jobs = (
        (
            str(root),
            task,
            candidate,
            sha256_document({
                "event_id": task.event_id,
                "candidate_topology_id": candidate,
            }),
        )
        for task in tasks
        for candidate in (COMPACT, LINE)
    )
    events = 0
    writes = 0
    duplicate_replays = 0
    candidate_aggregates = 0
    replicas = 0
    max_atomic_wall = 0.0
    started = perf_counter()
    try:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_configure_worker
        ) as pool:
            results = _bounded_ordered_results(
                pool,
                _recoverability_worker,
                jobs,
                workers=workers,
                timeout_seconds=timeout_seconds,
            )
            for task in tasks:
                units = (next(results), next(results))
                by_candidate = {
                    int(unit["candidate_topology_id"]): unit for unit in units
                }
                if set(by_candidate) != {COMPACT, LINE}:
                    raise ContinuationError("scheduler crossed a candidate-pair boundary")
                reconcile_started = perf_counter()
                transaction = reconcile_recoverability_candidate_results(
                    root,
                    task,
                    by_candidate[COMPACT]["result"],
                    by_candidate[LINE]["result"],
                    writer=writer,
                )
                reconciliation_wall = perf_counter() - reconcile_started
                events += 1
                candidate_aggregates += 2
                writes += int(transaction["write"]["official_counter_delta"])
                duplicate_replays += int(bool(transaction["write"]["duplicate_replay"]))
                replicas += sum(
                    len(unit["result"]["operational_timing"]["replica_rollout_seconds"])
                    for unit in units
                )
                max_atomic_wall = max(
                    max_atomic_wall, *(float(unit["wall_seconds"]) for unit in units)
                )
                telemetry = {
                    "schema_version": "rvt-phase9g-a1r-operational-event-telemetry/v1",
                    "observed_at_utc": _timestamp(),
                    "decision_event_id": task.event_id,
                    "candidate_units": [
                        {
                            "scheduler_atomic_unit_id": unit[
                                "scheduler_atomic_unit_id"
                            ],
                            "candidate_topology_id": unit[
                                "candidate_topology_id"
                            ],
                            "wall_seconds": unit["wall_seconds"],
                            "cpu_seconds": unit["cpu_seconds"],
                            "peak_rss_bytes": unit["peak_rss_bytes"],
                            "disposition": unit["result"]["disposition"],
                            "operational_timing": unit["result"][
                                "operational_timing"
                            ],
                        }
                        for unit in units
                    ],
                    "candidate_pair_reconciliation_wall_seconds": reconciliation_wall,
                    "transaction_status": transaction["reconciliation"]["status"],
                    "scientific_row_count": transaction["reconciliation"][
                        "actual_row_count"
                    ],
                    "official_counter_delta": transaction["write"][
                        "official_counter_delta"
                    ],
                    "duplicate_replay": transaction["write"]["duplicate_replay"],
                }
                _append_jsonl(telemetry_path, telemetry)
                status.update({
                    "state": "RUNNING",
                    "events_completed_this_continuation": events,
                    "candidate_aggregates_completed_this_continuation": (
                        candidate_aggregates
                    ),
                    "replicas_completed_this_continuation": replicas,
                    "maximum_atomic_unit_wall_seconds": max_atomic_wall,
                    "official_transactions_written_this_continuation": writes,
                    "duplicate_replays_this_continuation": duplicate_replays,
                    "updated_at_utc": _timestamp(),
                })
                _atomic_write(
                    status_path, status, "phase9g_a1r_continuation_status_sha256"
                )
    except BaseException as exc:
        status.update({
            "state": "FAILED",
            "failure_class": type(exc).__name__,
            "failure_message": str(exc),
            "events_completed_this_continuation": events,
            "candidate_aggregates_completed_this_continuation": candidate_aggregates,
            "replicas_completed_this_continuation": replicas,
            "maximum_atomic_unit_wall_seconds": max_atomic_wall,
            "official_transactions_written_this_continuation": writes,
            "duplicate_replays_this_continuation": duplicate_replays,
            "wall_seconds": perf_counter() - started,
            "updated_at_utc": _timestamp(),
        })
        _atomic_write(status_path, status, "phase9g_a1r_continuation_status_sha256")
        raise
    return {
        "events": events,
        "candidate_aggregates": candidate_aggregates,
        "replicas": replicas,
        "official_counter_delta": writes,
        "duplicate_replays": duplicate_replays,
        "maximum_atomic_unit_wall_seconds": max_atomic_wall,
        "wall_seconds": perf_counter() - started,
    }


def _source_binding_matches(root: Path, source_commit: str) -> bool:
    image_commit = os.environ.get("RVT_SOURCE_COMMIT")
    if image_commit is not None:
        return image_commit == source_commit
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=root,
        check=False,
    ).returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "validation"), required=True)
    parser.add_argument("--writer-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--docker-image", required=True)
    parser.add_argument("--job-manifest-sha256", required=True)
    parser.add_argument("--scientific-addendum-sha256", required=True)
    parser.add_argument("--generation-provenance-root", required=True)
    parser.add_argument("--authorization-scope", type=Path, required=True)
    parser.add_argument("--authorization-scope-sha256", required=True)
    parser.add_argument("--operational-amendment", type=Path, required=True)
    parser.add_argument("--operational-amendment-sha256", required=True)
    parser.add_argument("--authorization-continuation", type=Path, required=True)
    parser.add_argument("--authorization-continuation-sha256", required=True)
    parser.add_argument("--run-identity", type=Path, required=True)
    parser.add_argument("--run-identity-sha256", required=True)
    parser.add_argument("--minimum-checkpoint", type=Path)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--numeric-threads", type=int, required=True)
    parser.add_argument("--chunk-size", type=int, required=True)
    parser.add_argument("--infrastructure-timeout-seconds", type=float, required=True)
    parser.add_argument("--resolve-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    if not _source_binding_matches(root, args.source_commit):
        raise ContinuationError("scientific source binding mismatch")
    if args.job_manifest_sha256 != JOB_MANIFEST_SHA256:
        raise ContinuationError("job manifest binding mismatch")
    if args.numeric_threads != 1 or args.chunk_size != 1:
        raise ContinuationError("qualified numeric-thread/chunk binding mismatch")

    amendment = canonical_artifact(
        args.operational_amendment,
        "phase9g_a1r_operational_contract_amendment_sha256",
    )
    if amendment[
        "phase9g_a1r_operational_contract_amendment_sha256"
    ] != args.operational_amendment_sha256:
        raise ContinuationError("operational amendment CLI hash mismatch")
    profile = amendment["recoverability_profile"]
    expected_profile = {
        "workers": args.workers,
        "numeric_threads": args.numeric_threads,
        "chunk_size_atomic_units": args.chunk_size,
        "infrastructure_timeout_seconds": args.infrastructure_timeout_seconds,
    }
    if any(profile.get(key) != value for key, value in expected_profile.items()):
        raise ContinuationError("continuation profile differs from amendment")

    authorization = canonical_artifact(
        args.authorization_continuation,
        "phase9g_a1r_authorization_continuation_sha256",
    )
    if authorization[
        "phase9g_a1r_authorization_continuation_sha256"
    ] != args.authorization_continuation_sha256:
        raise ContinuationError("authorization continuation CLI hash mismatch")
    if args.split not in authorization["authorized_scope"]["splits"]:
        raise ContinuationError("split is outside continuation authorization")
    if authorization["authorized_scope"]["branch"] != "recoverability":
        raise ContinuationError("non-Recoverability continuation is prohibited")
    if authorization["operational_amendment_sha256"] != args.operational_amendment_sha256:
        raise ContinuationError("authorization does not bind the amendment")

    run = canonical_artifact(
        args.run_identity, "phase9g_a1r_continuation_run_identity_sha256"
    )
    if run["phase9g_a1r_continuation_run_identity_sha256"] != args.run_identity_sha256:
        raise ContinuationError("continuation run identity CLI hash mismatch")
    if run["authorization_continuation_sha256"] != args.authorization_continuation_sha256:
        raise ContinuationError("run identity does not bind authorization")

    scope = canonical_artifact(
        args.authorization_scope, "phase9_authorization_scope_sha256"
    )
    if scope["phase9_authorization_scope_sha256"] != args.authorization_scope_sha256:
        raise ContinuationError("authorization scope CLI hash mismatch")
    execution_authorized = validate_authorization_scope(
        {key: value for key, value in scope.items()
         if key != "phase9_authorization_scope_sha256"},
        study="study_a_zero_shot",
        split=args.split,
        branch="recoverability",
        source_commit=args.source_commit,
        docker_image=args.docker_image,
        addendum_sha256=args.scientific_addendum_sha256,
        provenance_root=args.generation_provenance_root,
    )
    if not execution_authorized:
        raise ContinuationError("frozen authorization scope rejected execution")

    tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split=args.split
    )
    completed = completed_event_ids(args.writer_root, tasks)
    if args.minimum_checkpoint is not None:
        checkpoint = canonical_artifact(
            args.minimum_checkpoint, "phase9g_a1r_staging_checkpoint_sha256"
        )
        required = frozenset(checkpoint["completed_event_ids"])
        if not required <= completed:
            raise ContinuationError("durable prefix lost a checkpoint event identity")
    pending = unresolved_tasks(tasks, completed)
    resolution = {
        "schema_version": "rvt-phase9g-a1r-continuation-resolution/v1",
        "run_id": run["run_id"],
        "parent_run_id": run["parent_run_id"],
        "split": args.split,
        "branch": "recoverability",
        "mode": "RESOLVE_ONLY" if args.resolve_only else OFFICIAL_STAGING,
        "total_event_identities": len(tasks),
        "completed_event_identities_reused": len(completed),
        "unresolved_event_identities_scheduled": len(pending),
        "existing_rows_reemitted": 0,
        "scientific_retry_count": 0,
        "workers": args.workers,
        "numeric_threads": args.numeric_threads,
        "chunk_size_atomic_units": args.chunk_size,
        "infrastructure_timeout_seconds": args.infrastructure_timeout_seconds,
        "operational_amendment_sha256": args.operational_amendment_sha256,
        "authorization_continuation_sha256": (
            args.authorization_continuation_sha256
        ),
        "run_identity_sha256": args.run_identity_sha256,
        "official_generation_execution_authorized": execution_authorized,
        "sealed_scope": run["sealed_scope"],
    }
    if args.resolve_only:
        print(json.dumps(resolution, sort_keys=True))
        return

    args.audit_root.mkdir(parents=True, exist_ok=True)
    telemetry_path = args.audit_root / f"{args.split}-operational-telemetry.jsonl"
    status_path = args.audit_root / f"{args.split}-continuation-status.json"
    if telemetry_path.exists():
        raise ContinuationError("telemetry path already exists for this continuation")
    status = {
        **resolution,
        "state": "RUNNING",
        "started_at_utc": _timestamp(),
        "updated_at_utc": _timestamp(),
        "events_completed_this_continuation": 0,
        "candidate_aggregates_completed_this_continuation": 0,
        "replicas_completed_this_continuation": 0,
        "official_transactions_written_this_continuation": 0,
        "duplicate_replays_this_continuation": 0,
        "maximum_atomic_unit_wall_seconds": 0.0,
    }
    _atomic_write(status_path, status, "phase9g_a1r_continuation_status_sha256")
    writer = CanonicalGenerationWriter(
        args.writer_root,
        mode=OFFICIAL_STAGING,
        official_execution_authorized=execution_authorized,
    )
    execution = execute_unresolved(
        root,
        pending,
        writer,
        workers=args.workers,
        timeout_seconds=args.infrastructure_timeout_seconds,
        telemetry_path=telemetry_path,
        status_path=status_path,
        status=status,
    )
    status.update({
        "state": "COMPLETE",
        "execution_summary": execution,
        "updated_at_utc": _timestamp(),
    })
    _atomic_write(status_path, status, "phase9g_a1r_continuation_status_sha256")
    resolution["execution_summary"] = execution
    print(json.dumps(resolution, sort_keys=True))


if __name__ == "__main__":
    main()
