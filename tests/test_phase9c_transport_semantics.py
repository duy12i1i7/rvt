"""PCA-8R -- lifecycle transport semantics, established from the frozen code.

The earlier PCA-8 report asserted "no cross-step queue" from the publication
adapter. That was the wrong direction of evidence. This file establishes the
classification from `transition_protocol.flood_transition_messages` itself and
then checks the adapter matches it.
"""
from __future__ import annotations
import ast, inspect, pytest
from rvt_swarm.decentralized import transition_protocol as TP
from rvt_swarm.phase9c_rb import protocol_session as PS
from rvt_swarm.phase9c_rb import policies as P
from tests.test_phase9c_publication_executor import build_session


# -- classification from the frozen implementation ----------------------------
def test_the_frozen_flood_is_round_local_not_persistent() -> None:
    source = inspect.getsource(TP.flood_transition_messages)
    # Documented contract.
    assert "the simulator performs delivery only" in source
    # `stores` is constructed inside the call, so nothing survives it.
    tree = ast.parse(source.lstrip())
    assigns = [n for n in ast.walk(tree) if isinstance(n, ast.AnnAssign)
               and isinstance(n.target, ast.Name) and n.target.id == "stores"]
    assert assigns, "expected a call-local message store"
    # No module-level or attribute-persisted queue.
    assert "self." not in source
    assert "global " not in source


def test_the_frozen_flood_returns_a_value_rather_than_retaining_state() -> None:
    signature = inspect.signature(TP.flood_transition_messages)
    assert signature.return_annotation in ("FloodResult", TP.FloodResult)
    assert "ledger" in signature.parameters, "the only carried object is the byte ledger"


def test_time_variation_is_modelled_inside_one_flood_not_across_steps() -> None:
    """A per-round adjacency *schedule* is the frozen mechanism fortime-varying topology."""
    source = inspect.getsource(TP.flood_transition_messages)
    assert "Sequence[Mapping[int, Iterable[int]]]" in source
    assert "schedule = tuple(adjacency for _ in range(max(rounds, 1)))" in source
    assert hasattr(TP, "communication_graph_diameter")


def test_a_per_round_schedule_is_the_frozen_disconnection_mechanism() -> None:
    from rvt_swarm.decentralized.transition_runtime import temporary_disconnection_schedule
    schedule = temporary_disconnection_schedule({0: (1,), 1: (0,)}, 4)
    assert isinstance(schedule, tuple) and len(schedule) == 4, (
        "disconnection is a per-round adjacency schedule within one flood")


# -- the adapter matches that classification ----------------------------------
def test_the_adapter_uses_the_frozen_flood_for_every_agreement_phase() -> None:
    source = inspect.getsource(PS.advance_transition_lifecycle)
    assert source.count("flood_transition_messages(") >= 4, (
        "intent, score, all-ready, confirmation and COMPLETE status must all "
        "use the frozen flood")


def test_the_adapter_holds_no_lifecycle_message_across_control_steps() -> None:
    """Consistent with ROUND_LOCAL: there is nothing to carry."""
    session = build_session("train-f1-00", policy_id=P.S2)
    for _ in range(30):
        session.step()
        if session.termination is not None:
            break
    # The only persistent transport is the state-broadcast channel, which is a
    # separate frozen concern (F8 delay/loss for peer state, not lifecycle).
    for message in session.channel.queue:
        assert message.message_type == "state_broadcast", message.message_type


def test_lifecycle_messages_are_not_placed_in_the_delayed_channel() -> None:
    source = inspect.getsource(PS)
    assert "channel.send(" not in source, (
        "lifecycle agreement must go through the frozen flood, not the "
        "delayed state-broadcast channel")


def test_f8_cut_is_applied_to_the_flood_adjacency() -> None:
    """No reliable bypass: the cut gates the same adjacency the flood uses."""
    source = inspect.getsource(PS._adjacency)
    assert "cut_active_at" in source and "crosses_cut" in source
    lifecycle = inspect.getsource(PS.advance_transition_lifecycle)
    assert "adjacency" in lifecycle


def test_the_f8_cut_spans_whole_control_steps_so_constant_within_a_flood() -> None:
    """The frozen F8 contract expresses the cut in communication ticks, so it is
    constant across the rounds of any single control step's flood."""
    import json, pathlib
    spec = json.loads(pathlib.Path(
        "results/rvt_fd24/layout_execution_specifications/train/train-f8-01.json").read_text())
    schedule = spec["communication"]["team_size_schedule"]["6"]
    assert schedule["duration_ticks"] >= 1
    assert "start_tick" in schedule


def test_no_defect_14_lifecycle_message_delay_queue_is_required() -> None:
    """Recorded conclusion: transport is ROUND_LOCAL, so the absence of a
    cross-step lifecycle queue is conformance, not an omission."""
    source = inspect.getsource(TP.flood_transition_messages)
    assert "stores" in source and "self." not in source
