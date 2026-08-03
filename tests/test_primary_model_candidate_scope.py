import pytest

from rvt_swarm.decentralized.online_topology_scope import (
    UNSUPPORTED_TRANSITION,
    request_publication_transition,
)
from rvt_swarm.decentralized.transition_protocol import (
    TransitionProtocolNode,
    TransitionProtocolRuntimeOptions,
)
from rvt_swarm.fd24.candidate_scope import (
    CANDIDATE_REJECTED,
    CHECKPOINT_COMPATIBLE,
    PRIMARY_MODEL_CANDIDATE_IDS,
    CandidateScore,
    authorize_primary_score_candidate,
    prepare_primary_score_agreement,
    primary_candidate_batch,
    validate_checkpoint_vocabulary,
    validate_primary_candidate_batch,
)
from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE, PRIMARY_TOPOLOGY_IDS


def _compact_node():
    return TransitionProtocolNode(
        0,
        tuple(range(5)),
        RuntimeConfig.for_team_size(5),
        COMPACT,
        TransitionProtocolRuntimeOptions(True),
    )


def test_primary_candidate_batch_contains_exactly_compact_and_line():
    assert PRIMARY_MODEL_CANDIDATE_IDS == (COMPACT, LINE)
    assert primary_candidate_batch() == (COMPACT, LINE)
    decision = validate_primary_candidate_batch((COMPACT, LINE))
    assert decision.admitted
    assert decision.canonical_candidate_ids == (COMPACT, LINE)


@pytest.mark.parametrize(
    "candidates",
    (
        (KEEP, COMPACT, LINE),
        (KEEP, LINE),
        (COMPACT,),
        (LINE,),
        (COMPACT, COMPACT),
    ),
)
def test_primary_candidate_batch_rejects_keep_missing_or_duplicate_entries(
    candidates,
):
    decision = validate_primary_candidate_batch(candidates)
    assert not decision.admitted


def test_keep_cannot_enter_primary_distributed_score_agreement():
    decision = authorize_primary_score_candidate(KEEP)
    assert decision.status == CANDIDATE_REJECTED
    assert not decision.admitted
    with pytest.raises(ValueError, match="exactly one COMPACT and one LINE"):
        prepare_primary_score_agreement(
            (
                CandidateScore(COMPACT, 0.7),
                CandidateScore(LINE, 0.8),
                CandidateScore(KEEP, 0.9),
            )
        )


def test_full_checkpoint_vocabulary_keeps_keep_inactive_for_compatibility():
    assert PRIMARY_TOPOLOGY_IDS == (KEEP, COMPACT, LINE)
    decision = validate_checkpoint_vocabulary(PRIMARY_TOPOLOGY_IDS)
    assert decision.status == CHECKPOINT_COMPATIBLE
    assert decision.compatible
    assert decision.activated_primary_candidate_ids == (COMPACT, LINE)
    assert decision.inactive_compatibility_ids == (KEEP,)


def test_candidate_order_is_irrelevant_and_output_order_is_canonical():
    decision = validate_primary_candidate_batch((LINE, COMPACT))
    assert decision.admitted
    assert decision.canonical_candidate_ids == (COMPACT, LINE)
    agreement = prepare_primary_score_agreement(
        (CandidateScore(LINE, 0.4), CandidateScore(COMPACT, 0.6))
    )
    assert tuple(
        item.candidate_topology for item in agreement.candidate_scores
    ) == (COMPACT, LINE)
    assert tuple(item.score for item in agreement.candidate_scores) == (0.6, 0.4)


def test_primary_publication_runtime_emits_no_keep_transition_request():
    node = _compact_node()
    result = request_publication_transition(
        node, 1, KEEP, "local_opening", 0.0
    )
    assert result.decision.status == UNSUPPORTED_TRANSITION
    assert result.intent is None
    assert node.active_intent is None
    assert node.mode_epoch_count == 0
