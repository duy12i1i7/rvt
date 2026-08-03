"""Dense quotas use deterministic target-neutral identity ranking."""

import inspect
from pathlib import Path

import pytest

from rvt_swarm.phase9b.budget import build_generation_budget_manifest
from rvt_swarm.phase9b.identity import DenseRecordIdentity, select_dense_records


ROOT = Path(__file__).resolve().parents[1]


def _records(count):
    return tuple(
        DenseRecordIdentity("episode-a", index, index % 4, 5 if index % 2 else 2, f"{index:064x}")
        for index in range(count)
    )


def test_dense_cell_quotas_reproduce_exact_dataset_totals():
    manifest = build_generation_budget_manifest(ROOT)
    for dataset in manifest["datasets"]:
        assert (
            dataset["derived_totals"]["cell_count"] * dataset["dense_records_per_cell"]
            == dataset["derived_totals"]["dense_residual_action_records"]
        )


def test_hash_ranking_is_input_order_independent_and_target_neutral():
    budget = build_generation_budget_manifest(ROOT)["generation_budget_sha256"]
    records = _records(12)
    first = select_dense_records(records, quota=5, cell_sha256="c" * 64, generation_budget_sha256=budget)
    second = select_dense_records(tuple(reversed(records)), quota=5, cell_sha256="c" * 64, generation_budget_sha256=budget)
    assert first == second
    source = inspect.getsource(select_dense_records)
    for prohibited in ("residual_magnitude", "expert_improvement", "label", "success"):
        assert prohibited not in source


def test_quota_shortfall_is_preserved_without_duplicates():
    budget = build_generation_budget_manifest(ROOT)["generation_budget_sha256"]
    selection = select_dense_records(_records(3), quota=8, cell_sha256="d" * 64, generation_budget_sha256=budget)
    assert len(selection.selected) == 3
    assert selection.shortfall == 5
    with pytest.raises(ValueError, match="duplicate dense"):
        select_dense_records(
            (_records(1)[0], _records(1)[0]),
            quota=2,
            cell_sha256="d" * 64,
            generation_budget_sha256=budget,
        )
