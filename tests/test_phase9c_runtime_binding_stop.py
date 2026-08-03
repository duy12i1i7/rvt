from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from rvt_swarm.phase8.scenario import ScenarioLayout


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/PHASE9C_SCENARIO_RUNTIME_BINDING_INVENTORY.md"
REPORT = ROOT / "docs/PHASE9C_RUNTIME_BINDING_REPORT.md"
CANARY_REPORT = ROOT / "docs/PHASE9C_RUNTIME_BINDING_CANARY_REPORT.md"


def test_inventory_names_every_authoritative_scenario_layout_field() -> None:
    text = INVENTORY.read_text(encoding="ascii")
    for field in fields(ScenarioLayout):
        assert f"`{field.name}`" in text


def test_rb1_stop_records_category_d_and_exact_verdict() -> None:
    inventory = INVENTORY.read_text(encoding="ascii")
    report = REPORT.read_text(encoding="ascii")
    assert "Category D" in inventory
    assert "D1 - Static corridor and bypass geometry" in inventory
    assert "D6 - Task evaluator" in inventory
    verdict = (
        "**A. ScenarioLayout still cannot be mapped uniquely into executable "
        "runtime semantics.**"
    )
    assert report.count(verdict) == 1


def test_stop_does_not_create_binding_or_execution_manifests() -> None:
    datasets = ROOT / "results/rvt_fd24/datasets"
    assert not (datasets / "scenario_runtime_binding_v1.json").exists()
    assert not (datasets / "phase9_execution_protocol_v1.json").exists()


def test_prebinding_canary_history_remains_zero_and_phase9c_is_not_run() -> None:
    audit = json.loads(
        (ROOT / "results/rvt_fd24/datasets/phase9_canary_audit.json").read_text(
            encoding="ascii"
        )
    )
    assert len(audit["attempts"]) == 2
    assert audit["scientific_source_episodes_completed"] == 0
    assert audit["recoverability_records_emitted"] == 0
    assert audit["final_test_runtime_access_count"] == 0
    canary_report = CANARY_REPORT.read_text(encoding="ascii")
    assert "NOT_RUN_RB1_BLOCKING_INVENTORY" in canary_report
