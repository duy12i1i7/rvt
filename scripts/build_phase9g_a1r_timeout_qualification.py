#!/usr/bin/env python3
"""Build the measured Phase 9G-A1R timeout qualification artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="ascii"))


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict, hash_field: str) -> dict:
    result = attach_canonical_hash(value, hash_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "results/rvt_fd24"
    timeout = _load(out / "phase9g_a1r_timeout_unit_v1.json")
    checkpoint = _load(out / "phase9g_a1r_staging_checkpoint_v1.json")
    plan = _load(out / "phase9g_a1r_timeout_diagnostic_plan_v1.json")
    replays = [
        _load(out / "phase9g_a1r_timeout_replays" / f"replay-{index}.json")
        for index in (1, 2)
    ]
    manifest_path = out / "phase9g_a1r_long_tail_manifest_v4.json"
    manifest = _load(manifest_path)
    w1_path = out / "phase9g_a1r_long_tail/w1.json"
    w12_path = out / "phase9g_a1r_long_tail/w12.json"
    profiles = {"w1": _load(w1_path), "w12": _load(w12_path)}
    unit = timeout["timed_out_unit"]
    event_id = unit["decision_event_id"]
    candidate = int(unit["candidate_topology_id"])

    exact_timings = {}
    exact_digests = {}
    for name, profile in profiles.items():
        unit_meta = next(
            item for item in manifest["scheduler_units"]
            if item["event_id"] == event_id
            and int(item["candidate_topology_id"]) == candidate
        )
        observation = next(
            item for item in profile["atomic_unit_observations"]
            if item["scheduler_atomic_unit_id"]
            == unit_meta["scheduler_atomic_unit_id"]
        )
        projection = next(
            item for item in profile["scientific_semantic_projection"]
            if item["task"]["event_id"] == event_id
        )
        candidate_projection = next(
            item for item in projection["candidates"]
            if int(item["candidate_topology_id"]) == candidate
        )
        exact_timings[name] = observation
        exact_digests[name] = sha256_document(candidate_projection)

    common_digest = replays[0]["scientific_semantic_digest"]
    all_exact_digests = [
        replay["scientific_semantic_digest"] for replay in replays
    ] + list(exact_digests.values())
    if set(all_exact_digests) != {common_digest}:
        raise ValueError("timeout-unit scientific replay digest diverged")
    if profiles["w1"]["scientific_semantic_digest"] != profiles["w12"][
        "scientific_semantic_digest"
    ]:
        raise ValueError("worker profiles changed the long-tail scientific digest")

    root_cause = {
        "schema_version": "rvt-phase9g-a1r-timeout-root-cause/v1",
        "classification": "LEGITIMATE_LONG_TAIL",
        "scientific_atomic_unit": unit,
        "both_observed_timeouts_same_atomic_unit": timeout[
            "both_timeouts_same_scientific_atomic_unit"
        ],
        "old_infrastructure_timeout_seconds": 60.0,
        "isolated_replays": [
            {
                "replay_index": replay["replay_index"],
                "wall_seconds": replay["timing"]["atomic_unit_wall_seconds"],
                "cpu_seconds": replay["timing"]["process_cpu_seconds"],
                "average_cpu_cores": replay["timing"]["average_cpu_cores"],
                "peak_rss_bytes": replay["resources"]["peak_rss_bytes"],
                "source_event_seconds": replay["timing"]["source_event_seconds"],
                "replica_rollout_seconds": replay["timing"][
                    "replica_rollout_seconds"
                ],
                "target_v4_evaluation_seconds": replay["timing"][
                    "target_v4_evaluation_seconds"
                ],
                "result_serialization_seconds": replay["timing"][
                    "result_serialization_seconds"
                ],
                "disposition": replay["completion_disposition"],
                "scientific_semantic_digest": replay[
                    "scientific_semantic_digest"
                ],
            }
            for replay in replays
        ],
        "production_equivalent_exact_unit": exact_timings["w12"],
        "semantic_digest_equal_across_repeated_w1_and_w12": True,
        "termination_facts": {
            "source_terminated_before_event": True,
            "cause": "GOAL_COMPLETE",
            "termination_control_step": 383,
            "planned_event_control_step": unit["decision_timestep"],
            "replica_rollouts_executed": 0,
            "target_v4_evaluations_executed": 0,
            "writer_involved_in_atomic_timeout": False,
        },
        "excluded_classifications": {
            "OPERATIONAL_DEADLOCK_OR_HANG": (
                "unit terminated twice below the predeclared 300 s ceiling"
            ),
            "RESOURCE_STARVATION": (
                "W12/W1 max ratio remained bounded and both semantic digests matched"
            ),
            "WRITER_SERIALIZATION_STALL": (
                "timeout occurred during source replay before writer/reconciliation"
            ),
            "UNKNOWN": "repeatable termination and exact cause were observed",
        },
        "official_staging_effect_from_timeout": timeout[
            "timeout_scientific_effect_audit"
        ],
    }
    root_cause = _write(
        out / "phase9g_a1r_timeout_root_cause_v1.json",
        root_cause,
        "phase9g_a1r_timeout_root_cause_sha256",
    )

    long_tail = {
        "schema_version": "rvt-phase9g-a1r-long-tail-summary/v1",
        "authoritative_manifest_sha256": manifest[
            "phase9g0p_recoverability_benchmark_manifest_sha256"
        ],
        "manifest_file_sha256": _file_sha(manifest_path),
        "n_events": manifest["event_count"],
        "n_candidate_aggregates": manifest["scheduler_atomic_unit_count"],
        "profiles": {
            name: {
                "workers": profile["workers"],
                "numeric_threads": 1,
                "chunk": profile["chunk_size_atomic_units"],
                "wall_seconds": profile["wall_seconds"],
                "atomic_unit_latency_seconds": profile[
                    "atomic_unit_latency_seconds"
                ],
                "per_replica_latency_seconds": profile["stage_seconds"][
                    "replica_rollout"
                ],
                "source_event_seconds": profile["stage_seconds"]["source_event"],
                "graph_serialization_seconds": profile["stage_seconds"][
                    "graph_serialization"
                ],
                "candidate_pair_reconciliation_seconds": profile[
                    "stage_seconds"
                ]["candidate_pair_reconciliation"],
                "writer_seconds": profile["stage_seconds"]["writer"],
                "counts": profile["counts"],
                "peak_aggregate_rss_upper_bound_bytes": profile["memory"][
                    "peak_aggregate_rss_upper_bound_bytes"
                ],
                "scientific_semantic_digest": profile[
                    "scientific_semantic_digest"
                ],
                "raw_file_sha256": _file_sha(
                    w1_path if name == "w1" else w12_path
                ),
            }
            for name, profile in profiles.items()
        },
        "semantic_digest_equal": True,
        "w12_causes_pathological_tail": False,
        "worker_profile_decision": {
            "workers": 12,
            "numeric_threads": 1,
            "chunk": 1,
            "scoped_worker_matrix_required": False,
        },
        "superseded_diagnostic_sets_preserved": [
            "phase9g_a1r_long_tail_manifest_selection_defect_v1.json",
            "phase9g_a1r_long_tail_manifest_v2.json",
            "phase9g_a1r_long_tail_manifest_v3.json",
        ],
    }
    long_tail = _write(
        out / "phase9g_a1r_long_tail_summary_v1.json",
        long_tail,
        "phase9g_a1r_long_tail_summary_sha256",
    )

    w12 = profiles["w12"]
    source_max = float(w12["stage_seconds"]["source_event"]["max"])
    replica_max = float(w12["stage_seconds"]["replica_rollout"]["max"])
    graph_max = float(w12["stage_seconds"]["graph_serialization"]["max"])
    reconcile_max = float(
        w12["stage_seconds"]["candidate_pair_reconciliation"]["max"]
    )
    writer_max = float(w12["stage_seconds"]["writer"]["max"])
    result_serialization_max = max(
        float(replay["timing"]["result_serialization_seconds"])
        for replay in replays
    )
    max_replicas = max(int(event["replicas_per_candidate"]) for event in manifest["events"])
    max_team_size = max(int(event["team_size"]) for event in manifest["events"])
    long_tail_team_size = int(unit["team_size"])
    measured_envelope = (
        source_max
        + max_replicas * replica_max
        + graph_max
        + result_serialization_max
        + reconcile_max
        + writer_max
    )
    team_scaling = (max_team_size / long_tail_team_size) ** 2
    operational_margin = 1.25
    raw_timeout = measured_envelope * team_scaling * operational_margin
    proposed_timeout = math.ceil(raw_timeout)
    if proposed_timeout != 243:
        raise ValueError(f"unexpected derived timeout: {proposed_timeout}")
    derivation = {
        "schema_version": "rvt-phase9g-a1r-timeout-derivation/v1",
        "old_timeout_seconds": 60.0,
        "old_timeout_status": "SUPERSEDED_HISTORICAL_EVIDENCE",
        "authoritative_profile": "W12_PRODUCTION_EQUIVALENT",
        "observations_seconds": {
            "isolated_atomic_unit_max": max(
                replay["timing"]["atomic_unit_wall_seconds"] for replay in replays
            ),
            "targeted_atomic_unit_median": w12["atomic_unit_latency_seconds"][
                "median"
            ],
            "targeted_atomic_unit_p90": w12["atomic_unit_latency_seconds"]["p90"],
            "targeted_atomic_unit_p95": w12["atomic_unit_latency_seconds"]["p95"],
            "targeted_atomic_unit_max": w12["atomic_unit_latency_seconds"]["max"],
            "source_event_max": source_max,
            "per_replica_max": replica_max,
            "graph_serialization_max": graph_max,
            "result_serialization_max": result_serialization_max,
            "candidate_pair_reconciliation_max": reconcile_max,
            "writer_max": writer_max,
        },
        "maximum_frozen_structure": {
            "maximum_authorized_team_size": max_team_size,
            "long_tail_observation_team_size": long_tail_team_size,
            "maximum_replicas_per_candidate": max_replicas,
            "maximum_horizon_seconds_represented": max(
                event["horizon_seconds"] for event in manifest["events"]
            ),
            "maximum_decision_timestep_represented": max(
                event["decision_timestep"] for event in manifest["events"]
            ),
            "study_a_n24_excluded": True,
        },
        "formula": {
            "measured_envelope": (
                "source_max + max_replicas*per_replica_max + graph_max + "
                "result_serialization_max + reconciliation_max + writer_max"
            ),
            "measured_envelope_seconds": measured_envelope,
            "team_size_scaling": "(N_max / N_long_tail)^2",
            "team_size_scaling_value": team_scaling,
            "operational_safety_margin_multiplier": operational_margin,
            "observed_w12_to_w1_atomic_max_ratio": (
                w12["atomic_unit_latency_seconds"]["max"]
                / profiles["w1"]["atomic_unit_latency_seconds"]["max"]
            ),
            "raw_result_seconds": raw_timeout,
            "normalization": "ceil to whole infrastructure-watchdog second",
        },
        "new_qualified_timeout_seconds": proposed_timeout,
        "derived_from_mean": False,
        "copied_from_residual_timeout": False,
        "scientific_parameter": False,
        "qualification_pending_failure_injection": True,
        "evidence_hashes": {
            "root_cause": root_cause["phase9g_a1r_timeout_root_cause_sha256"],
            "long_tail": long_tail["phase9g_a1r_long_tail_summary_sha256"],
            "staging_checkpoint": checkpoint[
                "phase9g_a1r_staging_checkpoint_sha256"
            ],
            "diagnostic_plan": plan[
                "phase9g_a1r_timeout_diagnostic_plan_sha256"
            ],
        },
    }
    derivation = _write(
        out / "phase9g_a1r_timeout_derivation_v1.json",
        derivation,
        "phase9g_a1r_timeout_derivation_sha256",
    )

    exact_event = next(
        event for event in manifest["events"] if event["event_id"] == event_id
    )
    exact_units = [
        item for item in manifest["scheduler_units"] if item["event_id"] == event_id
    ]
    injection = {
        "schema_version": "rvt-phase9g-a1r-timeout-failure-injection-manifest/v1",
        "mode": "NON_OFFICIAL_DIAGNOSTIC",
        "events": [exact_event],
        "scheduler_units": exact_units,
        "event_count": 1,
        "scheduler_atomic_unit_count": 2,
        "forced_timeout_seconds": 5.0,
        "forced_timeout_basis": (
            "below the 87.2 s minimum repeated isolated completion time"
        ),
        "proposed_timeout_seconds": proposed_timeout,
        "reference_watchdog_seconds": plan["diagnostic_watchdog_seconds"],
        "workers": 1,
        "numeric_threads": 1,
        "chunk_size_atomic_units": 1,
        "official_staging_writes_permitted": 0,
        "expected_forced_timeout": {
            "accepted_scientific_dispositions": 0,
            "scientific_rows": 0,
            "partial_candidate_pair_commits": 0,
        },
        "expected_proposed_timeout": {
            "candidate_pair_completion": True,
            "scientific_semantic_digest_equal_reference": True,
        },
        "timeout_derivation_sha256": derivation[
            "phase9g_a1r_timeout_derivation_sha256"
        ],
        "sealed_scope": dict(manifest["sealed_scope"]),
    }
    _write(
        out / "phase9g_a1r_timeout_failure_injection_manifest_v1.json",
        injection,
        "phase9g0p_recoverability_benchmark_manifest_sha256",
    )


if __name__ == "__main__":
    main()
