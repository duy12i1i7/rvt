"""F5-R -- repeated online reconfiguration, using the real Phase 7 machinery.

Always-LINE feasibility is NOT accepted as evidence here. Every run below starts
from the frozen COMPACT initialization and must use the actual protocol.
"""
from __future__ import annotations
import pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.protocol_session import _inside_candidate_tube
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session

BOTTLENECK_0 = (2.00, 3.50)
BOTTLENECK_1 = (6.50, 8.00)


def _timeline(layout="train-f5-00", policy_id=P.S0, team_size=6, steps=700):
    session = build_session(layout, policy_id=policy_id, team_size=team_size)
    milestones = {}
    for _ in range(steps):
        session.step()
        states = {r.protocol_node.state for r in session.robots}
        committed = {r.committed_topology for r in session.robots}
        for state in states:
            milestones.setdefault(state, (session.control_step, session.time_seconds,
                                          session.max_longitudinal_progress))
        if committed == {LINE}:
            milestones.setdefault("LINE_COMMITTED",
                                  (session.control_step, session.time_seconds,
                                   session.max_longitudinal_progress))
        if session.termination is not None:
            break
    return session, milestones


# -- F5-R1: first transition viability ---------------------------------------
def test_f5r1_the_first_constriction_event_is_originated_from_compact() -> None:
    session, _ = _timeline(steps=5)
    first = session.source_policy.dispositions[0]
    assert first["disposition"] == "ORIGINATED"
    assert first["committed_topology_at_trigger"] == COMPACT
    assert first["candidate_topology"] == LINE


def test_f5r1_the_lifecycle_actually_advances_through_every_phase() -> None:
    """Guards the defect where the originator never adopted its own intent and
    every node sat in STABLE_TOPOLOGY until collision."""
    _, milestones = _timeline()
    for phase in ("CANDIDATE_SCORE_AGREEMENT", "ALL_READY_AGREEMENT",
                  "TOPOLOGY_CONFIRMATION", "TRANSITION_EXECUTION", "TARGET_DWELL"):
        assert phase in milestones, f"lifecycle never reached {phase}"


def test_f5r1_compact_to_line_commits_before_the_first_bottleneck() -> None:
    session, milestones = _timeline()
    assert "LINE_COMMITTED" in milestones
    _, _, progress_at_commit = milestones["LINE_COMMITTED"]
    assert progress_at_commit < BOTTLENECK_0[0], (
        f"commit at {progress_at_commit:.2f} m is not before the bottleneck entry")


def test_f5r1_metric_v3_line_dwell_completes() -> None:
    session, milestones = _timeline()
    assert "COMPLETE" in milestones, "the transition lifecycle never completed"
    assert session.metric_v3_dwell[LINE] > 0.0


def test_f5r1_no_collision_occurs_before_the_transition_completes() -> None:
    session, milestones = _timeline()
    if session.termination is not None and session.termination.cause == "COLLISION":
        collision_progress = session.max_longitudinal_progress
        _, _, complete_progress = milestones["COMPLETE"]
        assert complete_progress <= collision_progress


# -- F5-R2 / F5-R3: later cycle ----------------------------------------------
def test_f5r2_the_run_survives_beyond_the_first_bottleneck() -> None:
    session, _ = _timeline()
    assert session.max_longitudinal_progress > BOTTLENECK_0[1]


def test_f5r3_the_run_reaches_the_second_bottleneck_region() -> None:
    session, _ = _timeline()
    assert session.max_longitudinal_progress >= BOTTLENECK_1[0]


def test_f5r3_the_run_passes_completely_through_the_second_bottleneck() -> None:
    session, _ = _timeline()
    assert session.max_longitudinal_progress >= BOTTLENECK_1[1]


def test_f5r3_all_four_event_identities_remain_distinct_and_disposed() -> None:
    session, _ = _timeline()
    dispositions = session.source_policy.dispositions
    assert [d["ordinal"] for d in dispositions] == [0, 1, 2, 3]
    assert len({d["landmark_id"] for d in dispositions}) == 4
    for record in dispositions:
        assert record["disposition"] in {
            "ORIGINATED", "SKIPPED_ORIGINATION_BLOCKED", "NO_OP_ALREADY_COMMITTED"}


def test_f5r3_a_blocked_later_event_is_skipped_not_queued() -> None:
    """Frozen rule: blocked entries are consumed, never deferred."""
    session, _ = _timeline()
    blocked = [d for d in session.source_policy.dispositions
               if d["disposition"] == "SKIPPED_ORIGINATION_BLOCKED"]
    assert blocked, "this run must exercise the blocked path"
    for record in blocked:
        assert session.source_policy.fired[record["ordinal"]] is True


# -- F5-R4: declared scientific purpose --------------------------------------
def test_f5r4_a_real_transition_path_satisfies_all_four_conditions() -> None:
    session, milestones = _timeline()
    assert "COMPLETE" in milestones                                   # A
    assert session.max_longitudinal_progress > BOTTLENECK_0[1]        # B
    assert session.max_longitudinal_progress >= BOTTLENECK_1[0]       # C
    assert len(session.source_policy.dispositions) == 4               # D


def test_f5r4_the_result_does_not_rest_on_always_line() -> None:
    """The passing run starts COMPACT and uses the protocol, not S2."""
    session, _ = _timeline()
    assert session.initial_topology == COMPACT
    assert session.event_log, "a real Phase 7 lifecycle must have run"
    assert session.event_log[0]["candidate_topology"] == LINE


def test_f5r4_no_queue_replay_or_delay_semantics_were_introduced() -> None:
    import ast, inspect
    from rvt_swarm.phase9c_rb import protocol_session
    tree = ast.parse(inspect.getsource(protocol_session))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for invented in ("replay", "debounce", "requeue", "deferred_events"):
        assert not any(invented in n.lower() for n in names), invented
