"""Normalized event slots map to physical control steps without replacement."""

from pathlib import Path

from rvt_swarm.phase9b.budget import SOURCE_CLASSES
from rvt_swarm.phase9b.identity import (
    build_dataset_cells,
    event_slot_count,
    map_event_slots,
)


ROOT = Path(__file__).resolve().parents[1]


def test_four_and_five_slot_schedules_are_exact_and_deterministic():
    four = map_event_slots(horizon_seconds=90.0, control_period_seconds=0.15, slot_count=4)
    five = map_event_slots(horizon_seconds=90.0, control_period_seconds=0.15, slot_count=5)
    assert [item.normalized_horizon_position for item in four] == [0.15, 0.40, 0.65, 0.90]
    assert [item.normalized_horizon_position for item in five] == [0.10, 0.30, 0.50, 0.70, 0.90]
    assert all(item.scheduled_timestamp_seconds >= item.requested_timestamp_seconds for item in five)


def test_early_termination_preserves_all_slots_and_marks_shortfall():
    slots = map_event_slots(
        horizon_seconds=90.0,
        control_period_seconds=0.15,
        slot_count=5,
        termination_step=200,
        termination_cause="source_goal_complete",
    )
    assert len(slots) == 5
    assert [item.available for item in slots] == [True, True, False, False, False]
    assert [item.slot_index for item in slots] == list(range(5))
    assert all(
        item.unavailable_reason == "source_goal_complete"
        for item in slots if not item.available
    )


def test_study_b_validation_has_one_rotating_five_slot_episode_per_cell():
    cells = build_dataset_cells(ROOT, "study_b_validation")
    for cell in cells:
        counts = [event_slot_count(cell, source) for source in SOURCE_CLASSES]
        assert counts.count(5) == 1
        assert counts.count(4) == 5
        assert sum(counts) == 25
