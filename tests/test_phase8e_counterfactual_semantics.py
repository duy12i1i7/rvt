from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _contract() -> dict:
    document = json.loads((
        ROOT / "results/rvt_fd24/executable_scientific_protocol_v1.json"
    ).read_text(encoding="ascii"))
    return document["counterfactual_execution_contract"]


def test_candidate_equal_current_never_creates_noop_epoch() -> None:
    assert _contract()["candidate_equals_current"] == "hold or continue; no source-equals-target epoch"


def test_changed_candidate_must_use_phase7_and_preserve_active_lifecycle() -> None:
    contract = _contract()
    assert contract["candidate_differs_stable"] == "originate candidate through Phase 7"
    assert contract["candidate_differs_from_active_target"].startswith("do not supersede")
    assert contract["protocol_initialization"] == "preserve source lifecycle exactly"


def test_clone_and_matching_contract_is_complete() -> None:
    contract = _contract()
    assert contract["clone_rule"].startswith("two independent deep clones")
    matching = set(contract["matching"])
    assert "initial snapshot hash" in matching
    assert "matched disturbance seed" in matching
    assert "dynamic obstacle snapshot and seed" in matching
    assert contract["invalid_pair"].startswith("generation-invalid")
