from __future__ import annotations

import json
from pathlib import Path

from rvt_swarm.phase8e.protocol import (
    OBSTACLE_REFERENCE_RADIUS_METERS,
    OBSTACLE_SURFACE_MARGIN_METERS,
    WORLD_BOUNDS_METERS,
)


ROOT = Path(__file__).resolve().parents[1]


def test_phase8e_declares_named_geometry_values_and_executes_zero_steps() -> None:
    protocol = json.loads((
        ROOT / "results/rvt_fd24/executable_scientific_protocol_v1.json"
    ).read_text(encoding="ascii"))
    assert protocol["scenario_geometry_contract"]["world_frame"]["bounds_meters"] == [
        list(WORLD_BOUNDS_METERS[0]), list(WORLD_BOUNDS_METERS[1])
    ]
    sensor = protocol["static_obstacle_contract"]["sensor_conversion"]
    assert sensor["support_disc_radius_meters"] == OBSTACLE_REFERENCE_RADIUS_METERS
    assert protocol["static_obstacle_contract"]["collision_inflation"][
        "obstacle_surface_margin_meters"
    ] == OBSTACLE_SURFACE_MARGIN_METERS
    assert protocol["simulator_semantics"]["simulator_steps_executed"] == 0
    assert protocol["simulator_semantics"]["runtime_binding_implemented"] is False


def test_phase8e_did_not_create_scientific_outputs_or_model_state() -> None:
    dataset_root = ROOT / "results/rvt_fd24"
    forbidden_suffixes = {".parquet", ".arrow", ".pt", ".pth", ".ckpt", ".optimizer"}
    forbidden = [
        path for path in dataset_root.rglob("*")
        if path.is_file() and path.suffix in forbidden_suffixes
    ]
    assert forbidden == []
    assert not (dataset_root / "datasets/scenario_runtime_binding_v1.json").exists()
    assert not (dataset_root / "datasets/phase9_execution_protocol_v1.json").exists()


def test_historical_phase8_and_phase9_hashes_remain_frozen() -> None:
    protocol = json.loads((
        ROOT / "results/rvt_fd24/executable_scientific_protocol_v1.json"
    ).read_text(encoding="ascii"))
    assert protocol["phase8_protocol_hash"] == "0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147"
    assert protocol["generation_budget_hash"] == "3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e"
    assert protocol["frozen_job_manifest_hash"] == "801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3"
