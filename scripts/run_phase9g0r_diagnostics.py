#!/usr/bin/env python3
"""Run Phase 9G0-R diagnostics without an official staging write."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21p.audit import audit_rb20_semantic_replay
from rvt_swarm.phase9g0r.compiler import (
    compile_recoverability_tasks,
    compile_source_tasks,
    compile_task_summary,
    load_authoritative_job_manifest,
)
from rvt_swarm.phase9g0r.preflight import positive_preflight, run_negative_preflight
from rvt_swarm.phase9g0r.producer import (
    plan_residual_retained_states,
    produce_recoverability_event,
    produce_residual_state,
)
from rvt_swarm.phase9g0r.writer import DIAGNOSTIC, CanonicalGenerationWriter


ADDENDUM_SHA256 = "523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0"
EXECUTABLE_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"


def _write(path: Path, document: Mapping[str, Any], hash_field: str) -> None:
    payload = attach_canonical_hash(dict(document), hash_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


def _task(root: Path, family: str, team_size: int, source_class: str):
    return next(
        item
        for item in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train"
        )
        if item.source.family == family
        and item.source.team_size == team_size
        and item.source.source_class == source_class
        and item.source.episode_index == 0
        and item.event_slot_index == 0
    )


def structural_canary(root: Path) -> Mapping[str, Any]:
    specifications = (
        ("F1", 5),
        ("F2", 6),
        ("F5", 8),
        ("F8", 12),
        ("F9", 16),
        ("F10", 16),
    )
    recoverability = []
    aggregate_dispositions: Counter[str] = Counter()
    with tempfile.TemporaryDirectory(prefix="phase9g0r-diagnostic-canary-") as temp:
        writer = CanonicalGenerationWriter(Path(temp) / "diagnostic", mode=DIAGNOSTIC)
        for family, team_size in specifications:
            task = _task(root, family, team_size, "S0_SCRIPTED_DIAGNOSTIC")
            started = perf_counter()
            result = produce_recoverability_event(root, task, writer=writer)
            elapsed = perf_counter() - started
            reconciliation = result["reconciliation"]
            dispositions = reconciliation["audit_dispositions"]
            aggregate_dispositions.update(
                item["disposition"] for item in dispositions
            )
            recoverability.append({
                "event_id": task.event_id,
                "family": family,
                "team_size": team_size,
                "replicas_per_candidate": task.replicas_per_candidate,
                "candidate_aggregates": dispositions,
                "reconciliation_status": reconciliation["status"],
                "expected_rows": reconciliation["expected_row_count"],
                "prospective_rows": reconciliation["actual_row_count"],
                "two_n_exact": reconciliation["actual_row_count"] in (
                    0, 2 * team_size
                ),
                "scientific_row_ids": [
                    row["scientific_row_id"] for row in reconciliation["rows"]
                ],
                "diagnostic_writer_counter_delta": result["write"][
                    "official_counter_delta"
                ],
                "wall_seconds": elapsed,
            })

        labeled_task = _task(root, "F1", 5, "S0_SCRIPTED_DIAGNOSTIC").source
        labeled_plan = plan_residual_retained_states(root, labeled_task)
        started = perf_counter()
        labeled = produce_residual_state(
            root,
            labeled_task,
            robot_id=0,
            timestep=labeled_plan[0][0],
            source_commit=EXECUTABLE_SOURCE_COMMIT,
            scientific_addendum_sha256=ADDENDUM_SHA256,
            writer=writer,
        )
        labeled_seconds = perf_counter() - started

        noeligible_task = _task(root, "F5", 8, "S1_ALWAYS_COMPACT").source
        noeligible_plan = plan_residual_retained_states(root, noeligible_task)
        if 43 not in noeligible_plan[3]:
            raise RuntimeError("frozen diagnostic NO_ELIGIBLE_ACTION state was not retained")
        started = perf_counter()
        noeligible = produce_residual_state(
            root,
            noeligible_task,
            robot_id=3,
            timestep=43,
            source_commit=EXECUTABLE_SOURCE_COMMIT,
            scientific_addendum_sha256=ADDENDUM_SHA256,
            writer=writer,
        )
        noeligible_seconds = perf_counter() - started

    residual = [
        {
            "family": "F1",
            "team_size": 5,
            "robot_id": 0,
            "timestep": labeled_plan[0][0],
            "disposition": labeled["audit"]["disposition"],
            "candidate_evaluations": labeled["audit"]["candidate_evaluations"],
            "scientific_row_id": labeled["audit"]["scientific_row_id"],
            "diagnostic_writer_counter_delta": labeled["write"][
                "official_counter_delta"
            ],
            "wall_seconds": labeled_seconds,
        },
        {
            "family": "F5",
            "team_size": 8,
            "robot_id": 3,
            "timestep": 43,
            "disposition": noeligible["audit"]["disposition"],
            "candidate_evaluations": noeligible["audit"]["candidate_evaluations"],
            "scientific_row_id": noeligible["audit"]["scientific_row_id"],
            "diagnostic_writer_counter_delta": noeligible["write"][
                "official_counter_delta"
            ],
            "wall_seconds": noeligible_seconds,
        },
    ]
    if residual[0]["disposition"] != "LABELED":
        raise RuntimeError("structural canary did not produce a LABELED residual row")
    if residual[1]["disposition"] != "NO_ELIGIBLE_ACTION":
        raise RuntimeError("natural NO_ELIGIBLE_ACTION canary changed disposition")
    return {
        "schema_version": "rvt-phase9g0r-structural-canary/v1",
        "mode": DIAGNOSTIC,
        "source_commit": EXECUTABLE_SOURCE_COMMIT,
        "scientific_addendum_sha256": ADDENDUM_SHA256,
        "recoverability": recoverability,
        "residual": residual,
        "coverage": {
            "families": sorted({item["family"] for item in recoverability}),
            "team_sizes": sorted({item["team_size"] for item in recoverability}),
            "recoverable_positive_aggregates": aggregate_dispositions[
                "RECOVERABLE_POSITIVE"
            ],
            "valid_task_negative_aggregates": aggregate_dispositions[
                "VALID_TASK_NEGATIVE"
            ],
            "generation_invalid_aggregates": aggregate_dispositions[
                "GENERATION_INVALID"
            ],
            "f8_f9_three_replicas": all(
                item["replicas_per_candidate"] == 3
                for item in recoverability
                if item["family"] in {"F8", "F9"}
            ),
            "two_n_or_atomic_zero_for_every_event": all(
                item["two_n_exact"] for item in recoverability
            ),
            "residual_labeled": 1,
            "residual_no_eligible_action": 1,
        },
        "official_counters": {
            "official_run_ids": 0,
            "official_staging_writes": 0,
            "official_recoverability_rows": 0,
            "official_residual_rows": 0,
            "official_shards": 0,
        },
    }


def matched_randomness(root: Path) -> Mapping[str, Any]:
    manifest = load_authoritative_job_manifest(root)
    groups: dict[tuple[str, int], dict[int, int]] = defaultdict(dict)
    family_by_event = {
        str(item["job_id"]): str(item["family_id"])
        for item in manifest["decision_event_jobs"]
        if not bool(item.get("sealed"))
    }
    for job in manifest["candidate_replica_jobs"]:
        if bool(job.get("sealed")):
            continue
        key = (str(job["decision_event_job_id"]), int(job["replica_index"]))
        groups[key][int(job["candidate_topology"])] = int(
            job["seeds"]["matched_disturbance_seed"]
        )
    mismatch = sum(
        len(seeds) != 2 or len(set(seeds.values())) != 1
        for seeds in groups.values()
    )
    f8_f9: dict[str, set[int]] = defaultdict(set)
    for (event_id, _), seeds in groups.items():
        if family_by_event[event_id] in {"F8", "F9"}:
            f8_f9[event_id].add(next(iter(seeds.values())))
    distinct_failures = sum(len(values) != 3 for values in f8_f9.values())
    return {
        "schema_version": "rvt-phase9g0r-matched-randomness-regression/v1",
        "authority": "rvt_swarm.phase9c.manifest._replica_seeds",
        "comparison_groups": len(groups),
        "candidate_pair_seed_mismatches": mismatch,
        "f8_f9_events": len(f8_f9),
        "f8_f9_three_distinct_seed_failures": distinct_failures,
        "worker_chunk_retry_order_in_scientific_seed_payload": False,
        "status": "PASS" if mismatch == distinct_failures == 0 else "FAIL",
        "official_rows": 0,
        "sealed_accesses": 0,
    }


def rb20_replay(root: Path) -> Mapping[str, Any]:
    replay = audit_rb20_semantic_replay(root)
    counts = replay["counts"]
    expected = {
        "source_episodes": 4,
        "recoverability_rollouts": 14,
        "residual_candidate_evaluations": 36,
        "semantic_mismatches": 0,
        "scientific_identity_mismatches": 0,
    }
    if counts != expected:
        raise RuntimeError(f"RB20 semantic replay mismatch: {counts}")
    return {
        "schema_version": "rvt-phase9g0r-rb20-official-path-replay/v1",
        "historical_replay": replay,
        "new_producer_path_binding": {
            "recoverability_engine": "rvt_swarm.phase9c_rb.counterfactual.execute_candidate",
            "residual_engine": "rvt_swarm.phase9c_rb.residual_expert_v2.evaluate_residual_expert_v2",
            "official_entry_points": [
                "rvt_swarm.phase9g0r.producer.produce_recoverability_event",
                "rvt_swarm.phase9g0r.producer.produce_residual_state",
            ],
            "historical_identity_scope": "already-frozen RB20 identities",
            "prospective_recoverability_row_identity_scope": (
                "validated separately under rvt-recoverability-row-identity/v1"
            ),
        },
        "status": "PASS",
        "official_staging_writes": 0,
    }


def preflight(root: Path) -> Mapping[str, Any]:
    positive = positive_preflight(root)
    negative = run_negative_preflight(root)
    if positive["status"] != "PASS" or negative["escapes"] != 0:
        raise RuntimeError("Phase 9G0-R preflight did not pass")
    return {
        "schema_version": "rvt-phase9g0r-preflight/v1",
        "positive": positive,
        "negative": negative,
        "status": "PASS",
        "official_staging_writes": 0,
    }


def counts(root: Path) -> Mapping[str, Any]:
    compiled = compile_task_summary(root)
    equations = {
        "source_episodes": "count(nonsealed authorized source_episode_jobs)",
        "source_events": "count(nonsealed authorized decision_event_jobs)",
        "candidate_aggregates": "2 * source_events",
        "replica_executions": "sum(2 * replicas_per_candidate over source events)",
        "recoverability_robot_local_row_capacity": "sum(2 * N over source events)",
        "residual_eligible_dense_states": "measured only during authorized execution; not inferred from manifest",
        "residual_retained_attempted_states": "sum(min(16, eligible_count) per episode and robot)",
        "residual_candidate_evaluations": "9 * residual_retained_attempted_states",
        "residual_labeled_rows": "count(retained attempts with LABELED disposition)",
        "no_eligible_actions": "count(retained attempts with NO_ELIGIBLE_ACTION disposition)",
    }
    return {
        "schema_version": "rvt-phase9g0r-count-reconciliation/v1",
        "equations": equations,
        "manifest_level_counts": compiled,
        "runtime_only_counts": {
            "residual_eligible_dense_states": "NOT_EXECUTED_OFFICIAL_DATA_ZERO",
            "residual_retained_attempted_states": "NOT_EXECUTED_OFFICIAL_DATA_ZERO",
            "residual_labeled_rows": 0,
            "no_eligible_actions": 0,
        },
        "strict_residual_cap": 536000,
        "strict_upper_bound": compiled[
            "residual_retained_attempted_state_strict_upper_bound"
        ],
        "remaining_capacity": 536000 - compiled[
            "residual_retained_attempted_state_strict_upper_bound"
        ],
        "cap_pass": compiled[
            "residual_retained_attempted_state_strict_upper_bound"
        ] <= 536000,
    }


def performance(root: Path) -> Mapping[str, Any]:
    canary_path = root / "results/rvt_fd24/phase9g0r_structural_canary_v1.json"
    canary = json.loads(canary_path.read_text(encoding="ascii"))
    return {
        "schema_version": "rvt-phase9g0r-performance-classification/v1",
        "classification": "RB21_PRODUCTION_PATH_REQUALIFICATION_REQUIRED",
        "reason": (
            "The real producer adds F1-F10 task compilation, per-event 2*N row "
            "materialization, candidate-pair reconciliation, dense-state retention, "
            "and canonical publication units that were absent from the RB21 benchmark."
        ),
        "diagnostic_timing_only": {
            "recoverability_atomic_wall_seconds": [
                item["wall_seconds"] for item in canary["recoverability"]
            ],
            "residual_atomic_wall_seconds": [
                item["wall_seconds"] for item in canary["residual"]
            ],
        },
        "rb21_profile": {
            "workers": 12,
            "numeric_threads_per_worker": 1,
            "chunk_size": 1,
            "timeout_seconds": 1200,
            "authoritative_for_official_production": False,
        },
        "full_worker_scaling_executed": False,
        "scientific_semantics_changed": False,
        "official_staging_writes": 0,
    }


COMMANDS = {
    "canary": (
        structural_canary,
        "phase9g0r_structural_canary_v1.json",
        "phase9g0r_structural_canary_sha256",
    ),
    "matched-randomness": (
        matched_randomness,
        "phase9g0r_matched_randomness_regression_v1.json",
        "phase9g0r_matched_randomness_regression_sha256",
    ),
    "rb20-replay": (
        rb20_replay,
        "phase9g0r_rb20_official_path_replay_v1.json",
        "phase9g0r_rb20_official_path_replay_sha256",
    ),
    "preflight": (
        preflight,
        "phase9g0r_preflight_v1.json",
        "phase9g0r_preflight_sha256",
    ),
    "counts": (
        counts,
        "phase9g0r_count_reconciliation_v1.json",
        "phase9g0r_count_reconciliation_sha256",
    ),
    "performance": (
        performance,
        "phase9g0r_performance_classification_v1.json",
        "phase9g0r_performance_classification_sha256",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=tuple(COMMANDS))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    function, filename, hash_field = COMMANDS[args.command]
    output = root / "results/rvt_fd24" / filename
    _write(output, function(root), hash_field)
    print(output)


if __name__ == "__main__":
    main()
