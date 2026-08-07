from __future__ import annotations

import json
import copy
from pathlib import Path

import pytest

from rvt_swarm.phase8e.protocol import (
    COMPACT,
    LINE,
    SOURCE_POLICY_IDS,
    s3_local_geometric_decision,
    validate_source_policy_contracts,
)


ROOT = Path(__file__).resolve().parents[1]


def _contract() -> dict:
    return json.loads((
        ROOT / "results/rvt_fd24/source_policy_contracts_v1.json"
    ).read_text(encoding="ascii"))


def test_all_six_source_policies_exist_and_validate() -> None:
    contract = _contract()
    validate_source_policy_contracts(contract)
    assert tuple(contract["policy_ids"]) == SOURCE_POLICY_IDS
    assert set(contract["policies"]) == set(SOURCE_POLICY_IDS)


@pytest.mark.parametrize(
    ("topology", "width", "open_view", "complete", "duration", "expected"),
    [
        (COMPACT, None, False, False, 1.0, "HOLD_UNKNOWN"),
        (COMPACT, 0.2, False, True, 1.0, "HOLD_UNKNOWN"),
        (COMPACT, 0.8, False, True, 1.0, "REQUEST_LINE"),
        (COMPACT, 1.5, False, True, 1.0, "HOLD_COMPACT"),
        (LINE, 1.2, False, True, 1.0, "HOLD_LINE"),
        (LINE, 1.5, False, True, 1.0, "REQUEST_COMPACT"),
        (LINE, None, True, True, 1.0, "REQUEST_COMPACT"),
        (LINE, 1.5, False, True, 0.1, "HOLD_INSUFFICIENT_EVIDENCE"),
    ],
)
def test_s3_rule_is_total_for_declared_local_state_classes(
    topology: int,
    width: float | None,
    open_view: bool,
    complete: bool,
    duration: float,
    expected: str,
) -> None:
    assert s3_local_geometric_decision(
        topology,
        measured_width_meters=width,
        complete_open_observation=open_view,
        complete_observation=complete,
        line_required_width_meters=0.4,
        compact_required_width_meters=1.3,
        spacing_margin_meters=0.05,
        evidence_duration_seconds=duration,
        evidence_persistence_seconds=0.45,
    ) == expected


def test_policy_interface_excludes_future_and_headroom_inputs() -> None:
    prohibited = set(_contract()["common_contract"]["typed_interface"]["prohibited_inputs"])
    assert {"headroom_category", "candidate_outcome", "future_obstacle_trajectory"} <= prohibited


@pytest.mark.parametrize("mutation", ["unknown", "omitted"])
def test_policy_behavior_fields_cannot_be_unknown_or_omitted(mutation: str) -> None:
    contract = copy.deepcopy(_contract())
    policy = contract["policies"]["S5_BOUNDED_PERTURBATION"]
    if mutation == "unknown":
        policy["retry_until_useful"] = True
    else:
        policy.pop("repeat_count")
    with pytest.raises(ValueError):
        validate_source_policy_contracts(contract)
