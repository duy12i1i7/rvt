"""Peer-to-peer neighbour discovery: beacons, neighbour tables, radio channel.

Runtime picture, per robot, once per communication period:

    emit own Beacon  ->  radio (range gate, loss, delay)  ->  peers' inboxes
    peers' Beacons   ->  NeighbourTable.ingest (converts to ego-relative)
                     ->  prune (staleness)  ->  neighbours() -> RobotView

Three of the four objects here are *deployable*: `Beacon`, `NeighbourTable` and
`OwnHistory` run unchanged on a real robot, because each one touches only that
robot's own state plus the bytes that arrived on its radio.

`RadioChannel` and `simulate_broadcast_round` are **simulation-only**.
`simulate_broadcast_round` is THE simulation boundary: the single function in
this package permitted to read the global simulator state and turn it into
per-robot `RobotView`s. See its docstring.

One-hop-only rule
-----------------
A `Beacon` carries the *sender's own* state and nothing else. There is no
neighbour list, no relay field, no aggregate over the sender's neighbours other
than the scalar `degree`. A `NeighbourTable` therefore cannot learn anything
about a two-hop robot except "my neighbour currently hears one more peer than
before". Enforced structurally (the beacon schema has no container field) and
executably by `tests/test_neighbour_discovery.py::test_no_two_hop_forwarding`.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections import deque
from dataclasses import dataclass
from typing import (Deque, Dict, Iterable, List, Mapping, Optional, Sequence,
                    Tuple)

import numpy as np

from .roles import RoleAssignment
from .system_model import KEEP, LINE, CommParams, NeighbourRecord, RobotView

Vec2 = Tuple[float, float]

# How many of a sender's most recent sequence numbers each table remembers for
# exact duplicate detection. Anything older is rejected by the out-of-order rule
# anyway (seq <= stored seq), so the horizon costs no correctness, only the
# ability to *label* a very old retransmission "duplicate" rather than
# "out-of-order".
SEEN_SEQ_HORIZON: int = 64

# Own-history window used for `local_progress`, in control steps.
# 5 steps = 0.75 s at t_ctrl = 0.15 s; at max_speed 0.9 m/s that is at most
# 0.675 m of travel, i.e. under one nominal spacing, so the signal is local in
# time as well as in space.
PROGRESS_WINDOW_STEPS: int = 5


# ---------------------------------------------------------------------------
# Beacon: the only thing that goes on the air
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Beacon:
    """One broadcast packet. This is the complete over-the-air schema.

    Absolute pose is permitted *inside* a beacon because that is literally what
    a real radio transmits; `NeighbourTable.ingest` converts it to ego-relative
    form at the instant of ingestion and the absolute value is never stored.

    Fields are exactly:

    ==================  =========================  =====================
    field               type                       bytes (little endian)
    ==================  =========================  =====================
    sender_id           int (uint16)               2
    timestamp_step      int (uint32)               4
    seq                 int (uint32)               4
    position            (float32, float32)         8
    velocity            (float32, float32)         8
    role_keep           (float32, float32)         8
    role_line           (float32, float32)         8
    committed_mode      int (uint8, KEEP|LINE)     1
    epoch_id            int (uint32)               4
    degree              int (uint8)                1
    valid               bool (uint8)               1
    ==================  =========================  =====================

    49 bytes of payload. There is deliberately no list-valued field: a beacon
    cannot carry a neighbour list, so no state can travel more than one hop.
    """

    sender_id: int
    timestamp_step: int
    seq: int
    position: Vec2
    velocity: Vec2
    role_keep: Vec2
    role_line: Vec2
    committed_mode: int
    epoch_id: int
    degree: int
    valid: bool

    def payload_bytes(self) -> bytes:
        """Canonical wire encoding. Used for digests and for size accounting."""
        return struct.pack(
            "<HII8f BIBB",
            int(self.sender_id) & 0xFFFF,
            int(self.timestamp_step) & 0xFFFFFFFF,
            int(self.seq) & 0xFFFFFFFF,
            float(self.position[0]), float(self.position[1]),
            float(self.velocity[0]), float(self.velocity[1]),
            float(self.role_keep[0]), float(self.role_keep[1]),
            float(self.role_line[0]), float(self.role_line[1]),
            int(self.committed_mode) & 0xFF,
            int(self.epoch_id) & 0xFFFFFFFF,
            int(self.degree) & 0xFF,
            1 if self.valid else 0,
        )


# ---------------------------------------------------------------------------
# Own history -> local_progress. Deployable: reads only robot i's own poses.
# ---------------------------------------------------------------------------
class OwnHistory:
    """Robot i's own recent poses. No swarm quantity ever enters here.

    `progress` is the robot's own displacement along the shared mission
    direction across the window. It is *not* the swarm's progress, not a
    centroid displacement, and not comparable across robots by construction.
    """

    __slots__ = ("window", "_buf")

    def __init__(self, window: int = PROGRESS_WINDOW_STEPS) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        self.window = int(window)
        # window + 1 samples so a full `window`-step displacement is available.
        self._buf: Deque[Tuple[int, Vec2]] = deque(maxlen=self.window + 1)

    def push(self, step: int, position: Vec2) -> None:
        self._buf.append((int(step), (float(position[0]), float(position[1]))))

    def progress(self, mission_dir: Vec2) -> float:
        """Own displacement along the unit mission direction over the window."""
        if len(self._buf) < 2:
            return 0.0
        dx, dy = float(mission_dir[0]), float(mission_dir[1])
        norm = math.hypot(dx, dy)
        if norm < 1e-9:
            return 0.0
        ux, uy = dx / norm, dy / norm
        (_, p_old) = self._buf[0]
        (_, p_new) = self._buf[-1]
        return float((p_new[0] - p_old[0]) * ux + (p_new[1] - p_old[1]) * uy)

    def __len__(self) -> int:
        return len(self._buf)


# ---------------------------------------------------------------------------
# Neighbour table. Deployable: own position + received beacons only.
# ---------------------------------------------------------------------------
@dataclass
class _Entry:
    """Internal per-sender record. Ego-relative only -- no absolute pose."""

    robot_id: int
    seq: int
    timestamp_step: int
    rel_position: Vec2
    rel_velocity: Vec2
    role_keep: Vec2
    role_line: Vec2
    committed_mode: int
    epoch_id: int
    degree: int
    valid: bool
    first_seq: int
    accepted: int
    stale_marked: bool


class NeighbourTable:
    """Robot i's one-hop neighbour table.

    Deployable. Constructed with the robot's own id and the shared `CommParams`;
    the robot's own position is written in with `set_own_position` before each
    ingestion round so incoming absolute poses can be differenced away
    immediately. Only `rel_position = p_j - p_i` and `rel_velocity = v_j - v_i`
    are ever stored, so a neighbour's absolute coordinates do not exist anywhere
    downstream of `ingest`.

    Staleness rule
    --------------
    ``age = now_step - timestamp_step``. A record with ``age > delta_stale_steps``
    is stale: excluded from `neighbours()` and from `degree()`. `prune()` marks
    it but keeps the sequence bookkeeping, so a reappearing neighbour is still
    protected against replayed old packets.
    """

    def __init__(self, robot_id: int, params: CommParams,
                 own_position: Vec2 = (0.0, 0.0),
                 own_velocity: Vec2 = (0.0, 0.0)) -> None:
        self.robot_id = int(robot_id)
        self.params = params
        self._own_position: Vec2 = (float(own_position[0]), float(own_position[1]))
        self._own_velocity: Vec2 = (float(own_velocity[0]), float(own_velocity[1]))
        self._entries: Dict[int, _Entry] = {}
        self._seen: Dict[int, set] = {}

        # -- counters (part of the public API) --
        self.duplicates_rejected: int = 0
        self.seq_restarts: int = 0
        self.out_of_order_rejected: int = 0
        self.stale_rejected: int = 0
        self.unknown_id_accepted: int = 0
        self.reappeared: int = 0
        # -- supplementary counters --
        self.accepted: int = 0
        self.self_rejected: int = 0
        self.future_rejected: int = 0
        self.stale_pruned: int = 0

    # -- own state ---------------------------------------------------------
    def set_own_position(self, position: Vec2,
                         velocity: Optional[Vec2] = None) -> None:
        self._own_position = (float(position[0]), float(position[1]))
        if velocity is not None:
            self._own_velocity = (float(velocity[0]), float(velocity[1]))

    @property
    def own_position(self) -> Vec2:
        return self._own_position

    # -- ingestion ---------------------------------------------------------
    def _remember_seq(self, sender_id: int, seq: int) -> None:
        seen = self._seen.setdefault(sender_id, set())
        seen.add(int(seq))
        if len(seen) > SEEN_SEQ_HORIZON:
            for old in sorted(seen)[:len(seen) - SEEN_SEQ_HORIZON]:
                seen.discard(old)

    def ingest(self, beacon: Beacon, now_step: int) -> bool:
        """Accept or reject one received beacon. Returns True iff accepted.

        Rejection order is fixed and total: self -> future -> stale ->
        duplicate -> out-of-order. Every rejected beacon increments exactly one
        counter and leaves the stored state untouched.
        """
        sender = int(beacon.sender_id)
        if sender == self.robot_id:
            self.self_rejected += 1
            return False

        age = int(now_step) - int(beacon.timestamp_step)
        if age < 0:
            # A packet stamped in the future cannot be used; accepting it would
            # be exactly the "replaced by future information" failure mode.
            self.future_rejected += 1
            return False
        if age > self.params.delta_stale_steps:
            self.stale_rejected += 1
            return False

        prev = self._entries.get(sender)

        # Sequence-counter restart (peer reboot / counter wrap). Detected by a
        # beacon that is FRESH by timestamp yet carries a sequence number at or
        # below the stored one. Without this branch an audit showed a rebooted
        # peer is rejected forever as a duplicate -- five fresh beacons in a row
        # all discarded, the neighbour silently gone for the rest of the mission.
        # Timestamp, not sequence, is the authority on freshness here: the
        # staleness check above has already established this beacon is recent,
        # and a replayed old beacon cannot reach this point because its
        # timestamp would be stale.
        restarted = (
            prev is not None
            and int(beacon.seq) <= prev.seq
            and int(beacon.timestamp_step) > prev.timestamp_step
        )
        if restarted:
            self.seq_restarts += 1
            self._seen.pop(sender, None)
            self._entries.pop(sender, None)
            prev = None
        elif int(beacon.seq) in self._seen.get(sender, ()):
            self.duplicates_rejected += 1
            return False
        self._remember_seq(sender, beacon.seq)

        if prev is not None and int(beacon.seq) <= prev.seq:
            self.out_of_order_rejected += 1
            return False

        px, py = self._own_position
        vx, vy = self._own_velocity
        rel_position = (float(beacon.position[0]) - px,
                        float(beacon.position[1]) - py)
        rel_velocity = (float(beacon.velocity[0]) - vx,
                        float(beacon.velocity[1]) - vy)

        if prev is None:
            self.unknown_id_accepted += 1
            entry = _Entry(
                robot_id=sender, seq=int(beacon.seq),
                timestamp_step=int(beacon.timestamp_step),
                rel_position=rel_position, rel_velocity=rel_velocity,
                role_keep=(float(beacon.role_keep[0]), float(beacon.role_keep[1])),
                role_line=(float(beacon.role_line[0]), float(beacon.role_line[1])),
                committed_mode=int(beacon.committed_mode),
                epoch_id=int(beacon.epoch_id), degree=int(beacon.degree),
                valid=bool(beacon.valid), first_seq=int(beacon.seq),
                accepted=1, stale_marked=False,
            )
            self._entries[sender] = entry
        else:
            was_stale = (int(now_step) - prev.timestamp_step) > self.params.delta_stale_steps
            if was_stale or prev.stale_marked:
                self.reappeared += 1
            prev.seq = int(beacon.seq)
            prev.timestamp_step = int(beacon.timestamp_step)
            prev.rel_position = rel_position
            prev.rel_velocity = rel_velocity
            prev.role_keep = (float(beacon.role_keep[0]), float(beacon.role_keep[1]))
            prev.role_line = (float(beacon.role_line[0]), float(beacon.role_line[1]))
            prev.committed_mode = int(beacon.committed_mode)
            prev.epoch_id = int(beacon.epoch_id)
            prev.degree = int(beacon.degree)
            prev.valid = bool(beacon.valid)
            prev.accepted += 1
            prev.stale_marked = False

        self.accepted += 1
        return True

    # -- staleness ---------------------------------------------------------
    def is_stale(self, sender_id: int, now_step: int) -> bool:
        entry = self._entries.get(int(sender_id))
        if entry is None:
            return True
        return (int(now_step) - entry.timestamp_step) > self.params.delta_stale_steps

    def prune(self, now_step: int) -> Tuple[int, ...]:
        """Mark every record older than `delta_stale_steps` stale.

        Records are marked rather than deleted so that (a) a replayed old packet
        from a neighbour that went silent is still rejected by the sequence
        rule, and (b) reappearance after silence is detectable and counted.
        Marked records are excluded from `neighbours()` and `degree()`.
        """
        marked: List[int] = []
        for sender, entry in self._entries.items():
            stale = (int(now_step) - entry.timestamp_step) > self.params.delta_stale_steps
            if stale and not entry.stale_marked:
                entry.stale_marked = True
                self.stale_pruned += 1
            if stale:
                marked.append(sender)
        return tuple(sorted(marked))

    # -- queries -----------------------------------------------------------
    def _loss_estimate(self, entry: _Entry) -> float:
        span = entry.seq - entry.first_seq + 1
        if span <= 0:
            return 0.0
        est = 1.0 - (float(entry.accepted) / float(span))
        return float(min(1.0, max(0.0, est)))

    def neighbours(self, now_step: int) -> Tuple[NeighbourRecord, ...]:
        """Fresh one-hop neighbours, ego-relative, sorted by robot_id.

        Pure: does not mutate the table. Sorting by robot_id makes the tuple
        independent of arrival order, which is what makes downstream consensus
        rounds reproducible.
        """
        out: List[NeighbourRecord] = []
        for sender in sorted(self._entries):
            entry = self._entries[sender]
            age = int(now_step) - entry.timestamp_step
            if age < 0 or age > self.params.delta_stale_steps:
                continue
            out.append(NeighbourRecord(
                robot_id=entry.robot_id,
                rel_position=entry.rel_position,
                rel_velocity=entry.rel_velocity,
                role_keep=entry.role_keep,
                role_line=entry.role_line,
                committed_mode=entry.committed_mode,
                epoch_id=entry.epoch_id,
                message_age_steps=int(age),
                degree=entry.degree,
                link_valid=bool(entry.valid),
                packet_loss_estimate=self._loss_estimate(entry),
            ))
        return tuple(out)

    def degree(self, now_step: int) -> int:
        return len(self.neighbours(now_step))

    def known_ids(self) -> Tuple[int, ...]:
        """Every sender ever accepted, fresh or not. Diagnostics only."""
        return tuple(sorted(self._entries))

    # -- determinism helpers ----------------------------------------------
    def counters(self) -> Dict[str, int]:
        return {
            "duplicates_rejected": self.duplicates_rejected,
            "out_of_order_rejected": self.out_of_order_rejected,
            "stale_rejected": self.stale_rejected,
            "unknown_id_accepted": self.unknown_id_accepted,
            "reappeared": self.reappeared,
            "accepted": self.accepted,
            "self_rejected": self.self_rejected,
            "future_rejected": self.future_rejected,
            "stale_pruned": self.stale_pruned,
        }

    def canonical_bytes(self, now_step: int) -> bytes:
        """Byte-exact serialization of the table's observable content."""
        parts: List[bytes] = [struct.pack("<ii", self.robot_id, int(now_step))]
        for sender in sorted(self._entries):
            e = self._entries[sender]
            parts.append(struct.pack(
                "<iiii", e.robot_id, e.seq, e.timestamp_step, e.first_seq))
            parts.append(struct.pack(
                "<8d", e.rel_position[0], e.rel_position[1],
                e.rel_velocity[0], e.rel_velocity[1],
                e.role_keep[0], e.role_keep[1], e.role_line[0], e.role_line[1]))
            parts.append(struct.pack(
                "<iiiiBB", e.committed_mode, e.epoch_id, e.degree, e.accepted,
                1 if e.valid else 0, 1 if e.stale_marked else 0))
        for key in sorted(self.counters()):
            parts.append(struct.pack("<i", self.counters()[key]))
        return b"".join(parts)

    def digest(self, now_step: int) -> str:
        return hashlib.sha256(self.canonical_bytes(now_step)).hexdigest()


# ---------------------------------------------------------------------------
# Radio channel. SIMULATION ONLY -- models the physical link.
# ---------------------------------------------------------------------------
def _u01(seed: int, step: int, src: int, dst: int) -> float:
    """Deterministic uniform in [0, 1) keyed by (seed, step, src, dst).

    A pure hash rather than a stateful RNG, so the draw for one (step, src, dst)
    is independent of how many other draws were taken, of iteration order, and
    of whether the simulation was resumed. Same key => same value, always.
    """
    payload = struct.pack("<qqqq", int(seed), int(step), int(src), int(dst))
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") / 18446744073709551616.0


class RadioChannel:
    """Simulated broadcast medium: range gate, Bernoulli loss, fixed delay.

    NOT deployable -- it exists only so the simulation can decide which packets
    a real radio would have delivered. It never reads a positions array: the
    boundary function hands it one source pose and one destination pose at a
    time, so the "only one function sees the joint state" property holds
    literally.

    Causality: the drop decision and the delivery step are both fixed at
    transmission time from `(seed, step, src, dst)` and the two poses at that
    step. Nothing later can revise them, so no future information can leak
    backwards into a delivery decision.
    """

    def __init__(self, params: CommParams, seed: int = 0) -> None:
        self.params = params
        self.seed = int(seed)
        self._queue: Dict[int, List[Tuple[int, Beacon]]] = {}
        self.transmitted: int = 0
        self.dropped_out_of_range: int = 0
        self.dropped_loss: int = 0
        self.delivered: int = 0
        self.dropped_expired: int = 0

    def reset(self) -> None:
        self._queue.clear()
        self.transmitted = 0
        self.dropped_out_of_range = 0
        self.dropped_loss = 0
        self.delivered = 0
        self.dropped_expired = 0

    def in_range(self, src_position: Vec2, dst_position: Vec2) -> bool:
        dx = float(dst_position[0]) - float(src_position[0])
        dy = float(dst_position[1]) - float(src_position[1])
        return math.hypot(dx, dy) <= self.params.r_comm

    def transmit(self, beacon: Beacon, src_position: Vec2, dst_id: int,
                 dst_position: Vec2, step: int) -> Optional[int]:
        """Offer one packet on one directed link. Returns the delivery step.

        Returns None when the packet is dropped (out of range, or lost).
        """
        self.transmitted += 1
        if not self.in_range(src_position, dst_position):
            self.dropped_out_of_range += 1
            return None
        if self.params.packet_loss > 0.0:
            u = _u01(self.seed, step, int(beacon.sender_id), int(dst_id))
            if u < self.params.packet_loss:
                self.dropped_loss += 1
                return None
        arrival = int(step) + int(self.params.delay_steps)
        self._queue.setdefault(arrival, []).append((int(dst_id), beacon))
        return arrival

    def deliver(self, step: int) -> Tuple[Tuple[int, Beacon], ...]:
        """Packets whose scheduled arrival is exactly `step`.

        Sorted by (dst_id, sender_id, seq) so delivery order is a function of
        the trace and not of dict iteration order. Anything scheduled for a step
        already in the past is counted as expired and dropped rather than
        silently delivered late.
        """
        for past in [s for s in self._queue if s < int(step)]:
            self.dropped_expired += len(self._queue.pop(past))
        due = self._queue.pop(int(step), [])
        due.sort(key=lambda item: (item[0], item[1].sender_id, item[1].seq))
        self.delivered += len(due)
        return tuple(due)

    def pending(self) -> int:
        return sum(len(v) for v in self._queue.values())


# ---------------------------------------------------------------------------
# Per-robot persistent radio state. Deployable container.
# ---------------------------------------------------------------------------
@dataclass
class RobotRadioState:
    """Everything robot i keeps between control steps for discovery.

    Deployable: a table over received packets, its own pose history, and its own
    transmit sequence counter. Nothing here is shared or global.
    """

    robot_id: int
    table: NeighbourTable
    history: OwnHistory
    seq: int = 0

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq


def make_radio_states(robot_ids: Iterable[int], params: CommParams,
                      progress_window: int = PROGRESS_WINDOW_STEPS
                      ) -> Dict[int, RobotRadioState]:
    return {
        int(i): RobotRadioState(
            robot_id=int(i),
            table=NeighbourTable(int(i), params),
            history=OwnHistory(progress_window),
        )
        for i in robot_ids
    }


def build_beacon(state: RobotRadioState, step: int, position: Vec2,
                 velocity: Vec2, role_keep: Vec2, role_line: Vec2,
                 committed_mode: int, epoch_id: int,
                 valid: bool = True) -> Beacon:
    """Robot i builds its own outgoing beacon. Deployable: own state only.

    `degree` is robot i's own current one-hop degree, i.e. a scalar count over
    its own table. It is not a neighbour list and carries no peer identity.
    """
    return Beacon(
        sender_id=state.robot_id,
        timestamp_step=int(step),
        seq=state.next_seq(),
        position=(float(position[0]), float(position[1])),
        velocity=(float(velocity[0]), float(velocity[1])),
        role_keep=(float(role_keep[0]), float(role_keep[1])),
        role_line=(float(role_line[0]), float(role_line[1])),
        committed_mode=int(committed_mode),
        epoch_id=int(epoch_id),
        degree=state.table.degree(step),
        valid=bool(valid),
    )


def simulate_local_obstacles(own_position: Vec2, obstacles: Optional[np.ndarray],
                             obstacle_radius: float, r_obs: float
                             ) -> Tuple[Tuple[float, float, float], ...]:
    """Simulated lidar gate. **Not deployable** -- part of the boundary.

    It reads the full obstacle array (a prohibited obs key) and returns only
    what robot i's own sensor would have seen: obstacles with
    ``||q - p_i|| <= r_obs``, as ``(rel_x, rel_y, radius)`` relative to p_i,
    ordered by distance then by index so the tuple is trace-determined. On real
    hardware the lidar driver produces this tuple directly and the full array
    never exists.
    """
    if obstacles is None:
        return ()
    arr = np.asarray(obstacles, dtype=np.float64).reshape(-1, 2)
    if arr.size == 0:
        return ()
    px, py = float(own_position[0]), float(own_position[1])
    rel = arr - np.array([px, py], dtype=np.float64)
    dist = np.hypot(rel[:, 0], rel[:, 1])
    keep = np.nonzero(dist <= float(r_obs))[0]
    order = sorted(keep.tolist(), key=lambda k: (float(dist[k]), int(k)))
    return tuple((float(rel[k, 0]), float(rel[k, 1]), float(obstacle_radius))
                 for k in order)


# ---------------------------------------------------------------------------
# THE SIMULATION BOUNDARY
# ---------------------------------------------------------------------------
def simulate_broadcast_round(
    step: int,
    positions: np.ndarray,
    velocities: np.ndarray,
    roles: RoleAssignment,
    committed_modes: Sequence[int],
    epoch_ids: Sequence[int],
    steps_since_decision: Sequence[int],
    states: Mapping[int, RobotRadioState],
    channel: RadioChannel,
    obstacles: Optional[np.ndarray],
    obstacle_radius: float,
    goal: Vec2,
    mission_dir: Vec2,
    params: CommParams,
    valid: Optional[Sequence[bool]] = None,
) -> Dict[int, RobotView]:
    """THE SIMULATION BOUNDARY. **Not deployable code.**

    This is the one and only function in `rvt_swarm.decentralized` allowed to
    read the global simulator state -- the (N,2) position and velocity arrays,
    the full obstacle array, and the per-robot mode/epoch arrays. It stands in
    for the physical radio and the physical sensors: it decides which packets
    each robot would actually have received and what each robot's own sensor
    would actually have seen, and returns one `RobotView` per robot.

    On real hardware this function does not exist. Each robot's radio driver
    delivers packets into its `NeighbourTable` and its lidar driver fills
    `obstacles`; every other function in this package already runs unchanged,
    because every other function takes a `RobotView` and never an array indexed
    by "all robots".

    Returned per robot i:
      * its own pose, role, committed mode, epoch, steps-since-decision,
      * `local_progress` from its OWN pose history only,
      * `NeighbourRecord`s built solely from beacons actually delivered to i,
        already differenced into ego-relative form,
      * obstacles within `r_obs` of p_i only, as (rel_x, rel_y, radius),
      * the shared mission constants `goal` and `mission_dir`.

    Order within one round: emit -> transmit -> deliver+ingest -> prune ->
    own-history update -> view construction. Emission uses the degree the robot
    knew at the *start* of the round, so no robot's beacon can depend on a
    packet it has not yet received.
    """
    pos = np.asarray(positions, dtype=np.float64).reshape(-1, 2)
    vel = np.asarray(velocities, dtype=np.float64).reshape(-1, 2)
    ids = sorted(int(i) for i in states)
    step = int(step)

    own_pos: Dict[int, Vec2] = {i: (float(pos[i, 0]), float(pos[i, 1])) for i in ids}
    own_vel: Dict[int, Vec2] = {i: (float(vel[i, 0]), float(vel[i, 1])) for i in ids}

    # 1. every robot writes its own current pose into its own table, so that an
    #    ingested absolute pose is differenced away immediately.
    for i in ids:
        states[i].table.set_own_position(own_pos[i], own_vel[i])

    # 2. emit -- one beacon per robot, from that robot's own state only.
    beacons: Dict[int, Beacon] = {}
    for i in ids:
        beacons[i] = build_beacon(
            states[i], step, own_pos[i], own_vel[i],
            roles.role_of(i, KEEP), roles.role_of(i, LINE),
            int(committed_modes[i]), int(epoch_ids[i]),
            True if valid is None else bool(valid[i]),
        )

    # 3. transmit on every directed link. Range/loss/delay decided here, once.
    for src in ids:
        for dst in ids:
            if src == dst:
                continue
            channel.transmit(beacons[src], own_pos[src], dst, own_pos[dst], step)

    # 4. deliver whatever is due *now* and ingest it.
    for dst, beacon in channel.deliver(step):
        if dst in states:
            states[dst].table.ingest(beacon, step)

    # 5. staleness, 6. own history, 7. views.
    views: Dict[int, RobotView] = {}
    for i in ids:
        states[i].table.prune(step)
        states[i].history.push(step, own_pos[i])
        views[i] = RobotView(
            robot_id=i,
            position=own_pos[i],
            velocity=own_vel[i],
            role_keep=roles.role_of(i, KEEP),
            role_line=roles.role_of(i, LINE),
            committed_mode=int(committed_modes[i]),
            epoch_id=int(epoch_ids[i]),
            steps_since_decision=int(steps_since_decision[i]),
            local_progress=states[i].history.progress(mission_dir),
            goal=(float(goal[0]), float(goal[1])),
            mission_dir=(float(mission_dir[0]), float(mission_dir[1])),
            neighbours=states[i].table.neighbours(step),
            obstacles=simulate_local_obstacles(
                own_pos[i], obstacles, obstacle_radius, params.r_obs),
        )
    return views


# ---------------------------------------------------------------------------
# Digest helpers for determinism tests
# ---------------------------------------------------------------------------
def view_canonical_bytes(view: RobotView) -> bytes:
    parts: List[bytes] = [struct.pack("<i", int(view.robot_id))]
    parts.append(struct.pack(
        "<10d", view.position[0], view.position[1],
        view.velocity[0], view.velocity[1],
        view.role_keep[0], view.role_keep[1],
        view.role_line[0], view.role_line[1],
        view.goal[0], view.goal[1]))
    parts.append(struct.pack(
        "<4i", int(view.committed_mode), int(view.epoch_id),
        int(view.steps_since_decision), len(view.neighbours)))
    parts.append(struct.pack("<3d", float(view.local_progress),
                             view.mission_dir[0], view.mission_dir[1]))
    for nb in view.neighbours:
        parts.append(struct.pack(
            "<i", int(nb.robot_id)))
        parts.append(struct.pack(
            "<9d", nb.rel_position[0], nb.rel_position[1],
            nb.rel_velocity[0], nb.rel_velocity[1],
            nb.role_keep[0], nb.role_keep[1], nb.role_line[0], nb.role_line[1],
            float(nb.packet_loss_estimate)))
        parts.append(struct.pack(
            "<iiiB", int(nb.committed_mode), int(nb.epoch_id),
            int(nb.message_age_steps), 1 if nb.link_valid else 0))
        parts.append(struct.pack("<i", int(nb.degree)))
    for ob in view.obstacles:
        parts.append(struct.pack("<3d", float(ob[0]), float(ob[1]), float(ob[2])))
    return b"".join(parts)


def view_digest(view: RobotView) -> str:
    return hashlib.sha256(view_canonical_bytes(view)).hexdigest()
