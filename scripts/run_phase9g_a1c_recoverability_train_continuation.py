#!/usr/bin/env python3
"""Resume only unresolved official Study-A Recoverability TRAIN identities."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from rvt_swarm.phase8.common import sha256_document
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
    unresolved_tasks,
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_exact_checkpoint(writer_root: Path, checkpoint: dict) -> frozenset[str]:
    transaction_root = writer_root.resolve() / "recoverability"
    expected = {
        str(item["decision_event_id"]): item
        for item in checkpoint["candidate_pair_transactions"]
    }
    paths = tuple(sorted(transaction_root.glob("event-*.json")))
    if len(paths) != len(expected):
        raise ContinuationError("STAGING transaction count differs from checkpoint")
    observed_ids = set()
    observed_rows = []
    for path in paths:
        document = json.loads(path.read_text(encoding="ascii"))
        body = dict(document)
        canonical_hash = str(body.pop("canonical_record_sha256", ""))
        if sha256_document(body) != canonical_hash:
            raise ContinuationError("STAGING transaction canonical hash mismatch")
        event_id = str(document["decision_event_id"])
        descriptor = expected.get(event_id)
        if descriptor is None:
            raise ContinuationError("STAGING contains an event outside checkpoint")
        if path.name != descriptor["file_name"]:
            raise ContinuationError("STAGING transaction filename differs from checkpoint")
        if canonical_hash != descriptor["canonical_record_sha256"]:
            raise ContinuationError("STAGING transaction content differs from checkpoint")
        if _file_sha256(path) != descriptor["file_sha256"]:
            raise ContinuationError("STAGING transaction file hash differs from checkpoint")
        row_ids = [str(row["scientific_row_id"]) for row in document["rows"]]
        if row_ids != descriptor["scientific_row_ids"]:
            raise ContinuationError("STAGING row identities differ from checkpoint")
        observed_rows.extend(row_ids)
        observed_ids.add(event_id)
    if observed_ids != set(expected):
        raise ContinuationError("STAGING completed identity set differs from checkpoint")
    if sorted(observed_rows) != sorted(checkpoint["scientific_row_ids"]):
        raise ContinuationError("STAGING scientific row set differs from checkpoint")
    if len(observed_rows) != 342 or len(set(observed_rows)) != 342:
        raise ContinuationError("STAGING initial row count or uniqueness changed")
    return frozenset(observed_ids)


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
    parser.add_argument("--authorization-continuation", type=Path, required=True)
    parser.add_argument("--authorization-continuation-sha256", required=True)
    parser.add_argument("--run-identity", type=Path, required=True)
    parser.add_argument("--run-identity-sha256", required=True)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--initial-checkpoint-sha256", required=True)
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
    if args.numeric_threads != 1 or args.chunk_size != 1:
        raise ContinuationError("qualified numeric-thread/chunk binding mismatch")

    amendment = canonical_artifact(
        args.operational_amendment,
        "phase9g_a1r_operational_contract_amendment_sha256",
    )
    if amendment["phase9g_a1r_operational_contract_amendment_sha256"] != (
        args.operational_amendment_sha256
    ):
        raise ContinuationError("operational amendment CLI hash mismatch")
    profile = amendment["recoverability_profile"]
    if (
        args.workers != 12
        or args.numeric_threads != 1
        or args.chunk_size != 1
        or args.infrastructure_timeout_seconds != 243
        or profile["workers"] != args.workers
        or profile["numeric_threads"] != args.numeric_threads
        or profile["chunk_size_atomic_units"] != args.chunk_size
        or profile["infrastructure_timeout_seconds"] != args.infrastructure_timeout_seconds
    ):
        raise ContinuationError("execution profile differs from qualified A1C profile")

    authorization = canonical_artifact(
        args.authorization_continuation,
        "phase9g_a1c_owner_authorization_continuation_sha256",
    )
    if authorization[
        "phase9g_a1c_owner_authorization_continuation_sha256"
    ] != args.authorization_continuation_sha256:
        raise ContinuationError("authorization continuation CLI hash mismatch")
    if authorization["authorized_scope"] != {
        "study": "study_a_zero_shot",
        "splits": ["train"],
        "branch": "recoverability",
        "operation": "OFFICIAL_STAGING_CONTINUATION_AND_TRAIN_FINALIZATION",
    }:
        raise ContinuationError("authorization is not TRAIN-only Recoverability")
    bindings = authorization["bindings"]
    required_bindings = {
        "executable_source_commit": args.source_commit,
        "production_image": args.docker_image,
        "scientific_provenance_root": args.generation_provenance_root,
        "scientific_addendum": args.scientific_addendum_sha256,
        "operational_amendment": args.operational_amendment_sha256,
        "initial_checkpoint": args.initial_checkpoint_sha256,
    }
    actual_bindings = {
        "executable_source_commit": bindings["executable_source_commit"],
        "production_image": bindings["production_image"],
        "scientific_provenance_root": bindings["scientific_provenance_root"],
        "scientific_addendum": bindings["s3_exact_centerline_addendum_sha256"],
        "operational_amendment": bindings["a1r_operational_amendment_sha256"],
        "initial_checkpoint": bindings["initial_staging_checkpoint_sha256"],
    }
    if actual_bindings != required_bindings:
        raise ContinuationError("authorization scientific/operational binding mismatch")

    run = canonical_artifact(
        args.run_identity, "phase9g_a1c_continuation_run_identity_sha256"
    )
    if run["phase9g_a1c_continuation_run_identity_sha256"] != args.run_identity_sha256:
        raise ContinuationError("continuation run identity CLI hash mismatch")
    if run["authorization_continuation_sha256"] != args.authorization_continuation_sha256:
        raise ContinuationError("run identity does not bind authorization")
    if run["same_staging_namespace_as_parent"] is not True:
        raise ContinuationError("continuation does not preserve STAGING lineage")

    scope = canonical_artifact(
        args.authorization_scope, "phase9_authorization_scope_sha256"
    )
    if scope["phase9_authorization_scope_sha256"] != args.authorization_scope_sha256:
        raise ContinuationError("authorization scope CLI hash mismatch")
    execution_authorized = validate_authorization_scope(
        {key: value for key, value in scope.items()
         if key != "phase9_authorization_scope_sha256"},
        study="study_a_zero_shot",
        split="train",
        branch="recoverability",
        source_commit=args.source_commit,
        docker_image=args.docker_image,
        addendum_sha256=args.scientific_addendum_sha256,
        provenance_root=args.generation_provenance_root,
    )
    if not execution_authorized:
        raise ContinuationError("frozen authorization scope rejected execution")

    checkpoint = canonical_artifact(
        args.initial_checkpoint, "phase9_s3_staging_checkpoint_sha256"
    )
    if checkpoint["phase9_s3_staging_checkpoint_sha256"] != args.initial_checkpoint_sha256:
        raise ContinuationError("initial checkpoint CLI hash mismatch")
    checkpoint_ids = validate_exact_checkpoint(args.writer_root, checkpoint)

    guard = canonical_artifact(
        args.s3_prestart_guard, "phase9g_a1c_s3_prestart_guard_sha256"
    )
    if guard["phase9g_a1c_s3_prestart_guard_sha256"] != args.s3_prestart_guard_sha256:
        raise ContinuationError("S3 guard CLI hash mismatch")
    if (
        guard["status"] != "PASS"
        or guard["counter_levels"]["unresolved_s3_ambiguities"] != 0
        or guard["scope"]["checkpoint_sha256"] != args.initial_checkpoint_sha256
    ):
        raise ContinuationError("S3 population guard did not pass")

    tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="train"
    )
    completed = completed_event_ids(args.writer_root, tasks)
    if completed != checkpoint_ids:
        raise ContinuationError("completed identity set changed after checkpoint validation")
    pending = unresolved_tasks(tasks, completed)
    if len(tasks) != 6000 or len(completed) != 210 or len(pending) != 5790:
        raise ContinuationError("A1C resume boundary differs from authorization")

    resolution = {
        "schema_version": "rvt-phase9g-a1c-train-continuation-resolution/v1",
        "run_id": run["run_id"],
        "parent_run_id": run["parent_run_id"],
        "study": "study_a_zero_shot",
        "split": "train",
        "branch": "recoverability",
        "mode": "RESOLVE_ONLY" if args.resolve_only else OFFICIAL_STAGING,
        "total_event_identities": len(tasks),
        "completed_event_identities_reused": len(completed),
        "unresolved_event_identities_scheduled": len(pending),
        "initial_scientific_rows_reused": 342,
        "existing_rows_reemitted": 0,
        "scientific_retry_count": 0,
        "job_manifest_sha256": JOB_MANIFEST_SHA256,
        "initial_checkpoint_sha256": args.initial_checkpoint_sha256,
        "s3_prestart_guard_sha256": args.s3_prestart_guard_sha256,
        "s3_counter_levels": guard["counter_levels"],
        "workers": args.workers,
        "numeric_threads": args.numeric_threads,
        "chunk_size_atomic_units": args.chunk_size,
        "infrastructure_timeout_seconds": args.infrastructure_timeout_seconds,
        "authorization_continuation_sha256": args.authorization_continuation_sha256,
        "run_identity_sha256": args.run_identity_sha256,
        "official_generation_execution_authorized": execution_authorized,
        "sealed_scope": run["sealed_scope"],
    }
    if args.resolve_only:
        print(json.dumps(resolution, sort_keys=True))
        return

    args.audit_root.mkdir(parents=True, exist_ok=True)
    telemetry_path = args.audit_root / "train-operational-telemetry.jsonl"
    status_path = args.audit_root / "train-continuation-status.json"
    if telemetry_path.exists() or status_path.exists():
        raise ContinuationError("A1C audit output already exists")
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
    hash_field = "phase9g_a1c_continuation_status_sha256"
    _atomic_write(status_path, status, hash_field)
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
        status_hash_field=hash_field,
    )
    status.update({
        "state": "COMPLETE",
        "execution_summary": execution,
        "updated_at_utc": _timestamp(),
    })
    _atomic_write(status_path, status, hash_field)
    resolution["execution_summary"] = execution
    print(json.dumps(resolution, sort_keys=True))


if __name__ == "__main__":
    main()
