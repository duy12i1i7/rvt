from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.decentralized.transition_messages import TransitionIntent
from rvt_swarm.decentralized.transition_protocol import (
    TransitionProtocolNode,
    TransitionProtocolRuntimeOptions,
)


def test_canonical_event_identity_excludes_originator_authority():
    first = TransitionIntent.create(
        3, 0, 0, 2, "local_constriction", 1.0, 5.0
    )
    second = TransitionIntent.create(
        3, 4, 0, 2, "local_constriction", 1.0, 5.0
    )
    assert first.token_hash == second.token_hash
    assert first.epoch_id == second.epoch_id
    assert first.originator_robot_id != second.originator_robot_id


def test_intent_cannot_change_committed_topology_or_bypass_phases():
    node = TransitionProtocolNode(
        1, tuple(range(5)), RuntimeConfig.for_team_size(5), 0,
        TransitionProtocolRuntimeOptions(True),
    )
    intent = TransitionIntent.create(
        1, 0, 0, 5, "externally_forced_diagnostic", 0.0, 10.0
    )
    node.adopt_intent(intent, 0.0)
    assert node.committed_topology == 0
    assert node.mode_epoch_count == 0


def test_duplicate_canonical_intent_does_not_restart_lifecycle():
    node = TransitionProtocolNode(
        1, tuple(range(5)), RuntimeConfig.for_team_size(5), 0,
        TransitionProtocolRuntimeOptions(True),
    )
    first = TransitionIntent.create(
        1, 0, 0, 2, "local_constriction", 0.0, 10.0
    )
    duplicate = TransitionIntent.create(
        1, 4, 0, 2, "local_constriction", 0.0, 10.0
    )
    assert node.adopt_intent(first, 0.0)
    entered = node.state_entered_seconds
    assert not node.adopt_intent(duplicate, 0.1)
    assert node.state_entered_seconds == entered
    assert node.duplicate_intent_count == 1
