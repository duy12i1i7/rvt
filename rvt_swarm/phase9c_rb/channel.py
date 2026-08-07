"""F8 communication execution (RB-10).

Implements the frozen `communication_degradation_contract` exactly. Nothing is
re-derived: the compiler already resolved the per-team-size disconnection
schedule (`communication.team_size_schedule`), so this module reads
`start_tick`, `duration_ticks` and `partition_ordinal` rather than recomputing
`ceil(d_entry/v_max/T_comm)` and risking a different rounding.

Two things stay strictly separate, per LIMITATION L1 and the contract's
`assumption_class`:

* `bounded_delay_loss` -- degradation **inside** method assumptions;
* `temporary_disconnection_then_restore` -- an **explicit assumption-violation
  stress** interval. A task failure caused by the declared cut is a legitimate
  valid task-negative. A *malformed* schedule is generation-invalid. The
  channel records which regime it is in; it never classifies the outcome.

Candidate matching: the delay/drop/cut schedule is counter-keyed, so paired
candidates draw identical values. Physical range edges may still diverge once
candidate motion differs -- that is treatment response, not unmatched
randomness, and the contract says so explicitly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .streams import STREAM_COMMUNICATION, CounterStream

PROFILE_NOMINAL = "nominal"
PROFILE_BOUNDED = "bounded_delay_loss"
PROFILE_DISCONNECTION = "temporary_disconnection_then_restore"

ASSUMPTION_INSIDE = "inside_method_assumptions"
ASSUMPTION_VIOLATION = "explicit_assumption_violation_stress"


@dataclass(frozen=True)
class PendingMessage:
    sender_id: int
    receiver_id: int
    sequence: int
    message_type: str
    payload: object
    send_time_seconds: float
    delivery_tick: int
    crossed_partition: bool

    def as_snapshot(self) -> Dict[str, object]:
        return {
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "sequence": self.sequence,
            "message_type": self.message_type,
            "send_time_seconds": float(self.send_time_seconds),
            "delivery_tick": int(self.delivery_tick),
            "crossed_partition": bool(self.crossed_partition),
        }


@dataclass
class CommunicationChannel:
    """One-hop channel with range gating, bounded delay/loss and an optional cut."""

    team_size: int
    profile: str
    assumption_class: str
    delay_upper_bound_seconds: float
    packet_drop_probability: float
    communication_range_meters: float
    communication_period_seconds: float
    maximum_message_age_seconds: float
    stream: CounterStream
    cut_start_tick: Optional[int] = None
    cut_duration_ticks: int = 0
    cut_partition_ordinal: Optional[int] = None

    tick: int = 0
    sequence_by_link: Dict[Tuple[int, int], int] = field(default_factory=dict)
    queue: List[PendingMessage] = field(default_factory=list)
    delivered_count: int = 0
    dropped_count: int = 0
    cut_dropped_count: int = 0
    assumption_violation_active: bool = False
    assumption_violation_observed: bool = False

    # -- schedule ----------------------------------------------------------
    def cut_active_at(self, tick: int) -> bool:
        if self.cut_start_tick is None or self.cut_duration_ticks <= 0:
            return False
        return self.cut_start_tick <= tick < self.cut_start_tick + self.cut_duration_ticks

    def _partition_side(self, role_ordinal: int) -> int:
        assert self.cut_partition_ordinal is not None
        return 0 if role_ordinal < self.cut_partition_ordinal else 1

    def crosses_cut(self, sender_id: int, receiver_id: int) -> bool:
        if self.cut_partition_ordinal is None:
            return False
        return self._partition_side(sender_id) != self._partition_side(receiver_id)

    # -- transmission ------------------------------------------------------
    def physical_edge(self, position_a: Sequence[float], position_b: Sequence[float]) -> bool:
        return math.hypot(position_a[0] - position_b[0],
                          position_a[1] - position_b[1]) <= self.communication_range_meters

    def send(self, sender_id: int, receiver_id: int, message_type: str, payload: object,
             now_seconds: float) -> bool:
        """Offer one directed message. Returns True when it was queued."""
        link = (sender_id, receiver_id)
        sequence = self.sequence_by_link.get(link, 0)
        self.sequence_by_link[link] = sequence + 1

        crossed = self.crosses_cut(sender_id, receiver_id)
        if crossed and self.cut_active_at(self.tick):
            # Explicit stress: cross-partition traffic is destroyed, not delayed.
            self.cut_dropped_count += 1
            self.assumption_violation_observed = True
            return False

        key = (sender_id, receiver_id, sequence, message_type)
        if self.packet_drop_probability > 0.0 and self.stream.bernoulli(
                self.packet_drop_probability, *key, "drop"):
            self.dropped_count += 1
            return False

        delay = 0.0
        if self.delay_upper_bound_seconds > 0.0:
            delay = self.stream.closed_interval(
                0.0, self.delay_upper_bound_seconds, *key, "delay")
        # First communication tick at or after send_time + delay.
        ticks_ahead = int(math.ceil(delay / self.communication_period_seconds - 1e-12))
        self.queue.append(PendingMessage(
            sender_id=sender_id, receiver_id=receiver_id, sequence=sequence,
            message_type=message_type, payload=payload, send_time_seconds=now_seconds,
            delivery_tick=self.tick + max(0, ticks_ahead), crossed_partition=crossed,
        ))
        return True

    def deliver(self, tick: int) -> Tuple[PendingMessage, ...]:
        """Messages due at `tick`. Cross-cut traffic queued before the cut is
        dropped and is never delivered after restoration."""
        due: List[PendingMessage] = []
        remaining: List[PendingMessage] = []
        cut_now = self.cut_active_at(tick)
        for message in self.queue:
            if message.crossed_partition and cut_now:
                self.cut_dropped_count += 1
                self.assumption_violation_observed = True
                continue
            if message.delivery_tick <= tick:
                due.append(message)
            else:
                remaining.append(message)
        self.queue = remaining
        self.delivered_count += len(due)
        due.sort(key=lambda m: (m.sender_id, m.receiver_id, m.sequence, m.message_type))
        return tuple(due)

    def advance(self) -> None:
        self.tick += 1
        self.assumption_violation_active = self.cut_active_at(self.tick)

    def is_stale(self, message_age_seconds: float) -> bool:
        return message_age_seconds > self.maximum_message_age_seconds

    # -- snapshot ----------------------------------------------------------
    def snapshot(self) -> Dict[str, object]:
        return {
            "tick": int(self.tick),
            "profile": self.profile,
            "assumption_class": self.assumption_class,
            "prf_identity": list(self.stream.identity()),
            "sequence_by_link": {f"{a}->{b}": int(v)
                                 for (a, b), v in sorted(self.sequence_by_link.items())},
            "queued_messages": [m.as_snapshot() for m in sorted(
                self.queue, key=lambda m: (m.delivery_tick, m.sender_id, m.receiver_id, m.sequence))],
            "cut_active": bool(self.cut_active_at(self.tick)),
            "cut_start_tick": self.cut_start_tick,
            "cut_duration_ticks": int(self.cut_duration_ticks),
            "cut_partition_ordinal": self.cut_partition_ordinal,
            "delivered_count": int(self.delivered_count),
            "dropped_count": int(self.dropped_count),
            "cut_dropped_count": int(self.cut_dropped_count),
            "assumption_violation_observed": bool(self.assumption_violation_observed),
        }

    def restore(self, snapshot: Mapping[str, object], payloads: Mapping[int, object]) -> None:
        self.tick = int(snapshot["tick"])
        self.sequence_by_link = {}
        for key, value in dict(snapshot["sequence_by_link"]).items():   # type: ignore[arg-type]
            sender, receiver = key.split("->")
            self.sequence_by_link[(int(sender), int(receiver))] = int(value)
        self.queue = []
        for index, entry in enumerate(list(snapshot["queued_messages"])):   # type: ignore[arg-type]
            self.queue.append(PendingMessage(
                sender_id=int(entry["sender_id"]), receiver_id=int(entry["receiver_id"]),
                sequence=int(entry["sequence"]), message_type=str(entry["message_type"]),
                payload=payloads.get(index), send_time_seconds=float(entry["send_time_seconds"]),
                delivery_tick=int(entry["delivery_tick"]),
                crossed_partition=bool(entry["crossed_partition"])))
        self.delivered_count = int(snapshot["delivered_count"])
        self.dropped_count = int(snapshot["dropped_count"])
        self.cut_dropped_count = int(snapshot["cut_dropped_count"])
        self.assumption_violation_observed = bool(snapshot["assumption_violation_observed"])
        self.assumption_violation_active = self.cut_active_at(self.tick)


def build_channel(specification: Mapping[str, object], team_size: int,
                  runtime_config: object, communication_seed: int) -> CommunicationChannel:
    """Build the channel for one compiled layout and team size.

    The disconnection schedule comes from the compiled record, not from a local
    recomputation of the `ceil(...)` formula.
    """
    contract = dict(specification["communication"])                  # type: ignore[arg-type]
    profile = str(contract["profile"])
    schedule = dict(contract.get("team_size_schedule") or {})
    entry = schedule.get(str(team_size))

    cut_start = cut_duration = cut_ordinal = None
    if profile == PROFILE_DISCONNECTION:
        if entry is None:
            raise ValueError(
                f"SCHEDULE_INVALID: no F8 disconnection schedule for N={team_size}")
        cut_start = int(entry["start_tick"])
        cut_duration = int(entry["duration_ticks"])
        cut_ordinal = int(entry["partition_ordinal"])

    return CommunicationChannel(
        team_size=int(team_size),
        profile=profile,
        assumption_class=str(contract["assumption_class"]),
        delay_upper_bound_seconds=float(contract["delay_upper_bound_seconds"]),
        packet_drop_probability=float(contract["packet_drop_probability"]),
        communication_range_meters=float(runtime_config.communication.communication_range_meters),
        communication_period_seconds=float(runtime_config.communication.communication_period_seconds),
        maximum_message_age_seconds=float(runtime_config.communication.maximum_message_age_seconds),
        stream=CounterStream(seed=int(communication_seed), process=STREAM_COMMUNICATION),
        cut_start_tick=cut_start,
        cut_duration_ticks=int(cut_duration or 0),
        cut_partition_ordinal=cut_ordinal,
    )
