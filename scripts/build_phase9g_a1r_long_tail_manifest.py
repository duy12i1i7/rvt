#!/usr/bin/env python3
"""Predeclare the authorized Phase 9G-A1R Recoverability long-tail set."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.topology_registry import COMPACT, LINE


SELECTIONS = (
    ("F2", "b0883e9e58df9dbae2deb41dfa9d7455e985ac80794fd89bac035ad0a1bef847",
     12, "S0_SCRIPTED_DIAGNOSTIC", 1, 2,
     ("exact_timed_out_structural_unit", "same_family_team_size")),
    ("F2", "b0883e9e58df9dbae2deb41dfa9d7455e985ac80794fd89bac035ad0a1bef847",
     12, "S0_SCRIPTED_DIAGNOSTIC", 0, 2,
     ("same_family_team_size", "matched_event_boundary_other_seed")),
    ("F5", "9a7cc9eed9e43489bcb5d743cb667713eddd43911c3d7ff036345502a78740f0",
     12, "S4_FROZEN_TRANSITION_PROTOCOL", 0, 4,
     ("changed_topology", "long_horizon", "late_event")),
    ("F8", "f8b97f208cd4a37403811d38476adfb87c1f111fbff30456e68012c41ac17254",
     12, "S0_SCRIPTED_DIAGNOSTIC", 0, 4,
     ("three_replicas", "long_horizon", "late_event")),
    ("F9", "24f67d947d0b71a8e386b7e84d1160ce70194704730f001530ba901a7bedccf4",
     16, "S0_SCRIPTED_DIAGNOSTIC", 0, 4,
     ("three_replicas", "dynamic_obstacle", "long_horizon", "late_event")),
    ("F9", "24f67d947d0b71a8e386b7e84d1160ce70194704730f001530ba901a7bedccf4",
     16, "S4_FROZEN_TRANSITION_PROTOCOL", 1, 4,
     ("three_replicas", "changed_topology", "long_horizon", "late_event")),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    tasks = compile_recoverability_tasks(
        root, study="study_a_zero_shot", split="train"
    )
    by_key = {
        (
            task.source.family,
            task.source.layout_sha256,
            task.source.team_size,
            task.source.source_class,
            task.source.episode_index,
            task.event_slot_index,
        ): task
        for task in tasks
    }
    events = []
    units = []
    for (family, layout_sha256, team_size, source_class, episode, slot,
         intent) in SELECTIONS:
        key = family, layout_sha256, team_size, source_class, episode, slot
        task = by_key.get(key)
        if task is None:
            raise ValueError(f"predeclared long-tail task is unavailable: {key}")
        event = {
            **asdict(task),
            "coverage_intent": list(intent),
            "source_job_id": task.source.job_id,
            "family": task.source.family,
            "team_size": task.source.team_size,
            "source_class": task.source.source_class,
            "episode_index": task.source.episode_index,
            "horizon_seconds": task.source.horizon_seconds,
            "decision_timestep": task.resolved_control_step,
        }
        events.append(event)
        for candidate in (COMPACT, LINE):
            units.append({
                "event_id": task.event_id,
                "candidate_topology_id": candidate,
                "replicas_per_candidate": task.replicas_per_candidate,
                "scheduler_atomic_unit_id": sha256_document({
                    "event_id": task.event_id,
                    "candidate_topology_id": candidate,
                }),
                "scientific_publication_boundary": task.event_id,
            })
    document = {
        "schema_version": "rvt-phase9g-a1r-long-tail-manifest/v1",
        "selection_key_fields": [
            "family", "layout_sha256", "team_size", "source_class",
            "episode_index", "event_slot_index",
        ],
        "mode": "NON_OFFICIAL_DIAGNOSTIC",
        "predeclared_before_measurement": True,
        "study": "study_a_zero_shot",
        "split": "train",
        "branch": "recoverability",
        "selection_rule": (
            "metadata-only structural coverage; no outcome or runtime from this "
            "set participated in selection"
        ),
        "event_count": len(events),
        "scheduler_atomic_unit_count": len(units),
        "candidate_pair_count": len(events),
        "workers_to_compare": [1, 12],
        "numeric_threads": 1,
        "chunk_size_atomic_units": 1,
        "diagnostic_profile_watchdog_seconds": 1800.0,
        "diagnostic_profile_watchdog_derivation": {
            "formula": "event_count * isolated_diagnostic_watchdog_seconds",
            "event_count": len(events),
            "isolated_diagnostic_watchdog_seconds": 300.0,
            "result_seconds": len(events) * 300.0,
            "production_authority": False,
        },
        "events": events,
        "scheduler_units": units,
        "official_staging_writes_permitted": 0,
        "production_image": (
            "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
        ),
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
    }
    document = attach_canonical_hash(
        document, "phase9g0p_recoverability_benchmark_manifest_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
