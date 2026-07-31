"""Leaderless decision-epoch protocol: trigger -> agree -> score -> confirm -> commit.

The problem this module solves
------------------------------
`consensus.py` gives every robot an identical finite-round averaging rule, but
averaging alone does not answer three questions that a decentralized selector
must answer without a coordinator:

1. *When* does a decision happen?  No robot may be told "now"; each one has to
   decide from its own sensors, and those independent decisions have to converge
   onto a single event.
2. *Which* event is it?  Two robots that trigger at almost the same instant must
   end up running ONE epoch, not two overlapping ones, or their score-consensus
   messages are mutually unusable (`ConsensusNode.accept` rejects an
   epoch-id mismatch, silently and correctly).
3. *When is the answer safe to act on?*  A robot that has merely computed a
   mode has not agreed on one; it must be able to tell the difference, and when
   it cannot, it must do something conservative rather than something arbitrary.

Everything here is per-robot except the four `simulate_`-prefixed harnesses,
which schedule and deliver messages exactly as `comms.simulate_broadcast_round`
and `consensus.simulate_consensus` do, and which compute nothing on a robot's
behalf.

The state machine
-----------------
::

    IDLE ---- local_trigger fires (own sensors only) ------> TRIGGERED
      ^                                                          |
      |                              k_trigger rounds of         |
      |                              max_consensus_trigger       |
      |                              (flag AND token)            |
      |                                                          v
      |                                                       SCORING
      |                            build G_i, score, k_score      |
      |                            rounds of ConsensusNode.step   |
      |                            argmax (ties -> KEEP)          |
      |                                                          v
      |                                                     CONFIRMING
      |                            k_confirm rounds of            |
      |                            confirm_mode (min AND max)     |
      |                                                          v
      +---- remaining_commitment hits 0 <---------------------- COMMITTED
                                        (commit_or_retain: commit
                                         the agreed mode, or RETAIN
                                         the previous one and log a
                                         disagreement -- never a
                                         fabricated fallback)

The token rule (this is the part that removes the leader)
---------------------------------------------------------
A trigger carries ``TriggerToken = (epoch_counter, trigger_timestamp,
robot_id)``.  Tokens are totally ordered lexicographically in that field order,
and the protocol keeps the **lexicographic MAXIMUM**.

Why maximum and not minimum: ``epoch_counter`` must be non-decreasing on every
robot, otherwise a robot that has already advanced could be dragged back into a
finished epoch by a stale packet.  Taking the maximum of the leading component
is therefore forced.  Having fixed that, using the maximum for the remaining two
components as well makes the whole rule a single monotone operation -- the same
``max`` that propagates the trigger flag also selects the epoch -- so trigger
propagation and epoch selection are literally the same computation and cannot
disagree with each other.  Ties inside one ``epoch_counter`` break towards the
later ``trigger_timestamp`` and then towards the higher ``robot_id``; the last
component makes the order total, because two distinct robots cannot share an ID.

`max` is associative, commutative and idempotent, so the agreed token does not
depend on delivery order, on how many copies of a message arrive, or on which
robot is asked -- which is exactly what "no leader" has to mean operationally.

What is deployable and what is not
----------------------------------
Deployable (robot i's own state plus messages addressed to it):
`local_trigger`, `trigger_reasons`, `observe_progress`,
`nearest_obstacle_distance`, `outgoing_trigger`, `max_consensus_trigger`,
`outgoing_confirm`, `confirm_mode`, `commit_or_retain`, and every `EpochState`
method.

Simulation boundary (schedulers; not deployable):
`simulate_trigger_consensus`, `simulate_confirm_consensus`,
`simulate_decision_epoch`.

Offline diagnostics (nobody computes them at runtime; they exist so the report
can be honest): `epoch_id_agreement`, `committed_mode_agreement`,
`component_epoch_agreement`.

A note on one parameter name
----------------------------
The per-robot epoch record is passed as ``epoch``, not ``state``: `guards.py`
treats any parameter whose name contains ``state`` as a suspected joint-state
container unless it carries a provably-scalar annotation, and `EpochState` is
not on that annotation allowlist.  Renaming the parameter keeps `guards.audit()`
discriminating instead of widening the allowlist, which would weaken the guard
for every future module.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..config import Config
from .comms import PROGRESS_WINDOW_STEPS, view_digest
from .consensus import ConsensusNode, simulate_consensus
from .ego_graph import EgoGraphConfig, build_ego_graph
from .guards import offline_diagnostic
from .local_controller import local_formation_error
from .system_model import (
    KEEP, LINE, CentralizedAccessError, CommParams, ConsensusParams, RobotView,
)

# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Passage lifecycle latch (Task 5-7). Robot-local hysteresis, no central tracker.
#
# One physical bottleneck should cost exactly two successful epochs. Without a
# latch the entry condition stays true for every step the team is inside the
# corridor, so the trigger refires the moment `h_commit` expires -- measured at
# 16.2 epochs per traversal against an ideal of 2.
#
# The latch is a per-robot state machine driven ONLY by robot i's own sensed
# clearance and its own committed mode. Nothing is shared, and no robot tracks
# "which bottleneck" the team is at.
LATCH_BEFORE_ENTRY = "BEFORE_ENTRY"
LATCH_INSIDE = "INSIDE_PASSAGE"
LATCH_COMPLETE = "COMPLETE"

# Consecutive steps of open clearance required to re-arm for a LATER, physically
# distinct bottleneck. Long enough that the tail of one passage cannot re-arm
# the entry trigger for the same passage.
REARM_OPEN_STEPS: int = 25

PHASE_IDLE = "IDLE"
PHASE_TRIGGERED = "TRIGGERED"
PHASE_SCORING = "SCORING"
PHASE_CONFIRMING = "CONFIRMING"
PHASE_COMMITTED = "COMMITTED"

PHASES: Tuple[str, ...] = (
    PHASE_IDLE, PHASE_TRIGGERED, PHASE_SCORING, PHASE_CONFIRMING,
    PHASE_COMMITTED,
)

# Sentinel epoch id meaning "no epoch is running on this robot".
EPOCH_ID_NONE: int = 0

# ---------------------------------------------------------------------------
# Mode-set code carried in ConfirmMessage.selected_mode
# ---------------------------------------------------------------------------
# Confirmation runs min-consensus and max-consensus on the same binary value at
# the same time.  One scalar field cannot carry two running aggregates, so the
# pair (lo, hi) is encoded as the SET of modes robot i has observed so far in
# its confirm neighbourhood.  With a binary mode there are exactly three
# reachable sets, so the encoding is exact and costs one byte:
#
#     lo == hi == KEEP  ->  0   (only keep observed)
#     lo == hi == LINE  ->  2   (only line observed)
#     lo != hi          ->  3   (both observed: min == KEEP, max == LINE)
#
# Union of sets IS simultaneous min and max: lo = min(lo, lo'), hi = max(hi, hi').
# The value 1 is deliberately left unused -- it was the removed `split` mode ID
# and reusing it would resurrect a retired label in the wire format.
MODE_SET_MIXED: int = 3
MODE_SET_CODES: Tuple[int, int, int] = (KEEP, LINE, MODE_SET_MIXED)

# Wire sizes, asserted against `payload_bytes()` in the tests.
TRIGGER_PAYLOAD_BYTES: int = 21
CONFIRM_PAYLOAD_BYTES: int = 16
TRIGGER_TOKEN_BYTES: int = 10

_TRIGGER_FMT = "<H I B I I H I"
_CONFIRM_FMT = "<H I B f B I"
_TOKEN_FMT = "<I I H"


# ---------------------------------------------------------------------------
# TriggerToken
# ---------------------------------------------------------------------------
@dataclass(frozen=True, order=True)
class TriggerToken:
    """(epoch_counter, trigger_timestamp, robot_id) with a total order.

    `order=True` on a frozen dataclass generates comparisons that compare the
    fields as a tuple in declaration order, i.e. exactly lexicographic order on
    (epoch_counter, trigger_timestamp, robot_id).  The order is *total* on real
    tokens because the last component is a persistent unique robot ID, so two
    distinct tokens can never compare equal.

    The protocol keeps the lexicographic MAXIMUM; see the module docstring for
    why maximum rather than minimum is forced by the epoch counter.
    """

    epoch_counter: int
    trigger_timestamp: int
    robot_id: int

    def as_tuple(self) -> Tuple[int, int, int]:
        return (int(self.epoch_counter), int(self.trigger_timestamp),
                int(self.robot_id))

    def pack(self) -> bytes:
        """10-byte canonical encoding, embedded in every TriggerMessage."""
        return struct.pack(
            _TOKEN_FMT,
            int(self.epoch_counter) & 0xFFFFFFFF,
            int(self.trigger_timestamp) & 0xFFFFFFFF,
            int(self.robot_id) & 0xFFFF,
        )


def token_max(left: Optional[TriggerToken],
              right: Optional[TriggerToken]) -> Optional[TriggerToken]:
    """Lexicographic max, with `None` ("no token held") as the identity element.

    Associative, commutative and idempotent, so folding any multiset of tokens
    in any order gives the same result. That is what makes duplicated and
    out-of-order trigger deliveries harmless.
    """
    if left is None:
        return right
    if right is None:
        return left
    return left if left >= right else right


def epoch_id_from_token(token: Optional[TriggerToken]) -> int:
    """Derive the epoch id every robot must agree on, from the token alone.

    A pure function of the token, so two robots holding the same token compute
    the same id with no exchange; two robots holding different tokens compute
    different ids and their score/confirm messages are mutually rejected --
    which is precisely how overlapping epochs are detected instead of silently
    blended.

    31 bits of BLAKE2b. Collisions (probability 2^-31 per pair) would merge two
    distinct epochs; the token itself, not the id, is the authority, and
    `simulate_decision_epoch` reports both.
    """
    if token is None:
        return EPOCH_ID_NONE
    digest = hashlib.blake2b(token.pack(), digest_size=4).digest()
    value = int.from_bytes(digest, "big") & 0x7FFFFFFF
    return value if value != EPOCH_ID_NONE else 1


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TriggerMessage:
    """Trigger-phase packet. Complete over-the-air schema.

    ==================  ==========================  =====================
    field               type                        bytes (little endian)
    ==================  ==========================  =====================
    sender_id           int (uint16)                2
    epoch_counter       int (uint32)                4
    trigger_flag        bool (uint8)                1
    trigger_token       (uint32, uint32, uint16)    10
    timestamp_step      int (uint32)                4
    ==================  ==========================  =====================

    21 bytes. No list-valued field, so a trigger cannot carry anyone's state
    and cannot relay a neighbour list. An all-zero token encodes "no token
    held": a real token always has ``epoch_counter >= 1`` because
    `EpochState.arm_trigger` proposes ``epoch_counter + 1`` starting from 0.
    """

    sender_id: int
    epoch_counter: int
    trigger_flag: bool
    trigger_token: Optional[TriggerToken]
    timestamp_step: int

    def payload_bytes(self) -> bytes:
        tok = self.trigger_token
        return struct.pack(
            _TRIGGER_FMT,
            int(self.sender_id) & 0xFFFF,
            int(self.epoch_counter) & 0xFFFFFFFF,
            1 if self.trigger_flag else 0,
            0 if tok is None else int(tok.epoch_counter) & 0xFFFFFFFF,
            0 if tok is None else int(tok.trigger_timestamp) & 0xFFFFFFFF,
            0 if tok is None else int(tok.robot_id) & 0xFFFF,
            int(self.timestamp_step) & 0xFFFFFFFF,
        )


@dataclass(frozen=True)
class ConfirmMessage:
    """Confirmation-phase packet. Complete over-the-air schema.

    ==================  =========================  =====================
    field               type                       bytes (little endian)
    ==================  =========================  =====================
    sender_id           int (uint16)               2
    epoch_id            int (uint32)               4
    selected_mode       int (uint8, mode-set code) 1
    margin              float (float32)            4
    confirm_round       int (uint8)                1
    timestamp_step      int (uint32)               4
    ==================  =========================  =====================

    16 bytes. `selected_mode` is the mode-SET code (see `MODE_SET_MIXED`), not a
    plain mode: it has to carry the running min and max simultaneously, and with
    a binary mode the set fits in the same byte a plain mode would have used.

    `margin` is float32 on the wire and float64 in memory; `payload_bytes` is
    used for size accounting and digests, never as the value source.
    """

    sender_id: int
    epoch_id: int
    selected_mode: int
    margin: float
    confirm_round: int
    timestamp_step: int

    @classmethod
    def from_bounds(cls, sender_id: int, epoch_id: int, mode_lo: int,
                    mode_hi: int, margin: float, confirm_round: int,
                    timestamp_step: int) -> "ConfirmMessage":
        return cls(sender_id=int(sender_id), epoch_id=int(epoch_id),
                   selected_mode=encode_mode_set(mode_lo, mode_hi),
                   margin=float(margin), confirm_round=int(confirm_round),
                   timestamp_step=int(timestamp_step))

    def mode_bounds(self) -> Tuple[int, int]:
        """(min, max) of the mode set this message carries."""
        return decode_mode_set(self.selected_mode)

    def payload_bytes(self) -> bytes:
        return struct.pack(
            _CONFIRM_FMT,
            int(self.sender_id) & 0xFFFF,
            int(self.epoch_id) & 0xFFFFFFFF,
            int(self.selected_mode) & 0xFF,
            float(self.margin),
            int(self.confirm_round) & 0xFF,
            int(self.timestamp_step) & 0xFFFFFFFF,
        )


def encode_mode_set(mode_lo: int, mode_hi: int) -> int:
    lo, hi = int(mode_lo), int(mode_hi)
    if lo not in (KEEP, LINE) or hi not in (KEEP, LINE):
        raise ValueError("modes must be KEEP(0) or LINE(2), got "
                         "({}, {})".format(mode_lo, mode_hi))
    if lo > hi:
        raise ValueError("mode_lo must not exceed mode_hi")
    return MODE_SET_MIXED if lo != hi else lo


def decode_mode_set(code: int) -> Tuple[int, int]:
    value = int(code)
    if value == MODE_SET_MIXED:
        return (KEEP, LINE)
    if value in (KEEP, LINE):
        return (value, value)
    raise ValueError("mode-set code {} is not in {}".format(code, MODE_SET_CODES))


# ---------------------------------------------------------------------------
# Disagreement record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DisagreementEvent:
    """Why one robot declined to commit. Recorded, never resolved by guessing."""

    robot_id: int
    epoch_id: int
    step: int
    reasons: Tuple[str, ...]
    mode_lo: int
    mode_hi: int
    margin_min: float
    retained_mode: int
    epoch_mismatch: int

    @property
    def kind(self) -> str:
        return self.reasons[0] if self.reasons else "none"


# Fixed priority so `kind` is deterministic when several reasons hold at once.
FAILURE_PRIORITY: Tuple[str, ...] = (
    "epoch_overlap", "mode_disagreement", "weak_margin",
)


# ---------------------------------------------------------------------------
# Trigger thresholds -- every one of them read off an existing env constant
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TriggerThresholds:
    """Local trigger thresholds, derived from `EnvConfig` and `ConsensusParams`.

    None of these is tuned on results. Each is an existing constant, or an
    existing constant combined in the same way the existing controller combines
    it, so the trigger cannot be accused of having been fitted to the metric it
    is later evaluated on.
    """

    # Nearest sensed obstacle, centre-to-centre. Set to
    # ``max(nominal_spacing, min_ro_distance)`` = 0.9 m, which is *exactly*
    # `ro_active` in `local_controller.local_controller` and in
    # `controllers.expert_action`: the distance at which the robot-obstacle
    # clearance kernel stops being identically zero. So the trigger fires
    # precisely when the robot's own avoidance term wakes up -- the same event,
    # not a second threshold invented for the trigger.
    clearance_m: float
    recovery_clearance_m: float

    # Own along-mission displacement over `PROGRESS_WINDOW_STEPS` steps
    # (`comms.OwnHistory.progress`). Set to ``dt * max_speed`` = 0.135 m: one
    # control step of free flight. Over a 5-step window that means the robot
    # averaged at most one fifth of max speed. Uses only dt and max_speed.
    progress_m: float

    # "Sustained" = held for one full progress window, so the streak cannot be
    # an artefact of a window that still overlaps pre-stall motion.
    progress_hold_steps: int

    # Magnitude of the locally estimated formation error. Set to the existing
    # `formation_tolerance` = 0.55 m, the constant the environment already uses
    # to decide whether the team is in formation.
    formation_err_m: float

    # Forced cadence, so an epoch happens even if nothing local looks wrong.
    decision_interval: int

    @classmethod
    def from_config(cls, cfg: Config,
                    consensus: Optional[ConsensusParams] = None) -> "TriggerThresholds":
        env = cfg.env
        cons = consensus or ConsensusParams()
        return cls(
            clearance_m=float(max(env.nominal_spacing, env.min_ro_distance)),
            # LINE -> KEEP. Robot i needs room on its own flanks before the
            # team can spread back into the nominal grid. Two nominal spacings
            # is the smallest clearance at which a 3-column keep template
            # (lateral extent 2 x spacing at N=6) can begin to re-form, and it
            # is strictly greater than `clearance_m`, so the entry and recovery
            # triggers cannot both fire on the same geometry.
            recovery_clearance_m=float(2.0 * env.nominal_spacing),
            progress_m=float(env.dt * env.max_speed),
            progress_hold_steps=int(PROGRESS_WINDOW_STEPS),
            formation_err_m=float(env.formation_tolerance),
            decision_interval=int(cons.decision_interval),
        )


# ---------------------------------------------------------------------------
# Per-robot epoch state
# ---------------------------------------------------------------------------
@dataclass
class EpochState:
    """Robot i's decision-epoch record. Local memory only.

    Every field is either robot i's own bookkeeping or the result of folding
    messages that were addressed to robot i. Nothing here is shared, and no
    instance ever reads another instance.
    """

    robot_id: int
    epoch_counter: int = 0
    epoch_id: int = EPOCH_ID_NONE
    trigger_token: Optional[TriggerToken] = None
    trigger_timestamp: int = -1
    phase: str = PHASE_IDLE
    consensus_round: int = 0
    committed_mode: int = KEEP
    remaining_commitment: int = 0

    # -- working state for the epoch currently in flight -------------------
    trigger_flag: bool = False
    mode_lo: int = KEEP
    mode_hi: int = KEEP
    margin_min: float = 0.0
    own_proposal: int = KEEP
    own_margin: float = 0.0
    confirm_round: int = 0
    epoch_mismatch: int = 0
    low_progress_streak: int = 0

    # -- diagnostics -------------------------------------------------------
    disagreements: List[DisagreementEvent] = field(default_factory=list)
    commits: int = 0
    retentions: int = 0
    rejected_stale: int = 0
    rejected_future: int = 0
    rejected_self: int = 0
    # -- passage lifecycle latch (Task 5-7) --
    passage_latch: str = LATCH_BEFORE_ENTRY
    open_clearance_streak: int = 0
    entry_epochs: int = 0
    recovery_epochs: int = 0
    suppressed_entry: int = 0
    suppressed_recovery: int = 0
    suppressed_noop_arm: int = 0

    @property
    def locked(self) -> bool:
        """True while the commitment window is still open."""
        return self.remaining_commitment > 0

    def arm_trigger(self, now_step: int) -> TriggerToken:
        """Robot i raises its own trigger. Proposes `epoch_counter + 1`.

        Starting from 0 the first proposal is counter 1, which is what makes an
        all-zero token unambiguously mean "no token held" on the wire.
        """
        token = TriggerToken(epoch_counter=int(self.epoch_counter) + 1,
                             trigger_timestamp=int(now_step),
                             robot_id=int(self.robot_id))
        self.trigger_flag = True
        self.trigger_token = token_max(self.trigger_token, token)
        self.adopt(self.trigger_token)
        if self.phase == PHASE_IDLE:
            self.phase = PHASE_TRIGGERED
        return token

    def adopt(self, token: TriggerToken) -> None:
        """Take on the agreed token and the epoch id derived from it."""
        self.trigger_token = token
        self.epoch_counter = max(int(self.epoch_counter), int(token.epoch_counter))
        self.trigger_timestamp = int(token.trigger_timestamp)
        self.epoch_id = epoch_id_from_token(token)

    def begin_scoring(self) -> None:
        self.phase = PHASE_SCORING
        self.consensus_round = 0

    def begin_confirming(self, mode: int, margin: float) -> None:
        """Seed min/max consensus with robot i's OWN post-score proposal."""
        if int(mode) not in (KEEP, LINE):
            raise ValueError("proposal must be KEEP(0) or LINE(2)")
        self.own_proposal = int(mode)
        self.own_margin = float(margin)
        self.mode_lo = int(mode)
        self.mode_hi = int(mode)
        self.margin_min = float(margin)
        self.confirm_round = 0
        self.epoch_mismatch = 0
        self.phase = PHASE_CONFIRMING

    def commit(self, mode: int, h_commit: int) -> None:
        if int(mode) not in (KEEP, LINE):
            raise ValueError("committed mode must be KEEP(0) or LINE(2)")
        self.committed_mode = int(mode)
        self.remaining_commitment = int(h_commit)
        self.phase = PHASE_COMMITTED
        self.trigger_flag = False
        self.commits += 1
        self.low_progress_streak = 0

    def retain(self, h_commit: int, reasons: Tuple[str, ...],
               now_step: int) -> DisagreementEvent:
        """Keep the previous committed mode and record why.

        No fallback mode is chosen. The robot leaves the epoch holding exactly
        what it held before, which is the only choice that adds no information
        the swarm did not actually agree on. The commitment dwell is applied the
        same way as after a successful commit, so a failed epoch cannot re-open
        immediately and turn a persistent disagreement into a retry storm.
        """
        event = DisagreementEvent(
            robot_id=int(self.robot_id), epoch_id=int(self.epoch_id),
            step=int(now_step), reasons=tuple(reasons),
            mode_lo=int(self.mode_lo), mode_hi=int(self.mode_hi),
            margin_min=float(self.margin_min),
            retained_mode=int(self.committed_mode),
            epoch_mismatch=int(self.epoch_mismatch),
        )
        self.disagreements.append(event)
        self.retentions += 1
        self.remaining_commitment = int(h_commit)
        self.phase = PHASE_COMMITTED
        self.trigger_flag = False
        self.low_progress_streak = 0
        return event

    def tick(self) -> int:
        """Advance one control step of the commitment window.

        Returns the remaining commitment. When it reaches zero the epoch is
        closed and the robot returns to IDLE, where `local_trigger` can fire
        again. Called exactly once per control step.
        """
        if self.remaining_commitment > 0:
            self.remaining_commitment -= 1
            if self.remaining_commitment == 0:
                self.close_epoch()
        return self.remaining_commitment

    def close_epoch(self) -> None:
        """Return to IDLE, keeping the committed mode and the epoch counter."""
        self.phase = PHASE_IDLE
        self.trigger_flag = False
        self.trigger_token = None
        self.epoch_id = EPOCH_ID_NONE
        self.consensus_round = 0
        self.confirm_round = 0
        self.epoch_mismatch = 0
        self.mode_lo = int(self.committed_mode)
        self.mode_hi = int(self.committed_mode)
        self.margin_min = 0.0

    def snapshot(self) -> Dict[str, object]:
        return {
            "robot_id": int(self.robot_id),
            "phase": self.phase,
            "epoch_counter": int(self.epoch_counter),
            "epoch_id": int(self.epoch_id),
            "token": None if self.trigger_token is None else self.trigger_token.as_tuple(),
            "committed_mode": int(self.committed_mode),
            "remaining_commitment": int(self.remaining_commitment),
            "mode_lo": int(self.mode_lo),
            "mode_hi": int(self.mode_hi),
            "margin_min": float(self.margin_min),
            "commits": int(self.commits),
            "retentions": int(self.retentions),
        }


# ---------------------------------------------------------------------------
# Local trigger. RobotView in, bool out. No global anything.
# ---------------------------------------------------------------------------
def nearest_obstacle_distance(view: RobotView) -> float:
    """Centre-to-centre distance to the nearest obstacle robot i sensed itself.

    `RobotView.obstacles` entries are already ego-relative `(dx, dy, radius)`
    (or the 5-tuple form with relative velocity), produced by robot i's own
    sensor within `r_obs`. Returns +inf when nothing is in view.
    """
    best = math.inf
    for entry in view.obstacles:
        d = math.hypot(float(entry[0]), float(entry[1]))
        if d < best:
            best = d
    return float(best)


def observe_progress(view: RobotView, cfg: Config, epoch: EpochState) -> int:
    """Advance robot i's own low-progress streak. Call once per control step.

    Kept separate from `local_trigger` so the trigger predicate stays pure: a
    predicate that silently mutated a counter would give different answers
    depending on how many times it was called within one step.
    """
    thresholds = TriggerThresholds.from_config(cfg)
    if float(view.local_progress) < thresholds.progress_m:
        epoch.low_progress_streak += 1
    else:
        epoch.low_progress_streak = 0
    return int(epoch.low_progress_streak)


def trigger_reasons(view: RobotView, cfg: Config,
                    epoch: Optional[EpochState] = None,
                    consensus: Optional[ConsensusParams] = None) -> Dict[str, bool]:
    """The four independent local trigger conditions, evaluated separately.

    Reported individually rather than as one boolean so the report can say WHY
    epochs fired, and so each condition can be tested in isolation.

    `low_progress` needs memory (it is a *sustained* condition), so it is the
    one condition that reads `epoch.low_progress_streak`. With `epoch=None` the
    streak is 0 and that condition is simply False: a `RobotView` on its own
    cannot know how long anything has been true, and pretending otherwise would
    be the dishonest option.
    """
    if not isinstance(view, RobotView):
        raise CentralizedAccessError(
            "local_trigger accepts a RobotView only; passing an obs dict, a "
            "joint-state array or a sequence of robot states is a "
            "centralization violation (got {})".format(type(view).__name__)
        )
    thresholds = TriggerThresholds.from_config(cfg, consensus)
    streak = 0 if epoch is None else int(epoch.low_progress_streak)
    err = local_formation_error(view, int(view.committed_mode))
    err_norm = float(math.hypot(float(err[0]), float(err[1])))
    return {
        "low_clearance": bool(nearest_obstacle_distance(view) <= thresholds.clearance_m),
        "low_progress": bool(streak >= thresholds.progress_hold_steps),
        "local_formation_error": bool(err_norm > thresholds.formation_err_m),
        "interval_expiry": bool(int(view.steps_since_decision) >= thresholds.decision_interval),
    }


# Which reasons may OPEN a KEEP -> LINE epoch. `trigger_reasons` still reports
# all four for diagnostics, but two are excluded from the decision:
#
#   local_formation_error -- a deformed formation is a CONSEQUENCE of a tight
#       passage, not independent evidence of one. Including it double-counted
#       the clearance signal and re-opened epochs in open space after the
#       passage latch re-armed (measured: 87 firings in one always-KEEP
#       episode, driving no-op epochs).
#   interval_expiry -- a fixed periodic timer. Task 3B removed periodic
#       decision-making from the deployable path; leaving it inside the trigger
#       would reintroduce it through the back door.
#
# Entry is therefore driven by robot i's own sensed clearance, or by its own
# sustained lack of progress, both of which are direct evidence that the route
# ahead does not admit the nominal formation.
ENTRY_TRIGGER_REASONS: Tuple[str, ...] = ("low_clearance", "low_progress")


def local_trigger(view: RobotView, cfg: Config,
                  epoch: Optional[EpochState] = None,
                  consensus: Optional[ConsensusParams] = None) -> bool:
    """Does robot i want to open a decision epoch right now?

    Inputs: robot i's own `RobotView`, the shared mission constants in `cfg`,
    and robot i's own epoch memory. There is no global trigger, no broadcast
    "decide now", and no robot whose trigger counts for more than another's.

    Returns False while an epoch is already in flight or the commitment window
    is still open -- `h_commit` is what bounds the switching rate, and letting
    the trigger fire through it would make the dwell meaningless.
    """
    if epoch is not None and (epoch.locked or epoch.phase != PHASE_IDLE):
        return False
    reasons = trigger_reasons(view, cfg, epoch, consensus)
    return any(reasons[k] for k in ENTRY_TRIGGER_REASONS)


def local_recovery_trigger(view: RobotView, cfg: Config,
                          epoch: Optional[EpochState] = None,
                          consensus: Optional[ConsensusParams] = None) -> bool:
    """LINE -> KEEP. Robot i's own detection that the passage is behind it.

    Strictly local: robot i asks whether *its own* sensed clearance has opened
    up past `recovery_clearance_m` while it is committed to LINE. No robot
    consults the team's position, the exit plane, or anyone else's clearance --
    the exit plane is an offline scoring construct (TASK_V2 section 3), never a
    runtime input.

    Like `local_trigger` this returns False while an epoch is in flight or the
    commitment window is open, so the dwell bound applies to both directions.
    """
    if epoch is not None and (epoch.locked or epoch.phase != PHASE_IDLE):
        return False
    if epoch is not None and epoch.committed_mode != LINE:
        return False        # only LINE can recover to KEEP
    th = TriggerThresholds.from_config(cfg, consensus)
    return bool(nearest_obstacle_distance(view) >= th.recovery_clearance_m)


def recovery_trigger_reasons(view: RobotView, cfg: Config,
                             epoch: Optional[EpochState] = None,
                             consensus: Optional[ConsensusParams] = None
                             ) -> Dict[str, bool]:
    th = TriggerThresholds.from_config(cfg, consensus)
    return {"clearance_reopened":
            bool(nearest_obstacle_distance(view) >= th.recovery_clearance_m)}


# ---------------------------------------------------------------------------
# Trigger propagation: max-consensus on (flag, token)
# ---------------------------------------------------------------------------
def outgoing_trigger(epoch: EpochState, now_step: int) -> TriggerMessage:
    """Robot i's own trigger packet for this round. Own state only."""
    return TriggerMessage(
        sender_id=int(epoch.robot_id),
        epoch_counter=int(epoch.epoch_counter),
        trigger_flag=bool(epoch.trigger_flag),
        trigger_token=epoch.trigger_token,
        timestamp_step=int(now_step),
    )


def max_consensus_trigger(epoch: EpochState, inbox: Sequence[TriggerMessage],
                          now_step: int,
                          delta_stale_steps: int = CommParams().delta_stale_steps
                          ) -> bool:
    """One round of ``b_i^(k+1) = max(b_i^(k), received)``.

    `b_i` is the pair (trigger_flag, trigger_token) and `max` is
    (logical-or, `token_max`). Both are idempotent, so re-delivering a message
    that has already been folded in changes nothing -- duplicate suppression is
    a property of the operator, not a table of message ids.

    Returns True iff robot i's own value changed this round.

    A robot inside its commitment window ignores triggers entirely: it has
    already promised to hold its mode for `h_commit` steps, and joining a new
    epoch would break that promise.
    """
    if epoch.locked:
        epoch.consensus_round += 1
        return False

    before = (bool(epoch.trigger_flag), epoch.trigger_token)
    for msg in sorted(inbox, key=lambda m: int(m.sender_id)):
        if int(msg.sender_id) == int(epoch.robot_id):
            epoch.rejected_self += 1
            continue
        age = int(now_step) - int(msg.timestamp_step)
        if age < 0:
            epoch.rejected_future += 1
            continue
        if age > int(delta_stale_steps):
            epoch.rejected_stale += 1
            continue
        if not bool(msg.trigger_flag):
            continue                     # max with the identity element
        epoch.trigger_flag = True
        epoch.trigger_token = token_max(epoch.trigger_token, msg.trigger_token)

    if epoch.trigger_flag and epoch.trigger_token is not None:
        epoch.adopt(epoch.trigger_token)
        if epoch.phase == PHASE_IDLE:
            epoch.phase = PHASE_TRIGGERED
    epoch.consensus_round += 1
    return (bool(epoch.trigger_flag), epoch.trigger_token) != before


# ---------------------------------------------------------------------------
# Confirmation: simultaneous min AND max consensus on the binary mode
# ---------------------------------------------------------------------------
def outgoing_confirm(epoch: EpochState, now_step: int) -> ConfirmMessage:
    """Robot i's own confirm packet: its running (min, max) and margin."""
    return ConfirmMessage.from_bounds(
        sender_id=int(epoch.robot_id), epoch_id=int(epoch.epoch_id),
        mode_lo=int(epoch.mode_lo), mode_hi=int(epoch.mode_hi),
        margin=float(epoch.margin_min), confirm_round=int(epoch.confirm_round),
        timestamp_step=int(now_step),
    )


def confirm_mode(epoch: EpochState, inbox: Sequence[ConfirmMessage],
                 now_step: int,
                 delta_stale_steps: int = CommParams().delta_stale_steps) -> bool:
    """One round of min-consensus AND max-consensus on the mode value.

        lo_i^(k+1) = min(lo_i^(k), lo_j^(k) for j in N_i)
        hi_i^(k+1) = max(hi_i^(k), hi_j^(k) for j in N_i)
        margin_i^(k+1) = min(margin_i^(k), margin_j^(k) for j in N_i)

    After k rounds lo_i is the minimum, and hi_i the maximum, of the proposals
    in robot i's k-hop neighbourhood -- one hop per round, exactly like the
    averaging consensus. `lo_i == hi_i` therefore certifies that every proposal
    robot i can reach agreed; `lo_i != hi_i` is a *witnessed* disagreement, not
    a guess.

    A message whose `epoch_id` differs from robot i's is REJECTED, never merged,
    and counted in `epoch_mismatch`. Merging it would fold a different epoch's
    decision into this one, which is the exact failure that "overlapping epochs"
    means.

    Returns True iff robot i's own bounds or margin changed this round.
    """
    before = (int(epoch.mode_lo), int(epoch.mode_hi), float(epoch.margin_min))
    for msg in sorted(inbox, key=lambda m: int(m.sender_id)):
        if int(msg.sender_id) == int(epoch.robot_id):
            epoch.rejected_self += 1
            continue
        age = int(now_step) - int(msg.timestamp_step)
        if age < 0:
            epoch.rejected_future += 1
            continue
        if age > int(delta_stale_steps):
            epoch.rejected_stale += 1
            continue
        if int(msg.epoch_id) != int(epoch.epoch_id):
            epoch.epoch_mismatch += 1
            continue
        lo, hi = msg.mode_bounds()
        epoch.mode_lo = min(int(epoch.mode_lo), int(lo))
        epoch.mode_hi = max(int(epoch.mode_hi), int(hi))
        epoch.margin_min = min(float(epoch.margin_min), float(msg.margin))
    epoch.confirm_round += 1
    return (int(epoch.mode_lo), int(epoch.mode_hi), float(epoch.margin_min)) != before


def commit_or_retain(epoch: EpochState, now_step: int,
                     consensus: Optional[ConsensusParams] = None) -> bool:
    """Close the epoch: commit the agreed mode, or retain the previous one.

    Commits iff ALL THREE hold, judged from robot i's own observations only:

    1. ``mode_lo == mode_hi``  -- every proposal reachable in k_confirm hops
       agreed;
    2. ``epoch_mismatch == 0`` -- no packet from a different epoch arrived, so
       robot i is not straddling two overlapping epochs;
    3. ``margin_min >= confirm_margin`` -- the weakest margin robot i heard about
       clears the threshold.

    Otherwise the previous committed mode is RETAINED and a `DisagreementEvent`
    is recorded. No fallback mode is invented: picking one (say "default to
    keep") would manufacture agreement that the swarm did not reach, and two
    robots doing it with different previous modes would still disagree while
    both believed they had committed.

    Returns True iff robot i committed.
    """
    params = consensus or ConsensusParams()
    failures: List[str] = []
    if int(epoch.epoch_mismatch) != 0:
        failures.append("epoch_overlap")
    if int(epoch.mode_lo) != int(epoch.mode_hi):
        failures.append("mode_disagreement")
    if float(epoch.margin_min) < float(params.confirm_margin):
        failures.append("weak_margin")

    if not failures:
        epoch.commit(int(epoch.mode_lo), int(params.h_commit))
        return True

    ordered = tuple(sorted(failures, key=FAILURE_PRIORITY.index))
    epoch.retain(int(params.h_commit), ordered, int(now_step))
    return False


# ---------------------------------------------------------------------------
# SIMULATION BOUNDARY -- schedulers only. They deliver; robots decide.
# ---------------------------------------------------------------------------
def simulate_trigger_consensus(
    epochs: Dict[int, EpochState],
    neighbours_of: Dict[int, Sequence[int]],
    k_rounds: int,
    *,
    start_step: int = 0,
    delta_stale_steps: int = 3,
    packet_loss: float = 0.0,
    delay_steps: int = 0,
    seed: int = 0,
    arm_offsets: Optional[Dict[int, int]] = None,
    record_history: bool = True,
    accountant: Optional[object] = None,
) -> Dict[str, object]:
    """Run `k_rounds` of trigger max-consensus. Simulation boundary.

    Schedules broadcasts, applies range (via `neighbours_of`), Bernoulli loss
    and a fixed delivery delay, and hands each robot its own inbox. Every value
    change happens inside `max_consensus_trigger`, which sees one robot's state
    and one robot's inbox.

    `arm_offsets` maps robot id -> the round at which that robot's own trigger
    fires, which is how a *delayed* independent trigger is exercised.
    """
    rng = np.random.default_rng(int(seed))
    ids = sorted(int(i) for i in epochs)
    offsets = {int(k): int(v) for k, v in (arm_offsets or {}).items()}
    pending: List[Tuple[int, int, TriggerMessage]] = []
    history: List[Dict[int, object]] = []
    sent = delivered = dropped = 0

    for k in range(int(k_rounds)):
        now = int(start_step) + k
        for i in ids:
            if offsets.get(i, -1) == k:
                epochs[i].arm_trigger(now)

        for i in ids:
            msg = outgoing_trigger(epochs[i], now)
            for j in neighbours_of.get(i, ()):
                if int(j) not in epochs:
                    continue
                sent += 1
                # Accounted at the SEND site from the real message object, so
                # the byte total is never a post-hoc reconstruction, and a
                # dropped packet still counts as transmitted airtime.
                if accountant is not None:
                    accountant.record_sent(msg, now, round_index=k)
                if packet_loss > 0.0 and rng.random() < float(packet_loss):
                    dropped += 1
                    continue
                pending.append((now + int(delay_steps), int(j), msg))

        inboxes: Dict[int, List[TriggerMessage]] = {i: [] for i in ids}
        still: List[Tuple[int, int, TriggerMessage]] = []
        for deliver_step, dst, msg in pending:
            if deliver_step <= now and dst in inboxes:
                inboxes[dst].append(msg)
                delivered += 1
            else:
                still.append((deliver_step, dst, msg))
        pending = still

        for i in ids:
            max_consensus_trigger(epochs[i], inboxes[i], now, delta_stale_steps)

        if record_history:
            history.append({i: (bool(epochs[i].trigger_flag),
                                None if epochs[i].trigger_token is None
                                else epochs[i].trigger_token.as_tuple())
                            for i in ids})

    return {
        "epochs": epochs,
        "rounds": int(k_rounds),
        "history": history,
        "tokens": {i: epochs[i].trigger_token for i in ids},
        "epoch_ids": {i: int(epochs[i].epoch_id) for i in ids},
        "flags": {i: bool(epochs[i].trigger_flag) for i in ids},
        "messages_sent": sent,
        "messages_delivered": delivered,
        "messages_dropped": dropped,
        "bytes_sent": sent * TRIGGER_PAYLOAD_BYTES,
    }


def simulate_confirm_consensus(
    epochs: Dict[int, EpochState],
    neighbours_of: Dict[int, Sequence[int]],
    k_rounds: int,
    *,
    start_step: int = 0,
    delta_stale_steps: int = 3,
    packet_loss: float = 0.0,
    delay_steps: int = 0,
    seed: int = 0,
    record_history: bool = True,
    accountant: Optional[object] = None,
) -> Dict[str, object]:
    """Run `k_rounds` of min/max confirmation consensus. Simulation boundary."""
    rng = np.random.default_rng(int(seed))
    ids = sorted(int(i) for i in epochs)
    pending: List[Tuple[int, int, ConfirmMessage]] = []
    history: List[Dict[int, object]] = []
    sent = delivered = dropped = 0

    for k in range(int(k_rounds)):
        now = int(start_step) + k
        for i in ids:
            msg = outgoing_confirm(epochs[i], now)
            for j in neighbours_of.get(i, ()):
                if int(j) not in epochs:
                    continue
                sent += 1
                # Accounted at the SEND site from the real message object, so
                # the byte total is never a post-hoc reconstruction, and a
                # dropped packet still counts as transmitted airtime.
                if accountant is not None:
                    accountant.record_sent(msg, now, round_index=k)
                if packet_loss > 0.0 and rng.random() < float(packet_loss):
                    dropped += 1
                    continue
                pending.append((now + int(delay_steps), int(j), msg))

        inboxes: Dict[int, List[ConfirmMessage]] = {i: [] for i in ids}
        still: List[Tuple[int, int, ConfirmMessage]] = []
        for deliver_step, dst, msg in pending:
            if deliver_step <= now and dst in inboxes:
                inboxes[dst].append(msg)
                delivered += 1
            else:
                still.append((deliver_step, dst, msg))
        pending = still

        for i in ids:
            confirm_mode(epochs[i], inboxes[i], now, delta_stale_steps)

        if record_history:
            history.append({i: (int(epochs[i].mode_lo), int(epochs[i].mode_hi))
                            for i in ids})

    return {
        "epochs": epochs,
        "rounds": int(k_rounds),
        "history": history,
        "bounds": {i: (int(epochs[i].mode_lo), int(epochs[i].mode_hi)) for i in ids},
        "epoch_mismatch": {i: int(epochs[i].epoch_mismatch) for i in ids},
        "messages_sent": sent,
        "messages_delivered": delivered,
        "messages_dropped": dropped,
        "bytes_sent": sent * CONFIRM_PAYLOAD_BYTES,
    }


def simulate_decision_epoch(
    views: Dict[int, RobotView],
    neighbours_of: Dict[int, Sequence[int]],
    epochs: Dict[int, EpochState],
    score_fn,
    *,
    cfg: Optional[Config] = None,
    comm: Optional[CommParams] = None,
    consensus: Optional[ConsensusParams] = None,
    start_step: int = 0,
    trigger_ids: Optional[Sequence[int]] = None,
    packet_loss: float = 0.0,
    delay_steps: int = 0,
    seed: int = 0,
) -> Dict[str, object]:
    """The whole epoch, end to end. Simulation boundary.

    Sequence, in order:

    0. **Freeze the snapshot.** `views` is the frozen per-robot view at trigger
       time and is never re-read from the simulator during the epoch, so every
       robot scores the same instant. `RobotView` is a frozen dataclass; the
       returned `snapshot_digest_before` / `snapshot_digest_after` are equal by
       construction and are reported so a test can assert it rather than trust
       it.
    1. **Trigger.** Each robot evaluates `local_trigger` on its own view (or the
       caller names the triggering robots explicitly through `trigger_ids`).
    2. **Agree which epoch.** `k_trigger` rounds of `max_consensus_trigger`.
    3. **Score.** Each participant builds G_i(KEEP) and G_i(LINE) from its own
       frozen view and calls `score_fn(view, g_keep, g_line) -> (q_keep, q_line)`.
       `score_fn` sees one robot's view and one robot's graphs; it is structurally
       incapable of pooling across robots.
    4. **Score consensus.** `k_score` rounds of `consensus.simulate_consensus`
       over the participant subgraph.
    5. **Argmax with a declared tie-break.** `ConsensusNode.decide` -- ties go to
       KEEP; this harness does not re-implement the rule, it calls it, so the
       two can never drift apart.
    6. **Confirm.** `k_confirm` rounds of min/max consensus.
    7. **Commit or retain.** `commit_or_retain`, which arms the `h_commit`
       dwell. The caller then calls `EpochState.tick()` once per control step;
       after exactly `h_commit` ticks the robot returns to IDLE.

    Returns per-robot mappings. There is deliberately no scalar "the mode" in
    the result: the protocol does not produce one, and offering one would invite
    exactly the centralized read this package exists to prevent.
    """
    comm_params = comm or CommParams()
    cons = consensus or ConsensusParams()
    ids = sorted(int(i) for i in views)
    step = int(start_step)

    digest_before = {i: view_digest(views[i]) for i in ids}

    # -- 1. local trigger ---------------------------------------------------
    fired: List[int] = []
    if trigger_ids is None:
        if cfg is None:
            raise ValueError("cfg is required when trigger_ids is not supplied: "
                             "local_trigger reads the env constants from it")
        for i in ids:
            observe_progress(views[i], cfg, epochs[i])
            if local_trigger(views[i], cfg, epochs[i], cons):
                fired.append(i)
    else:
        fired = [int(i) for i in trigger_ids]
    for i in fired:
        epochs[i].arm_trigger(step)

    # -- 2. which epoch -----------------------------------------------------
    trigger_result = simulate_trigger_consensus(
        epochs, neighbours_of, cons.k_trigger, start_step=step,
        delta_stale_steps=comm_params.delta_stale_steps,
        packet_loss=packet_loss, delay_steps=delay_steps, seed=int(seed) + 1)
    step += int(cons.k_trigger)

    participants = [i for i in ids
                    if epochs[i].trigger_flag and epochs[i].trigger_token is not None]
    member = set(participants)
    for i in participants:
        epochs[i].begin_scoring()

    # -- 3. score the frozen snapshot --------------------------------------
    ego_cfg = EgoGraphConfig(comm=comm_params, consensus=cons)
    logits: Dict[int, Tuple[float, float]] = {}
    for i in participants:
        g_keep = build_ego_graph(views[i], ego_cfg, KEEP)
        g_line = build_ego_graph(views[i], ego_cfg, LINE)
        q_keep, q_line = score_fn(views[i], g_keep, g_line)
        logits[i] = (float(q_keep), float(q_line))

    # -- 4. score consensus over the participant subgraph -------------------
    nodes = {
        i: ConsensusNode.from_logits(i, logits[i][0], logits[i][1],
                                     views[i].degree, epochs[i].epoch_id, cons)
        for i in participants
    }
    sub_neighbours = {
        i: [int(j) for j in neighbours_of.get(i, ()) if int(j) in member]
        for i in participants
    }
    score_result = simulate_consensus(
        nodes, sub_neighbours, cons.k_score, start_step=step,
        delta_stale_steps=comm_params.delta_stale_steps,
        packet_loss=packet_loss, delay_steps=delay_steps, seed=int(seed) + 2)
    step += int(cons.k_score)

    # -- 5. argmax (tie -> KEEP, from ConsensusNode.decide) -----------------
    proposals = {i: int(nodes[i].decide()) for i in participants}
    margins = {i: float(nodes[i].margin()) for i in participants}
    for i in participants:
        epochs[i].begin_confirming(proposals[i], margins[i])

    # -- 6. confirmation ----------------------------------------------------
    confirm_epochs = {i: epochs[i] for i in participants}
    confirm_result = simulate_confirm_consensus(
        confirm_epochs, sub_neighbours, cons.k_confirm, start_step=step,
        delta_stale_steps=comm_params.delta_stale_steps,
        packet_loss=packet_loss, delay_steps=delay_steps, seed=int(seed) + 3)
    step += int(cons.k_confirm)

    # -- 7. commit or retain ------------------------------------------------
    committed = {i: bool(commit_or_retain(epochs[i], step, cons))
                 for i in participants}

    digest_after = {i: view_digest(views[i]) for i in ids}

    return {
        "epochs": epochs,
        "fired": tuple(sorted(fired)),
        "participants": tuple(participants),
        "bystanders": tuple(i for i in ids if i not in member),
        "tokens": {i: epochs[i].trigger_token for i in ids},
        "epoch_ids": {i: int(epochs[i].epoch_id) for i in ids},
        "logits": logits,
        "proposals": proposals,
        "margins": margins,
        "committed": committed,
        "committed_modes": {i: int(epochs[i].committed_mode) for i in ids},
        "remaining_commitment": {i: int(epochs[i].remaining_commitment) for i in ids},
        "phases": {i: epochs[i].phase for i in ids},
        "disagreements": {i: tuple(epochs[i].disagreements) for i in ids},
        "commit_horizon": int(cons.h_commit),
        "trigger_result": trigger_result,
        "score_result": score_result,
        "confirm_result": confirm_result,
        "snapshot_digest_before": digest_before,
        "snapshot_digest_after": digest_after,
        "end_step": step,
    }


# ---------------------------------------------------------------------------
# Offline diagnostics -- nobody computes these at runtime
# ---------------------------------------------------------------------------
@offline_diagnostic
def epoch_id_agreement(epochs: Dict[int, EpochState]) -> float:
    """1.0 iff every robot holding an epoch holds the SAME epoch id.

    Swarm-wide by construction, hence offline-only. Reporting it without also
    reporting `component_epoch_agreement` would penalise the protocol for a
    connectivity fact it cannot control.
    """
    live = {int(e.epoch_id) for e in epochs.values() if e.epoch_id != EPOCH_ID_NONE}
    return 1.0 if len(live) <= 1 else 0.0


@offline_diagnostic
def committed_mode_agreement(epochs: Dict[int, EpochState]) -> float:
    modes = {int(e.committed_mode) for e in epochs.values()}
    return 1.0 if len(modes) <= 1 else 0.0


@offline_diagnostic
def component_epoch_agreement(epochs: Dict[int, EpochState],
                              components: Sequence[Sequence[int]]) -> float:
    """Mean over connected components of "this component agreed on one epoch".

    The honest metric when G_c is disconnected: robots that cannot exchange a
    single packet are not expected to agree, and counting that as a protocol
    failure would misattribute a connectivity fact.
    """
    if not components:
        return 1.0
    scores: List[float] = []
    for comp in components:
        live = {int(epochs[i].epoch_id) for i in comp
                if i in epochs and epochs[i].epoch_id != EPOCH_ID_NONE}
        scores.append(1.0 if len(live) <= 1 else 0.0)
    return float(np.mean(scores)) if scores else 1.0


def protocol_signature() -> Dict[str, object]:
    """Machine-readable protocol summary, for the docs and the comm-cost audit."""
    cons = ConsensusParams()
    return {
        "phases": PHASES,
        "token_rule": "lexicographic max of (epoch_counter, trigger_timestamp, robot_id)",
        "epoch_id": "blake2b-31(token) -- pure function of the token",
        "messages": {
            "TriggerMessage": {
                "bytes": TRIGGER_PAYLOAD_BYTES,
                "fields": ("sender_id", "epoch_counter", "trigger_flag",
                           "trigger_token", "timestamp_step"),
                "rounds_per_epoch": int(cons.k_trigger),
            },
            "ConfirmMessage": {
                "bytes": CONFIRM_PAYLOAD_BYTES,
                "fields": ("sender_id", "epoch_id", "selected_mode", "margin",
                           "confirm_round", "timestamp_step"),
                "rounds_per_epoch": int(cons.k_confirm),
            },
        },
        "score_rounds_per_epoch": int(cons.k_score),
        "h_commit": int(cons.h_commit),
        "decision_interval": int(cons.decision_interval),
        "confirm_margin": float(cons.confirm_margin),
        "tie_break": "argmax ties resolve to KEEP (consensus.ConsensusNode.decide)",
        "on_disagreement": "retain previous committed mode; record DisagreementEvent",
        "leader": None,
    }


# ---------------------------------------------------------------------------
# Passage lifecycle latching (Task 5-7)
# ---------------------------------------------------------------------------
def update_passage_latch(epoch: "EpochState", view: RobotView, cfg: Config,
                         consensus: Optional[ConsensusParams] = None) -> str:
    """Advance robot i's own passage latch from its own sensed clearance.

    Deployable and strictly local: reads `view.obstacles` (robot i's own sensor)
    and `epoch.committed_mode` (robot i's own memory). No peer state, no
    bottleneck identity, no central tracker.

    Re-arming for a LATER, physically distinct bottleneck requires
    `REARM_OPEN_STEPS` consecutive steps of open clearance, so the tail of one
    passage cannot re-arm the entry trigger for that same passage.
    """
    th = TriggerThresholds.from_config(cfg, consensus)
    clear = nearest_obstacle_distance(view)
    if clear >= th.recovery_clearance_m:
        epoch.open_clearance_streak += 1
    else:
        epoch.open_clearance_streak = 0

    if epoch.passage_latch == LATCH_COMPLETE:
        if epoch.open_clearance_streak >= REARM_OPEN_STEPS:
            epoch.passage_latch = LATCH_BEFORE_ENTRY
            epoch.open_clearance_streak = 0
    return epoch.passage_latch


def entry_trigger_allowed(epoch: "EpochState") -> bool:
    """KEEP -> LINE may only be proposed before the passage has been entered."""
    return (epoch.passage_latch == LATCH_BEFORE_ENTRY
            and epoch.committed_mode == KEEP)


def recovery_trigger_allowed(epoch: "EpochState") -> bool:
    """LINE -> KEEP may only be proposed once inside, and only from LINE."""
    return (epoch.passage_latch == LATCH_INSIDE
            and epoch.committed_mode == LINE)


def latched_local_trigger(view: RobotView, cfg: Config, epoch: "EpochState",
                          consensus: Optional[ConsensusParams] = None) -> bool:
    """The latched entry/recovery trigger. One call, correct direction.

    Returns True only when the latch permits that direction AND the underlying
    geometric condition holds. Suppressions are counted so churn is measurable
    rather than merely asserted.
    """
    update_passage_latch(epoch, view, cfg, consensus)
    if entry_trigger_allowed(epoch):
        return local_trigger(view, cfg, epoch, consensus)
    if recovery_trigger_allowed(epoch):
        return local_recovery_trigger(view, cfg, epoch, consensus)
    # the geometric condition may still hold; record that the latch stopped it
    if epoch.committed_mode == KEEP and local_trigger(view, cfg, epoch, consensus):
        epoch.suppressed_entry += 1
    elif epoch.committed_mode == LINE and local_recovery_trigger(
            view, cfg, epoch, consensus):
        epoch.suppressed_recovery += 1
    return False


def note_transition(epoch: "EpochState", new_mode: int) -> None:
    """Advance the latch after a CONFIRMED transition. Local bookkeeping only."""
    if new_mode == LINE and epoch.passage_latch == LATCH_BEFORE_ENTRY:
        epoch.passage_latch = LATCH_INSIDE
        epoch.entry_epochs += 1
        epoch.open_clearance_streak = 0
    elif new_mode == KEEP and epoch.passage_latch == LATCH_INSIDE:
        epoch.passage_latch = LATCH_COMPLETE
        epoch.recovery_epochs += 1
        epoch.open_clearance_streak = 0
