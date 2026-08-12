#!/usr/bin/env python3
"""Audit and freeze a Phase 9G-A1 stop caused by repeated infrastructure timeout."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.contracts import recoverability_scientific_row_id
from rvt_swarm.topology_registry import COMPACT, LINE

from scripts.finalize_phase9g_a1_recoverability import (
    SPLITS,
    STUDY,
    _candidate_dispositions,
    _canonical,
    _event_file_map,
    _expected_universe,
)


class OperationalStopError(RuntimeError):
    """The stopped run evidence is incomplete or internally inconsistent."""


def _attempts(audit_root: Path) -> list[Mapping[str, Any]]:
    result = []
    for attempt_path in sorted((audit_root / "attempts").glob("train-attempt-*")):
        lifecycle, lifecycle_sha256 = _canonical(
            attempt_path / "lifecycle.json",
            "phase9g_a1_command_lifecycle_sha256",
        )
        stderr = (attempt_path / "stderr.log").read_text(
            encoding="ascii", errors="replace"
        )
        result.append({
            "attempt": attempt_path.name,
            "lifecycle_sha256": lifecycle_sha256,
            "state": lifecycle["state"],
            "exit_code": lifecycle["exit_code"],
            "started_at_utc": lifecycle["started_at_utc"],
            "completed_at_utc": lifecycle["completed_at_utc"],
            "wall_seconds": lifecycle["wall_seconds"],
            "infrastructure_timeout_count": stderr.lower().count(
                "exceeded infrastructure timeout"
            ),
            "failure_class": (
                "ProductionInfrastructureError"
                if "ProductionInfrastructureError" in stderr
                else "UNEXPECTED"
            ),
            "scientific_disposition_emitted_for_timeout": False,
        })
    if len(result) != 2:
        raise OperationalStopError("exactly two failed train attempts must be preserved")
    if any(
        item["state"] != "FAILED"
        or item["exit_code"] != 1
        or item["infrastructure_timeout_count"] != 1
        or item["failure_class"] != "ProductionInfrastructureError"
        for item in result
    ):
        raise OperationalStopError("attempt failure evidence is not the repeated timeout")
    return result


def audit_partial_staging(root: Path, data_root: Path) -> Mapping[str, Any]:
    expected = _expected_universe(root)
    observed = _event_file_map(data_root)
    expected_order = list(expected["events"])
    if not set(observed).issubset(expected["events"]):
        raise OperationalStopError("staging contains an unexpected decision event")
    if set(expected_order[: len(observed)]) != set(observed):
        raise OperationalStopError("durable transactions do not form the executor prefix")

    counters: Counter[str] = Counter()
    row_ids: set[str] = set()
    source_observed: dict[str, set[str]] = defaultdict(set)
    distribution: Counter[tuple[str, str, int, int, int]] = Counter()
    for event_id, (split, _, document) in observed.items():
        event = expected["events"][event_id]
        source_id = str(event["source_episode_job_id"])
        source = expected["sources"][source_id]
        team_size = int(source["team_size"])
        if split != source["split"] or team_size == 24:
            raise OperationalStopError("staging crossed a sealed scope")
        if not document["scientific_completion_marker"]:
            raise OperationalStopError("incomplete transaction became durable")
        actual_rows = int(document["actual_row_count"])
        if actual_rows not in (0, 2 * team_size) or actual_rows != len(
            document["rows"]
        ):
            raise OperationalStopError("partial candidate-pair rows were published")
        source_observed[source_id].add(event_id)
        counters["decision_events_completed"] += 1
        counters["candidate_aggregates_completed"] += 2
        candidates, replicas, retries, failures = _candidate_dispositions(document)
        counters["replica_executions_completed"] += replicas
        counters["candidate_internal_retries"] += retries
        counters["candidate_infrastructure_failure_attempts"] += failures
        if document["status"] == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID":
            if actual_rows != 0:
                raise OperationalStopError("invalid event emitted rows")
            counters["candidate_pair_invalid_events"] += 1
            counters["GENERATION_INVALID_aggregates"] += 2
        elif document["status"] == "SCIENTIFICALLY_RECONCILED_LABELABLE":
            if len(candidates) != 2 or actual_rows != 2 * team_size:
                raise OperationalStopError("labelable candidate pair is incomplete")
            counters["candidate_pair_valid_events"] += 1
            expected_seeds = expected["replica_jobs"][event_id]
            for candidate_id, candidate in candidates.items():
                disposition = candidate["aggregate"]["disposition"]
                counters[f"{disposition}_aggregates"] += 1
                actual_seeds = {
                    int(replica["replica_index"]): int(
                        replica["matched_disturbance_seed"]
                    )
                    for replica in candidate["replicas"]
                }
                if actual_seeds != expected_seeds[candidate_id]:
                    raise OperationalStopError("replica seeds differ from manifest")
            if expected_seeds[COMPACT] != expected_seeds[LINE]:
                raise OperationalStopError("COMPACT/LINE matched streams diverged")
            candidate_rows: Counter[int] = Counter()
            candidate_robots: dict[int, set[int]] = defaultdict(set)
            for row in document["rows"]:
                row_id = str(row["scientific_row_id"])
                if row_id in row_ids:
                    raise OperationalStopError("duplicate scientific row identity")
                row_ids.add(row_id)
                if recoverability_scientific_row_id(
                    row["scientific_identity"]
                ) != row_id:
                    raise OperationalStopError("scientific row ID hash mismatch")
                if sha256_document(row["graph_payload"]) != row["graph_fingerprint"]:
                    raise OperationalStopError("graph fingerprint mismatch")
                identity = row["scientific_identity"]
                candidate_id = int(row["candidate_topology_id"])
                candidate_rows[candidate_id] += 1
                candidate_robots[candidate_id].add(int(identity["robot_id"]))
                distribution[(
                    split,
                    str(identity["family"]),
                    team_size,
                    int(row["candidate_topology_id"]),
                    int(row["target_v4_aggregate_label"]),
                )] += 1
            if candidate_rows != Counter({COMPACT: team_size, LINE: team_size}):
                raise OperationalStopError("labelable event does not contain N+N rows")
            if any(
                robots != set(range(team_size))
                for robots in candidate_robots.values()
            ):
                raise OperationalStopError("candidate rows omit a robot role")
        else:
            raise OperationalStopError("unresolved infrastructure transaction is durable")
        counters["scientific_rows"] += actual_rows

    expected_by_source: dict[str, set[str]] = defaultdict(set)
    for event_id, event in expected["events"].items():
        expected_by_source[str(event["source_episode_job_id"])].add(event_id)
    completed_sources = sum(
        source_observed[source_id] == event_ids
        for source_id, event_ids in expected_by_source.items()
    )
    next_event_index = len(observed)
    next_event_id = expected_order[next_event_index]
    next_event = expected["events"][next_event_id]
    next_source = expected["sources"][str(next_event["source_episode_job_id"])]
    return {
        "expected": {
            "source_episodes": len(expected["sources"]),
            "decision_events": len(expected["events"]),
            "candidate_aggregates": 2 * len(expected["events"]),
            "replica_executions": sum(
                len(replicas)
                for candidates in expected["replica_jobs"].values()
                for replicas in candidates.values()
            ),
        },
        "observed": {
            **dict(counters),
            "source_episodes_completed": completed_sources,
            "duplicate_scientific_identities": 0,
            "partial_candidate_pair_publications": 0,
            "unresolved_durable_transactions": 0,
            "schema_failures": 0,
            "hash_failures": 0,
            "seal_violations": 0,
        },
        "next_incomplete_atomic_boundary": {
            "event_index": next_event_index,
            "decision_event_id": next_event_id,
            "family": next_source["family_id"],
            "team_size": next_source["team_size"],
            "source_class": next_source["source_class"],
            "episode_index": next_source["episode_index"],
            "event_slot_index": next_event["event_slot_index"],
            "resolved_control_step": next_event["resolved_control_step"],
            "candidate_topology_inferred_from_traceback": "COMPACT",
            "inference_basis": (
                "127 ordered event transactions were durable and the traceback stopped "
                "at compact = next(results) for the following event"
            ),
        },
        "row_distribution": [
            {
                "split": split,
                "family": family,
                "team_size": team_size,
                "candidate_topology_id": candidate,
                "label": label,
                "rows": count,
            }
            for (split, family, team_size, candidate, label), count in sorted(
                distribution.items()
            )
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    data_root = args.data_root.resolve()
    audit_root = data_root / "audit" / args.run_id
    authorization, authorization_sha256 = _canonical(
        data_root / "authorization/phase9g_a1_owner_authorization_v1.json",
        "phase9g_a1_owner_authorization_sha256",
    )
    run, run_sha256 = _canonical(
        data_root / "authorization/phase9g_a1_recoverability_run_identity_v1.json",
        "phase9g_a1_recoverability_run_identity_sha256",
    )
    activation, activation_sha256 = _canonical(
        data_root / "authorization/phase9g_a1_recoverability_command_activation_v1.json",
        "phase9g_a1_recoverability_command_activation_sha256",
    )
    attempts = _attempts(audit_root)
    partial = audit_partial_staging(root, data_root)
    final_progress, final_progress_sha256 = _canonical(
        audit_root / "attempts/train-attempt-002/progress.json",
        "phase9g_a1_progress_sha256",
    )
    sampled_cpu_core_seconds = float(
        final_progress["operational"]["cpu_core_seconds_sampled"]
    )
    staging_bytes = sum(
        path.stat().st_size
        for path in (data_root / "staging").rglob("*")
        if path.is_file()
    )
    body = {
        "schema_version": "rvt-phase9g-a1-operational-stop/v1",
        "phase": "PHASE_9G_A1",
        "status": "STOPPED_UNRESOLVED_OPERATIONAL_TIMEOUT",
        "verdict": "D",
        "verdict_text": (
            "Official Study A generation remains incomplete after the qualified "
            "60-second Recoverability infrastructure timeout repeated on exact resume."
        ),
        "authorization": {
            "artifact": "phase9g_a1_owner_authorization_v1.json",
            "sha256": authorization_sha256,
            "exact_scope": authorization["scope_status"],
        },
        "run_identity": {
            "run_id": args.run_id,
            "sha256": run_sha256,
            "scientific_row_identity_includes_run_id": False,
        },
        "command_activation_sha256": activation_sha256,
        "production_image": run["production_image"],
        "scientific_source_commit": run["scientific_source_commit"],
        "generation_provenance_root": run["generation_provenance_root"],
        "operational_profile": run["operational_profile"],
        "attempts": attempts,
        "attempt_count": len(attempts),
        "run_level_resume_count": 1,
        "infrastructure_timeouts": sum(
            item["infrastructure_timeout_count"] for item in attempts
        ),
        "unresolved_infrastructure_failures": 1,
        "partial_staging_audit": partial,
        "operational": {
            "wall_seconds": sum(float(item["wall_seconds"]) for item in attempts),
            "sampled_cpu_core_seconds": sampled_cpu_core_seconds,
            "sampled_cpu_hours": sampled_cpu_core_seconds / 3600.0,
            "final_progress_sha256": final_progress_sha256,
            "staging_storage_bytes": staging_bytes,
            "staging_sealed_read_only": True,
            "unexpected_duplicate_scientific_identities": 0,
            "expected_idempotent_replay_events_in_attempt_2": len(
                list(_event_file_map(data_root))
            ),
            "durable_duplicate_detection_count_unavailable_after_aborted_summary": True,
        },
        "branch_state": {
            "recoverability_train": "INCOMPLETE_OPERATIONAL_FAILURE",
            "recoverability_validation": "NOT_STARTED_HARD_GATE",
            "residual_train": "NOT_STARTED_RECOVERABILITY_HARD_GATE",
            "residual_validation": "NOT_STARTED_RECOVERABILITY_HARD_GATE",
        },
        "datasets": {
            "recoverability_finalized": False,
            "recoverability_dataset_manifest_sha256": None,
            "residual_finalized": False,
            "residual_dataset_manifest_sha256": None,
            "official_shards": 0,
            "official_indexes": 0,
        },
        "classification": {
            "new_scientific_specification_problem": False,
            "scientific_semantic_inconsistency": False,
            "dataset_integrity_inconsistency": False,
            "confirmed_operational_profile_failure": True,
            "failure_cause": (
                "qualified Recoverability executor/profile combination repeatedly "
                "exceeded its 60-second infrastructure timeout at the same frozen "
                "full-production atomic boundary"
            ),
        },
        "sealed_domains": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
        },
        "training": {
            "training_operations": 0,
            "checkpoints": 0,
            "optimizer_states": 0,
            "hp_trials": 0,
            "class_weighting": "NOT_SELECTED",
        },
        "required_next_action": (
            "separate owner-authorized operational requalification of the full "
            "Recoverability production atomic-unit latency envelope; do not reinterpret "
            "the timeout as science and do not start Residual"
        ),
    }
    document = attach_canonical_hash(body, "phase9g_a1_operational_stop_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": document["status"],
        "events": partial["observed"]["decision_events_completed"],
        "rows": partial["observed"]["scientific_rows"],
        "timeouts": document["infrastructure_timeouts"],
        "sha256": document["phase9g_a1_operational_stop_sha256"],
        "verdict": document["verdict"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
