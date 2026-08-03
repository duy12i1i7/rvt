"""Every dataset gives F1-F10 equal event budgets before labels exist."""

from pathlib import Path

from rvt_swarm.phase9b.budget import build_generation_budget_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_each_dataset_has_equal_family_event_counts():
    datasets = build_generation_budget_manifest(ROOT)["datasets"]
    expected = [600, 150, 30, 600, 150]
    for dataset, family_budget in zip(datasets, expected):
        counts = dataset["derived_totals"]["decision_events_by_family"]
        assert set(counts) == {f"F{index}" for index in range(1, 11)}
        assert set(counts.values()) == {family_budget}


def test_f8_f9_replica_rule_reproduces_rollout_totals():
    datasets = build_generation_budget_manifest(ROOT)["datasets"]
    for dataset in datasets:
        family = dataset["derived_totals"]["decision_events_by_family"]
        expected = sum(
            count * 2 * (3 if name in ("F8", "F9") else 1)
            for name, count in family.items()
        )
        assert dataset["derived_totals"]["candidate_replica_rollouts"] == expected
