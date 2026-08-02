import pytest

from rvt_swarm.decentralized.transition_messages import (
    TRANSITION_PROTOCOL_SCHEMA_VERSION,
    ConfirmationMessage,
    TransitionIntent,
)
from rvt_swarm.decentralized.transition_protocol import (
    evaluate_confirmation_agreement,
    flood_transition_messages,
)
from rvt_swarm.decentralized.transition_runtime import communication_graph


def _confirmations(intent, decisions):
    return {
        robot_id: (ConfirmationMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION, intent.lifecycle_id,
            intent.epoch_id, robot_id, intent.source_topology,
            intent.candidate_topology, decision, 0.0, True,
        ),)
        for robot_id, decision in enumerate(decisions)
    }


@pytest.mark.parametrize("family", ("path", "ring", "star", "complete"))
def test_unanimous_confirmation_reaches_every_robot(family):
    members = tuple(range(5))
    intent = TransitionIntent.create(
        1, 0, 0, 5, "externally_forced_diagnostic", 0.0, 100.0
    )
    from rvt_swarm.decentralized.transition_protocol import communication_graph_diameter
    graph = communication_graph(5, family)
    flood = flood_transition_messages(
        members, _confirmations(intent, ("ACCEPT",) * 5), graph,
        communication_graph_diameter(members, graph),
    )
    assert evaluate_confirmation_agreement(
        flood, members, intent, now_seconds=1.0, maximum_age_seconds=10.0
    ).agreed


def test_path_endpoint_dissenter_and_stale_confirmation_block():
    members = tuple(range(5))
    intent = TransitionIntent.create(
        1, 0, 0, 5, "externally_forced_diagnostic", 0.0, 100.0
    )
    messages = _confirmations(intent, ("ACCEPT",) * 4 + ("DISSENT",))
    flood = flood_transition_messages(
        members, messages, communication_graph(5, "path"), 4
    )
    assert not evaluate_confirmation_agreement(
        flood, members, intent, now_seconds=1.0, maximum_age_seconds=10.0
    ).agreed
    stale = flood_transition_messages(
        members, _confirmations(intent, ("ACCEPT",) * 5),
        communication_graph(5, "complete"), 1,
    )
    assert not evaluate_confirmation_agreement(
        stale, members, intent, now_seconds=10.0, maximum_age_seconds=1.0
    ).agreed
