"""Source trajectories follow the frozen six-class cell allocation."""

from collections import Counter
from pathlib import Path

from rvt_swarm.phase9b.budget import SOURCE_CLASSES
from rvt_swarm.phase9b.identity import (
    build_dataset_cells,
    source_episode_counts,
    source_episode_identities,
)


ROOT = Path(__file__).resolve().parents[1]


def test_study_a_source_counts_are_exact_per_cell():
    train = build_dataset_cells(ROOT, "study_a_train")
    validation = build_dataset_cells(ROOT, "study_a_validation")
    evaluation = build_dataset_cells(ROOT, "study_a_n24_evaluation")
    assert source_episode_counts(train[0], train) == (2, 2, 2, 2, 2, 2)
    assert source_episode_counts(validation[0], validation) == (1, 1, 1, 1, 1, 1)
    assert source_episode_counts(evaluation[0], evaluation) == (1, 1, 1, 1, 1, 1)


def test_study_b_train_rotation_is_globally_balanced():
    cells = build_dataset_cells(ROOT, "study_b_train")
    totals = Counter()
    for cell in cells:
        counts = source_episode_counts(cell, cells)
        assert sorted(counts) == [1, 1, 2, 2, 2, 2]
        totals.update(dict(zip(SOURCE_CLASSES, counts)))
    assert totals == Counter({source: 200 for source in SOURCE_CLASSES})


def test_source_episode_ids_are_unique_and_outcome_free():
    cells = build_dataset_cells(ROOT, "study_b_train")
    identities = source_episode_identities(cells[0], cells)
    ids = [item.job_id() for item in identities]
    assert len(ids) == 10
    assert len(set(ids)) == 10
    assert all("label" not in item and "outcome" not in item for item in ids)
