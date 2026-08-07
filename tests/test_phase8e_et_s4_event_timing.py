"""ET-15 -- S4 originates from local evidence, never from a horizon fraction."""

from __future__ import annotations

import inspect
import json
import pathlib
import re

from rvt_swarm.phase8e import event_timing
from rvt_swarm.phase9c_rb import policies

ROOT = pathlib.Path("results/rvt_fd24")
ADDENDUM = json.loads((ROOT / "source_event_timing_addendum_v1.json").read_text())


def test_s4_has_no_horizon_fraction_event_trigger() -> None:
    assert ADDENDUM["s4_semantics"]["horizon_fraction_trigger_present"] is False
    source = inspect.getsource(policies.FrozenTransitionProtocolPolicy)
    assert not re.search(r"0\.(25|65)\b", source), "superseded 0.25H/0.65H trigger present"
    assert not re.search(r"\*\s*self\.horizon_seconds", source)


def test_s4_event_source_uses_the_frozen_local_geometry_predicate() -> None:
    predicate = ADDENDUM["local_evidence_predicate"]
    assert predicate["implementation"] == (
        "rvt_swarm.phase8e.protocol.s3_local_geometric_decision")
    assert predicate["second_threshold_system_introduced"] is False
    assert set(predicate["shared_by"]) == {
        "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR", "S4_FROZEN_TRANSITION_PROTOCOL"}
    source = inspect.getsource(policies.FrozenTransitionProtocolPolicy)
    assert "LocalGeometricSelectorPolicy" in source


def test_s4_runtime_contract_has_no_family_or_headroom_input() -> None:
    semantics = ADDENDUM["s4_semantics"]
    assert semantics["family_id_input"] is False
    assert semantics["headroom_input"] is False
    assert semantics["future_outcome_used"] is False
    assert semantics["global_geometry_injected"] is False
    prohibited = ADDENDUM["local_evidence_predicate"]["prohibited_inputs"]
    for item in ("family id as a runtime feature", "headroom category", "future outcome",
                 "global corridor width", "ScenarioLayout object"):
        assert item in prohibited


def test_s4_detector_is_not_a_leader_and_event_is_not_authorization() -> None:
    semantics = ADDENDUM["s4_semantics"]
    assert "not a leader" in semantics["originator"]
    assert semantics["event_implies_authorization"] is False
    assert semantics["readiness_still_gates_commitment"] is True
    assert semantics["propagation"].startswith("neighbour-only")


def test_s4_produces_no_transition_when_no_local_evidence_occurs() -> None:
    assert ADDENDUM["s4_semantics"]["no_evidence_means_no_transition"] is True


def test_s4_no_longer_pins_a_fixed_originator_robot() -> None:
    """The superseded contract fixed role-0000 as originator; local evidence
    origination means whichever robot crosses its own threshold first."""
    source = inspect.getsource(policies.FrozenTransitionProtocolPolicy)
    assert "ORIGINATOR_ROBOT_ID" not in source
