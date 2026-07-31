"""Communication cost accounting for the fully decentralized selector.

The question this module answers is "what does the decentralized selector cost
on the air?", and it answers it in bytes of a **declared, fixed-size wire
format** -- never in Python objects, never in `sys.getsizeof`, never in an
estimate.

Three rules make the numbers auditable:

1. **Every byte count is the length of a real encoding.** The only way to put
   a message into a `MessageAccountant` is to hand it the actual `bytes` that
   the message serialises to (`record_sent_bytes` takes `payload: bytes`, not
   an integer). There is no code path that accepts a byte *count*, so a
   fabricated number cannot enter the ledger.
2. **The encoding must match the declared schema.** Recording a payload whose
   length differs from `WIRE_SCHEMAS[type].size_bytes` raises `ValueError`.
   Every message type here is fixed-size by construction -- none has a
   list-valued field -- so a schema change cannot silently pass unnoticed.
3. **Totals are cross-checked against the payloads.** The accountant keeps the
   encoded payloads and `assert_consistent()` asserts
   ``sum(len(p) for p in payloads) == total_bytes`` as well as
   totals == sum over types == sum over robots == sum over decisions == sum
   over steps.

Message types
-------------
Four, matching the protocol in `docs/FULLY_DECENTRALIZED_SYSTEM_MODEL.md`:

===================  =========================================================
`beacon`             one-hop discovery beacon, one per robot per comm period
`trigger`            max-consensus decision trigger / epoch reconciliation
`score_consensus`    Metropolis-Hastings score averaging, `k_score` rounds
`mode_confirmation`  min/max-consensus mode confirmation, `k_confirm` rounds
===================  =========================================================

Schema provenance
-----------------
`beacon` and `score_consensus` are **measured**: `Beacon` declares its own
`payload_bytes()` in `comms.py` (49 bytes, verified by
`verify_schema_sizes()`), and `ScoreMessage` is defined in `consensus.py` with
an exact field list from which the encoding here is derived.

`trigger` and `mode_confirmation` were PROVISIONAL -- declared here from the
protocol field lists while `rvt_swarm/decentralized/epoch.py` did not exist --
and were **wrong**: 16 and 17 bytes against real encodings of 21 and 16. They
are now bound to `epoch.TriggerMessage.payload_bytes()` and
`epoch.ConfirmMessage.payload_bytes()`, and `_sample_messages()` builds its
samples from those classes, so a future divergence is a hard failure rather
than a silently skipped sample.

**Schema-verified is not the same as measured.** No trigger or confirmation
message is sent anywhere in the system yet: `runtime.py` does not import
`epoch.py`. Those two rows are a per-message byte cost and a message count of
zero, and that zero means *never sent*, not *free*. `pending` is True for any
category with no recorded message, and `format_report` marks the row
`[PENDING]`; a report must be read that way.

Deployability
-------------
Accounting is instrumentation, not robot code: a real robot does not need to
know the swarm's byte total. The accountant is therefore an offline analysis
object. The two instrumented subclasses (`_AccountingRadioChannel`,
`_AccountingConsensusNode`) exist only to observe the messages that the
existing simulation actually sends, so the ledger records deliveries and
transmissions that really happened rather than a recomputation of what should
have happened. `simulate_episode_message_cost` carries the `simulate_` boundary
prefix because it reads the environment's joint state.
"""

from __future__ import annotations

import importlib
import struct
from dataclasses import dataclass, field
from typing import (Dict, Iterable, List, Optional, Sequence, Set, Tuple)

from .comms import (Beacon, NeighbourTable, OwnHistory, RadioChannel,
                    RobotRadioState, simulate_broadcast_round)
from .consensus import ConsensusNode, ScoreMessage, simulate_consensus
from .guards import offline_diagnostic
from .roles import RoleAssignment
from .system_model import KEEP, LINE, CommParams, ConsensusParams

Vec2 = Tuple[float, float]

# ---------------------------------------------------------------------------
# Message type names. Fixed vocabulary; the accountant rejects anything else.
# ---------------------------------------------------------------------------
BEACON = "beacon"
TRIGGER = "trigger"
SCORE = "score_consensus"
CONFIRM = "mode_confirmation"
MESSAGE_TYPES: Tuple[str, ...] = (BEACON, TRIGGER, SCORE, CONFIRM)

EPOCH_MODULE = "rvt_swarm.decentralized.epoch"


# ---------------------------------------------------------------------------
# Wire schema declaration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldSpec:
    """One field of a serialized message. `n_bytes` is declared, not inferred.

    Declaring the width and then checking it against `struct.calcsize` is the
    point: if the two disagree the schema table in the documentation and the
    encoder have drifted apart, and `WireSchema.check()` says so.
    """

    name: str
    wire_type: str
    struct_code: str
    n_bytes: int
    note: str = ""


@dataclass(frozen=True)
class WireSchema:
    """The complete over-the-air format of one message type.

    Little-endian, no padding (`<` prefix), no list-valued field. The absence
    of a variable-length field is what makes `size_bytes` a constant and makes
    the byte total a function of the message *count* alone.
    """

    message_type: str
    fields: Tuple[FieldSpec, ...]
    source: str
    provisional: bool = False

    @property
    def struct_format(self) -> str:
        return "<" + "".join(f.struct_code for f in self.fields)

    @property
    def size_bytes(self) -> int:
        return int(struct.calcsize(self.struct_format))

    @property
    def declared_sum(self) -> int:
        return int(sum(f.n_bytes for f in self.fields))

    def check(self) -> None:
        """Declared field widths must sum to the packed size."""
        if self.declared_sum != self.size_bytes:
            raise ValueError(
                f"{self.message_type}: declared field widths sum to "
                f"{self.declared_sum} B but struct.calcsize("
                f"{self.struct_format!r}) is {self.size_bytes} B"
            )

    def markdown_table(self) -> str:
        head = ("| field | wire type | struct | bytes | note |\n"
                "|---|---|---|---|---|\n")
        rows = "".join(
            "| `{}` | {} | `{}` | {} | {} |\n".format(
                f.name, f.wire_type, f.struct_code, f.n_bytes, f.note)
            for f in self.fields
        )
        total = "| **total** | | `{}` | **{}** | |\n".format(
            self.struct_format, self.size_bytes)
        return head + rows + total


# -- beacon: mirrors comms.Beacon.payload_bytes ("<HII8f BIBB") --------------
BEACON_SCHEMA = WireSchema(
    message_type=BEACON,
    source="comms.Beacon.payload_bytes()",
    provisional=False,
    fields=(
        FieldSpec("sender_id", "uint16", "H", 2, "persistent robot id"),
        FieldSpec("timestamp_step", "uint32", "I", 4, "emission control step"),
        FieldSpec("seq", "uint32", "I", 4, "per-sender sequence counter"),
        FieldSpec("position", "float32 x2", "2f", 8, "absolute pose, differenced away on ingest"),
        FieldSpec("velocity", "float32 x2", "2f", 8, "absolute velocity"),
        FieldSpec("role_keep", "float32 x2", "2f", 8, "template-frame keep role"),
        FieldSpec("role_line", "float32 x2", "2f", 8, "template-frame line role"),
        FieldSpec("committed_mode", "uint8", "B", 1, "KEEP=0 | LINE=2"),
        FieldSpec("epoch_id", "uint32", "I", 4, "sender decision epoch"),
        FieldSpec("degree", "uint8", "B", 1, "sender's own one-hop degree"),
        FieldSpec("valid", "uint8", "B", 1, "link-valid flag"),
    ),
)

# -- score consensus: field list of consensus.ScoreMessage -------------------
SCORE_SCHEMA = WireSchema(
    message_type=SCORE,
    source="consensus.ScoreMessage field list; encoder declared here",
    provisional=False,
    fields=(
        FieldSpec("sender_id", "uint16", "H", 2, "persistent robot id"),
        FieldSpec("epoch_id", "uint32", "I", 4, "decision epoch being decided"),
        FieldSpec("round_index", "uint8", "B", 1, "0 .. k_score-1; k_score <= 6"),
        FieldSpec("z_keep", "float32", "f", 4, "current keep score iterate"),
        FieldSpec("z_line", "float32", "f", 4, "current line score iterate"),
        FieldSpec("degree", "uint8", "B", 1, "needed for the Metropolis-Hastings weight"),
        FieldSpec("timestamp_step", "uint32", "I", 4, "staleness gate"),
    ),
)

# -- trigger: BOUND to rvt_swarm/decentralized/epoch.TriggerMessage ----------
# Max-consensus over (trigger_flag, trigger_token). Max-consensus needs no
# weights, so -- unlike the score message -- there is deliberately no `degree`
# field: carrying one would be unjustified airtime.
#
# This schema was PROVISIONAL and WRONG. It declared 16 bytes against six
# fields that did not match epoch.TriggerMessage, whose real encoding is 21
# bytes over five fields. The recovery audit found the mismatch through
# verify_schema_sizes() self-reporting ok:false, which nothing consumed because
# no test exercised this module. The token is a (uint32, uint32, uint16)
# triple, which is the 10 bytes the old declaration was missing.
TRIGGER_SCHEMA = WireSchema(
    message_type=TRIGGER,
    source=f"{EPOCH_MODULE}.TriggerMessage.payload_bytes()",
    provisional=False,
    fields=(
        FieldSpec("sender_id", "uint16", "H", 2, "persistent robot id"),
        FieldSpec("epoch_counter", "uint32", "I", 4, "sender's local epoch counter"),
        FieldSpec("trigger_flag", "uint8", "B", 1, "max-consensus over {0,1}"),
        FieldSpec("token_epoch_counter", "uint32", "I", 4, "TriggerToken[0]"),
        FieldSpec("token_timestamp", "uint32", "I", 4, "TriggerToken[1]"),
        FieldSpec("token_robot_id", "uint16", "H", 2, "TriggerToken[2]; all-zero token = none held"),
        FieldSpec("timestamp_step", "uint32", "I", 4, "staleness gate"),
    ),
)

# -- mode confirmation: PROVISIONAL, pending epoch.py ------------------------
# Min/max-consensus over (proposed_mode, margin, confirm_flag). Also weightless,
# so also no `degree` field. `margin` is float32 because `confirm_margin` is a
# score-unit threshold and a min-consensus over it is what enforces the
# dead-band fleet-wide.
# Was PROVISIONAL and declared 17 bytes; epoch.ConfirmMessage encodes 16.
CONFIRM_SCHEMA = WireSchema(
    message_type=CONFIRM,
    source=f"{EPOCH_MODULE}.ConfirmMessage.payload_bytes()",
    provisional=False,
    fields=(
        FieldSpec("sender_id", "uint16", "H", 2, "persistent robot id"),
        FieldSpec("epoch_id", "uint32", "I", 4, "epoch being confirmed"),
        FieldSpec("selected_mode", "uint8", "B", 1, "mode-SET code, carries running min and max"),
        FieldSpec("margin", "float32", "f", 4, "|z_keep - z_line|, min-consensus"),
        FieldSpec("confirm_round", "uint8", "B", 1, "0 .. k_confirm-1"),
        FieldSpec("timestamp_step", "uint32", "I", 4, "staleness gate"),
    ),
)

WIRE_SCHEMAS: Dict[str, WireSchema] = {
    BEACON: BEACON_SCHEMA,
    TRIGGER: TRIGGER_SCHEMA,
    SCORE: SCORE_SCHEMA,
    CONFIRM: CONFIRM_SCHEMA,
}


# ---------------------------------------------------------------------------
# Schema-mirror message types
# ---------------------------------------------------------------------------
# These two classes were the PROVISIONAL stand-ins written before `epoch.py`
# existed. `epoch.py` is now authoritative for both, and `payload_of()` always
# prefers a message object's own `payload_bytes()`, so nothing in the pipeline
# depends on the encoders below.
#
# DEFECT FIXED HERE (see docs/DECENTRALIZED_COMMUNICATION_ACCOUNTING.md).
# When the two schemas were re-bound to `epoch.py` the field *lists* changed but
# these two encoders were left packing the old field lists into the new formats:
#
#     TriggerMessage.payload_bytes() -> struct.error: pack expected 7 items
#                                       for packing (got 6)
#     ConfirmMessage.payload_bytes() -> struct.error: pack expected 6 items
#                                       for packing (got 7)
#
# Every call raised. The fields below now mirror TRIGGER_SCHEMA / CONFIRM_SCHEMA
# one-for-one, which makes each class a second, independent encoder of the same
# schema; `test_communication_cost.py` asserts each is byte-identical to the
# `epoch.py` encoder for the same content, so the two modules cannot drift apart
# again without a test going red.
@dataclass(frozen=True)
class TriggerMessage:
    """Schema-mirror decision-trigger message. See TRIGGER_SCHEMA.

    `epoch.TriggerMessage` is the message the protocol actually sends; this is
    the wire format written out field by field, one field per FieldSpec.
    """

    sender_id: int
    epoch_counter: int
    trigger_flag: int
    token_epoch_counter: int
    token_timestamp: int
    token_robot_id: int
    timestamp_step: int

    def payload_bytes(self) -> bytes:
        return struct.pack(
            TRIGGER_SCHEMA.struct_format,
            int(self.sender_id) & 0xFFFF,
            int(self.epoch_counter) & 0xFFFFFFFF,
            1 if self.trigger_flag else 0,
            int(self.token_epoch_counter) & 0xFFFFFFFF,
            int(self.token_timestamp) & 0xFFFFFFFF,
            int(self.token_robot_id) & 0xFFFF,
            int(self.timestamp_step) & 0xFFFFFFFF,
        )


@dataclass(frozen=True)
class ConfirmMessage:
    """Schema-mirror mode-confirmation message. See CONFIRM_SCHEMA.

    `selected_mode` is the mode-SET code of `epoch.encode_mode_set`, not a plain
    mode: min- and max-consensus travel in the same byte.
    """

    sender_id: int
    epoch_id: int
    selected_mode: int
    margin: float
    confirm_round: int
    timestamp_step: int

    def payload_bytes(self) -> bytes:
        return struct.pack(
            CONFIRM_SCHEMA.struct_format,
            int(self.sender_id) & 0xFFFF,
            int(self.epoch_id) & 0xFFFFFFFF,
            int(self.selected_mode) & 0xFF,
            float(self.margin),
            int(self.confirm_round) & 0xFF,
            int(self.timestamp_step) & 0xFFFFFFFF,
        )


def encode_score_message(message: ScoreMessage) -> bytes:
    """Wire encoding for `consensus.ScoreMessage`.

    `ScoreMessage` is a frozen dataclass in `consensus.py` with no serializer
    of its own, and `consensus.py` is frozen, so the encoding is declared here
    instead of being added there. It is exactly SCORE_SCHEMA.
    """
    return struct.pack(
        SCORE_SCHEMA.struct_format,
        int(message.sender_id) & 0xFFFF,
        int(message.epoch_id) & 0xFFFFFFFF,
        int(message.round_index) & 0xFF,
        float(message.z_keep),
        float(message.z_line),
        int(message.degree) & 0xFF,
        int(message.timestamp_step) & 0xFFFFFFFF,
    )


# ---------------------------------------------------------------------------
# epoch.py dependency
# ---------------------------------------------------------------------------
_EPOCH_LOOKUP: Dict[str, object] = {}


def epoch_module_status() -> Dict[str, object]:
    """Is `rvt_swarm.decentralized.epoch` present, and does it define the two
    message types this module currently declares provisionally?

    Imported lazily and cached so importing `comm_cost` never depends on a
    module that may not exist, and so no import cycle can form.
    """
    if "checked" not in _EPOCH_LOOKUP:
        try:
            mod = importlib.import_module(EPOCH_MODULE)
        except ImportError:
            mod = None
        _EPOCH_LOOKUP["checked"] = True
        _EPOCH_LOOKUP["module"] = mod
    mod = _EPOCH_LOOKUP.get("module")
    trigger_cls = getattr(mod, "TriggerMessage", None) if mod is not None else None
    confirm_cls = (getattr(mod, "ConfirmMessage", None)
                   or getattr(mod, "ConfirmationMessage", None)) if mod is not None else None
    return {
        "module": EPOCH_MODULE,
        "available": mod is not None,
        "trigger_class": None if trigger_cls is None else trigger_cls.__name__,
        "confirm_class": None if confirm_cls is None else confirm_cls.__name__,
        "trigger_schema_source": "epoch" if trigger_cls is not None else "provisional",
        "confirm_schema_source": "epoch" if confirm_cls is not None else "provisional",
    }


def reset_epoch_lookup() -> None:
    """Drop the cached epoch-module probe. For tests that create the module."""
    _EPOCH_LOOKUP.clear()


# ---------------------------------------------------------------------------
# Encoding / classification of an arbitrary message object
# ---------------------------------------------------------------------------
_TYPE_BY_CLASS_NAME: Dict[str, str] = {
    "Beacon": BEACON,
    "ScoreMessage": SCORE,
    "TriggerMessage": TRIGGER,
    "ConfirmMessage": CONFIRM,
    "ConfirmationMessage": CONFIRM,
}


def message_type_of(message: object) -> str:
    """Which of the four wire categories this object belongs to.

    Keyed on class *name* rather than identity so that an `epoch.py`-provided
    `TriggerMessage` is classified identically to the provisional one here.
    """
    name = type(message).__name__
    if name not in _TYPE_BY_CLASS_NAME:
        raise TypeError(
            f"{name} is not a declared wire message type; declare a WireSchema "
            f"for it before it can be accounted"
        )
    return _TYPE_BY_CLASS_NAME[name]


def payload_of(message: object) -> bytes:
    """The message's own serialized wire form.

    A message that declares `payload_bytes()` is authoritative -- that is the
    encoding the radio would actually transmit. `ScoreMessage` has none, so the
    encoder declared above is used.
    """
    own = getattr(message, "payload_bytes", None)
    if callable(own):
        out = own()
        if not isinstance(out, (bytes, bytearray)):
            raise TypeError(f"{type(message).__name__}.payload_bytes() did not "
                            f"return bytes")
        return bytes(out)
    if isinstance(message, ScoreMessage):
        return encode_score_message(message)
    raise TypeError(f"no wire encoding available for {type(message).__name__}")


def wire_size(message: object) -> int:
    """Serialized size of this message, in bytes. Never an estimate."""
    return len(payload_of(message))


def _sample_messages() -> List[object]:
    """One fully-populated instance of each declared message type."""
    status = epoch_module_status()
    mod = _EPOCH_LOOKUP.get("module")
    out: List[object] = [
        Beacon(sender_id=3, timestamp_step=11, seq=5,
               position=(1.5, -2.25), velocity=(0.3, -0.1),
               role_keep=(0.45, 0.45), role_line=(-1.8, 0.0),
               committed_mode=LINE, epoch_id=2, degree=4, valid=True),
        ScoreMessage(sender_id=3, epoch_id=2, round_index=1,
                     z_keep=0.25, z_line=-0.75, degree=4, timestamp_step=11),
    ]
    trigger_cls = getattr(mod, "TriggerMessage", None) if mod is not None else None
    confirm_cls = (getattr(mod, "ConfirmMessage", None)
                   or getattr(mod, "ConfirmationMessage", None)) if mod is not None else None
    token_cls = getattr(mod, "TriggerToken", None) if mod is not None else None

    # Bound to epoch.py's real constructors. The previous version guessed a
    # signature and wrapped the call in `except TypeError: pass`, so when the
    # guess was wrong -- which it was, for both message types -- the sample was
    # silently dropped, `measured_bytes` stayed None, and the 16/17-byte
    # declarations went unchecked against the real 21/16. A schema mismatch
    # between two modules of the same package is now a hard failure.
    if trigger_cls is None or token_cls is None:
        raise ImportError(
            f"{EPOCH_MODULE} must provide TriggerMessage and TriggerToken; "
            "communication accounting cannot be verified without them"
        )
    out.append(trigger_cls(
        sender_id=3, epoch_counter=2, trigger_flag=True,
        trigger_token=token_cls(epoch_counter=2, trigger_timestamp=11, robot_id=3),
        timestamp_step=11))
    if confirm_cls is None:
        raise ImportError(f"{EPOCH_MODULE} must provide ConfirmMessage")
    out.append(confirm_cls(
        sender_id=3, epoch_id=2, selected_mode=LINE, margin=0.5,
        confirm_round=1, timestamp_step=11))
    del status
    return out


def verify_schema_sizes() -> Dict[str, Dict[str, object]]:
    """Encode one instance of every message type and compare with the schema.

    Returns per message type: the declared size, the measured size of a real
    encoding, whether the declared field widths sum to the packed size, and an
    `ok` flag. Nothing is raised -- the caller decides how loud to be -- except
    that a type whose sample could not be built is reported `measured=None`,
    never silently dropped.
    """
    measured: Dict[str, int] = {}
    for msg in _sample_messages():
        measured[message_type_of(msg)] = len(payload_of(msg))
    out: Dict[str, Dict[str, object]] = {}
    for name in MESSAGE_TYPES:
        schema = WIRE_SCHEMAS[name]
        got = measured.get(name)
        out[name] = {
            "declared_bytes": schema.size_bytes,
            "declared_field_sum": schema.declared_sum,
            "measured_bytes": got,
            "provisional": schema.provisional,
            "source": schema.source,
            "ok": bool(got is not None
                       and got == schema.size_bytes
                       and schema.declared_sum == schema.size_bytes),
        }
    return out


def assert_schema_sizes() -> Dict[str, Dict[str, object]]:
    """`verify_schema_sizes()`, but a mismatch is an exception."""
    table = verify_schema_sizes()
    bad = {k: v for k, v in table.items() if not v["ok"]}
    if bad:
        raise AssertionError(f"wire schema mismatch: {bad}")
    return table


# ---------------------------------------------------------------------------
# The accountant
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Record:
    message_type: str
    robot_id: int
    step: int
    decision_index: int
    round_index: int
    n_bytes: int


def _bump(target: Dict, key, amount: int) -> None:
    target[key] = target.get(key, 0) + amount


class MessageAccountant:
    """Counts messages and bytes by type, per robot, per decision, per episode.

    Transmissions and receptions are two separate ledgers. On a broadcast
    radio one transmission occupies the medium once regardless of how many
    peers hear it, so *transmitted* bytes are the airtime cost and the headline
    number; *received* bytes are reported alongside because they are what each
    robot's radio must actually demodulate and what a unicast mesh would have
    to pay for.

    Time base: `t_ctrl` seconds per control step, and `t_comm == t_ctrl` in the
    nominal configuration, so one communication period is one control step.
    Rates are therefore bytes-per-step / t_ctrl, with no other assumption.
    """

    def __init__(self, n_robots: int, params: Optional[CommParams] = None,
                 label: str = "", keep_payloads: bool = True) -> None:
        if int(n_robots) < 1:
            raise ValueError("n_robots must be >= 1")
        self.n_robots = int(n_robots)
        self.params = params or CommParams()
        self.t_ctrl = float(self.params.t_ctrl)
        self.label = str(label)
        self.keep_payloads = bool(keep_payloads)

        # Context used when a caller does not pass an explicit decision index.
        self.current_decision: int = 0

        # -- transmit ledger, independent accumulators ----------------------
        self._tx_records: List[_Record] = []
        self._tx_payloads: List[bytes] = []
        self._tx_bytes_total: int = 0
        self._tx_msgs_total: int = 0
        self._tx_bytes_by_type: Dict[str, int] = {}
        self._tx_msgs_by_type: Dict[str, int] = {}
        self._tx_bytes_by_robot: Dict[int, int] = {}
        self._tx_msgs_by_robot: Dict[int, int] = {}
        self._tx_bytes_by_decision: Dict[int, int] = {}
        self._tx_bytes_by_step: Dict[int, int] = {}
        self._tx_bytes_by_type_step: Dict[Tuple[str, int], int] = {}
        self._tx_bytes_by_type_robot_step: Dict[Tuple[str, int, int], int] = {}
        self._tx_bytes_by_type_robot: Dict[Tuple[str, int], int] = {}
        self._tx_msgs_by_type_robot: Dict[Tuple[str, int], int] = {}
        self._tx_bytes_by_type_decision: Dict[Tuple[str, int], int] = {}
        self._tx_msgs_by_type_decision: Dict[Tuple[str, int], int] = {}
        self._tx_rounds_by_type_decision: Dict[Tuple[str, int], Set[int]] = {}

        # -- receive ledger --------------------------------------------------
        self._rx_bytes_total: int = 0
        self._rx_msgs_total: int = 0
        self._rx_bytes_by_type: Dict[str, int] = {}
        self._rx_msgs_by_type: Dict[str, int] = {}
        self._rx_bytes_by_robot: Dict[int, int] = {}
        self._rx_payloads_len_total: int = 0

        self._steps: Set[int] = set()
        self._decisions: Set[int] = set()
        self._explicit_steps: Optional[int] = None

    # -- recording ---------------------------------------------------------
    def record_sent_bytes(self, message_type: str, sender_id: int,
                          payload: bytes, step: int,
                          round_index: int = 0,
                          decision_index: Optional[int] = None) -> int:
        """Record one transmission. `payload` is the real encoding, not a size.

        Returns the number of bytes recorded. Raises `ValueError` if the
        payload length disagrees with the declared fixed-size schema, because
        every message type here is fixed-size by construction.
        """
        if message_type not in WIRE_SCHEMAS:
            raise ValueError(f"unknown message type {message_type!r}; "
                             f"expected one of {MESSAGE_TYPES}")
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload must be bytes -- byte counts may not be "
                            "supplied directly")
        n = len(payload)
        expected = WIRE_SCHEMAS[message_type].size_bytes
        if n != expected:
            raise ValueError(
                f"{message_type}: encoded payload is {n} B but the declared "
                f"wire schema is {expected} B"
            )
        d = self.current_decision if decision_index is None else int(decision_index)
        rec = _Record(message_type, int(sender_id), int(step), d,
                      int(round_index), n)
        self._tx_records.append(rec)
        if self.keep_payloads:
            self._tx_payloads.append(bytes(payload))
        self._tx_bytes_total += n
        self._tx_msgs_total += 1
        _bump(self._tx_bytes_by_type, message_type, n)
        _bump(self._tx_msgs_by_type, message_type, 1)
        _bump(self._tx_bytes_by_robot, rec.robot_id, n)
        _bump(self._tx_msgs_by_robot, rec.robot_id, 1)
        _bump(self._tx_bytes_by_decision, d, n)
        _bump(self._tx_bytes_by_step, rec.step, n)
        _bump(self._tx_bytes_by_type_step, (message_type, rec.step), n)
        _bump(self._tx_bytes_by_type_robot_step,
              (message_type, rec.robot_id, rec.step), n)
        _bump(self._tx_bytes_by_type_robot, (message_type, rec.robot_id), n)
        _bump(self._tx_msgs_by_type_robot, (message_type, rec.robot_id), 1)
        _bump(self._tx_bytes_by_type_decision, (message_type, d), n)
        _bump(self._tx_msgs_by_type_decision, (message_type, d), 1)
        self._tx_rounds_by_type_decision.setdefault(
            (message_type, d), set()).add(int(round_index))
        self._steps.add(rec.step)
        self._decisions.add(d)
        return n

    def record_received_bytes(self, message_type: str, receiver_id: int,
                              payload: bytes, step: int,
                              decision_index: Optional[int] = None) -> int:
        """Record one reception (one radio actually demodulated this packet)."""
        if message_type not in WIRE_SCHEMAS:
            raise ValueError(f"unknown message type {message_type!r}")
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload must be bytes")
        n = len(payload)
        expected = WIRE_SCHEMAS[message_type].size_bytes
        if n != expected:
            raise ValueError(
                f"{message_type}: encoded payload is {n} B but the declared "
                f"wire schema is {expected} B"
            )
        self._rx_bytes_total += n
        self._rx_msgs_total += 1
        self._rx_payloads_len_total += n
        _bump(self._rx_bytes_by_type, message_type, n)
        _bump(self._rx_msgs_by_type, message_type, 1)
        _bump(self._rx_bytes_by_robot, int(receiver_id), n)
        self._steps.add(int(step))
        if decision_index is not None:
            self._decisions.add(int(decision_index))
        return n

    def record_sent(self, message: object, step: int, round_index: int = 0,
                    decision_index: Optional[int] = None) -> int:
        """Record a transmission from the message object itself."""
        return self.record_sent_bytes(
            message_type_of(message), int(getattr(message, "sender_id")),
            payload_of(message), step, round_index, decision_index)

    def record_received(self, message: object, receiver_id: int, step: int,
                        decision_index: Optional[int] = None) -> int:
        return self.record_received_bytes(
            message_type_of(message), receiver_id, payload_of(message), step,
            decision_index)

    # -- episode framing ---------------------------------------------------
    def set_episode_steps(self, n_steps: int) -> None:
        """Declare the episode length explicitly.

        Without this, the episode duration is inferred from the observed step
        span. Declaring it matters when the last control steps of an episode
        happen to carry no message: the average rate must be divided by the
        real duration, not by the duration of the part that had traffic.
        """
        if int(n_steps) < 0:
            raise ValueError("n_steps must be >= 0")
        self._explicit_steps = int(n_steps)

    @property
    def episode_steps(self) -> int:
        if self._explicit_steps is not None:
            return self._explicit_steps
        if not self._steps:
            return 0
        return max(self._steps) - min(self._steps) + 1

    @property
    def episode_seconds(self) -> float:
        return self.episode_steps * self.t_ctrl

    @property
    def n_decisions(self) -> int:
        return len(self._decisions)

    @property
    def total_bytes(self) -> int:
        return self._tx_bytes_total

    @property
    def total_messages(self) -> int:
        return self._tx_msgs_total

    def payload_bytes_ledger_total(self) -> int:
        """Sum of `len(payload_bytes())` over every message actually recorded.

        This is the independent quantity the accountant's totals are checked
        against; it is computed from the retained encodings, not from the
        counters.
        """
        if not self.keep_payloads:
            raise RuntimeError("accountant was built with keep_payloads=False; "
                               "the payload cross-check is unavailable")
        return int(sum(len(p) for p in self._tx_payloads))

    # -- consistency -------------------------------------------------------
    def assert_consistent(self) -> None:
        """Totals must equal the sum of every partition, and the payloads."""
        t = self._tx_bytes_total
        checks: List[Tuple[str, int, int]] = [
            ("sum over types", sum(self._tx_bytes_by_type.values()), t),
            ("sum over robots", sum(self._tx_bytes_by_robot.values()), t),
            ("sum over decisions", sum(self._tx_bytes_by_decision.values()), t),
            ("sum over steps", sum(self._tx_bytes_by_step.values()), t),
            ("sum over (type, step)", sum(self._tx_bytes_by_type_step.values()), t),
            ("sum over (type, robot)", sum(self._tx_bytes_by_type_robot.values()), t),
            ("sum over (type, decision)",
             sum(self._tx_bytes_by_type_decision.values()), t),
            ("sum over records", sum(r.n_bytes for r in self._tx_records), t),
        ]
        if self.keep_payloads:
            checks.append(("sum of len(payload_bytes())",
                           self.payload_bytes_ledger_total(), t))
        for name, got, want in checks:
            if got != want:
                raise AssertionError(
                    f"communication accounting inconsistent: {name} = {got} B "
                    f"but total = {want} B")
        m = self._tx_msgs_total
        for name, got in (
            ("messages by type", sum(self._tx_msgs_by_type.values())),
            ("messages by robot", sum(self._tx_msgs_by_robot.values())),
            ("messages by (type, robot)", sum(self._tx_msgs_by_type_robot.values())),
            ("messages by (type, decision)",
             sum(self._tx_msgs_by_type_decision.values())),
            ("message records", len(self._tx_records)),
        ):
            if got != m:
                raise AssertionError(
                    f"communication accounting inconsistent: {name} = {got} "
                    f"but total = {m}")
        if self.keep_payloads and len(self._tx_payloads) != m:
            raise AssertionError(
                f"payload ledger holds {len(self._tx_payloads)} encodings but "
                f"{m} messages were recorded")

    # -- reporting ---------------------------------------------------------
    def _category_report(self, name: Optional[str]) -> Dict[str, object]:
        """Metrics for one message type, or for every type when `name` is None."""
        steps = self.episode_steps
        seconds = self.episode_seconds
        n_rob = self.n_robots
        n_dec = max(1, self.n_decisions)

        if name is None:
            msgs = self._tx_msgs_total
            byts = self._tx_bytes_total
            by_step = dict(self._tx_bytes_by_step)
            by_robot_step: Dict[Tuple[int, int], int] = {}
            for (_t, r, s), v in self._tx_bytes_by_type_robot_step.items():
                _bump(by_robot_step, (r, s), v)
            rounds = [len(v) for (t_, d_), v in
                      self._tx_rounds_by_type_decision.items()]
            rounds_per_decision = (float(sum(rounds)) / float(n_dec)
                                   if rounds else 0.0)
            rx_msgs = self._rx_msgs_total
            rx_bytes = self._rx_bytes_total
            wire = None
            provisional = any(WIRE_SCHEMAS[t].provisional for t in MESSAGE_TYPES)
        else:
            msgs = self._tx_msgs_by_type.get(name, 0)
            byts = self._tx_bytes_by_type.get(name, 0)
            by_step = {s: v for (t_, s), v in self._tx_bytes_by_type_step.items()
                       if t_ == name}
            by_robot_step = {(r, s): v for (t_, r, s), v
                             in self._tx_bytes_by_type_robot_step.items()
                             if t_ == name}
            rounds = [len(v) for (t_, d_), v
                      in self._tx_rounds_by_type_decision.items() if t_ == name]
            rounds_per_decision = (float(sum(rounds)) / float(n_dec)
                                   if rounds else 0.0)
            rx_msgs = self._rx_msgs_by_type.get(name, 0)
            rx_bytes = self._rx_bytes_by_type.get(name, 0)
            wire = WIRE_SCHEMAS[name].size_bytes
            provisional = WIRE_SCHEMAS[name].provisional

        peak = (max(by_step.values()) / self.t_ctrl) if by_step else 0.0
        peak_rob = (max(by_robot_step.values()) / self.t_ctrl) if by_robot_step else 0.0
        avg = (byts / seconds) if seconds > 0.0 else 0.0

        return {
            "messages": int(msgs),
            "bytes": int(byts),
            "wire_bytes_per_message": wire,
            "schema_provisional": bool(provisional),
            # PENDING means "this row is not a measurement". Two ways that
            # happens: the schema is still provisional, or nothing of this type
            # was ever recorded -- a zero that means "never sent", not "free".
            #
            # DEFECT FIXED HERE. This read `provisional and msgs == 0`. Once the
            # trigger and confirmation schemas were bound to `epoch.py` their
            # `provisional` flags went False, so the two categories that the
            # runtime cannot yet send -- `epoch.py` is not wired into
            # `runtime.py` -- reported `pending=False` with 0 bytes, i.e. as a
            # measured zero. That is precisely the reading
            # `simulate_episode_message_cost` warns against in its own
            # docstring: "a report that shows them as zero cost is wrong and
            # must be read as pending".
            "pending": bool(provisional or msgs == 0),
            "messages_per_robot": msgs / n_rob,
            "bytes_per_robot_per_episode": byts / n_rob,
            "rounds_per_decision": rounds_per_decision,
            "messages_per_robot_per_decision": msgs / n_rob / n_dec,
            "bytes_per_robot_per_decision": byts / n_rob / n_dec,
            "peak_bytes_per_second": peak,
            "average_bytes_per_second": avg,
            "peak_bytes_per_second_per_robot": peak_rob,
            "average_bytes_per_second_per_robot": (avg / n_rob) if n_rob else 0.0,
            "received_messages": int(rx_msgs),
            "received_bytes": int(rx_bytes),
        }

    def report(self) -> Dict[str, object]:
        """Full cost report. Calls `assert_consistent()` before reporting.

        Every number below is derived from byte counts of the declared wire
        format; nothing measures a Python object.
        """
        self.assert_consistent()
        return {
            "label": self.label,
            "n_robots": self.n_robots,
            "t_ctrl_seconds": self.t_ctrl,
            "episode_steps": self.episode_steps,
            "episode_seconds": self.episode_seconds,
            "decisions_per_episode": self.n_decisions,
            "schema": verify_schema_sizes(),
            "epoch_module": epoch_module_status(),
            "categories": {name: self._category_report(name)
                           for name in MESSAGE_TYPES},
            "total": self._category_report(None),
            "consistent": True,
        }


def format_report(report: Dict[str, object]) -> str:
    """Fixed-width rendering of `MessageAccountant.report()`."""
    cats = report["categories"]
    lines: List[str] = []
    lines.append(f"label                : {report['label']}")
    lines.append(f"robots               : {report['n_robots']}")
    lines.append(f"t_ctrl               : {report['t_ctrl_seconds']:.3f} s")
    lines.append(f"episode steps        : {report['episode_steps']} "
                 f"({report['episode_seconds']:.2f} s)")
    lines.append(f"decisions per episode: {report['decisions_per_episode']}")
    lines.append("")
    header = ("{:<28} {:>6} {:>9} {:>9} {:>8} {:>10} {:>10} {:>10} {:>10}"
              .format("category", "B/msg", "messages", "bytes", "rnd/dec",
                      "msg/rob", "B/rob/dec", "peak B/s", "avg B/s"))
    lines.append(header)
    lines.append("-" * len(header))
    for name in list(MESSAGE_TYPES) + ["TOTAL"]:
        c = report["total"] if name == "TOTAL" else cats[name]
        wire = c["wire_bytes_per_message"]
        # Widened from 20 to 28 columns: "mode_confirmation [PENDING]" is 27
        # characters and used to be truncated to "mode_confirmation [P", which
        # hid the one flag that says the row is not a measurement.
        tag = name + (" [PENDING]" if c.get("pending") else "")
        lines.append(
            "{:<28} {:>6} {:>9} {:>9} {:>8.2f} {:>10.2f} {:>10.2f} {:>10.1f} {:>10.1f}"
            .format(tag[:28], "-" if wire is None else wire, c["messages"],
                    c["bytes"], c["rounds_per_decision"],
                    c["messages_per_robot"], c["bytes_per_robot_per_decision"],
                    c["peak_bytes_per_second"], c["average_bytes_per_second"]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Instrumented simulation objects (simulation-only; they observe, never decide)
# ---------------------------------------------------------------------------
class _AccountingRadioChannel(RadioChannel):
    """`RadioChannel` that reports every real transmission and delivery.

    Broadcast semantics: `simulate_broadcast_round` offers the same beacon on
    every directed link, but a broadcast radio keys the microphone once. The
    first offer of a given `(sender_id, seq)` is therefore counted as the one
    transmission; the remaining offers are link-level copies of it and are
    counted only when they are actually delivered.
    """

    def __init__(self, params: CommParams, seed: int = 0,
                 accountant: Optional[MessageAccountant] = None) -> None:
        super().__init__(params, seed=seed)
        self.accountant = accountant
        self._counted: Set[Tuple[int, int]] = set()

    def transmit(self, beacon: Beacon, src_position: Vec2, dst_id: int,
                 dst_position: Vec2, step: int) -> Optional[int]:
        if self.accountant is not None:
            key = (int(beacon.sender_id), int(beacon.seq))
            if key not in self._counted:
                self._counted.add(key)
                self.accountant.record_sent(beacon, step=int(step),
                                            round_index=int(step))
        return super().transmit(beacon, src_position, dst_id, dst_position, step)

    def deliver(self, step: int) -> Tuple[Tuple[int, Beacon], ...]:
        due = super().deliver(step)
        if self.accountant is not None:
            for dst_id, beacon in due:
                self.accountant.record_received(beacon, receiver_id=int(dst_id),
                                                step=int(step))
        return due


class _AccountingConsensusNode(ConsensusNode):
    """`ConsensusNode` that reports the score messages it really sends/receives.

    Overriding `outgoing` and `step` means the ledger records exactly the
    messages `simulate_consensus` moved, including those that admission control
    later rejects -- a rejected message still cost its bytes on the air.
    """

    accountant: Optional[MessageAccountant] = None

    def outgoing(self, now_step: int) -> ScoreMessage:
        msg = super().outgoing(now_step)
        if self.accountant is not None:
            self.accountant.record_sent(msg, step=int(now_step),
                                        round_index=int(msg.round_index))
        return msg

    def step(self, inbox: Sequence[ScoreMessage], now_step: int,
             delta_stale_steps: int):
        if self.accountant is not None:
            for msg in inbox:
                self.accountant.record_received(msg, receiver_id=self.robot_id,
                                                step=int(now_step))
        return super().step(inbox, now_step, delta_stale_steps)


# ---------------------------------------------------------------------------
# THE MEASUREMENT BOUNDARY
# ---------------------------------------------------------------------------
def simulate_episode_message_cost(
    cfg,
    n_agents: int,
    layout,
    seed: int,
    mode: int = KEEP,
    comm: Optional[CommParams] = None,
    consensus: Optional[ConsensusParams] = None,
    scenario: str = "cluttered",
    max_steps: Optional[int] = None,
) -> Dict[str, object]:
    """Run one episode of the decentralized runtime and account every message.

    **Not deployable** -- it reads the environment's joint state, which is why
    it carries the `simulate_` prefix.

    What is measured, and what is not
    ---------------------------------
    * Beacons: one per robot per control step (`t_comm == t_ctrl`), emitted by
      `simulate_broadcast_round`; transmissions and deliveries are observed
      through the instrumented radio channel, so the counts are the real ones.
    * Score consensus: `k_score` rounds are opened every
      `decision_interval` control steps and occupy control steps
      `s .. s + k_score - 1`, so beacon and score traffic overlap exactly as
      they would on the air. The messages are observed through the instrumented
      consensus node.
    * Trigger and mode-confirmation traffic is **not** simulated here.
      `rvt_swarm/decentralized/epoch.py` now exists and its two message
      encoders are what the schemas are checked against, but no runtime path
      sends either message -- neither this function nor `runtime.py` imports
      `epoch.py`. Those two categories report zero messages and `pending=True`;
      a report that shows them as zero cost is wrong and must be read as
      pending.

    Two deliberate simplifications, both stated because both are real:

    * The team stays committed to `mode` for the whole episode and the score
      iterates are initialised to that mode's one-hot. There is no trained
      selector in this measurement. This does not bias the byte counts -- the
      wire format is fixed-size, so cost is independent of the values carried,
      which `test_communication_cost.py` asserts directly -- but it does fix
      the trajectory, so keep and line are measured as two separate regimes
      rather than mixed. That is the informative split anyway: the keep grid is
      one-hop complete while the line is multi-hop.
    * The neighbour sets used by the consensus rounds are frozen at the
      epoch-opening step for all `k_score` rounds, while the robots keep
      moving. Over 4 rounds that is 0.6 s of graph drift not modelled inside
      the epoch.
    """
    from ..environment import SwarmFormationEnv       # local: heavy import

    if mode not in (KEEP, LINE):
        raise ValueError(f"mode must be KEEP({KEEP}) or LINE({LINE})")
    params = comm or CommParams()
    cparams = consensus or ConsensusParams()
    n = int(n_agents)

    env = SwarmFormationEnv(cfg)
    env.reset(n, scenario, seed=int(seed), layout=layout)
    horizon = int(max_steps if max_steps is not None else cfg.env.max_steps)

    roles = RoleAssignment.from_index(n, cfg.env.nominal_spacing)
    acct = MessageAccountant(
        n, params=params,
        label=f"n={n} mode={'keep' if mode == KEEP else 'line'} "
              f"layout={getattr(layout, 'layout_id', 'none')} seed={seed}")
    channel = _AccountingRadioChannel(params, seed=int(seed), accountant=acct)
    states = {i: RobotRadioState(robot_id=i,
                                 table=NeighbourTable(i, params),
                                 history=OwnHistory())
              for i in range(n)}

    modes = [int(mode)] * n
    epochs = [0] * n
    ssd = [0] * n
    decision_index = 0
    degrees: List[float] = []
    steps_run = 0
    done = False

    from .local_controller import local_controller     # local: torch-free path
    import numpy as np

    for t in range(horizon):
        acct.current_decision = decision_index
        goal = (float(env.state.goal[0]), float(env.state.goal[1]))
        mdir = (float(env.state.corridor_direction[0]),
                float(env.state.corridor_direction[1]))
        views = simulate_broadcast_round(
            step=t,
            positions=env.state.positions,
            velocities=env.state.velocities,
            roles=roles,
            committed_modes=modes,
            epoch_ids=epochs,
            steps_since_decision=ssd,
            states=states,
            channel=channel,
            obstacles=env.state.obstacles,
            obstacle_radius=cfg.env.obstacle_radius,
            goal=goal,
            mission_dir=mdir,
            params=params,
        )
        degrees.append(float(sum(views[i].degree for i in range(n))) / n)

        if t % cparams.decision_interval == 0:
            z0 = (1.0, 0.0) if mode == KEEP else (0.0, 1.0)
            nodes: Dict[int, ConsensusNode] = {}
            for i in range(n):
                node = _AccountingConsensusNode.from_logits(
                    i, z0[0], z0[1], views[i].degree, epochs[i], cparams)
                node.accountant = acct
                nodes[i] = node
            neighbours_of = {i: list(views[i].neighbour_ids()) for i in range(n)}
            simulate_consensus(
                nodes, neighbours_of, cparams.k_score,
                start_step=t,
                delta_stale_steps=params.delta_stale_steps,
                packet_loss=params.packet_loss,
                delay_steps=params.delay_steps,
                seed=int(seed) + decision_index,
                record_history=False,
            )
            decision_index += 1
            epochs = [e + 1 for e in epochs]
            ssd = [0] * n
        else:
            ssd = [s + 1 for s in ssd]

        actions = np.stack([local_controller(views[i], cfg, modes[i])
                            for i in range(n)])
        _obs, _r, done, _info = env.step(actions, int(mode))
        steps_run = t + 1
        if done:
            break

    acct.set_episode_steps(steps_run)
    return {
        "accountant": acct,
        "steps": steps_run,
        "done": bool(done),
        "mean_degree": (float(sum(degrees)) / len(degrees)) if degrees else 0.0,
        "decisions": decision_index,
        "channel_transmitted_links": channel.transmitted,
        "channel_delivered_links": channel.delivered,
    }


@offline_diagnostic
def mean_of_reports(reports: Sequence[Dict[str, object]]) -> Dict[str, object]:
    """Element-wise mean of several `report()` dicts. Offline analysis only.

    Averages every numeric leaf of `categories` and `total`, and reports the
    episode framing (steps, decisions) as means too, so a table row over
    several validation layouts is one honest average rather than a
    cherry-picked episode.
    """
    if not reports:
        raise ValueError("no reports to average")
    keys = [k for k, v in reports[0]["total"].items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    out: Dict[str, object] = {
        "label": f"mean of {len(reports)} episodes",
        "n_robots": reports[0]["n_robots"],
        "t_ctrl_seconds": reports[0]["t_ctrl_seconds"],
        "episodes": len(reports),
        "episode_steps": sum(float(r["episode_steps"]) for r in reports) / len(reports),
        "episode_seconds": sum(float(r["episode_seconds"]) for r in reports) / len(reports),
        "decisions_per_episode": sum(float(r["decisions_per_episode"])
                                     for r in reports) / len(reports),
        "schema": reports[0]["schema"],
        "epoch_module": reports[0]["epoch_module"],
    }
    cats: Dict[str, Dict[str, object]] = {}
    for name in MESSAGE_TYPES:
        row: Dict[str, object] = {}
        for k in keys:
            vals = [float(r["categories"][name][k]) for r in reports
                    if r["categories"][name][k] is not None]
            row[k] = (sum(vals) / len(vals)) if vals else 0.0
        row["wire_bytes_per_message"] = reports[0]["categories"][name][
            "wire_bytes_per_message"]
        row["schema_provisional"] = reports[0]["categories"][name][
            "schema_provisional"]
        row["pending"] = all(bool(r["categories"][name]["pending"])
                             for r in reports)
        cats[name] = row
    total: Dict[str, object] = {}
    for k in keys:
        vals = [float(r["total"][k]) for r in reports if r["total"][k] is not None]
        total[k] = (sum(vals) / len(vals)) if vals else 0.0
    total["wire_bytes_per_message"] = None
    total["schema_provisional"] = reports[0]["total"]["schema_provisional"]
    total["pending"] = False
    out["categories"] = cats
    out["total"] = total
    out["consistent"] = True
    return out
