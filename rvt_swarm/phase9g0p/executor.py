"""Bounded parallel executor for the frozen official generation producers."""

from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ProcessPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from .benchmark import (
    ADDENDUM_SHA256,
    _configure_worker,
    _recoverability_worker,
    _residual_worker,
)
from ..phase8.common import sha256_document
from ..phase9g0r.compiler import OfficialSourceTask
from ..phase9g0r.producer import (
    plan_residual_retained_states,
    reconcile_recoverability_candidate_results,
)
from ..phase9g0r.writer import CanonicalGenerationWriter
from ..topology_registry import COMPACT, LINE


class ProductionInfrastructureError(RuntimeError):
    """Infrastructure stopped before a complete scientific unit was durable."""


def _residual_plan_worker(
    job: tuple[str, OfficialSourceTask],
) -> tuple[OfficialSourceTask, Mapping[int, tuple[int, ...]]]:
    root_value, task = job
    return task, plan_residual_retained_states(Path(root_value), task)


def _bounded_ordered_results(
    pool: ProcessPoolExecutor,
    worker: Any,
    jobs: Iterable[Any],
    *,
    workers: int,
    timeout_seconds: float,
) -> Iterator[Any]:
    pending: deque[Future[Any]] = deque()
    iterator = iter(jobs)
    exhausted = False
    while pending or not exhausted:
        while not exhausted and len(pending) < 2 * workers:
            try:
                job = next(iterator)
            except StopIteration:
                exhausted = True
                break
            pending.append(pool.submit(worker, job))
        if not pending:
            break
        future = pending.popleft()
        try:
            yield future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise ProductionInfrastructureError(
                "atomic unit exceeded infrastructure timeout; no scientific "
                "disposition was emitted"
            ) from exc
        except Exception as exc:
            raise ProductionInfrastructureError(
                "worker failed before durable unit acknowledgement"
            ) from exc


def execute_recoverability(
    root: Path,
    tasks: Sequence[Any],
    writer: CanonicalGenerationWriter,
    *,
    workers: int,
    timeout_seconds: float,
) -> Mapping[str, int]:
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
    duplicates = 0
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
            compact = next(results)
            line = next(results)
            by_candidate = {
                int(compact["candidate_topology_id"]): compact["result"],
                int(line["candidate_topology_id"]): line["result"],
            }
            transaction = reconcile_recoverability_candidate_results(
                root,
                task,
                by_candidate[COMPACT],
                by_candidate[LINE],
                writer=writer,
            )
            events += 1
            writes += int(transaction["write"]["official_counter_delta"])
            duplicates += int(bool(transaction["write"]["duplicate_replay"]))
    return {"events": events, "official_counter_delta": writes, "duplicates": duplicates}


def execute_residual(
    root: Path,
    tasks: Sequence[Any],
    writer: CanonicalGenerationWriter,
    *,
    workers: int,
    timeout_seconds: float,
    source_commit: str,
    scientific_addendum_sha256: str = ADDENDUM_SHA256,
) -> Mapping[str, int]:
    with ProcessPoolExecutor(
        max_workers=workers, initializer=_configure_worker
    ) as pool:
        plans = list(_bounded_ordered_results(
            pool,
            _residual_plan_worker,
            ((str(root), task.source) for task in tasks),
            workers=workers,
            timeout_seconds=timeout_seconds,
        ))

    def jobs() -> Iterator[Any]:
        for task, retained in plans:
            for robot_id, timesteps in retained.items():
                for timestep in timesteps:
                    unit_id = sha256_document({
                        "source_job_id": task.job_id,
                        "robot_id": robot_id,
                        "timestep": timestep,
                    })
                    yield str(root), task, robot_id, timestep, unit_id

    attempts = 0
    writes = 0
    duplicates = 0
    with ProcessPoolExecutor(
        max_workers=workers, initializer=_configure_worker
    ) as pool:
        results = _bounded_ordered_results(
            pool,
            _residual_worker,
            jobs(),
            workers=workers,
            timeout_seconds=timeout_seconds,
        )
        for unit in results:
            result = unit["result"]
            write = writer.write_residual_attempt(
                scientific_row_id=str(result["audit"]["scientific_row_id"]),
                disposition=str(result["audit"]["disposition"]),
                row=result["row"],
                audit=result["audit"],
            )
            attempts += 1
            writes += int(write["official_counter_delta"])
            duplicates += int(bool(write["duplicate_replay"]))
    return {
        "attempts": attempts,
        "official_counter_delta": writes,
        "duplicates": duplicates,
    }

