"""D12 -- multi-epoch transition execution (defect 12 repair).

Root cause, class A: the frozen `mark_complete` deliberately leaves
`active_intent` and the agreement flags latched, and the frozen `try_rearm` is
what retires them after `rearm_inactive_seconds`. The adapter never called
`try_rearm`, so a completed epoch held its intent forever and no second epoch
could run.
"""
from __future__ import annotations
import math, pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb import protocol_session as PS
from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_hash, snapshot
from rvt_swarm.phase9c_rb.policies import SourcePolicy
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session

RESTING = ("COMPLETE", "REARMED", "STABLE_TOPOLOGY")


def _settle(session, steps=600):
    for _ in range(steps):
        session.step()
        if session.termination is not None:
            return False
        if all(r.protocol_node.state in RESTING for r in session.robots):
            return True
    return False


def _run_epoch(session, target, steps=600):
    requested = False
    for _ in range(steps):
        session.step()
        if session.termination is not None:
            break
        if not requested and all(
                r.protocol_node.state in ("REARMED", "STABLE_TOPOLOGY")
                for r in session.robots):
            requested = session.request_candidate(
                session.robots[0], target, "externally_forced_diagnostic")
        if requested and {r.committed_topology for r in session.robots} == {target} \
                and all(r.protocol_node.state in RESTING for r in session.robots):
            return True
    return False


def _s2_after_first_epoch(layout="train-f1-00"):
    session = build_session(layout, policy_id=P.S2)
    assert _settle(session)
    assert {r.committed_topology for r in session.robots} == {LINE}
    session.source_policy = SourcePolicy({}, 0, session.horizon_seconds, session.team_size)
    return session


# -- the frozen retirement step is now invoked -------------------------------
def test_the_adapter_calls_the_frozen_try_rearm() -> None:
    import inspect
    source = inspect.getsource(PS._retire_finished_lifecycles)
    assert "try_rearm" in source, "the frozen retirement step must be invoked"
    import ast
    calls = {n.func.attr for n in ast.walk(ast.parse(source.lstrip()))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert calls == {"try_rearm"}, f"only the frozen retirement call is allowed, got {calls}"


def test_no_central_reset_shortcut_exists() -> None:
    import pathlib
    text = "\n".join(p.read_text(encoding="ascii")
                     for p in pathlib.Path("rvt_swarm/phase9c_rb").glob("*.py"))
    for forbidden in ("reset_all_protocol_nodes", "reset_all", "clear_all_nodes"):
        assert forbidden not in text, forbidden


def test_a_completed_epoch_retires_its_intent() -> None:
    session = _s2_after_first_epoch()
    for _ in range(60):
        session.step()
        if all(r.protocol_node.state in ("REARMED", "STABLE_TOPOLOGY")
               for r in session.robots):
            break
    for robot in session.robots:
        assert robot.protocol_node.active_intent is None
        assert robot.transition_executor is None


# -- D12-G3 two epochs --------------------------------------------------------
def test_two_full_epochs_complete() -> None:
    session = _s2_after_first_epoch()
    assert _run_epoch(session, COMPACT), "second epoch did not complete"
    assert {r.committed_topology for r in session.robots} == {COMPACT}
    assert {r.protocol_node.mode_epoch_count for r in session.robots} == {2}


def test_epoch_identifiers_are_monotonic() -> None:
    session = _s2_after_first_epoch()
    before = {r.protocol_node.mode_epoch_count for r in session.robots}
    _run_epoch(session, COMPACT)
    after = {r.protocol_node.mode_epoch_count for r in session.robots}
    assert after.pop() > before.pop()


def test_the_second_epoch_uses_a_fresh_profile_and_dwell() -> None:
    session = _s2_after_first_epoch()
    for robot in session.robots:
        assert robot.transition_executor is None or robot.transition_progress >= 0.0
    assert _run_epoch(session, COMPACT)
    assert session.metric_v3_dwell[COMPACT] > 0.0


def test_no_stale_agreement_state_leaks_into_the_second_epoch() -> None:
    session = _s2_after_first_epoch()
    for _ in range(60):
        session.step()
        if all(r.protocol_node.state in ("REARMED", "STABLE_TOPOLOGY")
               for r in session.robots):
            break
    for robot in session.robots:
        node = robot.protocol_node
        assert node._score_agreed is False
        assert node._all_ready is False
        assert node._confirmed is False
        assert node.dwell_started_seconds is None
        assert node.local_dwell_complete is False


# -- D12-G8 snapshot across the epoch boundary --------------------------------
def test_snapshot_immediately_after_epoch_one_reproduces() -> None:
    session = _s2_after_first_epoch()
    snap = snapshot(session)
    restored = snap.restore()
    for _ in range(20):
        session.step()
        restored.step()
        assert canonical_execution_hash(session) == canonical_execution_hash(restored)


def test_snapshot_during_epoch_two_reproduces() -> None:
    session = _s2_after_first_epoch()
    requested = False
    for _ in range(200):
        session.step()
        if not requested and all(r.protocol_node.state in ("REARMED", "STABLE_TOPOLOGY")
                                 for r in session.robots):
            requested = session.request_candidate(
                session.robots[0], COMPACT, "externally_forced_diagnostic")
        if requested and any(r.transition_executor is not None for r in session.robots):
            break
    assert requested
    snap = snapshot(session)
    restored = snap.restore()
    for _ in range(20):
        session.step()
        restored.step()
        assert canonical_execution_hash(session) == canonical_execution_hash(restored)


# -- no collision across the chain -------------------------------------------
def test_the_two_epoch_chain_stays_collision_free() -> None:
    session = _s2_after_first_epoch()
    minimum = float("inf")
    _run_epoch(session, COMPACT)
    for i, a in enumerate(session.robots):
        for b in session.robots[i + 1:]:
            minimum = min(minimum, math.dist(a.position, b.position))
    required = float(session.runtime_config.derived.robot_robot_required_clearance_meters)
    assert minimum >= required
    assert session.termination is None or session.termination.cause != "COLLISION"
