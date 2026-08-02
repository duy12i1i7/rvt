"""Versioned immutable wire messages for the Phase 7 transition protocol."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import ClassVar, Dict, Mapping, Optional, Tuple, Type, Union

from ..topology_registry import PRIMARY_TOPOLOGY_IDS


TRANSITION_PROTOCOL_SCHEMA_VERSION = "rvt-transition-protocol/v1"
TRANSITION_WIRE_MAGIC = b"RVTP1\0"
_HEADER = struct.Struct(">6sI")
_DIGEST_BYTES = 32

SCORE_SEMANTICS = (
    "probability_like",
    "bounded_diagnostic",
    "unavailable",
)
READINESS_STATES = ("SAFE", "UNSAFE", "UNKNOWN")
CONFIRMATION_DECISIONS = ("ACCEPT", "DISSENT")
LIFECYCLE_STATUSES = ("COMMITTED", "ABORTED", "COMPLETE", "REARMED")
EVENT_TYPES = (
    "externally_forced_diagnostic",
    "deterministic_local_fixture",
    "local_constriction",
    "local_opening",
)


class TransitionMessageError(ValueError):
    """A protocol message is malformed, tampered, stale, or out of context."""


def _finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise TransitionMessageError(f"{name} must be finite")
    return result


def _validate_common(
    schema: str,
    lifecycle_id: int,
    epoch_id: int,
    robot_id: int,
    timestamp: float,
    validity: bool,
) -> None:
    if schema != TRANSITION_PROTOCOL_SCHEMA_VERSION:
        raise TransitionMessageError("unknown transition protocol schema")
    for name, value, allow_zero in (
        ("lifecycle_id", lifecycle_id, False),
        ("epoch_id", epoch_id, False),
        ("robot_id", robot_id, True),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TransitionMessageError(f"{name} must be an integer")
        if value < (0 if allow_zero else 1):
            raise TransitionMessageError(f"{name} is outside its valid range")
    _finite(timestamp, "timestamp")
    if timestamp < 0.0:
        raise TransitionMessageError("timestamp must be nonnegative")
    if not isinstance(validity, bool):
        raise TransitionMessageError("validity must be Boolean")


def _validate_topology(topology_id: int, name: str) -> None:
    if topology_id not in PRIMARY_TOPOLOGY_IDS:
        raise TransitionMessageError(f"{name} is not a primary topology")


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise TransitionMessageError("message is not canonicalizable") from exc


def canonical_event_token_hash(
    lifecycle_id: int,
    source_topology: int,
    candidate_topology: int,
    event_type: str,
    event_timestamp: float,
    evidence_valid_until: float,
) -> str:
    """Canonical event identity deliberately excludes originator robot ID."""
    payload = {
        "protocol_schema": TRANSITION_PROTOCOL_SCHEMA_VERSION,
        "lifecycle_id": int(lifecycle_id),
        "source_topology": int(source_topology),
        "candidate_topology": int(candidate_topology),
        "event_type": str(event_type),
        "event_timestamp": float(event_timestamp),
        "evidence_valid_until": float(evidence_valid_until),
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def epoch_id_from_token_hash(token_hash: str) -> int:
    if len(token_hash) != 64:
        raise TransitionMessageError("token hash must be a SHA-256 hex digest")
    try:
        raw = bytes.fromhex(token_hash)
    except ValueError as exc:
        raise TransitionMessageError("token hash is not hexadecimal") from exc
    result = int.from_bytes(raw[:4], "big") & 0x7FFFFFFF
    return result or 1


class _WireMessage:
    message_type: ClassVar[str]

    def payload_bytes(self) -> bytes:
        return serialize_transition_message(self)  # type: ignore[arg-type]


@dataclass(frozen=True)
class TransitionIntent(_WireMessage):
    message_type: ClassVar[str] = "intent"
    protocol_schema: str
    lifecycle_id: int
    epoch_id: int
    originator_robot_id: int
    source_topology: int
    candidate_topology: int
    event_type: str
    event_timestamp: float
    evidence_valid_until: float
    token_hash: str
    validity: bool

    def __post_init__(self) -> None:
        _validate_common(
            self.protocol_schema,
            self.lifecycle_id,
            self.epoch_id,
            self.originator_robot_id,
            self.event_timestamp,
            self.validity,
        )
        _validate_topology(self.source_topology, "source topology")
        _validate_topology(self.candidate_topology, "candidate topology")
        if self.source_topology == self.candidate_topology:
            raise TransitionMessageError("source-equals-target intent is invalid")
        if self.event_type not in EVENT_TYPES:
            raise TransitionMessageError("unknown transition event type")
        expiry = _finite(self.evidence_valid_until, "evidence_valid_until")
        if expiry < self.event_timestamp:
            raise TransitionMessageError("intent evidence expires before its event")
        expected = canonical_event_token_hash(
            self.lifecycle_id,
            self.source_topology,
            self.candidate_topology,
            self.event_type,
            self.event_timestamp,
            self.evidence_valid_until,
        )
        if self.token_hash != expected:
            raise TransitionMessageError("intent token hash is invalid")
        if self.epoch_id != epoch_id_from_token_hash(self.token_hash):
            raise TransitionMessageError("intent epoch ID does not match token")

    @classmethod
    def create(
        cls,
        lifecycle_id: int,
        originator_robot_id: int,
        source_topology: int,
        candidate_topology: int,
        event_type: str,
        event_timestamp: float,
        evidence_valid_until: float,
        *,
        validity: bool = True,
    ) -> "TransitionIntent":
        token_hash = canonical_event_token_hash(
            lifecycle_id,
            source_topology,
            candidate_topology,
            event_type,
            event_timestamp,
            evidence_valid_until,
        )
        return cls(
            TRANSITION_PROTOCOL_SCHEMA_VERSION,
            int(lifecycle_id),
            epoch_id_from_token_hash(token_hash),
            int(originator_robot_id),
            int(source_topology),
            int(candidate_topology),
            str(event_type),
            float(event_timestamp),
            float(evidence_valid_until),
            token_hash,
            bool(validity),
        )


@dataclass(frozen=True)
class CandidateScoreMessage(_WireMessage):
    message_type: ClassVar[str] = "score"
    protocol_schema: str
    lifecycle_id: int
    epoch_id: int
    robot_id: int
    candidate_topology: int
    score: Optional[float]
    score_semantics: str
    timestamp: float
    validity: bool

    def __post_init__(self) -> None:
        _validate_common(
            self.protocol_schema,
            self.lifecycle_id,
            self.epoch_id,
            self.robot_id,
            self.timestamp,
            self.validity,
        )
        _validate_topology(self.candidate_topology, "candidate topology")
        if self.score_semantics not in SCORE_SEMANTICS:
            raise TransitionMessageError("unknown score semantics")
        if self.score_semantics == "unavailable":
            if self.score is not None or self.validity:
                raise TransitionMessageError("unavailable score must be null and invalid")
            return
        if self.score is None:
            raise TransitionMessageError("available score cannot be null")
        score = _finite(self.score, "score")
        lower, upper = ((0.0, 1.0) if self.score_semantics == "probability_like"
                        else (-1.0, 1.0))
        if score < lower or score > upper:
            raise TransitionMessageError("score is outside declared semantics")


@dataclass(frozen=True)
class ReadinessMessage(_WireMessage):
    message_type: ClassVar[str] = "readiness"
    protocol_schema: str
    lifecycle_id: int
    epoch_id: int
    robot_id: int
    source_topology: int
    candidate_topology: int
    readiness_state: str
    readiness_margin: float
    timestamp: float
    validity: bool

    def __post_init__(self) -> None:
        _validate_common(
            self.protocol_schema,
            self.lifecycle_id,
            self.epoch_id,
            self.robot_id,
            self.timestamp,
            self.validity,
        )
        _validate_topology(self.source_topology, "source topology")
        _validate_topology(self.candidate_topology, "candidate topology")
        if self.source_topology == self.candidate_topology:
            raise TransitionMessageError("readiness pair must change topology")
        if self.readiness_state not in READINESS_STATES:
            raise TransitionMessageError("unknown readiness state")
        _finite(self.readiness_margin, "readiness margin")


@dataclass(frozen=True)
class ConfirmationMessage(_WireMessage):
    message_type: ClassVar[str] = "confirmation"
    protocol_schema: str
    lifecycle_id: int
    epoch_id: int
    robot_id: int
    source_topology: int
    candidate_topology: int
    decision: str
    timestamp: float
    validity: bool

    def __post_init__(self) -> None:
        _validate_common(
            self.protocol_schema,
            self.lifecycle_id,
            self.epoch_id,
            self.robot_id,
            self.timestamp,
            self.validity,
        )
        _validate_topology(self.source_topology, "source topology")
        _validate_topology(self.candidate_topology, "candidate topology")
        if self.source_topology == self.candidate_topology:
            raise TransitionMessageError("confirmation pair must change topology")
        if self.decision not in CONFIRMATION_DECISIONS:
            raise TransitionMessageError("unknown confirmation decision")


@dataclass(frozen=True)
class LifecycleStatusMessage(_WireMessage):
    message_type: ClassVar[str] = "status"
    protocol_schema: str
    lifecycle_id: int
    epoch_id: int
    robot_id: int
    source_topology: int
    candidate_topology: int
    status: str
    cause: str
    timestamp: float
    validity: bool

    def __post_init__(self) -> None:
        _validate_common(
            self.protocol_schema,
            self.lifecycle_id,
            self.epoch_id,
            self.robot_id,
            self.timestamp,
            self.validity,
        )
        _validate_topology(self.source_topology, "source topology")
        _validate_topology(self.candidate_topology, "candidate topology")
        if self.status not in LIFECYCLE_STATUSES:
            raise TransitionMessageError("unknown lifecycle status")
        if not isinstance(self.cause, str) or not self.cause:
            raise TransitionMessageError("lifecycle status cause must be nonempty")


TransitionMessage = Union[
    TransitionIntent,
    CandidateScoreMessage,
    ReadinessMessage,
    ConfirmationMessage,
    LifecycleStatusMessage,
]

_MESSAGE_TYPES: Dict[str, Type[TransitionMessage]] = {
    cls.message_type: cls
    for cls in (
        TransitionIntent,
        CandidateScoreMessage,
        ReadinessMessage,
        ConfirmationMessage,
        LifecycleStatusMessage,
    )
}


def serialize_transition_message(message: TransitionMessage) -> bytes:
    if not isinstance(message, tuple(_MESSAGE_TYPES.values())):
        raise TypeError("unsupported transition message type")
    payload = _canonical_json_bytes({
        "message_type": message.message_type,
        "fields": asdict(message),
    })
    digest = hashlib.sha256(payload).digest()
    return _HEADER.pack(TRANSITION_WIRE_MAGIC, len(payload)) + payload + digest


def deserialize_transition_message(frame: bytes) -> TransitionMessage:
    if not isinstance(frame, (bytes, bytearray)):
        raise TypeError("transition frame must be bytes")
    raw = bytes(frame)
    if len(raw) < _HEADER.size + _DIGEST_BYTES:
        raise TransitionMessageError("transition frame is truncated")
    magic, payload_length = _HEADER.unpack(raw[:_HEADER.size])
    if magic != TRANSITION_WIRE_MAGIC:
        raise TransitionMessageError("transition wire magic is invalid")
    expected_length = _HEADER.size + payload_length + _DIGEST_BYTES
    if len(raw) != expected_length:
        raise TransitionMessageError("transition frame length is invalid")
    payload = raw[_HEADER.size:_HEADER.size + payload_length]
    digest = raw[-_DIGEST_BYTES:]
    if hashlib.sha256(payload).digest() != digest:
        raise TransitionMessageError("transition frame integrity check failed")
    try:
        decoded = json.loads(payload.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransitionMessageError("transition payload is malformed") from exc
    if not isinstance(decoded, dict) or set(decoded) != {"message_type", "fields"}:
        raise TransitionMessageError("transition payload envelope is invalid")
    message_type = decoded["message_type"]
    fields = decoded["fields"]
    cls = _MESSAGE_TYPES.get(message_type)
    if cls is None or not isinstance(fields, dict):
        raise TransitionMessageError("transition message type is unknown")
    try:
        return cls(**fields)  # type: ignore[arg-type,return-value]
    except (TypeError, ValueError) as exc:
        if isinstance(exc, TransitionMessageError):
            raise
        raise TransitionMessageError("transition payload fields are invalid") from exc


def message_identity(message: TransitionMessage) -> Tuple[object, ...]:
    if isinstance(message, TransitionIntent):
        return (message.message_type, message.lifecycle_id, message.epoch_id,
                message.token_hash)
    return (message.message_type, message.lifecycle_id, message.epoch_id,
            message.robot_id)


def validate_message_context(
    message: TransitionMessage,
    *,
    member_ids: Tuple[int, ...],
    lifecycle_id: int,
    epoch_id: int,
    now_seconds: float,
    maximum_age_seconds: float,
) -> None:
    robot_id = (message.originator_robot_id if isinstance(message, TransitionIntent)
                else message.robot_id)
    if robot_id not in member_ids:
        raise TransitionMessageError("message robot ID is outside fixed membership")
    if message.lifecycle_id != lifecycle_id or message.epoch_id != epoch_id:
        raise TransitionMessageError("message lifecycle or epoch is stale")
    timestamp = (message.event_timestamp if isinstance(message, TransitionIntent)
                 else message.timestamp)
    if now_seconds < timestamp or now_seconds - timestamp > maximum_age_seconds:
        raise TransitionMessageError("message timestamp is stale")
    if isinstance(message, TransitionIntent) and now_seconds > message.evidence_valid_until:
        raise TransitionMessageError("intent evidence has expired")
    if not message.validity:
        raise TransitionMessageError("message is explicitly invalid")


@dataclass(frozen=True)
class TransitionByteRecord:
    phase: str
    sender_id: int
    receiver_id: Optional[int]
    retransmission: bool
    n_bytes: int


class TransitionByteLedger:
    """Actual frame-byte accounting with no integer-only recording API."""

    def __init__(self) -> None:
        self._records: list[TransitionByteRecord] = []

    def record(
        self,
        phase: str,
        sender_id: int,
        frame: bytes,
        *,
        receiver_id: Optional[int] = None,
        retransmission: bool = False,
    ) -> None:
        if phase not in _MESSAGE_TYPES:
            raise ValueError("unknown transition message phase")
        decoded = deserialize_transition_message(frame)
        if decoded.message_type != phase:
            raise ValueError("accounting phase does not match serialized message")
        self._records.append(TransitionByteRecord(
            phase,
            int(sender_id),
            None if receiver_id is None else int(receiver_id),
            bool(retransmission),
            len(frame),
        ))

    @property
    def records(self) -> Tuple[TransitionByteRecord, ...]:
        return tuple(self._records)

    @property
    def total_bytes(self) -> int:
        return sum(record.n_bytes for record in self._records)

    def report(self) -> Mapping[str, object]:
        by_phase: Dict[str, int] = defaultdict(int)
        by_robot: Dict[int, int] = defaultdict(int)
        retransmission = 0
        for record in self._records:
            by_phase[record.phase] += record.n_bytes
            by_robot[record.sender_id] += record.n_bytes
            if record.retransmission:
                retransmission += record.n_bytes
        return {
            "bytes_by_phase": dict(sorted(by_phase.items())),
            "bytes_by_robot": dict(sorted(by_robot.items())),
            "total_bytes": self.total_bytes,
            "retransmission_bytes": retransmission,
            "message_count": len(self._records),
        }
