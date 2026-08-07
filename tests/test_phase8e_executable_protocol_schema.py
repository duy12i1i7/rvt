from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rvt_swarm.phase8e.protocol import (
    COMPOSITE_GENERATION_PROTOCOL_SHA256,
    EXECUTABLE_PROTOCOL_SCHEMA_VERSION,
    FROZEN_JOB_MANIFEST_SHA256,
    GENERATION_BUDGET_SHA256,
    PHASE8_PROTOCOL_SHA256,
    build_executable_protocol,
    validate_executable_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "results/rvt_fd24/executable_scientific_protocol_v1.json"


def _artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="ascii"))


def test_executable_protocol_is_canonical_and_rebuilds_exactly() -> None:
    document = _artifact()
    validate_executable_protocol(document)
    assert document == build_executable_protocol(ROOT)
    assert document["schema_version"] == EXECUTABLE_PROTOCOL_SCHEMA_VERSION
    assert document["category_d_count"] == 0


def test_protocol_references_every_frozen_parent_hash() -> None:
    document = _artifact()
    assert document["phase8_protocol_hash"] == PHASE8_PROTOCOL_SHA256
    assert document["generation_budget_hash"] == GENERATION_BUDGET_SHA256
    assert document["composite_generation_protocol_hash"] == COMPOSITE_GENERATION_PROTOCOL_SHA256
    assert document["frozen_job_manifest_hash"] == FROZEN_JOB_MANIFEST_SHA256


@pytest.mark.parametrize("mutation", ["unknown", "omitted", "nested_omitted"])
def test_unknown_or_incomplete_behavior_fields_are_rejected(mutation: str) -> None:
    document = copy.deepcopy(_artifact())
    if mutation == "unknown":
        document["implicit_default"] = True
    elif mutation == "omitted":
        document.pop("disturbance_contract")
    else:
        document["scenario_geometry_contract"]["world_frame"].pop("origin_meters")
    with pytest.raises(ValueError):
        validate_executable_protocol(document)
