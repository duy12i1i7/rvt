#!/usr/bin/env python3
"""Predeclare the scoped A1S3Z Recoverability performance set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks


CASES = (
    (
        "NORMAL_S3",
        "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F1/"
        "c7696c20f835c039f775fafe343c87917c8b13c7bab6bc9af3d382b5869bfdb2/"
        "N8/S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR/episode-0/event-0",
    ),
    (
        "OLD_NEGATIVE_F3",
        "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F3/"
        "59dd0a284ff8482c2831245429ba843d4439d9ec6f8735696ae84e651d714dd1/"
        "N12/S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR/episode-0/event-0",
    ),
    (
        "OLD_NEGATIVE_F4",
        "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F4/"
        "27953c70b159a455745ecbe9acbc053a94c895c46d40e33dff8f18f2248a73ab/"
        "N5/S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR/episode-0/event-0",
    ),
    (
        "CENTERLINE_F6_TRAIN_00",
        "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F6/"
        "b63e08eeaacad624c27080a2468e751d06f2e2817a24242efab159864ce670c9/"
        "N16/S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR/episode-1/event-0",
    ),
    (
        "CENTERLINE_F6_TRAIN_01",
        "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F6/"
        "728cdce3394b2564ccdc1641d8ff2f9e6ade8cbdb6090eafbe9c2145847a7826/"
        "N16/S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR/episode-1/event-0",
    ),
    (
        "NON_S3_CONTROL",
        "rvt-generation-job-identity/v1/source_episode/study_a_zero_shot/train/F1/"
        "c7696c20f835c039f775fafe343c87917c8b13c7bab6bc9af3d382b5869bfdb2/"
        "N8/S1_ALWAYS_COMPACT/episode-0/event-0",
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    tasks = {
        task.event_id: task for task in compile_recoverability_tasks(
            root, study="study_a_zero_shot", split="train")
    }
    records = []
    for classification, event_id in CASES:
        task = tasks[event_id]
        records.append({
            "classification": classification,
            "decision_event_id": event_id,
            "family": task.source.family,
            "team_size": task.source.team_size,
            "source_class": task.source.source_class,
            "decision_timestep": task.resolved_control_step,
            "replicas_per_candidate": task.replicas_per_candidate,
            "candidate_topologies": [5, 6],
        })
    document = {
        "schema_version": "rvt-phase9-s3z-performance-manifest/v1",
        "phase": "PHASE_9G_A1S3Z",
        "predeclared_before_measurement": True,
        "scientific_scope": "Study A Recoverability TRAIN diagnostic only",
        "producer": "rvt_swarm.phase9g0r.producer.produce_recoverability_candidate",
        "profile": {
            "workers": 12,
            "numeric_threads_per_worker": 1,
            "chunk_size_atomic_units": 1,
            "infrastructure_timeout_seconds": 243,
        },
        "events": records,
        "event_count": len(records),
        "candidate_aggregate_count": 2 * len(records),
        "selection_balance": {
            "normal_s3": 1,
            "old_negative_f3_f4": 2,
            "new_centerline_f6_n16": 2,
            "non_s3_control": 1,
        },
        "writer_mode": "DIAGNOSTIC",
        "official_staging_mount": False,
        "residual_operations": 0,
        "sealed_scope": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "training_operations": 0,
        },
    }
    document = attach_canonical_hash(
        document, "phase9_s3z_performance_manifest_sha256")
    output = root / "results/rvt_fd24/phase9_s3z_performance_manifest_v1.json"
    output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(document["phase9_s3z_performance_manifest_sha256"])


if __name__ == "__main__":
    main()
