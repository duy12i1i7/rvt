#!/usr/bin/env python3
"""Resolve the repeated timeout boundary from canonical task metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


RUN_ID = "phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
COMPACT = 5
LINE = 2


class TimeoutUnitError(RuntimeError):
    """The stopped executor boundary does not resolve to one canonical unit."""


def _bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _canonical(path: Path, field: str) -> tuple[Mapping[str, Any], str]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if _sha(body) != expected:
        raise TimeoutUnitError(f"canonical artifact mismatch: {path.name}")
    return document, expected


def _write(path: Path, body: Mapping[str, Any]) -> str:
    document = dict(body)
    digest = _sha(document)
    document["phase9g_a1r_timeout_unit_sha256"] = digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--staging-checkpoint", type=Path, required=True)
    parser.add_argument("--operational-stop", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    checkpoint, checkpoint_sha256 = _canonical(
        args.staging_checkpoint, "phase9g_a1r_staging_checkpoint_sha256"
    )
    stop, stop_sha256 = _canonical(
        args.operational_stop, "phase9g_a1_operational_stop_sha256"
    )
    manifest_path = root / "results/rvt_fd24/datasets/phase9_job_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest_body = dict(manifest)
    manifest_sha256 = str(manifest_body.pop("job_manifest_sha256", ""))
    if _sha(manifest_body) != manifest_sha256:
        raise TimeoutUnitError("job manifest hash mismatch")

    sources = {
        str(job["job_id"]): job
        for job in manifest["source_episode_jobs"]
        if job.get("study") == "study_a_zero_shot"
        and job.get("split") == "train"
        and not bool(job.get("sealed"))
    }
    ordered_events = [
        job
        for job in manifest["decision_event_jobs"]
        if str(job["source_episode_job_id"]) in sources
        and not bool(job.get("sealed"))
    ]
    durable = set(checkpoint["completed_event_ids"])
    durable_prefix_length = 0
    for event in ordered_events:
        if event["job_id"] not in durable:
            break
        durable_prefix_length += 1
    if durable_prefix_length != len(durable) or durable_prefix_length != 127:
        raise TimeoutUnitError("durable transactions are not the exact executor prefix")

    event = ordered_events[durable_prefix_length]
    event_id = str(event["job_id"])
    source = sources[str(event["source_episode_job_id"])]
    candidate_jobs = sorted(
        (
            job for job in manifest["candidate_replica_jobs"]
            if job["decision_event_job_id"] == event_id and not bool(job.get("sealed"))
        ),
        key=lambda item: (
            0 if int(item["candidate_topology"]) == COMPACT else 1,
            int(item["replica_index"]),
        ),
    )
    if [int(job["candidate_topology"]) for job in candidate_jobs] != [COMPACT, LINE]:
        raise TimeoutUnitError("candidate ordering or replica universe changed")
    compact_jobs = [
        job for job in candidate_jobs if int(job["candidate_topology"]) == COMPACT
    ]
    compact_unit_id = _sha({
        "event_id": event_id,
        "candidate_topology_id": COMPACT,
    })
    if compact_unit_id in checkpoint["completed_atomic_unit_ids"]:
        raise TimeoutUnitError("timed-out unit already appears completed")
    if any(
        item["decision_event_id"] == event_id
        for item in checkpoint["transaction_descriptors"]
    ):
        raise TimeoutUnitError("timed-out event unexpectedly has a durable transaction")

    attempt_boundaries = []
    for attempt in stop["attempts"]:
        if attempt["failure_class"] != "ProductionInfrastructureError":
            raise TimeoutUnitError("attempt did not stop at infrastructure timeout")
        attempt_boundaries.append({
            "attempt": attempt["attempt"],
            "durable_event_prefix_count_at_stop": durable_prefix_length,
            "next_ordered_event_id": event_id,
            "next_ordered_candidate_topology_id": COMPACT,
            "scientific_atomic_unit_id": compact_unit_id,
        })
    same_unit = len({item["scientific_atomic_unit_id"] for item in attempt_boundaries}) == 1
    if not same_unit:
        raise TimeoutUnitError("attempts resolve to different scientific units")

    report = {
        "schema_version": "rvt-phase9g-a1r-timeout-unit/v1",
        "status": "RESOLVED_FROM_CANONICAL_TASK_ORDER",
        "run_id": RUN_ID,
        "staging_checkpoint_sha256": checkpoint_sha256,
        "operational_stop_sha256": stop_sha256,
        "job_manifest_sha256": manifest_sha256,
        "executor_order_contract": (
            "decision-event manifest order; within each event COMPACT then LINE"
        ),
        "durable_event_prefix_count": durable_prefix_length,
        "timed_out_unit": {
            "study": source["study"],
            "split": source["split"],
            "family": source["family_id"],
            "layout_id": source["layout_id"],
            "layout_sha256": source["layout_sha256"],
            "team_size": source["team_size"],
            "episode_id": source["job_id"],
            "episode_index": source["episode_index"],
            "source_class": source["source_class"],
            "source_seeds": source["seeds"],
            "episode_horizon_seconds": source["episode_horizon_seconds"],
            "decision_event_id": event_id,
            "event_slot_index": event["event_slot_index"],
            "decision_timestep": event["resolved_control_step"],
            "decision_timestamp_seconds": event["resolved_timestamp_seconds"],
            "candidate_topology_id": COMPACT,
            "candidate_topology_name": "COMPACT",
            "replica_identities": [job["job_id"] for job in compact_jobs],
            "replica_indices": [job["replica_index"] for job in compact_jobs],
            "matched_disturbance_seed_identities": [
                job["seeds"]["matched_disturbance_seed"] for job in compact_jobs
            ],
            "scientific_atomic_unit_id": compact_unit_id,
        },
        "attempt_boundaries": attempt_boundaries,
        "both_timeouts_same_scientific_atomic_unit": same_unit,
        "timeout_scientific_effect_audit": {
            "VALID_TASK_NEGATIVE_created": False,
            "GENERATION_INVALID_created": False,
            "scientific_training_row_created": False,
            "candidate_aggregate_modified": False,
            "partial_candidate_pair_rows_created": False,
            "scientific_state": "UNRESOLVED",
        },
        "evidence_method": {
            "canonical_task_metadata_used": True,
            "log_text_used_to_select_identity": False,
            "traceback_used_only_to_confirm_infrastructure_failure_class": True,
        },
        "sealed_domains": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "training_operations": 0,
        },
    }
    digest = _write(args.output, report)
    print(json.dumps({
        "status": report["status"],
        "event_id": event_id,
        "candidate": "COMPACT",
        "atomic_unit_id": compact_unit_id,
        "same_unit": same_unit,
        "sha256": digest,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
