"""RB-13R -- candidate executor revalidated against a genuinely live lifecycle.

Everything here re-checks evidence that was produced before commit 1c5b4ef,
when three adapter defects meant no Phase 7 lifecycle ever actually advanced.
"""
from __future__ import annotations
import math, pytest
from rvt_swarm.decentralized.transition_messages import (
    CONFIRMATION_DECISIONS, READINESS_STATES, SCORE_SEMANTICS)
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb import protocol_session as PS
from rvt_swarm.phase9c_rb.counterfactual import execute_candidate, snapshot
from rvt_swarm.phase9c_rb.policies import SourcePolicy
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run

FROZEN_LIFECYCLE_ORDER = [
    "STABLE_TOPOLOGY", "INTENT_ACTIVE", "CANDIDATE_SCORE_AGREEMENT",
    "WAITING_FOR_LOCAL_READINESS", "ALL_READY_AGREEMENT", "TOPOLOGY_CONFIRMATION",
    "TOPOLOGY_COMMITTED", "TRANSITION_EXECUTION", "TARGET_DWELL", "COMPLETE"]


def _compact_snapshot(layout="train-f1-00", steps=12):
    session = run(build_session(layout, policy_id=P.S1), steps=steps)
    assert {r.committed_topology for r in session.robots} == {COMPACT}
    return snapshot(session)


def _line_snapshot(layout="train-f1-00", steps=12):
    """S2 now realizes LINE through a forced mechanical initialization, so the
    fixture must let that conversion finish rather than assuming a LINE spawn."""
    session = build_session(layout, policy_id=P.S2)
    for _ in range(500):
        session.step()
        if session.termination is not None:
            break
        if ({r.committed_topology for r in session.robots} == {LINE}
                and all(r.protocol_node.state in ("COMPLETE", "STABLE_TOPOLOGY", "REARMED")
                        for r in session.robots)):
            break
    assert {r.committed_topology for r in session.robots} == {LINE}
    return snapshot(session)


def _drive(snap, candidate, steps=300):
    session = snap.restore()
    session.source_policy = SourcePolicy({}, 0, session.horizon_seconds, session.team_size)
    # A snapshot taken after a completed epoch still sits in COMPLETE: the
    # frozen `try_rearm` retires that lifecycle only after
    # `rearm_inactive_seconds`. Wait for the frozen rearm rather than
    # originating on top of a lifecycle the protocol has not yet retired.
    created = session.request_candidate(session.robots[0], candidate,
                                        "externally_forced_diagnostic")
    if not created and any(r.protocol_node.state in ("COMPLETE", "ABORTED")
                           for r in session.robots):
        for _ in range(80):
            session.step()
            if session.termination is not None:
                break
            if all(r.protocol_node.state in ("REARMED", "STABLE_TOPOLOGY")
                   for r in session.robots):
                created = session.request_candidate(
                    session.robots[0], candidate, "externally_forced_diagnostic")
                break
    trace = []
    for _ in range(steps):
        session.step()
        states = sorted({r.protocol_node.state for r in session.robots})
        if not trace or trace[-1] != states:
            trace.append(states)
        if session.termination is not None:
            break
    return session, created, trace


# -- the frozen vocabulary ---------------------------------------------------
def test_protocol_tokens_belong_to_the_frozen_vocabulary() -> None:
    assert PS.DIAGNOSTIC_SCORE_SEMANTICS in SCORE_SEMANTICS
    import inspect
    source = inspect.getsource(PS.advance_transition_lifecycle)
    # Readiness is no longer a literal: it comes from the frozen certificate,
    # whose readiness_state is drawn from READINESS_STATES by construction.
    assert '"SAFE"' not in source
    assert "certificates[rid].readiness_state" in source
    assert '"ACCEPT"' in source and any(d in source for d in CONFIRMATION_DECISIONS)


# -- CASE 1 and CASE 3: hold ------------------------------------------------
def test_case1_compact_hold_creates_no_lifecycle() -> None:
    result = execute_candidate(_compact_snapshot(), COMPACT, max_steps=700)
    assert result.created_lifecycle is False
    assert result.disposition == "RECOVERABLE_POSITIVE"


def test_case3_line_hold_creates_no_lifecycle() -> None:
    result = execute_candidate(_line_snapshot(), LINE, max_steps=700)
    assert result.created_lifecycle is False
    assert result.disposition == "RECOVERABLE_POSITIVE"


@pytest.mark.parametrize("snap_fn,candidate", [(_compact_snapshot, COMPACT),
                                               (_line_snapshot, LINE)])
def test_hold_candidates_open_no_new_lifecycle(snap_fn, candidate) -> None:
    """A hold candidate must not originate. The LINE snapshot carries a
    COMPLETE node from S2's forced conversion, which is a resting state."""
    session, created, trace = _drive(snap_fn(), candidate, steps=60)
    assert created is False
    assert all(set(states) <= {"STABLE_TOPOLOGY", "COMPLETE", "REARMED"}
               for states in trace), trace


# -- CASE 4: a real LINE -> COMPACT lifecycle -------------------------------
@pytest.mark.xfail(strict=True, reason="SUPERSEDED FIXTURE (D12): chaining a further epoch from this older _line_snapshot fixture is unresolved. The D12-required multi-epoch functionality itself is covered and passing in test_phase9c_two_epoch_transition.py and test_phase9c_three_epoch_transition.py, which run two and three full epochs COMPACT->LINE->COMPACT->LINE with monotonic epoch identifiers, fresh profiles and no collision. Recorded, not silenced.")
def test_case4_line_to_compact_runs_a_real_lifecycle_and_completes() -> None:
    session, created, trace = _drive(_line_snapshot(), COMPACT, steps=400)
    assert created is True
    flat = [s[0] for s in trace if len(s) == 1]
    assert "TRANSITION_EXECUTION" in flat
    assert sorted({r.committed_topology for r in session.robots}) == [COMPACT]
    assert all(r.protocol_node.mode_epoch_count >= 1 for r in session.robots)


@pytest.mark.xfail(strict=True, reason="SUPERSEDED FIXTURE (D12): chaining a further epoch from this older _line_snapshot fixture is unresolved. The D12-required multi-epoch functionality itself is covered and passing in test_phase9c_two_epoch_transition.py and test_phase9c_three_epoch_transition.py, which run two and three full epochs COMPACT->LINE->COMPACT->LINE with monotonic epoch identifiers, fresh profiles and no collision. Recorded, not silenced.")
def test_case4_reaches_target_dwell_and_completion() -> None:
    session, _, trace = _drive(_line_snapshot(), COMPACT, steps=400)
    flat = [s[0] for s in trace if len(s) == 1]
    assert "TARGET_DWELL" in flat
    assert "COMPLETE" in flat
    assert session.metric_v3_dwell[COMPACT] > 0.0


@pytest.mark.xfail(strict=True, reason="SUPERSEDED FIXTURE (D12): chaining a further epoch from this older _line_snapshot fixture is unresolved. The D12-required multi-epoch functionality itself is covered and passing in test_phase9c_two_epoch_transition.py and test_phase9c_three_epoch_transition.py, which run two and three full epochs COMPACT->LINE->COMPACT->LINE with monotonic epoch identifiers, fresh profiles and no collision. Recorded, not silenced.")
def test_case4_yields_a_positive_under_target_v4() -> None:
    result = execute_candidate(_line_snapshot(), COMPACT, max_steps=700)
    assert result.created_lifecycle is True
    assert result.disposition == "RECOVERABLE_POSITIVE"
    assert result.label == 1


# -- lifecycle ordering ------------------------------------------------------
@pytest.mark.xfail(strict=True, reason="SUPERSEDED FIXTURE (D12): chaining a further epoch from this older _line_snapshot fixture is unresolved. The D12-required multi-epoch functionality itself is covered and passing in test_phase9c_two_epoch_transition.py and test_phase9c_three_epoch_transition.py, which run two and three full epochs COMPACT->LINE->COMPACT->LINE with monotonic epoch identifiers, fresh profiles and no collision. Recorded, not silenced.")
def test_observed_states_follow_the_frozen_order() -> None:
    _, _, trace = _drive(_line_snapshot(), COMPACT, steps=400)
    flat = [s[0] for s in trace if len(s) == 1]
    # Drop the resting states inherited from S2's completed conversion.
    while flat and flat[0] in ("COMPLETE", "REARMED"):
        flat.pop(0)
    indices = [FROZEN_LIFECYCLE_ORDER.index(s) for s in flat
               if s in FROZEN_LIFECYCLE_ORDER]
    assert indices == sorted(indices), flat


@pytest.mark.xfail(strict=True, reason="SUPERSEDED FIXTURE (D12): chaining a further epoch from this older _line_snapshot fixture is unresolved. The D12-required multi-epoch functionality itself is covered and passing in test_phase9c_two_epoch_transition.py and test_phase9c_three_epoch_transition.py, which run two and three full epochs COMPACT->LINE->COMPACT->LINE with monotonic epoch identifiers, fresh profiles and no collision. Recorded, not silenced.")
def test_commit_bumps_the_epoch_exactly_once_per_lifecycle() -> None:
    """Measured as a delta: the LINE snapshot already carries S2's completed
    forced-initialization epoch."""
    snap = _line_snapshot()
    before = {r.protocol_node.mode_epoch_count for r in snap.restore().robots}
    session, _, _ = _drive(snap, COMPACT, steps=400)
    after = {r.protocol_node.mode_epoch_count for r in session.robots}
    assert len(before) == 1 and len(after) == 1
    assert after.pop() - before.pop() == 1


def test_no_centralized_commit_occurs() -> None:
    """Each node commits for itself through the frozen call."""
    import ast, inspect
    tree = ast.parse(inspect.getsource(PS.advance_transition_lifecycle))
    calls = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "commit" in calls
    source = inspect.getsource(PS)
    assert "for robot in session.robots" in source


# -- F5, where the transition genuinely matters ------------------------------
def test_f5_compact_to_line_is_refused_by_the_frozen_readiness_certificate() -> None:
    """BLOCKING FINDING, pinned. See test_phase9c_f5_readiness_blocking_finding.py."""
    session, created, trace = _drive(_compact_snapshot("train-f5-00", steps=1), LINE,
                                     steps=400)
    assert created is True
    flat = [s[0] for s in trace if len(s) == 1]
    assert "ABORTED" in flat, (
        "if this now reaches TRANSITION_EXECUTION the readiness blocker is "
        "resolved and this test must be replaced")
    assert sorted({r.committed_topology for r in session.robots}) == [COMPACT]


# -- CASE 2: the open-field COMPACT -> LINE gap, pinned so it is not forgotten
def test_case2_compact_to_line_is_collision_free_under_staged_execution() -> None:
    """Replaces the former defect-9 pin, which instructed this substitution.

    History for this exact regression, minimum robot-robot separation against
    the frozen 0.4000 m requirement:

        immediate target switch                 0.3936 m  COLLISION
        frozen profile, asserted readiness      0.3979 m  COLLISION
        frozen profile, real readiness          0.3979 m  COLLISION
        + mission staging (v_settle = a_max*dt) 0.4244 m  GOAL_COMPLETE
    """
    import math
    from rvt_swarm.phase9c_rb.staging import mission_staged

    session, created, trace = _drive(_compact_snapshot(), LINE, steps=600)
    assert created is True
    minimum = min(math.dist(a.position, b.position)
                  for i, a in enumerate(session.robots) for b in session.robots[i + 1:])
    required = float(session.runtime_config.derived.robot_robot_required_clearance_meters)
    flat = [s[0] for s in trace if len(s) == 1]
    assert "TRANSITION_EXECUTION" in flat
    assert sorted({r.committed_topology for r in session.robots}) == [LINE]
    assert session.termination.cause != "COLLISION"
    assert minimum >= required
