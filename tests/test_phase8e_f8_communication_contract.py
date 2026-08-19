from __future__ import annotations

import json
from pathlib import Path

from rvt_swarm.phase8e.compiler import compile_nonfinal_split
from rvt_swarm.phase8e.protocol import build_executable_protocol


ROOT = Path(__file__).resolve().parents[1]


def _f8_records() -> list[dict]:
    directory = ROOT / "results/rvt_fd24/layout_execution_specifications/train"
    # V2-era F8 layouts only; Phase 9G-V3X-Q added train-f8-02 additively.
    manifest = json.loads(
        (ROOT / "results/rvt_fd24/splits/train_layouts.json").read_text(
            encoding="ascii"))
    v2_era = {str(record["layout_id"]) for record in manifest["layout_records"]}
    return [json.loads(path.read_text(encoding="ascii"))
            for path in sorted(directory.glob("train-f8-*.json"))
            if path.stem in v2_era]


def test_f8_profiles_are_explicit_and_classified_before_execution() -> None:
    records = _f8_records()
    assert [item["communication"]["profile"] for item in records] == [
        "bounded_delay_loss", "temporary_disconnection_then_restore"
    ]
    assert records[0]["communication"]["assumption_class"] == "inside_method_assumptions"
    assert records[1]["communication"]["assumption_class"] == "explicit_assumption_violation_stress"


def test_temporary_cut_schedule_is_deterministic_and_scales_with_diameter() -> None:
    schedule = _f8_records()[1]["communication"]["team_size_schedule"]
    for team_size, item in schedule.items():
        n = int(team_size)
        assert item["duration_ticks"] == 2 * n
        assert item["partition_ordinal"] == (n + 1) // 2
        assert item["start_tick"] >= 0
    protocol = build_executable_protocol(ROOT)
    rebuilt = compile_nonfinal_split(ROOT, "train", protocol)
    rebuilt_f8 = [item for item in rebuilt if item["source_layout"]["family_id"] == "F8"][1]
    assert rebuilt_f8["communication"] == _f8_records()[1]["communication"]


def test_f8_message_freshness_and_stress_outcome_are_frozen() -> None:
    protocol = build_executable_protocol(ROOT)
    contract = protocol["communication_degradation_contract"]
    assert contract["freshness"]["stale_behavior"].startswith("exclude")
    stress = contract["temporary_disconnection_then_restore"]
    assert stress["outcome_treatment"].startswith("valid task-negative")
