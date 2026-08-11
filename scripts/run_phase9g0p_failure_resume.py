#!/usr/bin/env python3
"""Exercise scoped failure/resume behavior on the actual official producers."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0p.benchmark import (
    ADDENDUM_SHA256,
    SCIENTIFIC_SOURCE_COMMIT,
    _scientific_projection,
)
from rvt_swarm.phase9g0r.compiler import (
    compile_recoverability_tasks,
    compile_source_tasks,
)
from rvt_swarm.phase9g0r.producer import (
    produce_recoverability_candidate,
    produce_residual_state,
    reconcile_recoverability_candidate_results,
)
from rvt_swarm.phase9g0r.writer import DIAGNOSTIC, CanonicalGenerationWriter
from rvt_swarm.topology_registry import COMPACT, LINE


def _die_before_compute() -> None:
    os._exit(81)


def _compute_then_die(root: str, task: Any, candidate: int, connection: Any) -> None:
    result = produce_recoverability_candidate(Path(root), task, candidate)
    connection.send(sha256_document(_scientific_projection(result)))
    connection.close()
    os._exit(82)


def _result(case: str, passed: bool, evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"case": case, "passed": bool(passed), "evidence": dict(evidence)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    recoverability_manifest = json.loads((
        root / "results/rvt_fd24/phase9g0p_recoverability_benchmark_manifest_v1.json"
    ).read_text(encoding="ascii"))
    residual_manifest = json.loads((
        root / "results/rvt_fd24/phase9g0p_residual_benchmark_manifest_v1.json"
    ).read_text(encoding="ascii"))
    event_id = str(recoverability_manifest["events"][0]["event_id"])
    recoverability_task = next(
        task for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train"
        ) if task.event_id == event_id
    )
    residual_unit = next(
        item for item in residual_manifest["scheduler_units"]
        if item["family"] == "F1"
        and int(item["robot_id"]) == 0
        and int(item["retained_position"]) == 15
    )
    residual_task = next(
        task for task in compile_source_tasks(
            root, study="study_a_zero_shot", split="train"
        ) if task.job_id == residual_unit["source_job_id"]
    )

    compact = produce_recoverability_candidate(root, recoverability_task, COMPACT)
    line = produce_recoverability_candidate(root, recoverability_task, LINE)
    baseline_pair = reconcile_recoverability_candidate_results(
        root, recoverability_task, compact, line
    )
    baseline_pair_digest = sha256_document(_scientific_projection(baseline_pair))
    residual = produce_residual_state(
        root,
        residual_task,
        robot_id=int(residual_unit["robot_id"]),
        timestep=int(residual_unit["timestep"]),
        source_commit=SCIENTIFIC_SOURCE_COMMIT,
        scientific_addendum_sha256=ADDENDUM_SHA256,
    )
    residual_digest = sha256_document(_scientific_projection(residual))
    cases = []
    context = multiprocessing.get_context("fork")

    with tempfile.TemporaryDirectory(prefix="phase9g0p-failure-resume-") as temporary:
        temporary_root = Path(temporary)

        before_root = temporary_root / "before-completion-diagnostic"
        process = context.Process(target=_die_before_compute)
        process.start()
        process.join()
        cases.append(_result(
            "worker_dies_before_unit_completion",
            process.exitcode == 81 and not before_root.exists(),
            {"worker_exit_code": process.exitcode, "published_records": 0},
        ))

        receive, send = context.Pipe(duplex=False)
        process = context.Process(
            target=_compute_then_die,
            args=(str(root), recoverability_task, COMPACT, send),
        )
        process.start()
        computed_digest = receive.recv()
        process.join()
        replay_compact = produce_recoverability_candidate(
            root, recoverability_task, COMPACT
        )
        replay_digest = sha256_document(_scientific_projection(replay_compact))
        cases.append(_result(
            "worker_dies_after_compute_before_durable_ack",
            process.exitcode == 82 and computed_digest == replay_digest,
            {
                "worker_exit_code": process.exitcode,
                "computed_scientific_digest": computed_digest,
                "replay_scientific_digest": replay_digest,
                "published_records_before_replay": 0,
            },
        ))

        checkpoint = temporary_root / "candidate-checkpoint.json"
        checkpoint.write_text(
            json.dumps(compact, ensure_ascii=True, sort_keys=True), encoding="ascii"
        )
        resumed_pair = reconcile_recoverability_candidate_results(
            root,
            recoverability_task,
            json.loads(checkpoint.read_text(encoding="ascii")),
            produce_recoverability_candidate(root, recoverability_task, LINE),
        )
        resumed_pair_digest = sha256_document(_scientific_projection(resumed_pair))
        cases.append(_result(
            "termination_between_chunks_then_resume",
            resumed_pair_digest == baseline_pair_digest,
            {
                "baseline_pair_digest": baseline_pair_digest,
                "resumed_pair_digest": resumed_pair_digest,
                "candidate_pair_partially_published": False,
            },
        ))

        duplicate_writer = CanonicalGenerationWriter(
            temporary_root / "duplicate-diagnostic", mode=DIAGNOSTIC
        )
        reconciliation = baseline_pair["reconciliation"]
        from rvt_swarm.phase9g0r.contracts import CandidatePairReconciliation
        frozen_reconciliation = CandidatePairReconciliation(**reconciliation)
        first = duplicate_writer.write_recoverability_transaction(
            frozen_reconciliation,
            {**baseline_pair["audit"], "operational_timing": {"seconds": 1.0}},
        )
        duplicate = duplicate_writer.write_recoverability_transaction(
            frozen_reconciliation,
            {**baseline_pair["audit"], "operational_timing": {"seconds": 2.0}},
        )
        cases.append(_result(
            "duplicate_task_submission",
            not first["duplicate_replay"] and duplicate["duplicate_replay"]
            and first["canonical_sha256"] == duplicate["canonical_sha256"],
            {
                "first_duplicate_replay": first["duplicate_replay"],
                "second_duplicate_replay": duplicate["duplicate_replay"],
                "durable_record_count": 1,
            },
        ))

        partial_writer = CanonicalGenerationWriter(
            temporary_root / "partial-pair-diagnostic", mode=DIAGNOSTIC
        )
        destination = Path(first["path"])
        relative = destination.relative_to(duplicate_writer.root)
        partial_destination = partial_writer.root / relative
        partial_destination.parent.mkdir(parents=True)
        partial_destination.with_suffix(".json.partial").write_text(
            '{"rows":[{"candidate_topology_id":0}]}', encoding="ascii"
        )
        orphan_audit = partial_writer.root / "audit" / "event.partial"
        orphan_audit.parent.mkdir(parents=True)
        orphan_audit.write_text('{"incomplete":true}', encoding="ascii")
        completed = partial_writer.write_recoverability_transaction(
            frozen_reconciliation, baseline_pair["audit"]
        )
        persisted = json.loads(Path(completed["path"]).read_text(encoding="ascii"))
        cases.append(_result(
            "partial_recoverability_row_set_and_audit_sidecar_resume",
            persisted["scientific_completion_marker"]
            and persisted["actual_row_count"] in (0, persisted["expected_row_count"])
            and not partial_destination.with_suffix(".json.partial").exists()
            and not (partial_writer.root / "audit" / "event.json").exists(),
            {
                "actual_row_count": persisted["actual_row_count"],
                "expected_row_count": persisted["expected_row_count"],
                "orphan_partial_audit_was_never_published": True,
            },
        ))

        residual_writer = CanonicalGenerationWriter(
            temporary_root / "partial-residual-diagnostic", mode=DIAGNOSTIC
        )
        residual_id = str(residual["audit"]["scientific_row_id"])
        residual_destination = residual_writer.root / "residual" / f"state-{residual_id}.json"
        residual_destination.parent.mkdir(parents=True)
        residual_destination.with_suffix(".json.partial").write_text(
            '{"row":"incomplete"}', encoding="ascii"
        )
        residual_completed = residual_writer.write_residual_attempt(
            scientific_row_id=residual_id,
            disposition=str(residual["audit"]["disposition"]),
            row=residual["row"],
            audit=residual["audit"],
        )
        residual_persisted = json.loads(
            Path(residual_completed["path"]).read_text(encoding="ascii")
        )
        cases.append(_result(
            "partial_residual_row_resume",
            residual_persisted["scientific_completion_marker"]
            and not residual_destination.with_suffix(".json.partial").exists(),
            {
                "disposition": residual_persisted["disposition"],
                "durable_record_count": 1,
            },
        ))

        failure_writer = CanonicalGenerationWriter(
            temporary_root / "writer-failure-diagnostic", mode=DIAGNOSTIC
        )
        writer_failed = False
        with patch("rvt_swarm.phase9g0r.writer.os.replace", side_effect=OSError("injected")):
            try:
                failure_writer.write_residual_attempt(
                    scientific_row_id=residual_id,
                    disposition=str(residual["audit"]["disposition"]),
                    row=residual["row"],
                    audit=residual["audit"],
                )
            except OSError:
                writer_failed = True
        failure_destination = failure_writer.root / "residual" / f"state-{residual_id}.json"
        absent_after_failure = not failure_destination.exists()
        resumed = failure_writer.write_residual_attempt(
            scientific_row_id=residual_id,
            disposition=str(residual["audit"]["disposition"]),
            row=residual["row"],
            audit=residual["audit"],
        )
        cases.append(_result(
            "writer_failure_then_resume",
            writer_failed and absent_after_failure and Path(resumed["path"]).exists(),
            {
                "durable_record_absent_after_failure": absent_after_failure,
                "resume_duplicate_replay": resumed["duplicate_replay"],
            },
        ))

    residual_replay = produce_residual_state(
        root,
        residual_task,
        robot_id=int(residual_unit["robot_id"]),
        timestep=int(residual_unit["timestep"]),
        source_commit=SCIENTIFIC_SOURCE_COMMIT,
        scientific_addendum_sha256=ADDENDUM_SHA256,
    )
    residual_replay_digest = sha256_document(_scientific_projection(residual_replay))
    cases.append(_result(
        "residual_nine_candidate_exact_replay",
        residual_digest == residual_replay_digest
        and residual["audit"]["candidate_evaluations"] == 9,
        {
            "candidate_evaluations": residual["audit"]["candidate_evaluations"],
            "baseline_digest": residual_digest,
            "replay_digest": residual_replay_digest,
        },
    ))

    report = {
        "schema_version": "rvt-phase9g0p-failure-resume-qualification/v1",
        "mode": DIAGNOSTIC,
        "actual_official_producer_used": True,
        "recoverability_event_id": recoverability_task.event_id,
        "residual_scheduler_atomic_unit_id": residual_unit["scheduler_atomic_unit_id"],
        "cases": cases,
        "case_count": len(cases),
        "passes": sum(bool(case["passed"]) for case in cases),
        "failures": sum(not bool(case["passed"]) for case in cases),
        "candidate_pair_partial_scientific_publications": 0,
        "residual_partial_scientific_publications": 0,
        "official_run_ids": 0,
        "official_staging_writes": 0,
        "study_a_n24_accesses": 0,
        "final_test_accesses": 0,
    }
    document = attach_canonical_hash(
        report, "phase9g0p_failure_resume_qualification_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "case_count": document["case_count"],
        "passes": document["passes"],
        "failures": document["failures"],
        "sha256": document["phase9g0p_failure_resume_qualification_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
