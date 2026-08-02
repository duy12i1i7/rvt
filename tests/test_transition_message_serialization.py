from dataclasses import replace

import pytest

from rvt_swarm.decentralized.transition_messages import (
    TRANSITION_PROTOCOL_SCHEMA_VERSION,
    CandidateScoreMessage,
    ConfirmationMessage,
    LifecycleStatusMessage,
    ReadinessMessage,
    TransitionByteLedger,
    TransitionIntent,
    TransitionMessageError,
    deserialize_transition_message,
)


def _messages():
    intent = TransitionIntent.create(
        1, 0, 0, 2, "externally_forced_diagnostic", 0.0, 10.0
    )
    return (
        intent,
        CandidateScoreMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, intent.epoch_id, 0, 2,
            1.0, "bounded_diagnostic", 1.0, True,
        ),
        ReadinessMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, intent.epoch_id, 0, 0, 2,
            "SAFE", 0.5, 2.0, True,
        ),
        ConfirmationMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, intent.epoch_id, 0, 0, 2,
            "ACCEPT", 3.0, True,
        ),
        LifecycleStatusMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION, 1, intent.epoch_id, 0, 0, 2,
            "COMMITTED", "unanimous_confirmation", 4.0, True,
        ),
    )


@pytest.mark.parametrize("index", range(5))
def test_every_message_round_trips_and_counts_actual_bytes(index):
    message = _messages()[index]
    frame = message.payload_bytes()
    assert deserialize_transition_message(frame) == message
    ledger = TransitionByteLedger()
    ledger.record(message.message_type, 0, frame)
    assert ledger.total_bytes == len(frame)


@pytest.mark.parametrize("mutation", ("payload", "digest", "truncated", "trailing"))
def test_tampered_or_malformed_frames_are_rejected(mutation):
    frame = bytearray(_messages()[0].payload_bytes())
    if mutation == "payload":
        frame[20] ^= 0x01
    elif mutation == "digest":
        frame[-1] ^= 0x01
    elif mutation == "truncated":
        del frame[-1]
    else:
        frame.extend(b"x")
    with pytest.raises(TransitionMessageError):
        deserialize_transition_message(bytes(frame))


def test_wrong_schema_is_rejected_at_construction():
    intent = _messages()[0]
    with pytest.raises(TransitionMessageError):
        replace(intent, protocol_schema="wrong/v1")
