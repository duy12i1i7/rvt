import pytest

from rvt_swarm.decentralized.transition_messages import (
    TRANSITION_PROTOCOL_SCHEMA_VERSION,
    CandidateScoreMessage,
    TransitionIntent,
)
from rvt_swarm.decentralized.transition_protocol import (
    evaluate_score_agreement,
    flood_transition_messages,
)
from rvt_swarm.decentralized.transition_runtime import communication_graph


def _score(robot_id, intent, value, *, timestamp=0.0, valid=True):
    return CandidateScoreMessage(
        TRANSITION_PROTOCOL_SCHEMA_VERSION, intent.lifecycle_id, intent.epoch_id,
        robot_id, intent.candidate_topology,
        value if valid else None,
        "bounded_diagnostic" if valid else "unavailable",
        timestamp, valid,
    )


@pytest.mark.parametrize("values,agreed", [
    ((0.5, 0.7, 0.9, 0.6, 0.8), True),
    ((0.5, 0.7, -0.1, 0.6, 0.8), False),
    ((0.4, 0.4, 0.4, 0.4, 0.4), True),
])
def test_distributed_minimum_is_predeclared(values, agreed):
    members = tuple(range(5))
    intent = TransitionIntent.create(
        1, 0, 0, 2, "externally_forced_diagnostic", 0.0, 100.0
    )
    messages = {i: (_score(i, intent, value),) for i, value in enumerate(values)}
    flood = flood_transition_messages(
        members, messages, communication_graph(5, "path"), 4
    )
    result = evaluate_score_agreement(
        flood, members, intent, now_seconds=1.0,
        maximum_age_seconds=10.0, threshold=0.0,
    )
    assert result.agreed is agreed
    assert result.aggregate_score == min(values)


def test_unavailable_stale_and_disconnected_score_sets_block():
    members = tuple(range(5))
    intent = TransitionIntent.create(
        1, 0, 0, 2, "externally_forced_diagnostic", 0.0, 100.0
    )
    messages = {i: (_score(i, intent, 1.0),) for i in members}
    messages[4] = (_score(4, intent, 0.0, valid=False),)
    flood = flood_transition_messages(
        members, messages, communication_graph(5, "complete"), 1
    )
    assert not evaluate_score_agreement(
        flood, members, intent, now_seconds=1.0,
        maximum_age_seconds=10.0, threshold=0.0,
    ).agreed
    disconnected = flood_transition_messages(
        members, messages, {i: () for i in members}, 4
    )
    assert not evaluate_score_agreement(
        disconnected, members, intent, now_seconds=1.0,
        maximum_age_seconds=10.0, threshold=0.0,
    ).agreed
