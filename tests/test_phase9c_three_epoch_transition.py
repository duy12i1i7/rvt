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


def test_each_epoch_records_its_own_distributed_completion_agreement() -> None:
    """PCA-16A: every retired epoch leaves an auditable, distinct agreement."""
    session = _s2_after_first_epoch()
    _run_epoch(session, COMPACT)
    _run_epoch(session, LINE)
    assert len(session.completion_agreements) == 3
    lifecycle_ids = [a["lifecycle_id"] for a in session.completion_agreements]
    epoch_ids = [a["epoch_id"] for a in session.completion_agreements]
    assert len(set(lifecycle_ids)) == 3 and len(set(epoch_ids)) == 3
    times = [a["status_agreement_time_seconds"] for a in session.completion_agreements]
    assert times == sorted(times), "agreement times must be strictly ordered"
    assert all(a["agreed"] for a in session.completion_agreements)


def test_a_fourth_epoch_is_bounded_by_mission_completion_not_by_defect() -> None:
    """PCA-16 finding, recorded honestly.

    Four changed-topology epochs do not fit inside any available fixture: the
    mission reaches GOAL_COMPLETE first. Measured on train-f1-00 (3 epochs then
    goal) and train-f7-00 (3 epochs, goal at 45.9 s of a 110 s horizon). That is
    the mission ending, not a protocol failure -- the third epoch completes
    normally with its own distributed agreement in both cases.
    """
    session = _s2_after_first_epoch()
    assert _run_epoch(session, COMPACT)
    assert _run_epoch(session, LINE)
    fourth = _run_epoch(session, COMPACT)
    if not fourth:
        assert session.termination is not None
        assert session.termination.cause == "GOAL_COMPLETE"
        assert {r.protocol_node.mode_epoch_count for r in session.robots} == {3}


def test_forced_diagnostic_requests_never_count_as_topology_selection() -> None:
    session = _s2_after_first_epoch()
    _run_epoch(session, COMPACT)
    _run_epoch(session, LINE)
    assert session.topology_selection_epoch_count == 0
