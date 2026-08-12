#!/usr/bin/env python3
"""Bind the deterministic frozen-source stop found after A1R resume."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if _sha(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    results = args.results.resolve()
    identity = _canonical(
        results / "phase9g_a1r_worker_failure_identity_v1.json",
        "phase9g_a1r_worker_failure_identity_sha256",
    )
    plan = _canonical(
        results / "phase9g_a1r_worker_failure_diagnostic_plan_v1.json",
        "phase9g_a1r_worker_failure_diagnostic_plan_sha256",
    )
    stop = _canonical(
        results / "phase9g_a1r_continuation_stop_audit_v1.json",
        "phase9g_a1r_continuation_stop_audit_sha256",
    )
    replay_paths = sorted(
        (results / "phase9g_a1r_worker_failure_replays").glob("replay-*.json")
    )
    replays = [
        _canonical(path, "phase9g_a1r_worker_failure_diagnostic_replay_sha256")
        for path in replay_paths
    ]
    if len(replays) != 3:
        raise ValueError("exactly three diagnostic replays are required")

    expected_message = "S3 measured width must be finite and nonnegative"
    widths = {
        float(item["first_negative_measured_width_call"][
            "measured_width_meters"
        ])
        for item in replays
    }
    if widths != {-0.6143634774571596}:
        raise ValueError("diagnostic replays do not reproduce one exact width")
    if any(
        item["termination"]["exception_class"] != "ValueError"
        or item["termination"]["exception_message"] != expected_message
        or item["candidate_result_created"]
        or item["scientific_disposition_created"]
        or int(item["official_staging_writes"]) != 0
        for item in replays
    ):
        raise ValueError("diagnostic replay did not reproduce the clean stop")
    if [int(item["candidate_topology_id"]) for item in replays] != [5, 5, 2]:
        raise ValueError("diagnostic replay candidate coverage changed")
    failure = identity["failed_atomic_unit"]
    if stop["failure"]["failed_atomic_unit"] != failure:
        raise ValueError("stop audit and failure identity disagree")

    report = {
        "schema_version": "rvt-phase9g-a1r-frozen-source-stop/v1",
        "status": "CONFIRMED_FROZEN_SOURCE_EXCEPTION",
        "classification": "FROZEN_SCIENTIFIC_SOURCE_DEFECT",
        "official_failure": {
            "scientific_atomic_unit_id": failure["scientific_atomic_unit_id"],
            "decision_event_id": failure["decision_event_id"],
            "family": failure["family"],
            "layout_sha256": failure["layout_sha256"],
            "team_size": failure["team_size"],
            "source_class": failure["source_class"],
            "episode_index": failure["episode_index"],
            "event_slot_index": failure["event_slot_index"],
            "decision_timestep": failure["decision_timestep"],
            "decision_timestamp_seconds": failure[
                "decision_timestamp_seconds"
            ],
            "candidate_topology_id": failure["candidate_topology_id"],
            "matched_disturbance_seed_identities": failure[
                "matched_disturbance_seed_identities"
            ],
            "exception_class": "ValueError",
            "exception_message": expected_message,
        },
        "diagnostic_reproduction": {
            "predeclared_plan_sha256": plan[
                "phase9g_a1r_worker_failure_diagnostic_plan_sha256"
            ],
            "replay_count": len(replays),
            "candidate_topology_ids": [
                int(item["candidate_topology_id"]) for item in replays
            ],
            "measured_width_meters": next(iter(widths)),
            "exception_equal_across_replays": True,
            "candidate_independent_source_failure": True,
            "wall_seconds": [float(item["timing"]["wall_seconds"]) for item in replays],
            "replay_sha256": [
                item["phase9g_a1r_worker_failure_diagnostic_replay_sha256"]
                for item in replays
            ],
        },
        "scientific_effect": {
            "candidate_result_created": False,
            "scientific_disposition_created": False,
            "scientific_row_created": False,
            "candidate_pair_transaction_created": False,
            "partial_candidate_pair_transaction_created": False,
            "official_staging_writes_from_diagnostics": 0,
            "scientific_retry_count": 0,
        },
        "excluded_operational_causes": {
            "infrastructure_timeout": True,
            "worker_count_starvation": True,
            "writer_or_serialization_stall": True,
            "scheduler_cancellation": True,
            "candidate_specific_counterfactual": True,
        },
        "scope_decision": {
            "frozen_science_changed_in_phase9g_a1r": False,
            "automatic_scientific_repair_permitted": False,
            "official_recoverability_complete": False,
            "residual_started": False,
            "training_operations": 0,
        },
        "evidence_hashes": {
            "worker_failure_identity": identity[
                "phase9g_a1r_worker_failure_identity_sha256"
            ],
            "continuation_stop_audit": stop[
                "phase9g_a1r_continuation_stop_audit_sha256"
            ],
        },
        "sealed_scope": dict(stop["sealed_domains"]),
        "verdict": "A",
        "verdict_text": (
            "Recoverability continuation requires changing frozen science."
        ),
    }
    report["phase9g_a1r_frozen_source_stop_sha256"] = _sha(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(report["phase9g_a1r_frozen_source_stop_sha256"])


if __name__ == "__main__":
    main()
