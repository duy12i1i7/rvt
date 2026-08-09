#!/usr/bin/env python3
"""Run target writer, storage, failure, resume and timeout diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import shutil
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

from rvt_swarm.phase8.common import (
    attach_canonical_hash,
    canonical_json_bytes,
    sha256_document,
)
from rvt_swarm.phase9c_rb21.rb21_bench import distribution
from rvt_swarm.phase9c_rb21.rb21_manifest import write_json
from rvt_swarm.phase9c_rb21.rb21_storage import AtomicUnitStore, StorageContractError
from rvt_swarm.phase9c_rb21.rb21_units import infrastructure_timeout_result


def _commit_one(args: Tuple[str, int, Mapping[str, Any], Mapping[str, Any]]) -> int:
    root, index, template_record, template_sidecar = args
    unit_id = hashlib.sha256(f"writer-{index}".encode("ascii")).hexdigest()
    record = {**dict(template_record), "atomic_unit_id": unit_id}
    sidecar = dict(template_sidecar)
    AtomicUnitStore(Path(root)).commit(
        unit_id, record, sidecar, attempt_id=f"writer-attempt-{index}")
    return len(canonical_json_bytes(record)) + len(canonical_json_bytes(sidecar))


def _crashing_commit(root: str, unit_id: str, record: Mapping[str, Any],
                     sidecar: Mapping[str, Any], failure_point: str) -> None:
    try:
        AtomicUnitStore(Path(root)).commit(
            unit_id, record, sidecar, attempt_id=f"crash-{unit_id}",
            failure_point=failure_point)
    except StorageContractError:
        os._exit(17)
    os._exit(18)


def _between_chunks(root: str, record: Mapping[str, Any],
                    sidecar: Mapping[str, Any]) -> None:
    AtomicUnitStore(Path(root)).commit(
        "chunk-unit-a", record, sidecar, attempt_id="chunk-attempt-a")
    os._exit(19)


def _split_record(row: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    record = dict(row)
    if row["unit_kind"] == "RESIDUAL":
        sidecar = {"candidate_records": record.pop("candidate_records")}
    else:
        sidecar = {"replicas": record.pop("replicas")}
    return record, sidecar


def _size_distributions(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    residual_records = []
    residual_sidecars = []
    no_eligible_records = []
    recoverability_records = []
    recoverability_sidecars = []
    index_records = []
    for row in rows:
        record, sidecar = _split_record(row)
        record_size = len(canonical_json_bytes(record))
        sidecar_size = len(canonical_json_bytes(sidecar))
        index_size = len(canonical_json_bytes({
            "atomic_unit_id": row["atomic_unit_id"],
            "record_sha256": sha256_document(record),
            "sidecar_sha256": sha256_document(sidecar),
            "complete": True,
        }))
        index_records.append(index_size)
        if row["unit_kind"] == "RESIDUAL":
            residual_records.append(record_size)
            residual_sidecars.append(sidecar_size)
            if row["disposition"] == "NO_ELIGIBLE_ACTION":
                no_eligible_records.append(record_size + sidecar_size)
        else:
            recoverability_records.append(record_size)
            recoverability_sidecars.append(sidecar_size)
    shard_manifest = {
        "schema_version": "rvt-rb21-diagnostic-shard-index/v1",
        "unit_ids": [row["atomic_unit_id"] for row in rows],
        "complete": True,
    }
    return {
        "recoverability_scientific_record_bytes": distribution(recoverability_records),
        "recoverability_replica_audit_sidecar_bytes": distribution(
            recoverability_sidecars),
        "residual_labeled_or_disposition_row_bytes": distribution(residual_records),
        "residual_nine_candidate_sidecar_bytes": distribution(residual_sidecars),
        "no_eligible_audit_record_bytes": distribution(no_eligible_records),
        "index_record_bytes": distribution(index_records),
        "representative_shard_manifest_bytes": len(canonical_json_bytes(shard_manifest)),
    }


def _official_size_distributions(rb18: Mapping[str, Any]) -> Mapping[str, Any]:
    recoverability_records = [
        len(canonical_json_bytes(replica))
        for case in rb18["recoverability"] for replica in case["replica_records"]
    ]
    recoverability_sidecars = [
        len(canonical_json_bytes({
            "case_id": case["case_id"],
            "decision_snapshot_sha256": case["decision_snapshot_sha256"],
            "candidate_rollouts": case["candidate_rollouts"],
            "aggregate_labels": case["aggregate_labels"],
            "replica_records": case["replica_records"],
        }))
        for case in rb18["recoverability"]
    ]
    labeled = [row for row in rb18["residual"] if row["disposition"] == "LABELED"]
    no_eligible = [row for row in rb18["residual"]
                   if row["disposition"] == "NO_ELIGIBLE_ACTION"]
    residual_records = [len(canonical_json_bytes(row)) for row in labeled]
    residual_records_without_sidecar = [
        len(canonical_json_bytes({key: value for key, value in row.items()
                                  if key != "candidate_sidecar"}))
        for row in labeled
    ]
    residual_sidecars = [
        len(canonical_json_bytes(row["candidate_sidecar"])) for row in labeled
    ]
    no_eligible_records = [len(canonical_json_bytes(row)) for row in no_eligible]
    index_template = {
        "scientific_row_id": "u" * 64,
        "record_sha256": "r" * 64,
        "sidecar_sha256": "s" * 64,
        "complete": True,
    }
    shard_manifest = {
        "schema_version": "rvt-rb21-diagnostic-shard-index/v1",
        "unit_ids": ["u" * 64 for _ in range(
            len(recoverability_records) + len(rb18["residual"]))],
        "complete": True,
    }
    return {
        "source": "rb18_structural_generation_canary_v1.json_ALL_AVAILABLE_RECORDS",
        "recoverability_scientific_record_bytes": distribution(recoverability_records),
        "recoverability_replica_audit_sidecar_bytes": distribution(
            recoverability_sidecars),
        "residual_labeled_row_bytes": distribution(residual_records),
        "residual_labeled_row_excluding_embedded_sidecar_bytes": distribution(
            residual_records_without_sidecar),
        "residual_nine_candidate_sidecar_bytes": distribution(residual_sidecars),
        "no_eligible_audit_record_bytes": distribution(no_eligible_records),
        "index_record_bytes": len(canonical_json_bytes(index_template)),
        "representative_shard_manifest_bytes": len(canonical_json_bytes(shard_manifest)),
    }


def _writer_benchmark(root: Path, record: Mapping[str, Any], sidecar: Mapping[str, Any],
                      workers: int, repetitions: int) -> Mapping[str, Any]:
    staging = root / f"writer-w{workers}"
    arguments = [(str(staging), index, record, sidecar) for index in range(repetitions)]
    started = time.perf_counter()
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
        sizes = list(executor.map(_commit_one, arguments, chunksize=1))
    elapsed = time.perf_counter() - started
    store = AtomicUnitStore(staging)
    return {
        "workers": workers,
        "records": repetitions,
        "bytes": sum(sizes),
        "wall_seconds": elapsed,
        "records_per_second": repetitions / elapsed,
        "megabytes_per_second": sum(sizes) / elapsed / 1_000_000.0,
        "all_commits_validate": len(store.completed_unit_ids()) == repetitions,
        "encoding": "CANONICAL_JSON_UNCHANGED",
        "compression": "NONE",
    }


def _failure_resume(root: Path, record: Mapping[str, Any],
                    sidecar: Mapping[str, Any]) -> Mapping[str, Any]:
    store = AtomicUnitStore(root)
    partial = []
    for point in ("after_record", "after_sidecar", "before_promotion"):
        unit_id = f"partial-{point}"
        try:
            store.commit(unit_id, record, sidecar, attempt_id=f"attempt-{point}",
                         failure_point=point)
        except StorageContractError:
            pass
        partial.append({
            "failure_point": point,
            "accepted_as_complete": unit_id in store.completed_unit_ids(),
            "attempt_preserved": f"attempt-{point}" in store.incomplete_attempts(),
        })

    context = mp.get_context("spawn")
    processes = []
    for unit_id, point in (
            ("worker-before-complete", "after_record"),
            ("worker-after-compute-before-ack", "before_promotion")):
        process = context.Process(
            target=_crashing_commit,
            args=(str(root), unit_id, record, sidecar, point))
        process.start()
        process.join(30)
        processes.append({
            "case": unit_id,
            "exit_code": process.exitcode,
            "accepted_as_complete": unit_id in AtomicUnitStore(root).completed_unit_ids(),
        })

    between = context.Process(target=_between_chunks, args=(str(root), record, sidecar))
    between.start()
    between.join(30)

    success = store.commit("resume-unit", record, sidecar, attempt_id="success")
    duplicate = store.commit("resume-unit", record, sidecar, attempt_id="duplicate")
    changed_rejected = False
    try:
        store.commit("resume-unit", {**record, "changed": True}, sidecar,
                     attempt_id="changed-duplicate")
    except StorageContractError:
        changed_rejected = True

    insufficient_rejected = False
    try:
        store.commit(
            "insufficient-space", record, sidecar, attempt_id="insufficient-space",
            required_free_bytes=shutil.disk_usage(root).free + 1)
    except StorageContractError:
        insufficient_rejected = True

    reloaded = AtomicUnitStore(root)
    committed = json.loads(
        (root / "units/resume-unit/record.json").read_text(encoding="ascii"))
    committed_sidecar = json.loads(
        (root / "units/resume-unit/sidecar.json").read_text(encoding="ascii"))
    return {
        "partial_write_cases": partial,
        "abrupt_worker_cases": processes,
        "termination_between_chunks": {
            "exit_code": between.exitcode,
            "first_unit_complete": "chunk-unit-a" in reloaded.completed_unit_ids(),
            "unscheduled_second_unit_complete": "chunk-unit-b" in reloaded.completed_unit_ids(),
        },
        "first_commit": success,
        "duplicate_submission": duplicate,
        "changed_science_duplicate_rejected": changed_rejected,
        "insufficient_temporary_space_rejected": insufficient_rejected,
        "record_identity_equal_after_resume": sha256_document(committed) == sha256_document(record),
        "sidecar_identity_equal_after_resume": (
            sha256_document(committed_sidecar) == sha256_document(sidecar)),
        "incomplete_attempt_count": len(reloaded.incomplete_attempts()),
        "partial_record_accepted": any(row["accepted_as_complete"] for row in partial),
        "semantic_retry_count": 0,
        "infrastructure_retry_limit": 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--residual-baseline", type=Path, required=True)
    parser.add_argument("--recoverability-baseline", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selected-workers", type=int, required=True)
    parser.add_argument("--writer-repetitions", type=int, default=256)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    args = parser.parse_args()

    residual = json.loads(args.residual_baseline.read_text(encoding="ascii"))
    recoverability = json.loads(args.recoverability_baseline.read_text(encoding="ascii"))
    rows = residual["scientific_semantic_projection"] + recoverability[
        "scientific_semantic_projection"]
    rb18 = json.loads(
        (args.root / "results/rvt_fd24/rb18_structural_generation_canary_v1.json")
        .read_text(encoding="ascii")
    )
    labeled = next(row for row in rows if row["unit_kind"] == "RESIDUAL"
                   and row["disposition"] == "LABELED")
    record, sidecar = _split_record(labeled)

    disk = shutil.disk_usage(args.output.parent)
    with tempfile.TemporaryDirectory(
            prefix="rvt-rb21-target-probes-", dir=args.output.parent) as temporary:
        temporary_root = Path(temporary)
        writer = [
            _writer_benchmark(temporary_root, record, sidecar, workers, args.writer_repetitions)
            for workers in sorted({1, args.selected_workers})
        ]
        failure = _failure_resume(temporary_root / "failure", record, sidecar)

    timeout_probe = infrastructure_timeout_result("t" * 64, args.timeout_seconds)
    document = {
        "schema_version": "rvt-rb21-target-operational-probes/v1",
        "provenance_class": "OPERATIONAL_BENCHMARK_ONLY",
        "baseline_references": {
            "residual": residual["rb21_target_benchmark_run_sha256"],
            "recoverability": recoverability["rb21_target_benchmark_run_sha256"],
        },
        "canonical_size_distributions": {
            "official_qualified_serialization": _official_size_distributions(rb18),
            "target_benchmark_atomic_unit_envelopes": _size_distributions(rows),
        },
        "target_storage": {
            "path": str(args.output.parent.resolve()),
            "total_bytes": disk.total,
            "available_bytes": disk.free,
        },
        "writer_benchmarks": writer,
        "failure_resume": failure,
        "timeout_semantics_probe": timeout_probe,
        "official_generation_executed": False,
        "official_rows": 0,
        "official_shards": 0,
        "study_a_n24_accesses": 0,
        "final_test_accesses": 0,
    }
    write_json(
        args.output,
        attach_canonical_hash(document, "rb21_target_operational_probes_sha256"),
    )


if __name__ == "__main__":
    main()
