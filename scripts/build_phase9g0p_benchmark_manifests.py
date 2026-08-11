#!/usr/bin/env python3
"""Freeze Phase 9G0-P benchmark workloads before observing performance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import (
    JOB_MANIFEST_SHA256,
    compile_recoverability_tasks,
    compile_source_tasks,
)
from rvt_swarm.phase9g0r.producer import plan_residual_retained_states
from rvt_swarm.topology_registry import COMPACT, LINE


HANDOFF_COMMIT = "1676427c92d111c0aa7aebb2fe9e2cc035297605"
SCIENTIFIC_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
QUALIFIED_IMAGE = "sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c"


def _write(path: Path, body: Mapping[str, Any], field: str) -> str:
    document = attach_canonical_hash(dict(body), field)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(document[field])


def _recoverability_event(
    root: Path, family: str, team_size: int, source_class: str,
):
    return next(
        task
        for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train"
        )
        if task.source.family == family
        and task.source.team_size == team_size
        and task.source.source_class == source_class
        and task.source.episode_index == 0
        and task.event_slot_index == 0
    )


def _source(
    root: Path, family: str, team_size: int, source_class: str,
):
    return next(
        task
        for task in compile_source_tasks(
            root, study="study_a_zero_shot", split="train"
        )
        if task.family == family
        and task.team_size == team_size
        and task.source_class == source_class
        and task.episode_index == 0
    )


def build(root: Path) -> None:
    results = root / "results/rvt_fd24"
    recoverability_specs = (
        ("F1", 5, "S0_SCRIPTED_DIAGNOSTIC", ("positive coverage", "short continuation")),
        ("F1", 5, "S1_ALWAYS_COMPACT", ("fixed COMPACT source",)),
        ("F2", 8, "S0_SCRIPTED_DIAGNOSTIC", ("valid negative coverage", "long continuation")),
        ("F2", 8, "S1_ALWAYS_COMPACT", ("fixed COMPACT source",)),
        ("F5", 8, "S0_SCRIPTED_DIAGNOSTIC", ("changed topology",)),
        ("F5", 8, "S4_FROZEN_TRANSITION_PROTOCOL", ("transition source",)),
        ("F8", 12, "S0_SCRIPTED_DIAGNOSTIC", ("communication degraded", "three replicas")),
        ("F8", 12, "S1_ALWAYS_COMPACT", ("three replicas",)),
        ("F9", 16, "S0_SCRIPTED_DIAGNOSTIC", ("dynamic obstacle", "three replicas")),
        ("F9", 16, "S1_ALWAYS_COMPACT", ("three replicas",)),
        ("F10", 16, "S0_SCRIPTED_DIAGNOSTIC", ("additional family",)),
        ("F10", 16, "S4_FROZEN_TRANSITION_PROTOCOL", ("additional family", "transition source")),
    )
    events = []
    scheduler_units = []
    for family, team_size, source_class, coverage in recoverability_specs:
        task = _recoverability_event(root, family, team_size, source_class)
        events.append({
            "event_id": task.event_id,
            "source_job_id": task.source.job_id,
            "study": task.source.study,
            "split": task.source.split,
            "family": family,
            "team_size": team_size,
            "source_class": source_class,
            "event_slot_index": task.event_slot_index,
            "decision_timestep": task.resolved_control_step,
            "replicas_per_candidate": task.replicas_per_candidate,
            "candidate_pair_expected_rows": 2 * team_size,
            "coverage_intent": list(coverage),
        })
        for candidate in (COMPACT, LINE):
            identity = {
                "event_id": task.event_id,
                "candidate_topology_id": candidate,
                "replicas_per_candidate": task.replicas_per_candidate,
            }
            scheduler_units.append({
                "scheduler_atomic_unit_id": sha256_document(identity),
                **identity,
                "scientific_publication_boundary": task.event_id,
            })

    recoverability = {
        "schema_version": "rvt-phase9g0p-recoverability-benchmark-manifest/v1",
        "frozen_before_performance_observation": True,
        "handoff_commit": HANDOFF_COMMIT,
        "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
        "qualified_image_at_predeclaration": QUALIFIED_IMAGE,
        "job_manifest_sha256": JOB_MANIFEST_SHA256,
        "mode": "DIAGNOSTIC",
        "official_staging_writes": 0,
        "scheduler_atomic_unit": (
            "one source event x one candidate topology x all required replicas"
        ),
        "scientific_publication_unit": "one complete COMPACT/LINE event pair",
        "events": events,
        "scheduler_units": scheduler_units,
        "counts": {
            "events": len(events),
            "candidate_aggregates": len(scheduler_units),
            "replica_executions": sum(
                item["replicas_per_candidate"] for item in scheduler_units
            ),
            "prospective_robot_candidate_row_capacity": sum(
                item["candidate_pair_expected_rows"] for item in events
            ),
        },
        "coverage": {
            "families": sorted({item["family"] for item in events}),
            "team_sizes": sorted({item["team_size"] for item in events}),
            "contains_f8_f9_three_replica_aggregates": True,
            "contains_changed_topology_sources": True,
            "contains_prior_positive_and_valid_negative_coverage_cases": True,
            "selection_uses_timing_or_runtime_results": False,
        },
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "final_test_accesses": 0,
        },
    }
    recoverability_hash = _write(
        results / "phase9g0p_recoverability_benchmark_manifest_v1.json",
        recoverability,
        "phase9g0p_recoverability_benchmark_manifest_sha256",
    )

    residual_specs = (
        ("F1", 5, "S0_SCRIPTED_DIAGNOSTIC", {0: (0, 15), 4: (0, 15)},
         ("short and long retained positions",)),
        ("F2", 8, "S0_SCRIPTED_DIAGNOSTIC", {0: (0, 15), 7: (0, 15)},
         ("additional family",)),
        ("F5", 8, "S1_ALWAYS_COMPACT", {0: (0, 15), 3: (0, 7, 15)},
         ("LABELED and prior natural NO_ELIGIBLE_ACTION coverage",)),
        ("F8", 12, "S1_ALWAYS_COMPACT", {0: (0, 7, 15), 11: (0, 7, 15)},
         ("communication degraded", "tail coverage")),
        ("F9", 16, "S0_SCRIPTED_DIAGNOSTIC", {0: (0, 7, 15), 15: (0, 7, 15)},
         ("dynamic obstacle", "tail coverage")),
    )
    residual_units = []
    source_episodes = []
    for family, team_size, source_class, positions_by_robot, coverage in residual_specs:
        task = _source(root, family, team_size, source_class)
        retained = plan_residual_retained_states(root, task)
        source_episodes.append({
            "source_job_id": task.job_id,
            "family": family,
            "team_size": team_size,
            "source_class": source_class,
            "coverage_intent": list(coverage),
            "retention_k": 16,
        })
        for robot_id, retained_positions in positions_by_robot.items():
            timesteps = retained[robot_id]
            if len(timesteps) != 16:
                raise RuntimeError("benchmark source did not expose K=16 retained states")
            for retained_position in retained_positions:
                timestep = int(timesteps[retained_position])
                identity = {
                    "source_job_id": task.job_id,
                    "robot_id": robot_id,
                    "timestep": timestep,
                }
                residual_units.append({
                    "scheduler_atomic_unit_id": sha256_document(identity),
                    **identity,
                    "family": family,
                    "team_size": team_size,
                    "source_class": source_class,
                    "retained_position": retained_position,
                    "candidate_evaluations": 9,
                })

    residual = {
        "schema_version": "rvt-phase9g0p-residual-benchmark-manifest/v1",
        "frozen_before_performance_observation": True,
        "handoff_commit": HANDOFF_COMMIT,
        "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
        "qualified_image_at_predeclaration": QUALIFIED_IMAGE,
        "job_manifest_sha256": JOB_MANIFEST_SHA256,
        "mode": "DIAGNOSTIC",
        "official_staging_writes": 0,
        "scheduler_atomic_unit": (
            "one retained robot decision state x all nine residual candidates"
        ),
        "source_episodes": source_episodes,
        "scheduler_units": residual_units,
        "counts": {
            "source_episodes": len(source_episodes),
            "retained_state_units": len(residual_units),
            "candidate_evaluations": 9 * len(residual_units),
        },
        "coverage": {
            "families": sorted({item["family"] for item in residual_units}),
            "team_sizes": sorted({item["team_size"] for item in residual_units}),
            "retained_positions": sorted({
                item["retained_position"] for item in residual_units
            }),
            "contains_dynamic_obstacle": True,
            "contains_communication_degraded": True,
            "contains_prior_labeled_and_no_eligible_coverage": True,
            "selection_uses_timing_or_candidate_utilities": False,
        },
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "final_test_accesses": 0,
        },
    }
    residual_hash = _write(
        results / "phase9g0p_residual_benchmark_manifest_v1.json",
        residual,
        "phase9g0p_residual_benchmark_manifest_sha256",
    )

    root_manifest = {
        "schema_version": "rvt-phase9g0p-production-benchmark-manifest-root/v1",
        "frozen_before_performance_observation": True,
        "recoverability_manifest_sha256": recoverability_hash,
        "residual_manifest_sha256": residual_hash,
        "manifest_creation_uses_performance_results": False,
        "official_scientific_data_generated": False,
        "study_a_n24_accesses": 0,
        "final_test_accesses": 0,
    }
    root_hash = _write(
        results / "phase9g0p_production_benchmark_manifest_root_v1.json",
        root_manifest,
        "phase9g0p_production_benchmark_manifest_root_sha256",
    )
    print(json.dumps({
        "recoverability": recoverability_hash,
        "residual": residual_hash,
        "root": root_hash,
        "recoverability_units": len(scheduler_units),
        "residual_units": len(residual_units),
    }, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    build(args.root.resolve())


if __name__ == "__main__":
    main()
