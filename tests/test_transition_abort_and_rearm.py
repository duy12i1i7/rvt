import pytest

from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.decentralized.transition_protocol import (
    TransitionProtocolError,
    TransitionProtocolNode,
    TransitionProtocolRuntimeOptions,
)


def test_abort_clears_no_mode_and_rearm_is_not_step_literal():
    config = RuntimeConfig.for_team_size(5)
    node = TransitionProtocolNode(
        0, tuple(range(5)), config, 0, TransitionProtocolRuntimeOptions(True)
    )
    intent = node.request_intent(1, 2, "externally_forced_diagnostic", 0.0)
    assert intent is not None
    node.adopt_intent(intent, 0.0)
    node.abort("readiness_timeout", 1.0)
    assert node.mode_epoch_count == 0
    assert node.committed_topology == 0
    assert not node.try_rearm(1.0 + config.protocol.rearm_inactive_seconds - 0.01)
    assert node.try_rearm(1.0 + config.protocol.rearm_inactive_seconds)


def test_active_lifecycle_cannot_be_silently_superseded():
    node = TransitionProtocolNode(
        0, tuple(range(5)), RuntimeConfig.for_team_size(5), 0,
        TransitionProtocolRuntimeOptions(True),
    )
    first = node.request_intent(1, 2, "externally_forced_diagnostic", 0.0)
    assert first is not None
    node.adopt_intent(first, 0.0)
    newer = type(first).create(
        2, 1, 0, 5, "externally_forced_diagnostic", 0.1, 10.0
    )
    assert not node.adopt_intent(newer, 0.1)
    assert node.state == "ABORTED"
    assert node.abort_cause == "active_lifecycle_cannot_be_superseded"


def test_disabled_protocol_rejects_online_request():
    node = TransitionProtocolNode(
        0, tuple(range(5)), RuntimeConfig.for_team_size(5), 0
    )
    with pytest.raises(TransitionProtocolError):
        node.request_intent(1, 2, "externally_forced_diagnostic", 0.0)
