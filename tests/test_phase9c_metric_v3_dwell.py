"""RB-14R -- Metric V3 dwell clock, revalidated on real trajectories."""
from __future__ import annotations
import pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.protocol_session import _inside_candidate_tube
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run

DWELL_REQUIRED = 3.0


def test_dwell_uses_physical_time_not_a_step_count() -> None:
    session = build_session("train-f1-00", policy_id=P.S1)
    period = float(session.runtime_config.physical.control_period_seconds)
    session.step()
    assert session.metric_v3_dwell[COMPACT] in (0.0, pytest.approx(period))


def test_dwell_accumulates_only_while_inside_the_target_tube() -> None:
    session = build_session("train-f1-00", policy_id=P.S1)
    for _ in range(40):
        session.step()
        for topology in (COMPACT, LINE):
            if not _inside_candidate_tube(session, topology):
                assert session.metric_v3_dwell[topology] == 0.0


def test_hold_compact_satisfies_the_compact_dwell() -> None:
    session = run(build_session("train-f1-00", policy_id=P.S1), steps=60)
    assert session.metric_v3_dwell[COMPACT] >= DWELL_REQUIRED


def test_hold_line_satisfies_the_line_dwell() -> None:
    """S2 reaches LINE via its forced mechanical initialization, so the dwell
    begins only after the conversion enters the LINE tube."""
    session = run(build_session("train-f1-00", policy_id=P.S2), steps=500)
    assert session.metric_v3_dwell[LINE] >= DWELL_REQUIRED


def test_a_compact_hold_never_satisfies_the_line_dwell() -> None:
    session = run(build_session("train-f1-00", policy_id=P.S1), steps=60)
    assert session.metric_v3_dwell[LINE] == 0.0


def test_dwell_resets_the_instant_the_tube_is_left() -> None:
    """Interrupted-dwell fixture: inside -> partial -> exit -> re-enter."""
    session = run(build_session("train-f1-00", policy_id=P.S1), steps=40)
    assert session.metric_v3_dwell[COMPACT] > 0.0
    # Force an exit by displacing one robot well outside the tolerance tube.
    displaced = session.robots[0]
    original = displaced.position
    displaced.position = (original[0], original[1] + 5.0)
    session.step()
    assert session.metric_v3_dwell[COMPACT] == 0.0
    # Re-enter: the clock restarts from zero rather than resuming.
    displaced.position = original
    session.step()
    assert session.metric_v3_dwell[COMPACT] == pytest.approx(
        float(session.runtime_config.physical.control_period_seconds))


def test_a_transition_does_not_satisfy_the_target_dwell_before_tube_entry() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import snapshot
    from rvt_swarm.phase9c_rb.policies import SourcePolicy
    session = run(build_session("train-f1-00", policy_id=P.S2), steps=12)
    live = snapshot(session).restore()
    live.source_policy = SourcePolicy({}, 0, live.horizon_seconds, live.team_size)
    live.request_candidate(live.robots[0], COMPACT, "externally_forced_diagnostic")
    for _ in range(60):
        live.step()
        if live.termination is not None:
            break
        if not _inside_candidate_tube(live, COMPACT):
            assert live.metric_v3_dwell[COMPACT] == 0.0


def test_both_dwell_clocks_are_snapshot_and_restored() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_state, snapshot
    session = run(build_session("train-f1-00", policy_id=P.S1), steps=40)
    state = canonical_execution_state(session)
    clocks = state["mission_and_evaluator"]["metric_v3_dwell_seconds"]
    assert set(clocks) == {str(COMPACT), str(LINE)}
    snap = snapshot(session)
    session.metric_v3_dwell[COMPACT] = 99.0
    assert snap.restore().metric_v3_dwell[COMPACT] != 99.0
