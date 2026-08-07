"""ET-15 -- S0 diagnostic event timing is landmark-anchored, not clock-anchored.

Specification/static only: no simulator episode is constructed here.
"""

from __future__ import annotations

import inspect
import json
import pathlib
import re

import pytest

from rvt_swarm.phase8e import event_timing
from rvt_swarm.phase9c_rb import policies

ROOT = pathlib.Path("results/rvt_fd24")
ADDENDUM = json.loads((ROOT / "source_event_timing_addendum_v1.json").read_text())


def test_s0_declares_no_absolute_scientific_event_time() -> None:
    assert ADDENDUM["s0_semantics"]["absolute_event_seconds_present"] is False


def test_s0_implementation_has_no_horizon_fraction_trigger() -> None:
    """The superseded trigger was `fraction * horizon`. It must be gone.

    `horizon_seconds` still reaches the policy through the typed S0-S5
    interface -- that is the horizon's legitimate role as a timeout and
    evaluation bound. What must not exist is a *trigger* computed from it.
    """
    source = inspect.getsource(policies.ScriptedDiagnosticPolicy)
    assert not re.search(r"\*\s*self\.horizon_seconds", source)
    assert not re.search(r"horizon_seconds\s*\*", source)
    decide = inspect.getsource(policies.ScriptedDiagnosticPolicy.observe)
    assert "horizon" not in decide, decide


def test_s0_trigger_is_a_longitudinal_landmark_not_a_time() -> None:
    source = inspect.getsource(policies.ScriptedDiagnosticPolicy.observe)
    assert "trigger_longitudinal_meters" in source
    assert "time_seconds" not in source


def test_s0_landmarks_derive_only_from_approved_geometry_and_sensing() -> None:
    semantics = ADDENDUM["s0_semantics"]
    assert semantics["may_read_compiled_landmark"] is True
    assert semantics["may_read_headroom_or_outcome"] is False
    assert "sensing range" in semantics["new_trigger"] or "observability" in semantics["new_trigger"]


def test_s0_never_directly_commits_topology() -> None:
    assert ADDENDUM["s0_semantics"]["directly_sets_topology"] is False
    assert ADDENDUM["s0_semantics"]["enters_phase7_protocol"] is True
    source = inspect.getsource(policies.ScriptedDiagnosticPolicy)
    # It requests a candidate; it never assigns a committed topology.
    assert "request_candidate" in source
    assert "committed_topology =" not in source


def test_s0_event_ordinals_and_target_topologies_are_preserved() -> None:
    """ET-2: this phase changes the trigger, never the declared sequence."""
    contracts = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())
    table = contracts["policies"]["S0_SCRIPTED_DIAGNOSTIC"]["machine_readable_script"]
    audit = json.loads((ROOT / "event_timing_static_audit_v1.json").read_text())
    for record in audit["records"]:
        declared = [int(entry[1]) for entry in table[record["family_id"]]]
        planned = [e["candidate_topology"]
                   for e in record["by_team_size"]["6"]["events"]]
        assert planned == declared, (record["layout_id"], planned, declared)
