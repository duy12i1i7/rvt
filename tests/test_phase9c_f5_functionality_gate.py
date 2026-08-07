"""RB-18F5 -- F5 must still implement its declared sequential-bottleneck purpose.

This is a scenario-functionality criterion, not a label-balance criterion. No
geometry, speed, controller, safety, dwell, event timing or horizon is changed
to make it pass.
"""
from __future__ import annotations
import pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import execute_candidate, snapshot
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run

# Mission-frame longitudinal landmarks of train-f5-00, read from the compiled record.
BOTTLENECK_0_ENTRY = 2.00
BOTTLENECK_0_EXIT = 3.50
BOTTLENECK_1_ENTRY = 6.50
BOTTLENECK_1_EXIT = 8.00


def _run(policy_id, layout="train-f5-00", steps=900):
    return run(build_session(layout, policy_id=policy_id), steps=steps)


def test_s0_originates_the_first_f5_event() -> None:
    session = _run(P.S0, steps=40)
    dispositions = session.source_policy.dispositions
    assert dispositions, "S0 must originate at least one F5 event"
    assert dispositions[0]["ordinal"] == 0
    assert dispositions[0]["event_type"] == "local_constriction"
    assert dispositions[0]["candidate_topology"] == LINE


def test_the_first_f5_event_actually_initiates_a_compact_to_line_attempt() -> None:
    session = _run(P.S0, steps=40)
    first = session.source_policy.dispositions[0]
    assert first["disposition"] == "ORIGINATED"
    assert first["committed_topology_at_trigger"] == COMPACT
    assert session.event_log, "a Phase 7 lifecycle must have been created"


def test_the_first_event_disposition_is_explicit_and_auditable() -> None:
    session = _run(P.S0, steps=40)
    for record in session.source_policy.dispositions:
        assert record["disposition"] in {
            "ORIGINATED", "SKIPPED_ORIGINATION_BLOCKED", "NO_OP_ALREADY_COMMITTED"}
        for field in ("ordinal", "landmark_id", "trigger_longitudinal_meters",
                      "control_step", "protocol_state_at_trigger"):
            assert field in record


def test_at_least_one_frozen_non_learned_path_survives_the_first_bottleneck() -> None:
    """S2 holds LINE, whose required width (0.40 m) fits F5's 1.40 m free width."""
    session = _run(P.S2)
    assert session.max_longitudinal_progress > BOTTLENECK_0_EXIT, (
        "no frozen path clears the first bottleneck")


def test_a_frozen_non_learned_path_reaches_the_later_bottleneck_region() -> None:
    """The RB-18F5 gate proper: the second cycle must be structurally reachable."""
    session = _run(P.S2)
    assert session.max_longitudinal_progress >= BOTTLENECK_1_ENTRY, (
        f"F5 cannot exercise its declared second bottleneck: "
        f"max progress {session.max_longitudinal_progress:.2f} m "
        f"< entry {BOTTLENECK_1_ENTRY} m")


def test_that_path_passes_completely_through_the_second_bottleneck() -> None:
    session = _run(P.S2)
    assert session.max_longitudinal_progress >= BOTTLENECK_1_EXIT


def test_a_line_counterfactual_candidate_can_also_traverse() -> None:
    """The counterfactual arm, not only the source arm, can reach the later region."""
    session = run(build_session("train-f5-00", policy_id=P.S2), steps=10)
    result = execute_candidate(snapshot(session), LINE, max_steps=900)
    assert result.control_steps > 0
    assert result.disposition in {"RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"}


def test_compact_hold_legitimately_fails_the_first_bottleneck() -> None:
    """Required COMPACT width 1.30 m against 1.40 m free leaves 0.05 m per side,
    which lateral tracking error exceeds. That is why F5 needs LINE at all."""
    session = _run(P.S1)
    assert session.termination is not None
    assert session.termination.cause == "COLLISION"
    assert session.max_longitudinal_progress < BOTTLENECK_0_ENTRY


def test_later_f5_event_identities_remain_auditable_even_when_unreached() -> None:
    from rvt_swarm.phase9c_rb.session import build_event_plan
    from tests.test_phase9c_f5_multievent_sequence import _plan
    _, plan = _plan()
    assert len(plan) == 4
    assert [e.ordinal for e in plan] == [0, 1, 2, 3]
    assert all(e.reachable_before_goal for e in plan)


def test_no_queue_replay_or_delay_semantics_were_introduced() -> None:
    """Executable code only -- the docstring legitimately names what is absent."""
    import ast, inspect
    tree = ast.parse(inspect.getsource(P.ScriptedDiagnosticPolicy).lstrip())
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    for invented in ("queue", "replay", "debounce", "defer", "retry_at",
                     "pending_events", "delay"):
        offenders = [n for n in names if invented in n.lower()]
        assert offenders == [], (invented, offenders)
