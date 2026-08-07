from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from rvt_swarm.phase8.scenario import ScenarioLayout
from rvt_swarm.phase8e.protocol import validate_executable_protocol


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> dict:
    return json.loads(
        (ROOT / "results/rvt_fd24/executable_scientific_protocol_v1.json").read_text(
            encoding="ascii"
        )
    )


def test_every_scenario_layout_field_is_consumed_or_audit_only() -> None:
    protocol = _protocol()
    validate_executable_protocol(protocol)
    dispositions = protocol["scenario_geometry_contract"]["layout_field_dispositions"]
    assert {entry["field"] for entry in dispositions} == {field.name for field in fields(ScenarioLayout)}
    assert all(entry["visibility"] for entry in dispositions)


def test_every_family_has_exactly_one_compiler_rule() -> None:
    compilers = _protocol()["scenario_geometry_contract"]["family_compilers"]
    assert set(compilers) == {f"F{index}" for index in range(1, 11)}
    assert all(isinstance(value, str) and value for value in compilers.values())


def test_geometry_contract_has_no_headroom_execution_path() -> None:
    geometry = _protocol()["scenario_geometry_contract"]
    assert geometry["headroom_use"] == "audit_only_prohibited_from_compilation_and_execution"
    headroom = next(
        item for item in geometry["layout_field_dispositions"]
        if item["field"] == "diagnostic_headroom_by_team_size"
    )
    assert headroom["visibility"] == "audit_only"
