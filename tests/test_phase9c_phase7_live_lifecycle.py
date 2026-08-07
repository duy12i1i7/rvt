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
    session = run(build_session(layout, policy_id=P.S2), steps=steps)
    assert {r.committed_topology for r in session.robots} == {LINE}
    return snapshot(session)


def _drive(snap, candidate, steps=300):
    session = snap.restore()
    session.source_policy = SourcePolicy({}, 0, session.horizon_seconds, session.team_size)
    created = session.request_candidate(session.robots[0], candidate,
                                        "externally_forced_diagnostic")
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
    assert '"SAFE"' in source and any(s in source for s in READINESS_STATES)
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
def test_hold_candidates_never_leave_stable_topology(snap_fn, candidate) -> None:
    session, created, trace = _drive(snap_fn(), candidate, steps=60)
    assert created is False
    assert trace == [["STABLE_TOPOLOGY"]], trace


# -- CASE 4: a real LINE -> COMPACT lifecycle -------------------------------
def test_case4_line_to_compact_runs_a_real_lifecycle_and_completes() -> None:
    session, created, trace = _drive(_line_snapshot(), COMPACT, steps=400)
    assert created is True
    flat = [s[0] for s in trace if len(s) == 1]
    assert "TRANSITION_EXECUTION" in flat
    assert sorted({r.committed_topology for r in session.robots}) == [COMPACT]
    assert all(r.protocol_node.mode_epoch_count >= 1 for r in session.robots)


def test_case4_reaches_target_dwell_and_completion() -> None:
    session, _, trace = _drive(_line_snapshot(), COMPACT, steps=400)
    flat = [s[0] for s in trace if len(s) == 1]
    assert "TARGET_DWELL" in flat
    assert "COMPLETE" in flat
    assert session.metric_v3_dwell[COMPACT] > 0.0


def test_case4_yields_a_positive_under_target_v4() -> None:
    result = execute_candidate(_line_snapshot(), COMPACT, max_steps=700)
    assert result.created_lifecycle is True
    assert result.disposition == "RECOVERABLE_POSITIVE"
    assert result.label == 1


# -- lifecycle ordering ------------------------------------------------------
def test_observed_states_follow_the_frozen_order() -> None:
    _, _, trace = _drive(_line_snapshot(), COMPACT, steps=400)
    flat = [s[0] for s in trace if len(s) == 1]
    indices = [FROZEN_LIFECYCLE_ORDER.index(s) for s in flat
               if s in FROZEN_LIFECYCLE_ORDER]
    assert indices == sorted(indices), flat


def test_commit_bumps_the_epoch_exactly_once_per_lifecycle() -> None:
    session, _, _ = _drive(_line_snapshot(), COMPACT, steps=400)
    assert {r.protocol_node.mode_epoch_count for r in session.robots} == {1}


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
def test_f5_compact_to_line_completes_and_commits_before_the_bottleneck() -> None:
    session, created, trace = _drive(_compact_snapshot("train-f5-00", steps=1), LINE,
                                     steps=400)
    assert created is True
    flat = [s[0] for s in trace if len(s) == 1]
    assert "TRANSITION_EXECUTION" in flat
    assert sorted({r.committed_topology for r in session.robots}) == [LINE]


# -- CASE 2: the open-field COMPACT -> LINE gap, pinned so it is not forgotten
def test_case2_compact_to_line_currently_collides_during_reconfiguration() -> None:
    """RUNTIME INTEGRATION DEFECT, pinned deliberately.

    The publication session switches the controller's target topology
    immediately on commit. The frozen contract instead requires the smooth
    role-space profile (`generic_role_space_profile`, implemented by
    `transition_execution.RobotLocalTransitionExecutor`), which exists precisely
    to keep robots separated while they exchange grid positions.

    Under the immediate switch, an open-field COMPACT -> LINE reconfiguration
    puts robots 2 and 3 within 0.3936 m of the 0.40 m required clearance, with
    no obstacle involved. This test records the defect; it must be replaced by
    an assertion of success once the frozen profile is bound.
    """
    from rvt_swarm.decentralized.transition_runtime import TRANSITION_EXECUTION_STRATEGIES
    assert "generic_role_space_profile" in TRANSITION_EXECUTION_STRATEGIES
    result = execute_candidate(_compact_snapshot(), LINE, max_steps=700)
    assert result.created_lifecycle is True
    assert result.termination_cause == "COLLISION", (
        "if this now passes, the smooth profile has been bound and this test "
        "must be replaced by a success assertion")
    assert result.disposition == "VALID_TASK_NEGATIVE", (
        "a collision must stay a valid task-negative, never generation-invalid")
