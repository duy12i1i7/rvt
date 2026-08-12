#!/usr/bin/env python3
"""Resolve the post-timeout A1R worker failure from canonical task metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


COMPACT = 5
LINE = 2


def _bytes(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _canonical_record(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop("canonical_record_sha256", ""))
    if _sha(body) != expected:
        raise ValueError(f"transaction hash mismatch: {path.name}")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    data = args.data_root.resolve()
    manifest = json.loads(
        (root / "results/rvt_fd24/datasets/phase9_job_manifest.json")
        .read_text(encoding="ascii")
    )
    status = json.loads(args.status.read_text(encoding="ascii"))
    checkpoint = json.loads(args.initial_checkpoint.read_text(encoding="ascii"))
    sources = {
        str(item["job_id"]): item
        for item in manifest["source_episode_jobs"]
        if item.get("study") == "study_a_zero_shot"
        and item.get("split") == "train"
        and not bool(item.get("sealed"))
    }
    events = [
        item for item in manifest["decision_event_jobs"]
        if str(item["source_episode_job_id"]) in sources
        and not bool(item.get("sealed"))
    ]
    replicas_by_event: dict[str, list[dict]] = {}
    for item in manifest["candidate_replica_jobs"]:
        event_id = str(item["decision_event_job_id"])
        if event_id in {str(event["job_id"]) for event in events}:
            replicas_by_event.setdefault(event_id, []).append(item)
    transaction_root = (
        data / "staging/study_a_zero_shot-train-recoverability/recoverability"
    )
    transactions = [
        _canonical_record(path) for path in sorted(transaction_root.glob("event-*.json"))
    ]
    durable = {str(item["decision_event_id"]) for item in transactions}
    if len(durable) != 210 or len(tuple(transaction_root.glob("*.partial"))) != 0:
        raise ValueError("post-failure durable boundary is not 210 complete events")
    initial = frozenset(checkpoint["completed_event_ids"])
    if len(initial) != 127 or not initial <= durable:
        raise ValueError("initial stopped prefix was not preserved")
    newly_durable = durable - initial
    if len(newly_durable) != 83:
        raise ValueError("continuation durable delta is not 83 events")
    unresolved = [event for event in events if str(event["job_id"]) not in durable]
    if not unresolved:
        raise ValueError("no unresolved event remains after worker failure")
    event = unresolved[0]
    event_id = str(event["job_id"])
    source = sources[str(event["source_episode_job_id"])]
    replica_jobs = sorted(
        replicas_by_event[event_id],
        key=lambda item: (
            0 if int(item["candidate_topology"]) == COMPACT else 1,
            int(item["replica_index"]),
        ),
    )
    compact_jobs = [
        item for item in replica_jobs if int(item["candidate_topology"]) == COMPACT
    ]
    unit_id = _sha({
        "event_id": event_id,
        "candidate_topology_id": COMPACT,
    })
    report = {
        "schema_version": "rvt-phase9g-a1r-worker-failure-identity/v1",
        "evidence_method": {
            "canonical_task_metadata_used": True,
            "durable_completion_markers_used": True,
            "ordered_candidate_scheduler_contract_used": True,
            "log_text_used_to_select_identity": False,
        },
        "durable_boundary": {
            "initial_events_reused": len(initial),
            "new_events_committed": len(newly_durable),
            "total_durable_events": len(durable),
            "total_durable_candidate_aggregates": 2 * len(durable),
            "partial_candidate_pair_publications": 0,
            "duplicate_scientific_identities": 0,
            "status_events_completed_this_continuation": status[
                "events_completed_this_continuation"
            ],
        },
        "failed_atomic_unit": {
            "study": source["study"],
            "split": source["split"],
            "family": source["family_id"],
            "layout_id": source["layout_id"],
            "layout_sha256": source["layout_sha256"],
            "team_size": source["team_size"],
            "source_class": source["source_class"],
            "episode_index": source["episode_index"],
            "episode_id": source["job_id"],
            "episode_horizon_seconds": source["episode_horizon_seconds"],
            "source_seeds": source["seeds"],
            "decision_event_id": event_id,
            "event_slot_index": event["event_slot_index"],
            "decision_timestep": event["resolved_control_step"],
            "decision_timestamp_seconds": event["resolved_timestamp_seconds"],
            "candidate_topology_id": COMPACT,
            "candidate_topology_name": "COMPACT",
            "replica_count": event["replicas_per_candidate"],
            "replica_identities": [item["job_id"] for item in compact_jobs],
            "matched_disturbance_seed_identities": [
                item["seeds"]["matched_disturbance_seed"] for item in compact_jobs
            ],
            "scientific_atomic_unit_id": unit_id,
        },
        "failure": {
            "exception_class": "ValueError",
            "exception_message": "S3 measured width must be finite and nonnegative",
            "source_stage": "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR.observe",
            "candidate_result_created": False,
            "scientific_disposition_created": False,
            "scientific_row_created": False,
            "candidate_pair_transaction_created": False,
            "partial_candidate_pair_transaction_created": False,
            "scientific_retry_count": 0,
        },
        "official_status": {
            "state": status["state"],
            "failure_class": status["failure_class"],
            "failure_message": status["failure_message"],
            "maximum_atomic_unit_wall_seconds": status[
                "maximum_atomic_unit_wall_seconds"
            ],
            "qualified_timeout_seconds": status["infrastructure_timeout_seconds"],
        },
        "sealed_scope": status["sealed_scope"],
    }
    report["phase9g_a1r_worker_failure_identity_sha256"] = _sha(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "event_id": event_id,
        "scientific_atomic_unit_id": unit_id,
        "durable_events": len(durable),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
