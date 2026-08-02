import pytest

from rvt_swarm.decentralized.transition_messages import (
    TRANSITION_PROTOCOL_SCHEMA_VERSION,
    CandidateScoreMessage,
    TransitionMessageError,
)


def test_score_semantics_are_explicit_and_bounded():
    message = CandidateScoreMessage(
        TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, 7, 0, 2,
        0.75, "bounded_diagnostic", 1.0, True,
    )
    assert message.score == 0.75
    assert "learned" not in message.score_semantics
    CandidateScoreMessage(
        TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, 7, 0, 2,
        0.9, "probability_like", 1.0, True,
    )


def test_unavailable_score_has_no_scalar_and_is_invalid():
    message = CandidateScoreMessage(
        TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, 7, 0, 2,
        None, "unavailable", 1.0, False,
    )
    assert message.score is None
    with pytest.raises(TransitionMessageError):
        CandidateScoreMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, 7, 0, 2,
            0.0, "unavailable", 1.0, True,
        )


@pytest.mark.parametrize("score", (-1.01, 1.01, float("nan")))
def test_invalid_diagnostic_scores_are_rejected(score):
    with pytest.raises(TransitionMessageError):
        CandidateScoreMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, 7, 0, 2,
            score, "bounded_diagnostic", 1.0, True,
        )
