"""Leaderless Phase 7 transition lifecycle and neighbour flooding mechanics."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

from ..runtime_configuration import RuntimeConfig
from ..topology_registry import PRIMARY_TOPOLOGY_IDS
from .guards import offline_diagnostic
from .transition_messages import (
    TRANSITION_PROTOCOL_SCHEMA_VERSION,
    CandidateScoreMessage,
    ConfirmationMessage,
    LifecycleStatusMessage,
    ReadinessMessage,
    TransitionByteLedger,
    TransitionIntent,
    TransitionMessage,
    TransitionMessageError,
    deserialize_transition_message,
    message_identity,
    validate_message_context,
)


TRANSITION_STATES: Tuple[str, ...] = (
    "STABLE_TOPOLOGY",
    "INTENT_ACTIVE",
    "CANDIDATE_SCORE_AGREEMENT",
    "WAITING_FOR_LOCAL_READINESS",
    "ALL_READY_AGREEMENT",
    "TOPOLOGY_CONFIRMATION",
    "TOPOLOGY_COMMITTED",
    "TRANSITION_EXECUTION",
    "TARGET_DWELL",
    "COMPLETE",
    "REARMED",
    "ABORTED",
)

PRECOMMIT_STATES = frozenset(TRANSITION_STATES[1:6])
ACTIVE_STATES = frozenset(TRANSITION_STATES[1:10])


class TransitionProtocolError(RuntimeError):
    """A lifecycle operation violates the authoritative state machine."""


@dataclass(frozen=True)
class TransitionProtocolRuntimeOptions:
    """Explicit opt-in; the legacy scientific runtime remains unchanged."""

    transition_protocol_v1_enabled: bool = False
    deterministic_score_threshold: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.transition_protocol_v1_enabled, bool):
            raise TypeError("transition protocol enable flag must be Boolean")
        if (
            not math.isfinite(self.deterministic_score_threshold)
            or not -1.0 <= self.deterministic_score_threshold <= 1.0
        ):
            raise ValueError("diagnostic score threshold must be in [-1, 1]")


@dataclass(frozen=True)
class AgreementResult:
    agreed: bool
    reason: str
    lifecycle_id: Optional[int]
    epoch_id: Optional[int]
    candidate_topology: Optional[int]
    aggregate_score: Optional[float] = None
    aggregate_readiness: Optional[str] = None
    aggregate_margin: Optional[float] = None
    complete_membership: bool = False


@dataclass(frozen=True)
class FloodResult:
    records_by_robot: Mapping[int, Tuple[TransitionMessage, ...]]
    rounds_executed: int
    graph_connected_each_round: bool
    final_union_connected: bool
    conflicts: Tuple[str, ...]
    ledger: TransitionByteLedger
    serialization_compute_seconds: Tuple[float, ...]
    ingestion_compute_seconds: Tuple[float, ...]


def _timestamp(message: TransitionMessage) -> float:
    return (
        message.event_timestamp
        if isinstance(message, TransitionIntent)
        else message.timestamp
    )


def _message_robot_id(message: TransitionMessage) -> int:
    return (
        message.originator_robot_id
        if isinstance(message, TransitionIntent)
        else message.robot_id
    )


def _validate_members(member_ids: Sequence[int]) -> Tuple[int, ...]:
    members = tuple(sorted(int(robot_id) for robot_id in member_ids))
    if not members or len(set(members)) != len(members) or members[0] < 0:
        raise ValueError("fixed protocol membership is invalid")
    return members


@offline_diagnostic
def _normalize_adjacency(
    member_ids: Tuple[int, ...],
    adjacency: Mapping[int, Iterable[int]],
) -> Dict[int, Tuple[int, ...]]:
    member_set = set(member_ids)
    normalized: Dict[int, Tuple[int, ...]] = {}
    for robot_id in member_ids:
        neighbours = tuple(sorted(set(int(x) for x in adjacency.get(robot_id, ()))))
        if robot_id in neighbours or any(x not in member_set for x in neighbours):
            raise ValueError("communication graph contains invalid neighbour")
        normalized[robot_id] = neighbours
    for robot_id, neighbours in normalized.items():
        for neighbour in neighbours:
            if robot_id not in normalized[neighbour]:
                raise ValueError("transition protocol requires symmetric links")
    return normalized


@offline_diagnostic
def communication_graph_diameter(
    member_ids: Sequence[int],
    adjacency: Mapping[int, Iterable[int]],
) -> int:
    members = _validate_members(member_ids)
    graph = _normalize_adjacency(members, adjacency)
    diameter = 0
    for source in members:
        distances = {source: 0}
        queue = [source]
        for current in queue:
            for neighbour in graph[current]:
                if neighbour not in distances:
                    distances[neighbour] = distances[current] + 1
                    queue.append(neighbour)
        if len(distances) != len(members):
            return -1
        diameter = max(diameter, max(distances.values(), default=0))
    return diameter


@offline_diagnostic
def _union_graph(
    members: Tuple[int, ...],
    schedule: Sequence[Mapping[int, Iterable[int]]],
) -> Dict[int, Tuple[int, ...]]:
    union: Dict[int, set[int]] = {robot_id: set() for robot_id in members}
    for raw in schedule:
        graph = _normalize_adjacency(members, raw)
        for robot_id, neighbours in graph.items():
            union[robot_id].update(neighbours)
    return {robot_id: tuple(sorted(neighbours)) for robot_id, neighbours in union.items()}


@offline_diagnostic
def flood_transition_messages(
    member_ids: Sequence[int],
    initial_messages: Mapping[int, Sequence[TransitionMessage]],
    adjacency: Mapping[int, Iterable[int]] | Sequence[Mapping[int, Iterable[int]]],
    rounds: int,
    *,
    ledger: Optional[TransitionByteLedger] = None,
) -> FloodResult:
    """Flood immutable original records; the simulator performs delivery only."""
    members = _validate_members(member_ids)
    if isinstance(rounds, bool) or rounds < 0:
        raise ValueError("rounds must be nonnegative")
    if isinstance(adjacency, Mapping):
        schedule = tuple(adjacency for _ in range(max(rounds, 1)))
    else:
        schedule = tuple(adjacency)
        if not schedule:
            raise ValueError("time-varying communication schedule is empty")
        if len(schedule) < max(rounds, 1):
            schedule = schedule + tuple(schedule[-1] for _ in range(rounds - len(schedule)))
    graphs = tuple(_normalize_adjacency(members, schedule[index]) for index in range(rounds))
    account = ledger or TransitionByteLedger()
    serialization_timings: list[float] = []
    ingestion_timings: list[float] = []
    stores: Dict[int, Dict[Tuple[object, ...], TransitionMessage]] = {
        robot_id: {} for robot_id in members
    }
    conflicts = []
    for owner, messages in initial_messages.items():
        if owner not in stores:
            raise ValueError("initial message owner is outside membership")
        for message in messages:
            started = time.perf_counter()
            frame = message.payload_bytes()
            serialization_timings.append(time.perf_counter() - started)
            started = time.perf_counter()
            decoded = deserialize_transition_message(frame)
            ingestion_timings.append(time.perf_counter() - started)
            if _message_robot_id(decoded) != owner:
                raise ValueError("initial message provenance does not match owner")
            stores[owner][message_identity(decoded)] = decoded

    sent_once: set[Tuple[int, Tuple[object, ...]]] = set()
    connected_each_round = True
    for round_index, graph in enumerate(graphs):
        connected_each_round = connected_each_round and (
            communication_graph_diameter(members, graph) >= 0
        )
        snapshot = {
            robot_id: tuple(records.values())
            for robot_id, records in stores.items()
        }
        deliveries: Dict[int, list[bytes]] = {robot_id: [] for robot_id in members}
        for sender_id in members:
            if not graph[sender_id]:
                continue
            for message in snapshot[sender_id]:
                started = time.perf_counter()
                frame = message.payload_bytes()
                if len(serialization_timings) < 2048:
                    serialization_timings.append(time.perf_counter() - started)
                identity = message_identity(message)
                retransmission = (sender_id, identity) in sent_once
                account.record(
                    message.message_type,
                    sender_id,
                    frame,
                    retransmission=retransmission,
                )
                sent_once.add((sender_id, identity))
                for receiver_id in graph[sender_id]:
                    deliveries[receiver_id].append(frame)
        for receiver_id, frames in deliveries.items():
            for frame in frames:
                started = time.perf_counter()
                incoming = deserialize_transition_message(frame)
                if len(ingestion_timings) < 2048:
                    ingestion_timings.append(time.perf_counter() - started)
                identity = message_identity(incoming)
                previous = stores[receiver_id].get(identity)
                if previous is None:
                    stores[receiver_id][identity] = incoming
                elif previous != incoming:
                    if (
                        isinstance(previous, TransitionIntent)
                        and isinstance(incoming, TransitionIntent)
                        and previous.token_hash == incoming.token_hash
                    ):
                        chosen = min(
                            (previous, incoming),
                            key=lambda item: item.originator_robot_id,
                        )
                        stores[receiver_id][identity] = chosen
                    else:
                        conflicts.append(
                            f"robot {receiver_id} received conflicting {incoming.message_type} record"
                        )
    union = _union_graph(members, schedule[:max(rounds, 1)])
    return FloodResult(
        records_by_robot={
            robot_id: tuple(sorted(
                records.values(),
                key=lambda item: (item.message_type, item.lifecycle_id,
                                  item.epoch_id, _message_robot_id(item)),
            ))
            for robot_id, records in stores.items()
        },
        rounds_executed=rounds,
        graph_connected_each_round=connected_each_round,
        final_union_connected=communication_graph_diameter(members, union) >= 0,
        conflicts=tuple(sorted(set(conflicts))),
        ledger=account,
        serialization_compute_seconds=tuple(serialization_timings),
        ingestion_compute_seconds=tuple(ingestion_timings),
    )


def _messages_of_type(
    flood: FloodResult,
    robot_id: int,
    cls: type,
) -> Tuple[TransitionMessage, ...]:
    return tuple(
        message for message in flood.records_by_robot[robot_id]
        if isinstance(message, cls)
    )


def evaluate_intent_propagation(
    flood: FloodResult,
    member_ids: Sequence[int],
    *,
    now_seconds: float,
    maximum_age_seconds: float,
) -> AgreementResult:
    members = _validate_members(member_ids)
    if flood.conflicts or not flood.final_union_connected:
        return AgreementResult(False, "graph_or_record_conflict", None, None, None)
    reference: Optional[Tuple[int, int, int, str]] = None
    for robot_id in members:
        intents = _messages_of_type(flood, robot_id, TransitionIntent)
        valid = []
        for message in intents:
            assert isinstance(message, TransitionIntent)
            try:
                validate_message_context(
                    message,
                    member_ids=members,
                    lifecycle_id=message.lifecycle_id,
                    epoch_id=message.epoch_id,
                    now_seconds=now_seconds,
                    maximum_age_seconds=maximum_age_seconds,
                )
            except TransitionMessageError:
                continue
            valid.append(message)
        identities = {
            (item.lifecycle_id, item.epoch_id, item.candidate_topology, item.token_hash)
            for item in valid
        }
        if len(identities) != 1:
            return AgreementResult(False, "missing_stale_or_conflicting_intent", None, None, None)
        identity = next(iter(identities))
        if reference is None:
            reference = identity
        elif identity != reference:
            return AgreementResult(False, "intent_disagreement", None, None, None)
    assert reference is not None
    return AgreementResult(
        True, "intent_propagated", reference[0], reference[1], reference[2],
        complete_membership=True,
    )


def evaluate_score_agreement(
    flood: FloodResult,
    member_ids: Sequence[int],
    intent: TransitionIntent,
    *,
    now_seconds: float,
    maximum_age_seconds: float,
    threshold: float,
) -> AgreementResult:
    members = _validate_members(member_ids)
    if flood.conflicts or not flood.final_union_connected:
        return AgreementResult(False, "graph_or_record_conflict", intent.lifecycle_id,
                               intent.epoch_id, intent.candidate_topology)
    node_minima = []
    for observer_id in members:
        messages = _messages_of_type(flood, observer_id, CandidateScoreMessage)
        by_sender: Dict[int, CandidateScoreMessage] = {}
        for raw in messages:
            assert isinstance(raw, CandidateScoreMessage)
            try:
                validate_message_context(
                    raw, member_ids=members, lifecycle_id=intent.lifecycle_id,
                    epoch_id=intent.epoch_id, now_seconds=now_seconds,
                    maximum_age_seconds=maximum_age_seconds,
                )
            except TransitionMessageError:
                continue
            if raw.candidate_topology != intent.candidate_topology:
                return AgreementResult(False, "candidate_conflict", intent.lifecycle_id,
                                       intent.epoch_id, intent.candidate_topology)
            by_sender[raw.robot_id] = raw
        if set(by_sender) != set(members):
            return AgreementResult(False, "incomplete_score_membership",
                                   intent.lifecycle_id, intent.epoch_id,
                                   intent.candidate_topology)
        semantics = {message.score_semantics for message in by_sender.values()}
        if semantics == {"unavailable"} or "unavailable" in semantics:
            return AgreementResult(False, "unavailable_score", intent.lifecycle_id,
                                   intent.epoch_id, intent.candidate_topology,
                                   complete_membership=True)
        if len(semantics) != 1 or any(
            not message.validity or message.score is None
            for message in by_sender.values()
        ):
            return AgreementResult(False, "invalid_score_set", intent.lifecycle_id,
                                   intent.epoch_id, intent.candidate_topology,
                                   complete_membership=True)
        node_minima.append(min(float(message.score) for message in by_sender.values()))
    if len(set(node_minima)) != 1:
        return AgreementResult(False, "score_aggregate_disagreement",
                               intent.lifecycle_id, intent.epoch_id,
                               intent.candidate_topology, min(node_minima))
    aggregate = node_minima[0]
    return AgreementResult(
        aggregate >= threshold,
        "score_agreed" if aggregate >= threshold else "score_rejected",
        intent.lifecycle_id,
        intent.epoch_id,
        intent.candidate_topology,
        aggregate_score=aggregate,
        complete_membership=True,
    )


def evaluate_readiness_agreement(
    flood: FloodResult,
    member_ids: Sequence[int],
    intent: TransitionIntent,
    *,
    now_seconds: float,
    maximum_age_seconds: float,
) -> AgreementResult:
    members = _validate_members(member_ids)
    if flood.conflicts or not flood.final_union_connected:
        return AgreementResult(False, "graph_or_record_conflict", intent.lifecycle_id,
                               intent.epoch_id, intent.candidate_topology)
    node_states = []
    node_margins = []
    for observer_id in members:
        messages = _messages_of_type(flood, observer_id, ReadinessMessage)
        by_sender: Dict[int, ReadinessMessage] = {}
        for raw in messages:
            assert isinstance(raw, ReadinessMessage)
            try:
                validate_message_context(
                    raw, member_ids=members, lifecycle_id=intent.lifecycle_id,
                    epoch_id=intent.epoch_id, now_seconds=now_seconds,
                    maximum_age_seconds=maximum_age_seconds,
                )
            except TransitionMessageError:
                continue
            if (
                raw.source_topology != intent.source_topology
                or raw.candidate_topology != intent.candidate_topology
            ):
                return AgreementResult(False, "readiness_pair_conflict",
                                       intent.lifecycle_id, intent.epoch_id,
                                       intent.candidate_topology)
            by_sender[raw.robot_id] = raw
        if set(by_sender) != set(members):
            return AgreementResult(False, "incomplete_readiness_membership",
                                   intent.lifecycle_id, intent.epoch_id,
                                   intent.candidate_topology)
        states = {message.readiness_state for message in by_sender.values()}
        aggregate = (
            "UNKNOWN" if "UNKNOWN" in states
            else "UNSAFE" if "UNSAFE" in states
            else "SAFE"
        )
        node_states.append(aggregate)
        node_margins.append(min(message.readiness_margin for message in by_sender.values()))
    if len(set(node_states)) != 1 or len(set(node_margins)) != 1:
        return AgreementResult(False, "readiness_aggregate_disagreement",
                               intent.lifecycle_id, intent.epoch_id,
                               intent.candidate_topology)
    state = node_states[0]
    return AgreementResult(
        state == "SAFE",
        "all_ready" if state == "SAFE" else f"readiness_{state.lower()}",
        intent.lifecycle_id,
        intent.epoch_id,
        intent.candidate_topology,
        aggregate_readiness=state,
        aggregate_margin=node_margins[0],
        complete_membership=True,
    )


def evaluate_confirmation_agreement(
    flood: FloodResult,
    member_ids: Sequence[int],
    intent: TransitionIntent,
    *,
    now_seconds: float,
    maximum_age_seconds: float,
) -> AgreementResult:
    members = _validate_members(member_ids)
    if flood.conflicts or not flood.final_union_connected:
        return AgreementResult(False, "graph_or_record_conflict", intent.lifecycle_id,
                               intent.epoch_id, intent.candidate_topology)
    for observer_id in members:
        messages = _messages_of_type(flood, observer_id, ConfirmationMessage)
        by_sender: Dict[int, ConfirmationMessage] = {}
        for raw in messages:
            assert isinstance(raw, ConfirmationMessage)
            try:
                validate_message_context(
                    raw, member_ids=members, lifecycle_id=intent.lifecycle_id,
                    epoch_id=intent.epoch_id, now_seconds=now_seconds,
                    maximum_age_seconds=maximum_age_seconds,
                )
            except TransitionMessageError:
                continue
            if (
                raw.source_topology != intent.source_topology
                or raw.candidate_topology != intent.candidate_topology
            ):
                return AgreementResult(False, "confirmation_pair_conflict",
                                       intent.lifecycle_id, intent.epoch_id,
                                       intent.candidate_topology)
            by_sender[raw.robot_id] = raw
        if set(by_sender) != set(members):
            return AgreementResult(False, "incomplete_confirmation_membership",
                                   intent.lifecycle_id, intent.epoch_id,
                                   intent.candidate_topology)
        if any(message.decision != "ACCEPT" for message in by_sender.values()):
            return AgreementResult(False, "confirmation_dissent",
                                   intent.lifecycle_id, intent.epoch_id,
                                   intent.candidate_topology,
                                   complete_membership=True)
    return AgreementResult(
        True, "topology_confirmed", intent.lifecycle_id, intent.epoch_id,
        intent.candidate_topology, complete_membership=True,
    )


def evaluate_lifecycle_status_agreement(
    flood: FloodResult,
    member_ids: Sequence[int],
    intent: TransitionIntent,
    required_status: str,
    *,
    now_seconds: float,
    maximum_age_seconds: float,
) -> AgreementResult:
    """Fixed-membership agreement over one local lifecycle status per robot."""
    members = _validate_members(member_ids)
    if flood.conflicts or not flood.final_union_connected:
        return AgreementResult(False, "graph_or_record_conflict", intent.lifecycle_id,
                               intent.epoch_id, intent.candidate_topology)
    for observer_id in members:
        messages = _messages_of_type(flood, observer_id, LifecycleStatusMessage)
        by_sender: Dict[int, LifecycleStatusMessage] = {}
        for raw in messages:
            assert isinstance(raw, LifecycleStatusMessage)
            try:
                validate_message_context(
                    raw, member_ids=members, lifecycle_id=intent.lifecycle_id,
                    epoch_id=intent.epoch_id, now_seconds=now_seconds,
                    maximum_age_seconds=maximum_age_seconds,
                )
            except TransitionMessageError:
                continue
            if (
                raw.source_topology != intent.source_topology
                or raw.candidate_topology != intent.candidate_topology
            ):
                return AgreementResult(False, "status_pair_conflict",
                                       intent.lifecycle_id, intent.epoch_id,
                                       intent.candidate_topology)
            by_sender[raw.robot_id] = raw
        if set(by_sender) != set(members):
            return AgreementResult(False, "incomplete_status_membership",
                                   intent.lifecycle_id, intent.epoch_id,
                                   intent.candidate_topology)
        if any(message.status != required_status for message in by_sender.values()):
            return AgreementResult(False, "lifecycle_status_disagreement",
                                   intent.lifecycle_id, intent.epoch_id,
                                   intent.candidate_topology,
                                   complete_membership=True)
    return AgreementResult(
        True, "lifecycle_status_agreed", intent.lifecycle_id, intent.epoch_id,
        intent.candidate_topology, complete_membership=True,
    )


@dataclass
class TransitionProtocolNode:
    """One robot's independent lifecycle; no shared swarm state is accepted."""

    robot_id: int
    member_ids: Tuple[int, ...]
    runtime_config: RuntimeConfig
    committed_topology: int
    options: TransitionProtocolRuntimeOptions = field(
        default_factory=TransitionProtocolRuntimeOptions
    )
    state: str = "STABLE_TOPOLOGY"
    active_intent: Optional[TransitionIntent] = None
    mode_epoch_count: int = 0
    duplicate_intent_count: int = 0
    abort_cause: Optional[str] = None
    state_entered_seconds: float = 0.0
    dwell_started_seconds: Optional[float] = None
    rearm_started_seconds: Optional[float] = None
    local_dwell_complete: bool = False
    _score_agreed: bool = False
    _all_ready: bool = False
    _confirmed: bool = False

    def __post_init__(self) -> None:
        self.member_ids = _validate_members(self.member_ids)
        if self.robot_id not in self.member_ids:
            raise TransitionProtocolError("node robot ID is outside membership")
        if self.committed_topology not in PRIMARY_TOPOLOGY_IDS:
            raise TransitionProtocolError("node committed topology is invalid")
        if not isinstance(self.runtime_config, RuntimeConfig):
            raise TypeError("protocol node requires RuntimeConfig")
        if self.runtime_config.mission.team_size != len(self.member_ids):
            raise TransitionProtocolError("membership conflicts with runtime team size")

    def _require_enabled(self) -> None:
        if not self.options.transition_protocol_v1_enabled:
            raise TransitionProtocolError("transition protocol v1 is disabled")

    def _advance(self, state: str, timestamp_seconds: float) -> None:
        if state not in TRANSITION_STATES:
            raise TransitionProtocolError("unknown transition state")
        if not math.isfinite(timestamp_seconds) or timestamp_seconds < self.state_entered_seconds:
            raise TransitionProtocolError("state timestamp is nonmonotonic")
        self.state = state
        self.state_entered_seconds = float(timestamp_seconds)

    def request_intent(
        self,
        lifecycle_id: int,
        candidate_topology: int,
        event_type: str,
        timestamp_seconds: float,
    ) -> Optional[TransitionIntent]:
        self._require_enabled()
        if candidate_topology == self.committed_topology:
            return None
        return TransitionIntent.create(
            lifecycle_id,
            self.robot_id,
            self.committed_topology,
            candidate_topology,
            event_type,
            timestamp_seconds,
            timestamp_seconds
            + self.runtime_config.protocol.evidence_persistence_seconds
            + self.runtime_config.derived.k_intent_rounds
            * self.runtime_config.communication.communication_period_seconds,
        )

    def adopt_intent(self, intent: TransitionIntent, now_seconds: float) -> bool:
        self._require_enabled()
        if now_seconds > intent.evidence_valid_until or not intent.validity:
            raise TransitionProtocolError("invalid_or_stale_intent")
        if intent.originator_robot_id not in self.member_ids:
            raise TransitionProtocolError("invalid_intent_originator")
        if intent.source_topology != self.committed_topology:
            raise TransitionProtocolError("source_topology_mismatch")
        if self.active_intent is not None:
            if self.active_intent.token_hash == intent.token_hash:
                self.duplicate_intent_count += 1
                return False
            if intent.lifecycle_id <= self.active_intent.lifecycle_id:
                self.abort("conflicting_lifecycle", now_seconds)
                return False
            if self.state in ACTIVE_STATES:
                self.abort("active_lifecycle_cannot_be_superseded", now_seconds)
                return False
        if self.state not in ("STABLE_TOPOLOGY", "REARMED", "COMPLETE"):
            raise TransitionProtocolError("node cannot adopt intent in current state")
        self.active_intent = intent
        self.abort_cause = None
        self._score_agreed = False
        self._all_ready = False
        self._confirmed = False
        self._advance("INTENT_ACTIVE", now_seconds)
        return True

    def begin_score_agreement(self, now_seconds: float) -> None:
        if self.state != "INTENT_ACTIVE":
            raise TransitionProtocolError("score agreement requires active intent")
        self._advance("CANDIDATE_SCORE_AGREEMENT", now_seconds)

    def accept_score_agreement(self, result: AgreementResult, now_seconds: float) -> None:
        if self.state != "CANDIDATE_SCORE_AGREEMENT":
            raise TransitionProtocolError("score result is out of phase")
        if not result.agreed:
            self.abort(result.reason, now_seconds)
            return
        self._score_agreed = True
        self._advance("WAITING_FOR_LOCAL_READINESS", now_seconds)

    def begin_all_ready_agreement(self, now_seconds: float) -> None:
        if self.state != "WAITING_FOR_LOCAL_READINESS" or not self._score_agreed:
            raise TransitionProtocolError("all-ready requires score agreement")
        self._advance("ALL_READY_AGREEMENT", now_seconds)

    def accept_all_ready(self, result: AgreementResult, now_seconds: float) -> None:
        if self.state != "ALL_READY_AGREEMENT":
            raise TransitionProtocolError("readiness result is out of phase")
        if not result.agreed or result.aggregate_readiness != "SAFE":
            # UNSAFE/UNKNOWN is a blocking observation, not a new epoch and not
            # an immediate failure. The same lifecycle waits for fresh local
            # certificates until its physical timeout.
            self._advance("WAITING_FOR_LOCAL_READINESS", now_seconds)
            return
        self._all_ready = True
        self._advance("TOPOLOGY_CONFIRMATION", now_seconds)

    def accept_confirmation(self, result: AgreementResult, now_seconds: float) -> None:
        if self.state != "TOPOLOGY_CONFIRMATION" or not self._all_ready:
            raise TransitionProtocolError("confirmation result is out of phase")
        if not result.agreed:
            self.abort(result.reason, now_seconds)
            return
        self._confirmed = True

    def commit(self, now_seconds: float) -> LifecycleStatusMessage:
        if self.state != "TOPOLOGY_CONFIRMATION" or not self._confirmed:
            raise TransitionProtocolError("commit requires unanimous confirmation")
        assert self.active_intent is not None
        self.committed_topology = self.active_intent.candidate_topology
        self.mode_epoch_count += 1
        self._advance("TOPOLOGY_COMMITTED", now_seconds)
        return self.status_message("COMMITTED", "unanimous_confirmation", now_seconds)

    def begin_execution(self, now_seconds: float) -> None:
        if self.state != "TOPOLOGY_COMMITTED":
            raise TransitionProtocolError("execution requires committed topology")
        self._advance("TRANSITION_EXECUTION", now_seconds)

    def observe_target_tube(self, inside: bool, now_seconds: float) -> bool:
        if self.state not in ("TRANSITION_EXECUTION", "TARGET_DWELL"):
            raise TransitionProtocolError("target observation is out of phase")
        if not inside:
            self.dwell_started_seconds = None
            self.local_dwell_complete = False
            if self.state == "TARGET_DWELL":
                self._advance("TRANSITION_EXECUTION", now_seconds)
            return False
        if self.dwell_started_seconds is None:
            self.dwell_started_seconds = float(now_seconds)
            self._advance("TARGET_DWELL", now_seconds)
            return False
        if (
            now_seconds - self.dwell_started_seconds + 1e-12
            >= self.runtime_config.mission.recovery_dwell_seconds
        ):
            self.local_dwell_complete = True
            return True
        return False

    def mark_complete(self, now_seconds: float) -> None:
        if self.state != "TARGET_DWELL" or not self.local_dwell_complete:
            raise TransitionProtocolError("completion requires local target dwell")
        self.rearm_started_seconds = float(now_seconds)
        self._advance("COMPLETE", now_seconds)

    def abort(self, cause: str, now_seconds: float) -> None:
        if not cause:
            raise TransitionProtocolError("abort cause must be nonempty")
        if self.state in ("COMPLETE", "REARMED"):
            raise TransitionProtocolError("completed lifecycle cannot abort")
        self.abort_cause = cause
        self.rearm_started_seconds = float(now_seconds)
        self._advance("ABORTED", now_seconds)

    def try_rearm(self, now_seconds: float) -> bool:
        if self.state not in ("ABORTED", "COMPLETE"):
            return False
        if self.rearm_started_seconds is None:
            self.rearm_started_seconds = self.state_entered_seconds
        if (
            now_seconds - self.rearm_started_seconds + 1e-12
            < self.runtime_config.protocol.rearm_inactive_seconds
        ):
            return False
        self.active_intent = None
        self._score_agreed = False
        self._all_ready = False
        self._confirmed = False
        self.dwell_started_seconds = None
        self.local_dwell_complete = False
        self._advance("REARMED", now_seconds)
        return True

    def status_message(
        self, status: str, cause: str, timestamp_seconds: float
    ) -> LifecycleStatusMessage:
        if self.active_intent is None:
            raise TransitionProtocolError("status requires an active lifecycle")
        return LifecycleStatusMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION,
            self.active_intent.lifecycle_id,
            self.active_intent.epoch_id,
            self.robot_id,
            self.active_intent.source_topology,
            self.active_intent.candidate_topology,
            status,
            cause,
            timestamp_seconds,
            True,
        )

    def score_message(
        self,
        score: Optional[float],
        semantics: str,
        timestamp_seconds: float,
        *,
        validity: bool = True,
    ) -> CandidateScoreMessage:
        if self.active_intent is None:
            raise TransitionProtocolError("score requires active lifecycle")
        return CandidateScoreMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION,
            self.active_intent.lifecycle_id,
            self.active_intent.epoch_id,
            self.robot_id,
            self.active_intent.candidate_topology,
            score,
            semantics,
            timestamp_seconds,
            validity,
        )

    def readiness_message(
        self,
        state: str,
        margin: float,
        timestamp_seconds: float,
    ) -> ReadinessMessage:
        if self.active_intent is None:
            raise TransitionProtocolError("readiness requires active lifecycle")
        return ReadinessMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION,
            self.active_intent.lifecycle_id,
            self.active_intent.epoch_id,
            self.robot_id,
            self.active_intent.source_topology,
            self.active_intent.candidate_topology,
            state,
            margin,
            timestamp_seconds,
            True,
        )

    def confirmation_message(
        self,
        decision: str,
        timestamp_seconds: float,
    ) -> ConfirmationMessage:
        if self.active_intent is None:
            raise TransitionProtocolError("confirmation requires active lifecycle")
        return ConfirmationMessage(
            TRANSITION_PROTOCOL_SCHEMA_VERSION,
            self.active_intent.lifecycle_id,
            self.active_intent.epoch_id,
            self.robot_id,
            self.active_intent.source_topology,
            self.active_intent.candidate_topology,
            decision,
            timestamp_seconds,
            True,
        )
