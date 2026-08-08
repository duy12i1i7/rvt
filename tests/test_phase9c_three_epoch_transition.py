"""D12-G4 -- three complete mechanical epochs. Runtime stress fixture only."""
from __future__ import annotations
import math, pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_two_epoch_transition import _run_epoch, _s2_after_first_epoch


def test_three_epochs_complete_with_monotonic_identifiers() -> None:
    session = _s2_after_first_epoch()
    assert {r.committed_topology for r in session.robots} == {LINE}
    assert _run_epoch(session, COMPACT), "epoch 2 failed"
    assert _run_epoch(session, LINE), "epoch 3 failed"
    assert {r.committed_topology for r in session.robots} == {LINE}
    assert {r.protocol_node.mode_epoch_count for r in session.robots} == {3}


def test_three_epoch_chain_is_collision_free() -> None:
    session = _s2_after_first_epoch()
    _run_epoch(session, COMPACT)
    _run_epoch(session, LINE)
    minimum = min(math.dist(a.position, b.position)
                  for i, a in enumerate(session.robots) for b in session.robots[i + 1:])
    required = float(session.runtime_config.derived.robot_robot_required_clearance_meters)
    assert minimum >= required
    assert session.termination is None or session.termination.cause != "COLLISION"


def test_forced_diagnostic_requests_never_count_as_topology_selection() -> None:
    session = _s2_after_first_epoch()
    _run_epoch(session, COMPACT)
    _run_epoch(session, LINE)
    assert session.topology_selection_epoch_count == 0
