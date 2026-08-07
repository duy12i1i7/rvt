from __future__ import annotations

import json
from pathlib import Path

import pytest

from rvt_swarm.phase8e.compiler import dynamic_obstacle_state


ROOT = Path(__file__).resolve().parents[1]


def _obstacle() -> dict:
    record = json.loads((
        ROOT / "results/rvt_fd24/layout_execution_specifications/train/train-f9-00.json"
    ).read_text(encoding="ascii"))
    return record["dynamic_obstacles"][0]


def test_waypoint_time_is_authoritative_and_declared_speed_is_audit_only() -> None:
    obstacle = _obstacle()
    segment = obstacle["segments"][0]
    assert segment["speed_meters_per_second"] == pytest.approx(5.0 / 12.0)
    assert obstacle["declared_speed_meters_per_second_audit_only"] == pytest.approx(0.15)
    assert segment["speed_meters_per_second"] != obstacle["declared_speed_meters_per_second_audit_only"]


def test_dynamic_state_replay_is_exact_at_start_middle_and_after_end() -> None:
    obstacle = _obstacle()
    assert dynamic_obstacle_state(obstacle, 0.0)["position_meters"] == [-0.5, -2.5]
    middle = dynamic_obstacle_state(obstacle, 6.0)
    assert middle["position_meters"] == pytest.approx([-0.5, 0.0])
    assert middle == dynamic_obstacle_state(obstacle, 6.0)
    end = dynamic_obstacle_state(obstacle, 30.0)
    assert end["position_meters"] == [-0.5, 2.5]
    assert end["velocity_meters_per_second"] == [0.0, 0.0]


def test_future_dynamic_path_is_not_robot_visible() -> None:
    assert _obstacle()["future_trajectory_robot_visible"] is False
