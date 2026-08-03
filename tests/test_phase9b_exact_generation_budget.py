"""Exact Phase 9B totals are derived from approved layouts and cells."""

import json
from pathlib import Path

from rvt_swarm.phase9b.budget import (
    DATASET_BUDGETS,
    build_generation_budget_manifest,
    derive_dataset_totals,
)


ROOT = Path(__file__).resolve().parents[1]


def test_exact_dataset_and_aggregate_totals_reproduce():
    manifest = build_generation_budget_manifest(ROOT)
    assert manifest["exact_total_budget"] == {
        "source_episodes": 3120,
        "decision_events": 15300,
        "candidate_replica_rollouts": 42840,
        "recoverability_robot_candidate_records": 332900,
        "dense_residual_action_records": 536000,
    }
    for spec, stored in zip(DATASET_BUDGETS, manifest["datasets"]):
        assert derive_dataset_totals(ROOT, spec) == stored["derived_totals"]


def test_committed_budget_artifact_is_the_deterministic_builder_output():
    stored = json.loads(
        (ROOT / "results/rvt_fd24/datasets/generation_budget_v1.json").read_text(
            encoding="ascii"
        )
    )
    assert stored == build_generation_budget_manifest(ROOT)


def test_per_dataset_exact_counts_are_frozen():
    by_id = {
        item["dataset_id"]: item["derived_totals"]
        for item in build_generation_budget_manifest(ROOT)["datasets"]
    }
    assert by_id["study_a_train"]["source_episodes"] == 1200
    assert by_id["study_a_n24_evaluation"]["decision_events"] == 300
    assert by_id["study_b_train"]["recoverability_robot_candidate_records"] == 142000
    assert by_id["study_b_validation"]["dense_residual_action_records"] == 48000
