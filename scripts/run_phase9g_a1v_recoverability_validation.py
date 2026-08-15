#!/usr/bin/env python3
"""Execute the distinct official Study-A Recoverability VALIDATION split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.phase9g0r.compiler import JOB_MANIFEST_SHA256, compile_recoverability_tasks
from rvt_swarm.phase9g0r.preflight import validate_authorization_scope
from rvt_swarm.phase9g0r.writer import CanonicalGenerationWriter, OFFICIAL_STAGING
from scripts.run_phase9g_a1r_recoverability_continuation import (
    ContinuationError,
    _atomic_write,
    _source_binding_matches,
    _timestamp,
    canonical_artifact,
    completed_event_ids,
    execute_unresolved,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--writer-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--docker-image", required=True)
    parser.add_argument("--scientific-addendum-sha256", required=True)
    parser.add_argument("--generation-provenance-root", required=True)
    parser.add_argument("--authorization-scope", type=Path, required=True)
    parser.add_argument("--authorization-scope-sha256", required=True)
    parser.add_argument("--operational-amendment", type=Path, required=True)
    parser.add_argument("--operational-amendment-sha256", required=True)
    parser.add_argument("--owner-authorization", type=Path, required=True)
    parser.add_argument("--owner-authorization-sha256", required=True)
    parser.add_argument("--run-identity", type=Path, required=True)
    parser.add_argument("--run-identity-sha256", required=True)
    parser.add_argument("--task-manifest", type=Path, required=True)
    parser.add_argument("--task-manifest-sha256", required=True)
    parser.add_argument("--s3-prestart-guard", type=Path, required=True)
    parser.add_argument("--s3-prestart-guard-sha256", required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--numeric-threads", type=int, required=True)
    parser.add_argument("--chunk-size", type=int, required=True)
    parser.add_argument("--infrastructure-timeout-seconds", type=float, required=True)
    parser.add_argument("--resolve-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    if not _source_binding_matches(root, args.source_commit):
        raise ContinuationError("scientific source binding mismatch")
    amendment = canonical_artifact(
        args.operational_amendment,
        "phase9g_a1r_operational_contract_amendment_sha256",
    )
    profile = amendment["recoverability_profile"]
    if (
        args.operational_amendment_sha256
        != amendment["phase9g_a1r_operational_contract_amendment_sha256"]
        or args.workers != 12
        or args.numeric_threads != 1
        or args.chunk_size != 1
        or args.infrastructure_timeout_seconds != 243
        or profile["workers"] != args.workers
        or profile["numeric_threads"] != args.numeric_threads
        or profile["chunk_size_atomic_units"] != args.chunk_size
        or profile["infrastructure_timeout_seconds"]
        != args.infrastructure_timeout_seconds
    ):
        raise ContinuationError("execution profile differs from qualified profile")

    authorization = canonical_artifact(
        args.owner_authorization, "phase9g_a1v_owner_authorization_sha256"
    )
    if (
        authorization["phase9g_a1v_owner_authorization_sha256"]
        != args.owner_authorization_sha256
        or authorization["authorized_scope"]
        != {
            "study": "study_a_zero_shot",
            "splits": ["validation"],
            "branch": "recoverability",
            "operation": "OFFICIAL_VALIDATION_STAGING_AND_FINALIZATION",
        }
    ):
        raise ContinuationError("authorization is not validation-only Recoverability")
    bindings = authorization["bindings"]
    if (
        bindings["executable_source_commit"] != args.source_commit
        or bindings["production_image"] != args.docker_image
        or bindings["scientific_provenance_root"] != args.generation_provenance_root
        or bindings["scientific_addendum_sha256"] != args.scientific_addendum_sha256
        or bindings["operational_amendment_sha256"]
        != args.operational_amendment_sha256
        or bindings["validation_task_manifest_sha256"] != args.task_manifest_sha256
    ):
        raise ContinuationError("authorization binding mismatch")

    scope = canonical_artifact(args.authorization_scope, "phase9_authorization_scope_sha256")
    if scope["phase9_authorization_scope_sha256"] != args.authorization_scope_sha256:
        raise ContinuationError("authorization scope CLI hash mismatch")
    execution_authorized = validate_authorization_scope(
        {key: value for key, value in scope.items() if key != "phase9_authorization_scope_sha256"},
        study="study_a_zero_shot",
        split="validation",
        branch="recoverability",
        source_commit=args.source_commit,
        docker_image=args.docker_image,
        addendum_sha256=args.scientific_addendum_sha256,
        provenance_root=args.generation_provenance_root,
    )
    if not execution_authorized:
        raise ContinuationError("validation scope rejected execution")

    run = canonical_artifact(args.run_identity, "phase9g_a1v_validation_run_identity_sha256")
    manifest = canonical_artifact(
        args.task_manifest, "phase9g_a1v_validation_task_manifest_sha256"
    )
    guard = canonical_artifact(
        args.s3_prestart_guard, "phase9g_a1v_s3_prestart_guard_sha256"
    )
    if (
        run["phase9g_a1v_validation_run_identity_sha256"] != args.run_identity_sha256
        or run["authorization_sha256"] != args.owner_authorization_sha256
        or manifest["phase9g_a1v_validation_task_manifest_sha256"]
        != args.task_manifest_sha256
        or guard["phase9g_a1v_s3_prestart_guard_sha256"]
        != args.s3_prestart_guard_sha256
        or guard["status"] != "PASS"
        or guard["counter_levels"]["unresolved_s3_ambiguities"] != 0
    ):
        raise ContinuationError("run, task manifest, or S3 guard binding mismatch")

    tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="validation"
    )
    if (
        len(tasks) != 1500
        or manifest["decision_events"] != 1500
        or {task.event_id for task in tasks}
        != {item["decision_event_id"] for item in manifest["decision_event_tasks"]}
    ):
        raise ContinuationError("compiled VALIDATION universe changed")
    writer_root = args.writer_root.resolve()
    completed = completed_event_ids(writer_root, tasks)
    if completed:
        raise ContinuationError("VALIDATION namespace is not empty at first execution")
    if writer_root.exists() and any(writer_root.rglob("*")):
        raise ContinuationError("VALIDATION namespace contains preexisting content")

    resolution = {
        "schema_version": "rvt-phase9g-a1v-validation-resolution/v1",
        "run_id": run["run_id"],
        "parent_run_id": run["parent_run_id"],
        "study": "study_a_zero_shot",
        "split": "validation",
        "branch": "recoverability",
        "mode": "RESOLVE_ONLY" if args.resolve_only else OFFICIAL_STAGING,
        "source_episodes": 300,
        "total_event_identities": len(tasks),
        "candidate_aggregate_identities": 2 * len(tasks),
        "candidate_replica_slots": sum(
            2 * task.replicas_per_candidate for task in tasks
        ),
        "preexisting_event_identities": 0,
        "scientific_retry_count": 0,
        "job_manifest_sha256": JOB_MANIFEST_SHA256,
        "validation_task_manifest_sha256": args.task_manifest_sha256,
        "s3_prestart_guard_sha256": args.s3_prestart_guard_sha256,
        "workers": args.workers,
        "numeric_threads": args.numeric_threads,
        "chunk_size_atomic_units": args.chunk_size,
        "infrastructure_timeout_seconds": args.infrastructure_timeout_seconds,
        "authorization_sha256": args.owner_authorization_sha256,
        "run_identity_sha256": args.run_identity_sha256,
        "official_generation_execution_authorized": execution_authorized,
        "sealed_scope": run["sealed_scope"],
    }
    if args.resolve_only:
        print(json.dumps(resolution, sort_keys=True))
        return

    args.audit_root.mkdir(parents=True, exist_ok=True)
    telemetry_path = args.audit_root / "validation-operational-telemetry.jsonl"
    status_path = args.audit_root / "validation-status.json"
    if telemetry_path.exists() or status_path.exists():
        raise ContinuationError("A1V audit output already exists")
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
        "infrastructure_timeouts": 0,
        "writer_failures": 0,
        "partial_transactions": 0,
        "unresolved_s3_ambiguities": 0,
    }
    hash_field = "phase9g_a1v_validation_status_sha256"
    _atomic_write(status_path, status, hash_field)
    writer = CanonicalGenerationWriter(
        writer_root,
        mode=OFFICIAL_STAGING,
        official_execution_authorized=execution_authorized,
    )
    execution = execute_unresolved(
        root,
        tasks,
        writer,
        workers=args.workers,
        timeout_seconds=args.infrastructure_timeout_seconds,
        telemetry_path=telemetry_path,
        status_path=status_path,
        status=status,
        status_hash_field=hash_field,
    )
    status.update({"state": "COMPLETE", "execution_summary": execution, "updated_at_utc": _timestamp()})
    _atomic_write(status_path, status, hash_field)
    resolution["execution_summary"] = execution
    print(json.dumps(resolution, sort_keys=True))


if __name__ == "__main__":
    main()
