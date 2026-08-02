import pytest

from rvt_swarm.decentralized.transition_messages import TransitionIntent
from rvt_swarm.decentralized.transition_protocol import (
    evaluate_intent_propagation,
    flood_transition_messages,
)
from rvt_swarm.decentralized.transition_runtime import communication_graph


@pytest.mark.parametrize("n", (5, 8, 12, 16, 24))
@pytest.mark.parametrize(
    "family", ("path", "ring", "star", "sparse_random_connected", "complete")
)
def test_connected_graph_propagates_same_token_within_diameter(n, family):
    members = tuple(range(n))
    graph = communication_graph(n, family)
    from rvt_swarm.decentralized.transition_protocol import communication_graph_diameter
    rounds = communication_graph_diameter(members, graph)
    intent = TransitionIntent.create(
        1, n - 1, 0, 2, "externally_forced_diagnostic", 0.0, 100.0
    )
    flood = flood_transition_messages(members, {n - 1: (intent,)}, graph, rounds)
    result = evaluate_intent_propagation(
        flood, members, now_seconds=float(rounds), maximum_age_seconds=100.0
    )
    assert result.agreed
    assert all(len(flood.records_by_robot[robot_id]) == 1 for robot_id in members)


def test_disconnected_component_cannot_claim_whole_team_propagation():
    members = tuple(range(5))
    graph = {robot_id: () for robot_id in members}
    intent = TransitionIntent.create(
        1, 0, 0, 2, "externally_forced_diagnostic", 0.0, 100.0
    )
    flood = flood_transition_messages(members, {0: (intent,)}, graph, 4)
    assert not evaluate_intent_propagation(
        flood, members, now_seconds=1.0, maximum_age_seconds=100.0
    ).agreed


def test_conflicting_candidates_are_explicitly_rejected():
    members = tuple(range(5))
    graph = communication_graph(5, "complete")
    first = TransitionIntent.create(
        1, 0, 0, 2, "externally_forced_diagnostic", 0.0, 100.0
    )
    second = TransitionIntent.create(
        1, 1, 0, 5, "externally_forced_diagnostic", 0.0, 100.0
    )
    flood = flood_transition_messages(
        members, {0: (first,), 1: (second,)}, graph, 1
    )
    result = evaluate_intent_propagation(
        flood, members, now_seconds=1.0, maximum_age_seconds=100.0
    )
    assert not result.agreed
    assert "conflicting" in result.reason
