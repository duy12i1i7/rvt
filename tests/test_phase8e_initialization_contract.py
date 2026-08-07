from __future__ import annotations

import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.scenario import SUPPORTED_TEAM_SIZES
from rvt_swarm.phase8e.protocol import COMPACT, counter_uniform


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> dict:
    return json.loads(
        (ROOT / "results/rvt_fd24/executable_scientific_protocol_v1.json").read_text(
            encoding="ascii"
        )
    )


def test_initialization_has_one_explicit_source_for_every_state_group() -> None:
    contract = _protocol()["initialization_contract"]
    assert contract["initial_topology"]["required_layout_value"] == COMPACT
    assert contract["initial_topology"]["keep_status"] == "prohibited"
    assert contract["topology_origin_formula"] == "ScenarioLayout.start_center_meters"
    assert contract["message_queues"].startswith("empty")
    assert contract["dynamic_obstacle_phase"] == "absolute episode time zero"
    assert contract["invalidity_handling"].startswith("record one rejected")


def test_compiled_layouts_include_roles_for_every_supported_team_size() -> None:
    path = ROOT / "results/rvt_fd24/layout_execution_specifications/train/train-f1-00.json"
    record = json.loads(path.read_text(encoding="ascii"))
    assert set(record["initialization_by_team_size"]) == {str(size) for size in SUPPORTED_TEAM_SIZES}
    for size in SUPPORTED_TEAM_SIZES:
        assert len(record["initialization_by_team_size"][str(size)]["role_ids"]) == size


def test_counter_prf_is_deterministic_order_independent_and_bounded() -> None:
    first = counter_uniform(123, "initial_position", 4, "lateral")
    unrelated = counter_uniform(123, "initial_position", 1, "longitudinal")
    second = counter_uniform(123, "initial_position", 4, "lateral")
    assert unrelated != first
    assert first == second
    assert 0.0 <= first < 1.0
    with pytest.raises(ValueError):
        counter_uniform(-1, "initial_position", 0)
