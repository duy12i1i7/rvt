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


def test_fixed_line_pays_the_forced_conversion_cost_at_n6() -> None:
    """Under the owner-decided S2 semantics the fixed-LINE baseline starts at
    COMPACT and must convert; at N=6 on F5 it does not complete the task."""
    session = _run(P.S2)
    assert session.termination is not None
    assert session.termination.cause == "COLLISION"


def test_f5_still_exposes_switching_headroom_at_small_n() -> None:
    import json, pathlib
    v5 = json.loads(pathlib.Path(
        "results/rvt_fd24/headroom_requalification_v5.json").read_text())
    f5 = [c for c in v5["cells"] if c["family"] == "F5"]
    assert len(f5) == 15
    assert any(c["line"]["success"] for c in f5), (
        "fixed LINE must still succeed somewhere in F5")


def test_f5_categories_follow_executable_outcomes() -> None:
    import json, pathlib
    v5 = json.loads(pathlib.Path(
        "results/rvt_fd24/headroom_requalification_v5.json").read_text())
    assert sum(v5["f5"]["categories"].values()) == 15
    assert v5["f5"]["necessity_claim_restored"] is False


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
