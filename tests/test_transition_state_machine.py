from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.decentralized.transition_protocol import (
    AgreementResult,
    TransitionProtocolNode,
    TransitionProtocolRuntimeOptions,
)


def _node():
    return TransitionProtocolNode(
        0, tuple(range(5)), RuntimeConfig.for_team_size(5), 0,
        TransitionProtocolRuntimeOptions(True),
    )


def _agreement(intent, *, readiness=None):
    return AgreementResult(
        True, "agreed", intent.lifecycle_id, intent.epoch_id,
        intent.candidate_topology,
        aggregate_score=1.0 if readiness is None else None,
        aggregate_readiness=readiness,
        aggregate_margin=0.5 if readiness else None,
        complete_membership=True,
    )


def test_authoritative_state_sequence_and_one_mode_epoch():
    node = _node()
    intent = node.request_intent(1, 2, "externally_forced_diagnostic", 0.0)
    assert intent is not None
    node.adopt_intent(intent, 0.0)
    node.begin_score_agreement(0.0)
    node.accept_score_agreement(_agreement(intent), 0.1)
    node.begin_all_ready_agreement(0.1)
    node.accept_all_ready(_agreement(intent, readiness="SAFE"), 0.2)
    node.accept_confirmation(_agreement(intent), 0.3)
    node.commit(0.3)
    assert node.committed_topology == 2
    assert node.mode_epoch_count == 1
    node.begin_execution(0.3)
    assert not node.observe_target_tube(True, 0.3)
    assert node.observe_target_tube(True, 3.3)
    node.mark_complete(3.3)
    assert node.state == "COMPLETE"
    assert node.try_rearm(7.05)
    assert node.state == "REARMED"


def test_unsafe_readiness_waits_without_new_epoch():
    node = _node()
    intent = node.request_intent(1, 5, "deterministic_local_fixture", 0.0)
    assert intent is not None
    node.adopt_intent(intent, 0.0)
    node.begin_score_agreement(0.0)
    node.accept_score_agreement(_agreement(intent), 0.1)
    node.begin_all_ready_agreement(0.1)
    blocked = AgreementResult(
        False, "readiness_unsafe", 1, intent.epoch_id, 5,
        aggregate_readiness="UNSAFE", aggregate_margin=-0.1,
        complete_membership=True,
    )
    node.accept_all_ready(blocked, 0.2)
    assert node.state == "WAITING_FOR_LOCAL_READINESS"
    assert node.committed_topology == 0
    assert node.mode_epoch_count == 0


def test_precommit_abort_retains_source_and_requires_rearm_time():
    node = _node()
    intent = node.request_intent(1, 2, "externally_forced_diagnostic", 0.0)
    assert intent is not None
    node.adopt_intent(intent, 0.0)
    node.abort("communication_timeout", 1.0)
    assert node.committed_topology == 0
    assert node.mode_epoch_count == 0
    assert not node.try_rearm(4.0)
    assert node.try_rearm(4.75)
