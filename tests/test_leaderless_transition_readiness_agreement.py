import pytest

from rvt_swarm.decentralized.transition_messages import (
    TRANSITION_PROTOCOL_SCHEMA_VERSION,
    ReadinessMessage,
    TransitionIntent,
)
from rvt_swarm.decentralized.transition_protocol import (
    evaluate_readiness_agreement,
    flood_transition_messages,
)
from rvt_swarm.decentralized.transition_runtime import communication_graph


def _messages(intent, states):
    return {
        robot_id: (ReadinessMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION, intent.lifecycle_id,
            intent.epoch_id, robot_id, intent.source_topology,
            intent.candidate_topology, state,
            0.5 if state == "SAFE" else -0.1, 0.0, True,
        ),)
        for robot_id, state in enumerate(states)
    }


@pytest.mark.parametrize("states,agreed,aggregate", [
    (("SAFE",) * 5, True, "SAFE"),
    (("SAFE", "SAFE", "UNSAFE", "SAFE", "SAFE"), False, "UNSAFE"),
    (("SAFE", "SAFE", "UNKNOWN", "SAFE", "SAFE"), False, "UNKNOWN"),
])
def test_conservative_all_ready_lattice(states, agreed, aggregate):
    members = tuple(range(5))
    intent = TransitionIntent.create(
        1, 0, 2, 0, "local_opening", 0.0, 100.0
    )
    flood = flood_transition_messages(
        members, _messages(intent, states), communication_graph(5, "path"), 4
    )
    result = evaluate_readiness_agreement(
        flood, members, intent, now_seconds=1.0, maximum_age_seconds=10.0
    )
    assert result.agreed is agreed
    assert result.aggregate_readiness == aggregate


def test_disconnected_graph_and_stale_safe_block_whole_team_claim():
    members = tuple(range(5))
    intent = TransitionIntent.create(
        1, 0, 2, 0, "local_opening", 0.0, 100.0
    )
    messages = _messages(intent, ("SAFE",) * 5)
    disconnected = flood_transition_messages(
        members, messages, {i: () for i in members}, 4
    )
    assert not evaluate_readiness_agreement(
        disconnected, members, intent, now_seconds=1.0,
        maximum_age_seconds=10.0,
    ).agreed
    connected = flood_transition_messages(
        members, messages, communication_graph(5, "complete"), 1
    )
    assert not evaluate_readiness_agreement(
        connected, members, intent, now_seconds=10.0,
        maximum_age_seconds=1.0,
    ).agreed
