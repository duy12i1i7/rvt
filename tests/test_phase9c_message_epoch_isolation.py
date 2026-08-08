"""PCA-8 -- message epoch and freshness isolation.

Structural note established by this file: the publication adapter does not carry
a persistent agreement-message queue across control steps. Each protocol phase
constructs its messages fresh from the nodes' *current* lifecycle state and
floods them synchronously over the current adjacency. There is therefore no
cross-epoch message reservoir that could contaminate a later epoch -- the
isolation is structural, not merely filtered.

Because the frozen validators are what would reject a stale or wrong-epoch
message if one ever were presented, they are exercised directly here with
genuinely constructed messages.
"""
from __future__ import annotations
import ast, inspect, pytest
from rvt_swarm.decentralized.transition_messages import (
    TransitionMessageError, validate_message_context,
)
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb import protocol_session as PS
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_two_epoch_transition import _run_epoch, _s2_after_first_epoch


def _epoch_one_messages(session):
    """Genuine epoch-1 messages built by the frozen node methods."""
    node = session.robots[0].protocol_node
    return node


# -- structural isolation ------------------------------------------------------
def test_the_adapter_keeps_no_cross_step_agreement_message_queue() -> None:
    source = inspect.getsource(PS.advance_transition_lifecycle)
    # Every phase builds `initial = {...}` fresh from current node state.
    assert source.count("initial = {") >= 3
    assert "self.pending_messages" not in source
    assert "message_backlog" not in source


def test_no_manual_queue_clearing_is_performed() -> None:
    import pathlib
    text = "\n".join(p.read_text(encoding="ascii")
                     for p in pathlib.Path("rvt_swarm/phase9c_rb").glob("*.py"))
    for forbidden in ("purge_messages", "drop_stale_messages", "clear_agreement_queue"):
        assert forbidden not in text, forbidden


# -- PCA-8A/8B/8C/8D: wrong-epoch messages are rejected by the frozen validator
@pytest.mark.parametrize("builder,label", [
    (lambda n, t: n.score_message(1.0, "bounded_diagnostic", t), "score"),
    (lambda n, t: n.readiness_message("SAFE", 0.0, t), "readiness"),
    (lambda n, t: n.confirmation_message("ACCEPT", t), "confirmation"),
    (lambda n, t: n.status_message("COMPLETE", "local_target_dwell", t), "complete_status"),
])
def test_a_message_from_a_previous_epoch_is_rejected(builder, label) -> None:
    session = _s2_after_first_epoch()
    node = session.robots[0].protocol_node
    intent = session.completion_agreements[0]
    # The node still carries epoch 1's identifiers at this point.
    message = builder(node, session.time_seconds)
    assert message.epoch_id == intent["epoch_id"], label
    # Present it against a *different* epoch, as a delayed delivery would be.
    with pytest.raises(TransitionMessageError):
        validate_message_context(
            message, member_ids=tuple(range(session.team_size)),
            lifecycle_id=int(intent["lifecycle_id"]) + 1,
            epoch_id=int(intent["epoch_id"]) + 1,
            now_seconds=session.time_seconds,
            maximum_age_seconds=float(
                session.runtime_config.communication.maximum_message_age_seconds))


# -- PCA-8E: same-epoch but stale beyond the frozen age bound -----------------
def test_a_same_epoch_message_beyond_the_frozen_age_bound_is_rejected() -> None:
    session = _s2_after_first_epoch()
    node = session.robots[0].protocol_node
    record = session.completion_agreements[0]
    maximum_age = float(session.runtime_config.communication.maximum_message_age_seconds)
    message = node.score_message(1.0, "bounded_diagnostic", session.time_seconds)
    with pytest.raises(TransitionMessageError):
        validate_message_context(
            message, member_ids=tuple(range(session.team_size)),
            lifecycle_id=int(record["lifecycle_id"]), epoch_id=int(record["epoch_id"]),
            now_seconds=session.time_seconds + maximum_age * 2.0,
            maximum_age_seconds=maximum_age)


def test_a_fresh_same_epoch_message_is_accepted() -> None:
    """Non-vacuity: the validator must not reject everything."""
    session = _s2_after_first_epoch()
    node = session.robots[0].protocol_node
    record = session.completion_agreements[0]
    message = node.score_message(1.0, "bounded_diagnostic", session.time_seconds)
    validate_message_context(
        message, member_ids=tuple(range(session.team_size)),
        lifecycle_id=int(record["lifecycle_id"]), epoch_id=int(record["epoch_id"]),
        now_seconds=session.time_seconds,
        maximum_age_seconds=float(
            session.runtime_config.communication.maximum_message_age_seconds))


def test_the_frozen_age_bound_is_not_redefined_in_the_adapter() -> None:
    import pathlib
    text = "\n".join(p.read_text(encoding="ascii")
                     for p in pathlib.Path("rvt_swarm/phase9c_rb").glob("*.py"))
    assert "maximum_message_age_seconds" in text
    assert "0.45" not in text, "the frozen freshness bound must not be duplicated"


# -- PCA-8F: duplicate delivery is idempotent ---------------------------------
def test_duplicate_epoch_two_execution_does_not_double_count() -> None:
    session = _s2_after_first_epoch()
    before_epochs = {r.protocol_node.mode_epoch_count for r in session.robots}
    before_agreements = len(session.completion_agreements)
    assert _run_epoch(session, COMPACT)
    assert {r.protocol_node.mode_epoch_count for r in session.robots} == {
        before_epochs.pop() + 1}
    assert len(session.completion_agreements) == before_agreements + 1
    # A second request for the topology already committed must be refused.
    assert session.request_candidate(
        session.robots[0], COMPACT, "externally_forced_diagnostic") is False
    assert len(session.completion_agreements) == before_agreements + 1


# -- PCA-8G: F8 uses the same path ---------------------------------------------
def test_f8_lifecycle_messages_use_the_same_degraded_adjacency() -> None:
    source = inspect.getsource(PS._adjacency)
    assert "cut_active_at" in source and "physical_edge" in source
    lifecycle = inspect.getsource(PS.advance_transition_lifecycle)
    assert lifecycle.count("adjacency") >= 4, (
        "every agreement phase, including COMPLETE status, must flood over the "
        "same range-gated cut-aware adjacency")
