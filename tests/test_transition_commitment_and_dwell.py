from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.decentralized.transition_protocol import (
    AgreementResult,
    TransitionProtocolNode,
    TransitionProtocolRuntimeOptions,
)


def _committed_node():
    node = TransitionProtocolNode(
        0, tuple(range(5)), RuntimeConfig.for_team_size(5), 0,
        TransitionProtocolRuntimeOptions(True),
    )
    intent = node.request_intent(1, 2, "externally_forced_diagnostic", 0.0)
    assert intent is not None
    node.adopt_intent(intent, 0.0)
    node.begin_score_agreement(0.0)
    node.accept_score_agreement(AgreementResult(
        True, "score", 1, intent.epoch_id, 2, aggregate_score=1.0,
        complete_membership=True,
    ), 0.1)
    node.begin_all_ready_agreement(0.1)
    node.accept_all_ready(AgreementResult(
        True, "ready", 1, intent.epoch_id, 2,
        aggregate_readiness="SAFE", aggregate_margin=0.5,
        complete_membership=True,
    ), 0.2)
    node.accept_confirmation(AgreementResult(
        True, "confirmed", 1, intent.epoch_id, 2,
        complete_membership=True,
    ), 0.3)
    node.commit(0.3)
    node.begin_execution(0.3)
    return node


def test_target_dwell_uses_physical_seconds_and_resets_on_exit():
    node = _committed_node()
    assert not node.observe_target_tube(True, 1.0)
    assert not node.observe_target_tube(False, 2.0)
    assert not node.observe_target_tube(True, 3.0)
    assert not node.observe_target_tube(True, 5.9)
    assert node.observe_target_tube(True, 6.0)
    node.mark_complete(6.0)
    assert node.state == "COMPLETE"
    assert node.mode_epoch_count == 1
