"""D13 -- distributed lifecycle completion binding."""
from __future__ import annotations
import ast, inspect, pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb import protocol_session as PS
from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_hash, snapshot
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session

RESTING = ("COMPLETE", "REARMED", "STABLE_TOPOLOGY")


def _run_to_completion(layout="train-f1-00", policy_id=P.S2, steps=500):
    session = build_session(layout, policy_id=policy_id)
    for _ in range(steps):
        session.step()
        if session.termination is not None:
            break
        if all(r.protocol_node.state in RESTING for r in session.robots):
            break
    return session


# -- D13-G2 / D13-G3: the frozen calls are bound ------------------------------
def test_status_message_is_bound() -> None:
    source = inspect.getsource(PS.advance_transition_lifecycle)
    assert 'status_message("COMPLETE", "local_target_dwell", now)' in source


def test_lifecycle_status_agreement_is_bound_not_reimplemented() -> None:
    source = inspect.getsource(PS.advance_transition_lifecycle)
    assert "evaluate_lifecycle_status_agreement" in source
    tree = ast.parse(inspect.getsource(PS))
    assert not any(isinstance(n, ast.FunctionDef)
                   and "lifecycle_status" in n.name for n in ast.walk(tree)), (
        "the frozen agreement must be called, never recreated")


def test_no_centralized_completion_shortcut_exists() -> None:
    import pathlib
    text = "\n".join(p.read_text(encoding="ascii")
                     for p in pathlib.Path("rvt_swarm/phase9c_rb").glob("*.py"))
    for forbidden in ("mark_complete_all", "complete_all_nodes", "finalize_all"):
        assert forbidden not in text, forbidden


# -- D13-G4 / D13-2: local dwell is necessary, not sufficient ------------------
def test_local_dwell_alone_does_not_complete_the_lifecycle() -> None:
    source = inspect.getsource(PS.advance_transition_lifecycle)
    assert "if not all(node.local_dwell_complete for node in nodes.values()):" in source
    assert "local dwell is necessary, not sufficient" in source


def test_completion_records_local_dwell_and_agreement_times_separately() -> None:
    session = _run_to_completion()
    assert session.completion_agreements, "no distributed completion was recorded"
    record = session.completion_agreements[0]
    assert record["agreed"] is True
    assert record["reason"] == "lifecycle_status_agreed"
    assert record["status_agreement_time_seconds"] > record[
        "local_dwell_complete_time_seconds"], (
        "completion must be decided after status agreement, not at local dwell")


def test_the_agreement_delay_equals_the_frozen_confirm_round_budget() -> None:
    session = _run_to_completion()
    record = session.completion_agreements[0]
    config = session.runtime_config
    expected = (float(config.derived.k_confirm_rounds)
                * float(config.communication.communication_period_seconds))
    delta = (record["status_agreement_time_seconds"]
             - record["local_dwell_complete_time_seconds"])
    assert delta == pytest.approx(expected), (delta, expected)


def test_mark_complete_is_reached_only_through_the_agreement_branch() -> None:
    source = inspect.getsource(PS.advance_transition_lifecycle)
    index = source.index("protocol_node.mark_complete(")   # the call, not the docstring
    preceding = source[:index]
    assert "if agreement.agreed:" in preceding
    assert preceding.rindex("if agreement.agreed:") > preceding.rindex(
        "evaluate_lifecycle_status_agreement")


def test_the_lifecycle_actually_reaches_complete() -> None:
    session = _run_to_completion()
    assert all(r.protocol_node.state == "COMPLETE" for r in session.robots)
    assert {r.committed_topology for r in session.robots} == {LINE}


# -- D13-G9: snapshot carries distributed-completion state --------------------
def test_completion_agreements_are_snapshot_and_restored() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_state
    session = _run_to_completion()
    state = canonical_execution_state(session)
    assert "completion_agreements" in state["mission_and_evaluator"]
    snap = snapshot(session)
    session.completion_agreements.append({"injected": True})
    assert snap.restore().completion_agreements == snap.canonical_state[
        "mission_and_evaluator"]["completion_agreements"]


def test_snapshot_before_agreement_reproduces_the_completion_trace() -> None:
    session = build_session("train-f1-00", policy_id=P.S2)
    for _ in range(500):
        session.step()
        if session.termination is not None:
            break
        if any(r.protocol_node.state == "TARGET_DWELL" for r in session.robots):
            break
    assert not session.completion_agreements, "snapshot must precede agreement"
    snap = snapshot(session)
    restored = snap.restore()
    for _ in range(40):
        session.step()
        restored.step()
        assert canonical_execution_hash(session) == canonical_execution_hash(restored)
    assert session.completion_agreements == restored.completion_agreements


# -- D13-G10: multi-epoch status isolation ------------------------------------
def test_each_epoch_records_its_own_completion_agreement() -> None:
    from tests.test_phase9c_two_epoch_transition import _run_epoch, _s2_after_first_epoch
    session = _s2_after_first_epoch()
    assert len(session.completion_agreements) == 1
    assert _run_epoch(session, COMPACT)
    assert len(session.completion_agreements) == 2
    first, second = session.completion_agreements
    assert first["lifecycle_id"] != second["lifecycle_id"]
    assert first["epoch_id"] != second["epoch_id"]
    assert second["status_agreement_time_seconds"] > first["status_agreement_time_seconds"]


def test_f8_completion_uses_the_degraded_channel(monkeypatch) -> None:
    """Status messages are not special-cased to be reliable."""
    session = build_session("train-f8-01", policy_id=P.S2, team_size=6)
    source = inspect.getsource(PS.advance_transition_lifecycle)
    # The completion flood uses the same adjacency as every other phase, which
    # `_adjacency` builds from the range-gated, cut-aware channel.
    assert "flood_transition_messages(\n            member_ids, completion_messages, adjacency," in source
