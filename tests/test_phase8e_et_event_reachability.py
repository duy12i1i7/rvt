"""ET-15 -- static reachability of every declared S0 diagnostic event.

Static geometry only: mission distance, v_max, landmark, sensing range and the
trigger definition. No simulator step is taken and no closed-loop transition
success is claimed.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase8e import event_timing
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG

ROOT = pathlib.Path("results/rvt_fd24")
AUDIT = json.loads((ROOT / "event_timing_static_audit_v1.json").read_text())
FAMILIES = tuple(f"F{i}" for i in range(1, 11))


def test_audit_covers_all_thirty_nonfinal_layouts_and_all_families() -> None:
    assert AUDIT["layouts_audited"] == 30
    assert {r["family_id"] for r in AUDIT["records"]} == set(FAMILIES)
    assert {r["split"] for r in AUDIT["records"]} == {"train", "validation"}


def test_no_simulator_step_was_executed_to_produce_the_audit() -> None:
    assert AUDIT["simulator_steps_executed"] == 0
    assert AUDIT["specification_only"] is True


def test_every_declared_s0_event_is_statically_reachable_before_the_goal() -> None:
    assert AUDIT["unreachable_declared_events"] == []
    for record in AUDIT["records"]:
        for team_size, entry in record["by_team_size"].items():
            assert entry["all_declared_events_reachable"], (record["layout_id"], team_size)
            for event in entry["events"]:
                assert event["reachable_before_goal"], (record["layout_id"], event)


def test_every_trigger_precedes_the_minimum_unconstrained_traverse_time() -> None:
    """The defect this addendum repairs: triggers must not sit past the mission."""
    for record in AUDIT["records"]:
        limit = record["minimum_unconstrained_traverse_seconds"]
        for entry in record["by_team_size"].values():
            for event in entry["events"]:
                assert event["trigger_lower_bound_seconds"] <= limit, (
                    record["layout_id"], event)


def test_superseded_horizon_fraction_triggers_would_have_been_unreachable() -> None:
    """Non-vacuity: the old contract really did fail this test."""
    superseded_first_event_fraction = {
        "F2": 0.20, "F3": 0.20, "F4": 0.20, "F5": 0.15, "F6": 0.50,
        "F7": 0.33, "F8": 0.20, "F9": 0.33, "F10": 0.40,
    }
    failures = 0
    for record in AUDIT["records"]:
        fraction = superseded_first_event_fraction.get(record["family_id"])
        if fraction is None:
            continue
        old_trigger_seconds = fraction * record["episode_horizon_seconds"]
        if old_trigger_seconds > record["minimum_unconstrained_traverse_seconds"]:
            failures += 1
    assert failures > 0, "the superseded contract must actually fail this check"


def test_all_qualified_team_sizes_are_audited() -> None:
    for record in AUDIT["records"]:
        assert sorted(int(k) for k in record["by_team_size"]) == [5, 6, 8, 12, 16, 24]


def test_no_event_families_are_supported_and_declared() -> None:
    """F1 declares no topology event; its circles are geometrically unobservable."""
    f1 = [r for r in AUDIT["records"] if r["family_id"] == "F1"]
    assert f1
    for record in f1:
        for entry in record["by_team_size"].values():
            assert entry["no_event_family"] is True
            assert entry["events"] == []
            assert entry["declared_event_count"] == 0


def test_f1_circles_lie_beyond_the_frozen_obstacle_sensing_range() -> None:
    sensing = float(CONFIG.sensing.obstacle_sensing_range_meters)
    for record in AUDIT["records"]:
        if record["family_id"] != "F1":
            continue
        for landmark in record["landmarks"]:
            assert abs(landmark["lateral_meters"]) >= sensing, landmark


def test_f6_event_exists_and_encodes_no_headroom_or_global_outcome() -> None:
    """ET-11: the false bottleneck must still originate a local constriction,
    and that event must not assert that LINE is globally needed."""
    f6 = [r for r in AUDIT["records"] if r["family_id"] == "F6"]
    assert f6
    for record in f6:
        for entry in record["by_team_size"].values():
            assert len(entry["events"]) == 1
            event = entry["events"][0]
            assert event["event_type"] == event_timing.EVENT_CONSTRICTION
            assert event["reachable_before_goal"] is True
            blob = json.dumps(event).lower()
            assert "headroom" not in blob
            assert "bypass_available" not in blob
            assert "optimal" not in blob


def test_f10_infeasible_family_declares_a_constriction_and_no_opening() -> None:
    for record in AUDIT["records"]:
        if record["family_id"] != "F10":
            continue
        for entry in record["by_team_size"].values():
            kinds = [e["event_type"] for e in entry["events"]]
            assert kinds == [event_timing.EVENT_CONSTRICTION], kinds


def test_f7_neutral_clutter_keeps_its_declared_events() -> None:
    """ET-12: an event is not deleted merely because both candidates may succeed."""
    for record in AUDIT["records"]:
        if record["family_id"] != "F7":
            continue
        for entry in record["by_team_size"].values():
            assert entry["declared_event_count"] == 2
            assert len(entry["events"]) == 2
