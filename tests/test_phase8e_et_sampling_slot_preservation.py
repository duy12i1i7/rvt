"""ET-15 / ET-8 -- decision-state sampling slots are not source-policy event times."""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path("results/rvt_fd24")
ADDENDUM = json.loads((ROOT / "source_event_timing_addendum_v1.json").read_text())
MANIFEST = json.loads((ROOT / "datasets" / "phase9_job_manifest.json").read_text())

FROZEN_JOB_MANIFEST_SHA256 = (
    "801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3")


def test_job_manifest_hash_is_unchanged() -> None:
    assert MANIFEST["job_manifest_sha256"] == FROZEN_JOB_MANIFEST_SHA256


def test_planned_decision_event_slot_count_is_unchanged() -> None:
    assert len(MANIFEST["decision_event_jobs"]) == 15300
    assert ADDENDUM["event_slot_distinction"]["planned_decision_event_slots"] == 15300


def test_sampling_slot_schedules_are_unchanged() -> None:
    observed = sorted({job["scheduled_normalized_time"]
                       for job in MANIFEST["decision_event_jobs"]})
    for value in observed:
        assert value in set(ADDENDUM["event_slot_distinction"]["five_slot_episodes"]) | set(
            ADDENDUM["event_slot_distinction"]["four_slot_episodes"]), value


def test_five_and_four_slot_schedules_match_the_frozen_values() -> None:
    distinction = ADDENDUM["event_slot_distinction"]
    assert distinction["five_slot_episodes"] == [0.10, 0.30, 0.50, 0.70, 0.90]
    assert distinction["four_slot_episodes"] == [0.15, 0.40, 0.65, 0.90]
    assert distinction["modified_by_this_addendum"] is False


def test_sampling_slots_are_documented_as_distinct_from_event_times() -> None:
    statement = ADDENDUM["event_slot_distinction"]["statement"].lower()
    assert "sampling" in statement
    assert "not source-policy transition event times" in statement


def test_horizon_remains_a_timeout_and_evaluation_bound_only() -> None:
    semantics = ADDENDUM["horizon_semantics"]
    assert "timeout boundary" in semantics["roles"]
    assert "may not be the sole detector" in semantics["prohibited_use"]
