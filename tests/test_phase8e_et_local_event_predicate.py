"""ET-15 -- one shared local geometric evidence predicate for S3 and S4."""

from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase8e import event_timing
from rvt_swarm.phase8e.protocol import s3_local_geometric_decision
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG
from rvt_swarm.topology_registry import COMPACT, LINE

ROOT = pathlib.Path("results/rvt_fd24")
ADDENDUM = json.loads((ROOT / "source_event_timing_addendum_v1.json").read_text())

LINE_REQUIRED_WIDTH = 0.86      # LINE lateral span 0 + 2*(0.18+0.02) rounded up in fixtures
COMPACT_REQUIRED_WIDTH = 2.30


def _decide(committed, width, *, open_observation=False, complete=True, elapsed=1.0):
    return s3_local_geometric_decision(
        committed,
        measured_width_meters=width,
        complete_open_observation=open_observation,
        complete_observation=complete or open_observation,
        line_required_width_meters=LINE_REQUIRED_WIDTH,
        compact_required_width_meters=COMPACT_REQUIRED_WIDTH,
        spacing_margin_meters=float(CONFIG.formation.spacing_margin_meters),
        evidence_duration_seconds=elapsed,
        evidence_persistence_seconds=float(CONFIG.protocol.evidence_persistence_seconds),
    )


def test_the_four_declared_states_are_reachable_from_the_frozen_predicate() -> None:
    states = ADDENDUM["local_evidence_predicate"]["states"]
    assert _decide(COMPACT, 1.2) == states["LOCAL_LINE_REQUIRED"]
    assert _decide(COMPACT, 5.0) == states["LOCAL_COMPACT_FEASIBLE"]
    assert _decide(LINE, None, open_observation=True) == states["LOCAL_OPENING_FOR_COMPACT"]
    assert _decide(COMPACT, None, complete=False) == states["LOCAL_GEOMETRY_UNKNOWN"]


def test_state_names_map_onto_the_module_constants() -> None:
    states = ADDENDUM["local_evidence_predicate"]["states"]
    assert states["LOCAL_LINE_REQUIRED"] == event_timing.LOCAL_LINE_REQUIRED
    assert states["LOCAL_COMPACT_FEASIBLE"] == event_timing.LOCAL_COMPACT_FEASIBLE
    assert states["LOCAL_OPENING_FOR_COMPACT"] == event_timing.LOCAL_OPENING_FOR_COMPACT
    assert states["LOCAL_GEOMETRY_UNKNOWN"] == event_timing.LOCAL_GEOMETRY_UNKNOWN


def test_insufficient_evidence_holds_rather_than_originating() -> None:
    """Frozen persistence still gates origination; the addendum did not relax it."""
    assert _decide(COMPACT, 1.2, elapsed=0.0) == "HOLD_INSUFFICIENT_EVIDENCE"


def test_event_vocabulary_is_the_frozen_phase7_set() -> None:
    from rvt_swarm.decentralized.transition_messages import EVENT_TYPES
    for name in ADDENDUM["event_vocabulary"]:
        assert name in EVENT_TYPES, name


def test_hysteresis_and_rearm_are_not_modified() -> None:
    reference = ADDENDUM["hysteresis_and_rearm_reference"]
    assert reference["modified_by_this_addendum"] is False
    assert reference["commitment_seconds"] == float(CONFIG.protocol.commitment_seconds)
    assert reference["evidence_persistence_seconds"] == float(
        CONFIG.protocol.evidence_persistence_seconds)
    assert reference["rearm_inactive_seconds"] == float(
        CONFIG.protocol.rearm_inactive_seconds)
