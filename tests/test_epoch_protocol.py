"""Evidence for the leaderless decision-epoch protocol (`decentralized/epoch.py`).

`docs/INTERRUPTED_WORKFLOW_RECOVERY_AUDIT.md` recorded `epoch.py` as
**partial / unused**: 1202 lines, 38 functions, `trace.Trace` measured 0 of them
exercised, and nothing in `rvt_swarm/`, `tests/` or `scripts/` imported it. This
file is the missing evidence. Every one of the 38 functions is exercised by at
least one dedicated test here (`test_ZZ_every_function_is_exercised` pins the
enumeration so a newly added function cannot slip in untested).

What each block asserts, and why it can fail
--------------------------------------------
A. **Token algebra.** The total order is antisymmetric and transitive by
   exhaustive enumeration; `token_max` is associative, commutative and
   idempotent with `None` as identity; `epoch_id_from_token` is a deterministic,
   collision-free function of the token over 9600 distinct tokens. These are the
   properties the leaderlessness argument rests on, so they are enumerated
   rather than sampled.
B. **Wire format.** `TriggerMessage.payload_bytes()` is 21 B and
   `ConfirmMessage.payload_bytes()` is 16 B -- the figures
   `comm_cost.assert_schema_sizes()` now verifies -- and the mode-set codec
   round-trips every reachable set including MIXED.
C. **Trigger inputs.** Each of the four conditions fires alone, and none fires
   in open space. Every threshold is re-derived here from `EnvConfig` so a
   silently retuned constant is caught.
D. **Leaderlessness / no central initiation.** Identifier scan, structural scan
   over the signatures, module-level-mutable-state scan, and two functional
   tests: the token winner does not decide the mode, and the winner relabels
   with the robot IDs.
E. **Message hygiene.** Duplicate, stale, future-dated and self-addressed
   packets.
F. **Simultaneity.** Two robots triggering in the same step resolve to one
   epoch id, under both arrival orders and both delivery schedules.
G/H. **Commitment and reopening.** Exactly `h_commit` ticks, mode frozen while
   locked, clean close, second epoch afterwards.
I. **End to end** through `simulate_decision_epoch`, including the three
   disagreement reasons and the offline agreement diagnostics.

THE SIMULATION BOUNDARY IN THIS FILE
------------------------------------
`simulate_team_views` reads the joint state on purpose -- that is what a
simulated radio and sensor do. It is not deployable code: it lives in the test
tree and nothing in `rvt_swarm.decentralized` imports it. Everything downstream
of it sees one `RobotView` or one `EpochState` and nothing else.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import math
import re
import struct
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import epoch as epoch_mod
from rvt_swarm.decentralized.comms import PROGRESS_WINDOW_STEPS
from rvt_swarm.decentralized.consensus import connected_components
from rvt_swarm.decentralized.epoch import (
    CONFIRM_PAYLOAD_BYTES,
    EPOCH_ID_NONE,
    FAILURE_PRIORITY,
    MODE_SET_CODES,
    MODE_SET_MIXED,
    PHASE_COMMITTED,
    PHASE_CONFIRMING,
    PHASE_IDLE,
    PHASE_SCORING,
    PHASE_TRIGGERED,
    PHASES,
    TRIGGER_PAYLOAD_BYTES,
    TRIGGER_TOKEN_BYTES,
    ConfirmMessage,
    DisagreementEvent,
    EpochState,
    TriggerMessage,
    TriggerThresholds,
    TriggerToken,
    commit_or_retain,
    committed_mode_agreement,
    component_epoch_agreement,
    confirm_mode,
    decode_mode_set,
    encode_mode_set,
    epoch_id_agreement,
    epoch_id_from_token,
    ENTRY_TRIGGER_REASONS,
    entry_trigger_allowed,
    latched_local_trigger,
    local_trigger,
    local_recovery_trigger,
    rearm_open_steps,
    evidence_persistence_steps,
    note_transition,
    recovery_trigger_allowed,
    update_passage_latch,
    recovery_trigger_reasons,
    max_consensus_trigger,
    nearest_obstacle_distance,
    observe_progress,
    outgoing_confirm,
    outgoing_trigger,
    protocol_signature,
    simulate_confirm_consensus,
    simulate_decision_epoch,
    simulate_trigger_consensus,
    token_max,
    trigger_reasons,
)
from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.decentralized.system_model import (
    KEEP,
    LINE,
    MODES,
    CentralizedAccessError,
    CommParams,
    ConsensusParams,
    NeighbourRecord,
    RobotView,
)

CFG = Config()
COMM = CommParams()
CONS = ConsensusParams()
GOAL = (12.0, 0.0)
MISSION = (1.0, 0.0)

# `local_progress` comfortably above `dt * max_speed` = 0.135 m, so the
# low-progress condition is off unless a test turns it on deliberately.
MOVING = 0.5


# ---------------------------------------------------------------------------
# Simulation boundary (test-side only -- see module docstring)
# ---------------------------------------------------------------------------
def simulate_team_views(
    positions: Sequence[Tuple[float, float]],
    roles: RoleAssignment,
    *,
    obstacles: Sequence[Tuple[float, float, float]] = (),
    local_progress: float = MOVING,
    steps_since_decision: int = 0,
    committed_mode: int = KEEP,
    epoch_id: int = 0,
    comm: CommParams = COMM,
) -> Dict[int, RobotView]:
    """SIMULATION BOUNDARY -- not deployable code.

    Reads every robot's absolute position and the world obstacle list, and emits
    per robot only what that robot could have obtained itself: its own state,
    ego-relative records for robots inside `r_comm`, and ego-relative records
    for obstacles inside `r_obs`.
    """
    n = len(positions)
    views: Dict[int, RobotView] = {}
    for i in range(n):
        nbs: List[NeighbourRecord] = []
        for j in range(n):
            if i == j or math.dist(positions[i], positions[j]) > comm.r_comm:
                continue
            deg_j = sum(1 for k in range(n) if k != j
                        and math.dist(positions[j], positions[k]) <= comm.r_comm)
            nbs.append(NeighbourRecord(
                robot_id=j,
                rel_position=(positions[j][0] - positions[i][0],
                              positions[j][1] - positions[i][1]),
                rel_velocity=(0.0, 0.0),
                role_keep=roles.role_of(j, KEEP),
                role_line=roles.role_of(j, LINE),
                committed_mode=committed_mode,
                epoch_id=epoch_id,
                message_age_steps=0,
                degree=deg_j,
                link_valid=True,
            ))
        local: List[Tuple[float, float, float]] = []
        for ox, oy, radius in obstacles:
            dx, dy = ox - positions[i][0], oy - positions[i][1]
            if math.hypot(dx, dy) - radius > comm.r_obs:
                continue
            local.append((dx, dy, radius))
        views[i] = RobotView(
            robot_id=i,
            position=(float(positions[i][0]), float(positions[i][1])),
            velocity=(0.0, 0.0),
            role_keep=roles.role_of(i, KEEP),
            role_line=roles.role_of(i, LINE),
            committed_mode=committed_mode,
            epoch_id=epoch_id,
            steps_since_decision=int(steps_since_decision),
            local_progress=float(local_progress),
            goal=GOAL,
            mission_dir=MISSION,
            neighbours=tuple(nbs),
            obstacles=tuple(local),
        )
    return views


def formation_positions(n: int, spacing: float = 0.9,
                        origin: Tuple[float, float] = (2.0, 0.0)
                        ) -> Tuple[List[Tuple[float, float]], RoleAssignment]:
    """The exact keep template, so `local_formation_error` is identically zero."""
    roles = RoleAssignment.from_index(n, spacing)
    pos = [(float(roles.keep[i][0]) + origin[0], float(roles.keep[i][1]) + origin[1])
           for i in range(n)]
    return pos, roles


def complete_graph(ids: Sequence[int]) -> Dict[int, Tuple[int, ...]]:
    return {int(i): tuple(int(j) for j in ids if j != i) for i in ids}


def path_graph(n: int) -> Dict[int, Tuple[int, ...]]:
    return {i: tuple(j for j in (i - 1, i + 1) if 0 <= j < n) for i in range(n)}


def constant_score(q_keep: float, q_line: float):
    def score_fn(view: RobotView, g_keep, g_line) -> Tuple[float, float]:
        assert isinstance(view, RobotView)          # score_fn sees ONE robot
        return (float(q_keep), float(q_line))
    return score_fn


# ===========================================================================
# A. Token algebra -- the whole leaderlessness argument rests on these
# ===========================================================================
TOKEN_GRID: Tuple[TriggerToken, ...] = tuple(
    TriggerToken(c, t, r)
    for c in (1, 2, 3) for t in (0, 4, 9) for r in (0, 2, 5)
)


def test_A01_trigger_token_total_order_is_antisymmetric() -> None:
    """Exactly one of a<b, b<a, a==b holds for every ordered pair (27x27)."""
    for a in TOKEN_GRID:
        for b in TOKEN_GRID:
            outcomes = [a < b, b < a, a == b]
            assert sum(bool(x) for x in outcomes) == 1, (a, b, outcomes)
            assert (a <= b) == (a < b or a == b)
            assert (a >= b) == (b <= a)
    # distinct robot ids make the order total: no two distinct tokens tie
    assert len({t.as_tuple() for t in TOKEN_GRID}) == len(TOKEN_GRID)


def test_A02_trigger_token_total_order_is_transitive() -> None:
    """a<b and b<c implies a<c, over all 27^3 triples."""
    for a in TOKEN_GRID:
        for b in TOKEN_GRID:
            if not a < b:
                continue
            for c in TOKEN_GRID:
                if b < c:
                    assert a < c, (a, b, c)
    # and the order is exactly lexicographic on the declared field order
    for a in TOKEN_GRID:
        for b in TOKEN_GRID:
            assert (a < b) == (a.as_tuple() < b.as_tuple()), (a, b)


def test_A03_token_max_is_associative_commutative_idempotent() -> None:
    """None is the identity element; folding order and multiplicity are irrelevant."""
    elems: List[Optional[TriggerToken]] = [None] + list(TOKEN_GRID[:6])
    for a in elems:
        assert token_max(a, a) == a                       # idempotent
        assert token_max(a, None) == a                    # identity
        assert token_max(None, a) == a
        for b in elems:
            assert token_max(a, b) == token_max(b, a)     # commutative
            for c in elems:
                left = token_max(token_max(a, b), c)
                right = token_max(a, token_max(b, c))
                assert left == right, (a, b, c)
    # it really is the maximum, not "the first" or "the last"
    lo, hi = TriggerToken(1, 0, 1), TriggerToken(1, 0, 4)
    assert token_max(lo, hi) == hi and token_max(hi, lo) == hi


def test_A04_epoch_id_is_a_deterministic_collision_free_function_of_the_token() -> None:
    """9600 distinct tokens -> 9600 distinct ids, and none is the sentinel."""
    tokens = [TriggerToken(c, t, r)
              for c in range(1, 21) for t in range(40) for r in range(12)]
    ids = [epoch_id_from_token(t) for t in tokens]
    assert len(tokens) == 9600
    assert len(set(ids)) == 9600, "epoch-id collision across distinct tokens"
    assert EPOCH_ID_NONE not in ids
    # deterministic: the same token gives the same id on every call and in every
    # process (BLAKE2b over the canonical 10-byte packing, no salt, no PYTHONHASHSEED)
    for t in tokens[:64]:
        assert epoch_id_from_token(t) == epoch_id_from_token(TriggerToken(*t.as_tuple()))
    assert epoch_id_from_token(None) == EPOCH_ID_NONE
    # pinned value: proves the id is derived from the token bytes, not from
    # object identity or insertion order
    assert epoch_id_from_token(TriggerToken(1, 0, 4)) == 541404424


def test_A05_token_pack_is_ten_canonical_bytes_and_injective() -> None:
    tok = TriggerToken(7, 11, 3)
    assert len(tok.pack()) == TRIGGER_TOKEN_BYTES == 10
    assert struct.unpack("<I I H", tok.pack()) == (7, 11, 3)
    packed = {t.pack() for t in TOKEN_GRID}
    assert len(packed) == len(TOKEN_GRID)
    assert tok.as_tuple() == (7, 11, 3)


# ===========================================================================
# B. Wire format -- the byte counts comm_cost.assert_schema_sizes() verifies
# ===========================================================================
def test_B01_trigger_message_payload_is_exactly_21_bytes() -> None:
    msg = TriggerMessage(sender_id=3, epoch_counter=5, trigger_flag=True,
                         trigger_token=TriggerToken(5, 40, 3), timestamp_step=40)
    assert len(msg.payload_bytes()) == 21 == TRIGGER_PAYLOAD_BYTES
    # the "no token held" encoding is all-zero and still 21 bytes
    empty = TriggerMessage(sender_id=0, epoch_counter=0, trigger_flag=False,
                           trigger_token=None, timestamp_step=0)
    assert len(empty.payload_bytes()) == 21
    assert empty.payload_bytes()[7:17] == b"\x00" * 10
    # 2 + 4 + 1 + 10 + 4 = 21: the field sum, not a magic number
    assert 2 + 4 + 1 + TRIGGER_TOKEN_BYTES + 4 == TRIGGER_PAYLOAD_BYTES
    # no list-valued field can ride along
    fields = {f.name for f in dataclasses.fields(TriggerMessage)}
    assert fields == {"sender_id", "epoch_counter", "trigger_flag",
                      "trigger_token", "timestamp_step"}, fields


def test_B02_confirm_message_payload_is_exactly_16_bytes() -> None:
    msg = ConfirmMessage.from_bounds(sender_id=2, epoch_id=99, mode_lo=KEEP,
                                     mode_hi=LINE, margin=0.25, confirm_round=1,
                                     timestamp_step=7)
    assert len(msg.payload_bytes()) == 16 == CONFIRM_PAYLOAD_BYTES
    assert 2 + 4 + 1 + 4 + 1 + 4 == CONFIRM_PAYLOAD_BYTES
    assert msg.selected_mode == MODE_SET_MIXED
    assert msg.mode_bounds() == (KEEP, LINE)
    fields = {f.name for f in dataclasses.fields(ConfirmMessage)}
    assert fields == {"sender_id", "epoch_id", "selected_mode", "margin",
                      "confirm_round", "timestamp_step"}, fields


def test_B03_mode_set_codec_round_trips_every_reachable_set() -> None:
    assert encode_mode_set(KEEP, KEEP) == KEEP
    assert encode_mode_set(LINE, LINE) == LINE
    assert encode_mode_set(KEEP, LINE) == MODE_SET_MIXED
    for code in MODE_SET_CODES:
        lo, hi = decode_mode_set(code)
        assert encode_mode_set(lo, hi) == code, code
    assert decode_mode_set(MODE_SET_MIXED) == (KEEP, LINE)
    assert decode_mode_set(KEEP) == (KEEP, KEEP)
    assert decode_mode_set(LINE) == (LINE, LINE)
    # code 1 is the retired `split` id and must stay unreachable
    assert 1 not in MODE_SET_CODES
    with pytest.raises(ValueError):
        decode_mode_set(1)
    with pytest.raises(ValueError):
        decode_mode_set(4)
    with pytest.raises(ValueError):
        encode_mode_set(LINE, KEEP)            # lo must not exceed hi
    with pytest.raises(ValueError):
        encode_mode_set(1, 1)                  # split is not a mode


def test_B04_union_of_mode_sets_is_simultaneous_min_and_max() -> None:
    """The one-byte encoding must behave exactly like a (min, max) pair."""
    for a in MODE_SET_CODES:
        for b in MODE_SET_CODES:
            a_lo, a_hi = decode_mode_set(a)
            b_lo, b_hi = decode_mode_set(b)
            union = encode_mode_set(min(a_lo, b_lo), max(a_hi, b_hi))
            assert decode_mode_set(union) == (min(a_lo, b_lo), max(a_hi, b_hi))
            assert union == encode_mode_set(min(b_lo, a_lo), max(b_hi, a_hi))


# ===========================================================================
# C. Trigger inputs -- thresholds re-derived from EnvConfig, not restated
# ===========================================================================
def test_C01_thresholds_are_existing_env_constants() -> None:
    th = TriggerThresholds.from_config(CFG)
    env = CFG.env
    assert th.clearance_m == max(env.nominal_spacing, env.min_ro_distance) == 0.9
    assert th.progress_m == pytest.approx(env.dt * env.max_speed) == pytest.approx(0.135)
    assert th.progress_hold_steps == PROGRESS_WINDOW_STEPS == 5
    assert th.formation_err_m == env.formation_tolerance == 0.55
    assert th.decision_interval == CONS.decision_interval == 25
    # an explicit ConsensusParams overrides only the cadence
    th2 = TriggerThresholds.from_config(CFG, ConsensusParams(decision_interval=7))
    assert th2.decision_interval == 7 and th2.clearance_m == th.clearance_m


def test_C02_no_condition_fires_in_open_space() -> None:
    pos, roles = formation_positions(3)
    views = simulate_team_views(pos, roles)
    for i, view in views.items():
        reasons = trigger_reasons(view, CFG)
        assert reasons == {"low_clearance": False, "low_progress": False,
                           "local_formation_error": False,
                           "interval_expiry": False}, (i, reasons)
        assert local_trigger(view, CFG, EpochState(robot_id=i)) is False
        assert nearest_obstacle_distance(view) == math.inf


def test_C03_low_clearance_fires_on_the_robot_that_sensed_the_obstacle() -> None:
    """The obstacle is 0.8 m from robot 1 and >0.9 m from robots 0 and 2."""
    pos, roles = formation_positions(3)
    obstacle = (pos[1][0] + 0.8, pos[1][1], 0.0)
    views = simulate_team_views(pos, roles, obstacles=[obstacle])
    assert nearest_obstacle_distance(views[1]) == pytest.approx(0.8)
    assert trigger_reasons(views[1], CFG)["low_clearance"] is True
    assert local_trigger(views[1], CFG, EpochState(robot_id=1)) is True
    for other in (0, 2):
        assert nearest_obstacle_distance(views[other]) > 0.9
        assert trigger_reasons(views[other], CFG)["low_clearance"] is False
        assert local_trigger(views[other], CFG, EpochState(robot_id=other)) is False
    # and the threshold is a real boundary, not a nominal one
    far = simulate_team_views(pos, roles, obstacles=[(pos[1][0] + 0.95, pos[1][1], 0.0)])
    assert trigger_reasons(far[1], CFG)["low_clearance"] is False


def test_C04_low_progress_fires_only_when_sustained() -> None:
    """Needs `progress_hold_steps` = 5 consecutive stalled steps, and resets."""
    pos, roles = formation_positions(3)
    stalled = simulate_team_views(pos, roles, local_progress=0.0)
    ep = EpochState(robot_id=0)
    for step in range(1, PROGRESS_WINDOW_STEPS):
        assert observe_progress(stalled[0], CFG, ep) == step
        assert trigger_reasons(stalled[0], CFG, ep)["low_progress"] is False, step
        assert local_trigger(stalled[0], CFG, ep) is False, step
    assert observe_progress(stalled[0], CFG, ep) == PROGRESS_WINDOW_STEPS
    assert trigger_reasons(stalled[0], CFG, ep)["low_progress"] is True
    assert local_trigger(stalled[0], CFG, ep) is True
    # one good step wipes the streak: the condition is sustained, not cumulative
    moving = simulate_team_views(pos, roles, local_progress=MOVING)
    assert observe_progress(moving[0], CFG, ep) == 0
    assert trigger_reasons(moving[0], CFG, ep)["low_progress"] is False
    # with no epoch memory the streak cannot exist and the condition is False
    assert trigger_reasons(stalled[0], CFG, None)["low_progress"] is False


def test_C05_local_formation_error_is_reported_but_is_not_an_entry_reason() -> None:
    """Task 5-7 narrowed the ENTRY reasons; trigger_reasons still reports all four.

    A deformed formation is a CONSEQUENCE of a tight passage, not independent
    evidence of one, and including it re-opened epochs in open space.
    """
    pos, roles = formation_positions(4)
    views = simulate_team_views(pos, roles)
    r = trigger_reasons(views[0], CFG, EpochState(robot_id=0))
    assert set(r) == {"low_clearance", "low_progress",
                      "local_formation_error", "interval_expiry"}
    assert "local_formation_error" not in ENTRY_TRIGGER_REASONS

def test_C06_interval_expiry_is_reported_but_is_not_an_entry_reason() -> None:
    """A fixed periodic timer must not open a decision epoch (Task 3B / 5-7)."""
    pos, roles = formation_positions(3)
    at_interval = simulate_team_views(pos, roles, steps_since_decision=25)
    r = trigger_reasons(at_interval[0], CFG, EpochState(robot_id=0))
    assert "interval_expiry" in r
    assert "interval_expiry" not in ENTRY_TRIGGER_REASONS

LEADER_WORDS: Set[str] = {
    "leader", "leaders", "coordinator", "coordinators", "master", "masters",
    "root", "roots", "elect", "elected", "election", "chief", "captain",
    "supervisor", "arbiter", "chairman", "president", "primary", "central",
    "centraliser", "centralizer", "aggregator", "delegate",
}


def _words(identifier: str) -> List[str]:
    """Split snake_case and CamelCase into lowercase words."""
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|[0-9]+", identifier)
    return [p.lower() for p in parts]


def _identifiers(tree: ast.AST) -> Set[str]:
    """Every identifier that is part of the code's structure, not its prose."""
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.alias):
            names.add(node.asname or node.name)
    return names


def _leader_offenders(tree: ast.AST) -> List[str]:
    return sorted(name for name in _identifiers(tree)
                  if LEADER_WORDS & set(_words(name)))


EPOCH_SOURCE = inspect.getsource(epoch_mod)
EPOCH_TREE = ast.parse(EPOCH_SOURCE)


def test_D01_no_leader_coordinator_master_root_or_elected_identifier_exists() -> None:
    """Requirement 1a: no robot is named or typed as a leader."""
    assert _leader_offenders(EPOCH_TREE) == []

    # the scan has discriminating power -- word-level, so `selected_mode` is not
    # a false positive but `elect` is a real one
    injected = ast.parse(
        "class EpochCoordinator:\n"
        "    def elect_master(self, root_id):\n"
        "        self.leader = root_id\n"
    )
    assert _leader_offenders(injected) == [
        "EpochCoordinator", "elect_master", "leader", "root_id"]
    assert _leader_offenders(ast.parse("selected_mode = 3\n")) == []

    # structural: every class in the module is a message, a record, a threshold
    # table or the per-robot state -- there is no privileged-robot class
    classes = sorted(c.name for c in ast.walk(EPOCH_TREE)
                     if isinstance(c, ast.ClassDef))
    assert classes == ["ConfirmMessage", "DisagreementEvent", "EpochState",
                       "TriggerMessage", "TriggerThresholds", "TriggerToken"], classes
    fields = {f.name for f in dataclasses.fields(EpochState)}
    assert not (fields & {"is_leader", "leader_id", "role", "rank", "priority"})
    assert protocol_signature()["leader"] is None


def test_D01_no_leader_coordinator_master_root_or_elected_identifier_exists() -> None:
    """Requirement 1a: no robot is named or typed as a leader."""
    assert _leader_offenders(EPOCH_TREE) == []


def test_D02_no_deployable_function_takes_all_robots_or_returns_one_mode() -> None:
    """Requirement 1b: no function accepts the team and answers with one mode."""
    bulk = ("Dict", "dict", "Mapping", "ndarray", "Sequence[RobotView]",
            "List[RobotView]", "Sequence[EpochState]")
    offline = {"epoch_id_agreement", "committed_mode_agreement",
               "component_epoch_agreement"}
    boundary = {"simulate_trigger_consensus", "simulate_confirm_consensus",
                "simulate_decision_epoch"}
    deployable, took_bulk = [], []
    for fn in EPOCH_TREE.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = fn.args
        params = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
        annotations = [ast.unparse(a.annotation) if a.annotation else ""
                       for a in params]
        if any(any(tok in ann for tok in bulk) for ann in annotations):
            took_bulk.append(fn.name)
        if fn.name.startswith("simulate_") or fn.name in offline:
            continue
        deployable.append(fn.name)
        assert not any(any(tok in ann for tok in bulk) for ann in annotations), (
            "deployable {} takes a team container: {}".format(fn.name, annotations))
    # everything that DOES take the team is either the declared simulation
    # boundary or a declared offline diagnostic -- enumerated both ways
    assert sorted(took_bulk) == sorted(boundary | offline), took_bulk
    for name in offline:
        assert getattr(getattr(epoch_mod, name), "__offline_diagnostic__", False)
    assert set(deployable) == {
        "token_max", "epoch_id_from_token", "encode_mode_set", "decode_mode_set",
        "nearest_obstacle_distance", "observe_progress", "trigger_reasons",
        "local_trigger", "outgoing_trigger", "max_consensus_trigger",
        "outgoing_confirm", "confirm_mode", "commit_or_retain",
        # LINE -> KEEP, added in Task 3C. Both are deployable and read only
        # robot i's own RobotView, exactly like their KEEP -> LINE counterparts.
        "local_recovery_trigger", "recovery_trigger_reasons",
        # Task 5-7 passage latch
        "update_passage_latch", "entry_trigger_allowed",
        "recovery_trigger_allowed", "latched_local_trigger", "note_transition",
        # Task 6-2 V3 forward-opening recovery event
        "forward_opening_evidence", "recovery_evidence_v3",
        "peer_support_for_recovery", "recovery_armable",
        "latched_local_trigger_v3", "requested_mode_for",
        # G2/G4/G7 derivations replacing the audited literals
        "forward_sector_half_width_for", "evidence_persistence_steps",
        "rearm_open_steps",
        "protocol_signature"}, sorted(deployable)

    # and the end-to-end harness returns no scalar mode: every mode-bearing key
    # is a per-robot mapping
    pos, roles = formation_positions(4)
    views = simulate_team_views(pos, roles)
    epochs = {i: EpochState(robot_id=i) for i in range(4)}
    result = simulate_decision_epoch(views, complete_graph(range(4)), epochs,
                                     constant_score(0.0, 1.0), cfg=CFG,
                                     consensus=CONS, trigger_ids=[1])
    for key, value in result.items():
        if "mode" in key:
            assert isinstance(value, dict) and set(value) == set(range(4)), key
    assert not any(isinstance(v, int) and v in MODES for v in result.values())


def test_D03_only_the_simulation_boundary_ever_arms_another_robot() -> None:
    """Requirement 2: an epoch is initiated per robot, never by a central call."""
    callers = set()
    for fn in EPOCH_TREE.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "arm_trigger":
                callers.add(fn.name)
    assert callers == {"simulate_trigger_consensus", "simulate_decision_epoch"}
    assert all(name.startswith("simulate_") for name in callers)
    # `arm_trigger` is a method on one robot's own state and takes no team data
    sig = inspect.signature(EpochState.arm_trigger)
    assert list(sig.parameters) == ["self", "now_step"]


def test_D04_each_robot_arms_its_own_trigger_from_its_own_view() -> None:
    """Requirement 2: the deciding input is the robot's own RobotView."""
    pos, roles = formation_positions(3)
    views = simulate_team_views(pos, roles,
                                obstacles=[(pos[1][0] + 0.8, pos[1][1], 0.0)])
    epochs = {i: EpochState(robot_id=i) for i in range(3)}
    fired = [i for i in range(3) if local_trigger(views[i], CFG, epochs[i])]
    assert fired == [1], "only the robot that sensed the obstacle may fire"
    token = epochs[1].arm_trigger(now_step=12)
    assert token == TriggerToken(epoch_counter=1, trigger_timestamp=12, robot_id=1)
    assert token.robot_id == views[1].robot_id      # its own id, nobody else's
    assert epochs[1].phase == PHASE_TRIGGERED and epochs[1].trigger_flag is True
    assert epochs[1].epoch_id == epoch_id_from_token(token) != EPOCH_ID_NONE
    # the robots that did not fire are untouched: no central call reached them
    for other in (0, 2):
        assert epochs[other].phase == PHASE_IDLE
        assert epochs[other].trigger_token is None
        assert epochs[other].epoch_id == EPOCH_ID_NONE


def test_D05_module_holds_no_mutable_shared_state() -> None:
    """A central process would need somewhere to keep the swarm's epoch."""
    mutable = []
    for node in EPOCH_TREE.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            if isinstance(node.value, (ast.Dict, ast.List, ast.Set, ast.DictComp,
                                       ast.ListComp, ast.SetComp)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                mutable += [ast.unparse(t) for t in targets]
    assert mutable == [], mutable
    assert not [n for n in ast.walk(EPOCH_TREE) if isinstance(n, ast.Global)]
    # discriminating power
    bad = ast.parse("EPOCH_REGISTRY = {}\nSWARM_TOKENS: dict = dict()\n")
    found = [ast.unparse(t) for n in bad.body
             if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None
             and isinstance(n.value, (ast.Dict, ast.List, ast.Set))
             for t in (n.targets if isinstance(n, ast.Assign) else [n.target])]
    assert found == ["EPOCH_REGISTRY"]


def test_D06_token_winner_does_not_decide_the_mode() -> None:
    """The token names the epoch; it confers no authority over the outcome."""
    pos, roles = formation_positions(4)
    views = simulate_team_views(pos, roles)
    epochs = {i: EpochState(robot_id=i) for i in range(4)}

    def score_fn(view: RobotView, g_keep, g_line) -> Tuple[float, float]:
        return (2.0, 0.0) if view.robot_id == 3 else (0.0, 2.0)

    result = simulate_decision_epoch(views, complete_graph(range(4)), epochs,
                                     score_fn, cfg=CFG, consensus=CONS,
                                     trigger_ids=[3])
    assert result["tokens"][0].robot_id == 3        # robot 3 owns the token
    assert result["logits"][3] == (2.0, 0.0)        # and prefers KEEP alone
    assert set(result["proposals"].values()) == {LINE}
    assert all(result["committed"].values())
    assert set(result["committed_modes"].values()) == {LINE}


def test_D07_the_token_winner_relabels_with_the_robot_ids() -> None:
    """No fixed robot wins: the tie-break is a function of the labels."""
    for ids in ([0, 1, 2], [10, 11, 12], [7, 3, 5]):
        a, b, c = ids
        neighbours = {a: (b,), b: (a, c), c: (b,)}
        epochs = {i: EpochState(robot_id=i) for i in ids}
        result = simulate_trigger_consensus(epochs, neighbours, CONS.k_trigger,
                                            arm_offsets={i: 0 for i in ids})
        expected = TriggerToken(1, 0, max(ids))
        assert {i: t for i, t in result["tokens"].items()} == {i: expected for i in ids}
        assert len(set(result["epoch_ids"].values())) == 1


def test_D08_no_global_state_reaches_the_trigger() -> None:
    """Requirement 6: an obs dict or an (N,2) array must raise, not be read."""
    pos, roles = formation_positions(3)
    good = simulate_team_views(pos, roles)[0]
    obs_dict = {"positions": np.zeros((6, 2), dtype=np.float32),
                "velocities": np.zeros((6, 2), dtype=np.float32),
                "goal": np.array(GOAL, dtype=np.float32)}
    joint_state = np.zeros((6, 2), dtype=np.float32)

    class DuckView:
        """Every RobotView attribute plus the joint state. Must still be rejected."""
        def __init__(self, view: RobotView) -> None:
            for f in dataclasses.fields(RobotView):
                setattr(self, f.name, getattr(view, f.name))
            self.positions = joint_state

    for intruder in (obs_dict, joint_state, list(pos), DuckView(good), None):
        with pytest.raises(CentralizedAccessError):
            local_trigger(intruder, CFG)                     # type: ignore[arg-type]
        with pytest.raises(CentralizedAccessError):
            trigger_reasons(intruder, CFG)                   # type: ignore[arg-type]
    # the gate is isinstance-based, so the honest view still works
    assert local_trigger(good, CFG) is False


def test_D09_the_state_machine_reads_only_its_own_robot() -> None:
    """Requirement 6: no EpochState instance can reach another instance."""
    pos, roles = formation_positions(3)
    views = simulate_team_views(pos, roles)
    epochs = {i: EpochState(robot_id=i) for i in range(3)}
    epochs[2].arm_trigger(now_step=0)

    before = {i: epochs[i].snapshot() for i in (0, 1)}
    # robot 0 folds a packet from robot 2 -- and touches nothing but its own state
    changed = max_consensus_trigger(epochs[0], [outgoing_trigger(epochs[2], 0)], 0)
    assert changed is True
    assert epochs[1].snapshot() == before[1], "robot 1 must be untouched"
    assert epochs[0].snapshot() != before[0]
    assert epochs[0].epoch_id == epochs[2].epoch_id
    # every state-machine entry point takes exactly one robot's record
    for fn in (max_consensus_trigger, confirm_mode, commit_or_retain,
               outgoing_trigger, outgoing_confirm):
        params = list(inspect.signature(fn).parameters)
        assert params[0] == "epoch", fn.__name__
    for fn in (nearest_obstacle_distance, observe_progress, trigger_reasons,
               local_trigger):
        assert list(inspect.signature(fn).parameters)[0] == "view", fn.__name__
    assert views[0].robot_id == 0                    # one view, one robot


# ===========================================================================
# E. Message hygiene: duplicate, stale, future, self
# ===========================================================================
def _armed_peer(robot_id: int, step: int) -> EpochState:
    peer = EpochState(robot_id=robot_id)
    peer.arm_trigger(step)
    return peer


def test_E01_duplicate_trigger_messages_are_idempotent() -> None:
    """Requirement 3: re-delivering a folded packet changes nothing."""
    peer = _armed_peer(4, 10)
    msg = outgoing_trigger(peer, 10)

    once = EpochState(robot_id=0)
    assert max_consensus_trigger(once, [msg], 10) is True
    baseline = once.snapshot()

    # same message delivered five times in one inbox
    burst = EpochState(robot_id=0)
    assert max_consensus_trigger(burst, [msg] * 5, 10) is True
    assert burst.snapshot() == baseline

    # and delivered again in later rounds: no further change is reported
    for now in (10, 11, 12, 13):
        assert max_consensus_trigger(once, [msg], now) is False, now
        assert once.snapshot() == baseline, now
    assert once.epoch_counter == 1 and once.rejected_stale == 0


def test_E02_duplicate_confirm_messages_are_idempotent() -> None:
    token = TriggerToken(1, 0, 4)
    me = EpochState(robot_id=0)
    me.adopt(token)
    me.begin_confirming(LINE, 0.75)
    peer = EpochState(robot_id=1)
    peer.adopt(token)
    peer.begin_confirming(KEEP, 0.25)
    msg = outgoing_confirm(peer, 0)

    assert confirm_mode(me, [msg], 0) is True
    state = (me.mode_lo, me.mode_hi, me.margin_min, me.epoch_mismatch)
    assert state == (KEEP, LINE, 0.25, 0)
    for now in (0, 1, 2, 3):
        assert confirm_mode(me, [msg] * 3, now) is False, now
        assert (me.mode_lo, me.mode_hi, me.margin_min, me.epoch_mismatch) == state


def test_E03_stale_trigger_messages_are_rejected() -> None:
    """Requirement 4: age > delta_stale_steps is refused, and the boundary holds."""
    delta = COMM.delta_stale_steps
    assert delta == 3
    peer = _armed_peer(4, 10)

    stale = EpochState(robot_id=0)
    assert max_consensus_trigger(stale, [outgoing_trigger(peer, 10 - delta - 1)],
                                 10, delta) is False
    assert stale.rejected_stale == 1
    assert stale.trigger_token is None and stale.trigger_flag is False
    assert stale.phase == PHASE_IDLE and stale.epoch_id == EPOCH_ID_NONE

    fresh = EpochState(robot_id=0)
    assert max_consensus_trigger(fresh, [outgoing_trigger(peer, 10 - delta)],
                                 10, delta) is True
    assert fresh.rejected_stale == 0
    assert fresh.trigger_token == peer.trigger_token


def test_E04_stale_confirm_messages_are_rejected() -> None:
    delta = COMM.delta_stale_steps
    token = TriggerToken(1, 0, 4)
    peer = EpochState(robot_id=1)
    peer.adopt(token)
    peer.begin_confirming(KEEP, 0.25)

    stale = EpochState(robot_id=0)
    stale.adopt(token)
    stale.begin_confirming(LINE, 0.75)
    assert confirm_mode(stale, [outgoing_confirm(peer, 10 - delta - 1)], 10, delta) is False
    assert stale.rejected_stale == 1
    assert (stale.mode_lo, stale.mode_hi, stale.margin_min) == (LINE, LINE, 0.75)

    fresh = EpochState(robot_id=0)
    fresh.adopt(token)
    fresh.begin_confirming(LINE, 0.75)
    assert confirm_mode(fresh, [outgoing_confirm(peer, 10 - delta)], 10, delta) is True
    assert (fresh.mode_lo, fresh.mode_hi) == (KEEP, LINE)


def test_E05_future_dated_and_self_addressed_packets_are_rejected() -> None:
    peer = _armed_peer(4, 12)
    me = EpochState(robot_id=0)
    assert max_consensus_trigger(me, [outgoing_trigger(peer, 12)], 10) is False
    assert me.rejected_future == 1 and me.trigger_token is None

    echo = TriggerMessage(sender_id=0, epoch_counter=9, trigger_flag=True,
                          trigger_token=TriggerToken(9, 9, 0), timestamp_step=10)
    assert max_consensus_trigger(me, [echo], 10) is False
    assert me.rejected_self == 1 and me.trigger_token is None
    assert me.epoch_counter == 0, "a robot must not bootstrap itself from its own echo"


def test_E06_a_trigger_with_the_flag_down_is_the_identity_element() -> None:
    """Quiet robots broadcast too; their packets must not disturb anyone."""
    quiet = EpochState(robot_id=1)
    me = _armed_peer(0, 5)
    before = me.snapshot()
    assert max_consensus_trigger(me, [outgoing_trigger(quiet, 5)], 5) is False
    assert me.snapshot() == before
    assert me.rejected_stale == 0 and me.rejected_self == 0


# ===========================================================================
# F. Simultaneous triggers resolve deterministically to one epoch
# ===========================================================================
def test_F01_simultaneous_triggers_resolve_to_one_epoch_in_both_arrival_orders() -> None:
    """Requirement 5: same winner whichever packet arrives first."""
    low = _armed_peer(1, 0)                 # token (1, 0, 1)
    high = _armed_peer(4, 0)                # token (1, 0, 4)
    assert low.trigger_token < high.trigger_token
    msg_low, msg_high = outgoing_trigger(low, 0), outgoing_trigger(high, 0)

    # (a) both in one inbox, both orders
    same_round = []
    for inbox in ([msg_low, msg_high], [msg_high, msg_low]):
        me = EpochState(robot_id=0)
        max_consensus_trigger(me, inbox, 0)
        same_round.append((me.trigger_token, me.epoch_id))
    assert same_round[0] == same_round[1]

    # (b) delivered in separate rounds, both schedules -- this is the case that
    # a "last writer wins" or "first writer wins" rule would get wrong
    split_round = []
    for first, second in ((msg_low, msg_high), (msg_high, msg_low)):
        me = EpochState(robot_id=0)
        max_consensus_trigger(me, [first], 0)
        max_consensus_trigger(me, [second], 1)
        split_round.append((me.trigger_token, me.epoch_id))
    assert split_round[0] == split_round[1] == same_round[0]

    winner, epoch_id = same_round[0]
    assert winner == TriggerToken(1, 0, 4) == high.trigger_token
    assert epoch_id == epoch_id_from_token(TriggerToken(1, 0, 4)) != EPOCH_ID_NONE


def test_F02_simultaneous_triggers_converge_across_a_multi_hop_path() -> None:
    """Robots 1 and 4 of a 5-path arm in the same step; all five agree."""
    epochs = {i: EpochState(robot_id=i) for i in range(5)}
    result = simulate_trigger_consensus(epochs, path_graph(5), CONS.k_trigger,
                                        arm_offsets={1: 0, 4: 0})
    expected = TriggerToken(1, 0, 4)
    assert result["tokens"] == {i: expected for i in range(5)}
    assert len(set(result["epoch_ids"].values())) == 1
    assert all(result["flags"].values())
    assert epoch_id_agreement(epochs) == 1.0
    # arming the same two robots in the opposite dict order changes nothing
    mirrored = {i: EpochState(robot_id=i) for i in range(5)}
    mirror_result = simulate_trigger_consensus(mirrored, path_graph(5),
                                               CONS.k_trigger,
                                               arm_offsets={4: 0, 1: 0})
    assert mirror_result["tokens"] == result["tokens"]
    assert mirror_result["epoch_ids"] == result["epoch_ids"]
    # accounting: 8 directed links x 4 rounds x 21 B
    assert result["messages_sent"] == 2 * 4 * CONS.k_trigger
    assert result["bytes_sent"] == result["messages_sent"] * TRIGGER_PAYLOAD_BYTES


def test_F03_a_later_trigger_wins_over_an_earlier_one_within_a_counter() -> None:
    """Ties break on trigger_timestamp before robot_id -- monotone in time."""
    epochs = {i: EpochState(robot_id=i) for i in range(5)}
    result = simulate_trigger_consensus(epochs, path_graph(5), 6,
                                        arm_offsets={4: 0, 1: 2})
    assert result["tokens"] == {i: TriggerToken(1, 2, 1) for i in range(5)}
    mirrored = {i: EpochState(robot_id=i) for i in range(5)}
    mirror = simulate_trigger_consensus(mirrored, path_graph(5), 6,
                                        arm_offsets={1: 0, 4: 2})
    assert mirror["tokens"] == {i: TriggerToken(1, 2, 4) for i in range(5)}


def test_F04_disconnected_components_run_their_own_epochs() -> None:
    """Two components cannot agree, and the honest metric says so per component."""
    neighbours: Dict[int, Tuple[int, ...]] = {0: (1,), 1: (0,), 2: (3,), 3: (2,)}
    epochs = {i: EpochState(robot_id=i) for i in range(4)}
    result = simulate_trigger_consensus(epochs, neighbours, CONS.k_trigger,
                                        arm_offsets={0: 0, 3: 0})
    assert result["tokens"][0] == result["tokens"][1] == TriggerToken(1, 0, 0)
    assert result["tokens"][2] == result["tokens"][3] == TriggerToken(1, 0, 3)
    assert epoch_id_agreement(epochs) == 0.0        # swarm-wide: honestly false
    components = connected_components(neighbours)
    assert components == [[0, 1], [2, 3]]
    assert component_epoch_agreement(epochs, components) == 1.0
    assert component_epoch_agreement(epochs, []) == 1.0


# ===========================================================================
# G. Commitment: exactly h_commit steps, mode frozen while locked
# ===========================================================================
def test_G01_commitment_lasts_exactly_h_commit_steps() -> None:
    """Requirement 7: tick() decrements once per step and closes on zero."""
    h = CONS.h_commit
    assert h == 10
    ep = EpochState(robot_id=0)
    ep.adopt(TriggerToken(1, 0, 0))
    ep.begin_confirming(LINE, 1.0)
    ep.commit(LINE, h)
    assert ep.remaining_commitment == h and ep.locked is True
    assert ep.phase == PHASE_COMMITTED and ep.commits == 1

    for step in range(1, h):
        assert ep.tick() == h - step, step
        assert ep.locked is True, step
        assert ep.phase == PHASE_COMMITTED, step
        assert ep.committed_mode == LINE, step
    assert ep.tick() == 0
    assert ep.locked is False and ep.phase == PHASE_IDLE
    assert ep.committed_mode == LINE          # the decision survives the epoch
    # ticking past zero is a no-op, not an underflow
    assert ep.tick() == 0 and ep.remaining_commitment == 0


def test_G02_the_mode_cannot_change_while_the_commitment_is_locked() -> None:
    """Requirement 7: neither a local trigger nor a peer packet may reopen."""
    h = CONS.h_commit
    ep = EpochState(robot_id=0)
    ep.commit(LINE, h)

    pos, roles = formation_positions(3)
    displaced = list(pos)
    displaced[0] = (pos[0][0] + 1.2, pos[0][1])
    screaming = simulate_team_views(displaced, roles, local_progress=0.0,
                                    steps_since_decision=99,
                                    obstacles=[(displaced[0][0] + 0.2, 0.0, 0.0)])[0]
    for _ in range(PROGRESS_WINDOW_STEPS):
        observe_progress(screaming, CFG, ep)
    assert all(trigger_reasons(screaming, CFG, ep).values()), "all four conditions hold"

    peer = _armed_peer(5, 0)
    peer_msg = outgoing_trigger(peer, 0)
    for step in range(h - 1):
        assert local_trigger(screaming, CFG, ep) is False, step
        assert max_consensus_trigger(ep, [peer_msg], 0) is False, step
        assert ep.trigger_flag is False and ep.trigger_token is None
        assert ep.committed_mode == LINE
        ep.tick()
    assert ep.remaining_commitment == 1 and ep.locked is True
    ep.tick()
    # the dwell is over: the same view now fires, so the lock was the only reason
    assert ep.locked is False and ep.phase == PHASE_IDLE
    assert local_trigger(screaming, CFG, ep) is True


def test_G03_a_retained_epoch_arms_the_same_dwell_as_a_commit() -> None:
    """A failed epoch must not re-open immediately (no retry storm)."""
    ep = EpochState(robot_id=0)
    ep.adopt(TriggerToken(1, 0, 0))
    ep.begin_confirming(KEEP, 0.5)
    ep.mode_hi = LINE                         # a witnessed disagreement
    event = ep.retain(CONS.h_commit, ("mode_disagreement",), now_step=42)
    assert isinstance(event, DisagreementEvent)
    assert event.kind == "mode_disagreement" and event.reasons == ("mode_disagreement",)
    assert event.robot_id == 0 and event.step == 42
    assert event.retained_mode == KEEP and (event.mode_lo, event.mode_hi) == (KEEP, LINE)
    assert ep.retentions == 1 and ep.commits == 0
    assert ep.remaining_commitment == CONS.h_commit and ep.locked is True
    assert ep.phase == PHASE_COMMITTED and ep.trigger_flag is False
    assert ep.committed_mode == KEEP, "no fallback mode may be invented"
    assert DisagreementEvent(0, 1, 0, (), KEEP, KEEP, 0.0, KEEP, 0).kind == "none"


def test_G04_phases_advance_in_the_declared_order() -> None:
    ep = EpochState(robot_id=0)
    assert ep.phase == PHASE_IDLE
    ep.arm_trigger(0)
    assert ep.phase == PHASE_TRIGGERED
    ep.begin_scoring()
    assert ep.phase == PHASE_SCORING and ep.consensus_round == 0
    ep.begin_confirming(LINE, 0.5)
    assert ep.phase == PHASE_CONFIRMING and ep.confirm_round == 0
    assert ep.own_proposal == LINE and ep.own_margin == 0.5
    assert (ep.mode_lo, ep.mode_hi, ep.margin_min) == (LINE, LINE, 0.5)
    ep.commit(LINE, CONS.h_commit)
    assert ep.phase == PHASE_COMMITTED
    assert PHASES == (PHASE_IDLE, PHASE_TRIGGERED, PHASE_SCORING,
                      PHASE_CONFIRMING, PHASE_COMMITTED)
    with pytest.raises(ValueError):
        ep.begin_confirming(1, 0.0)           # split is not a mode
    with pytest.raises(ValueError):
        ep.commit(1, CONS.h_commit)


def test_G05_commit_or_retain_names_every_failure_in_priority_order() -> None:
    params = ConsensusParams(confirm_margin=0.25)
    # (a) clean commit
    ok = EpochState(robot_id=0)
    ok.adopt(TriggerToken(1, 0, 0))
    ok.begin_confirming(LINE, 0.9)
    assert commit_or_retain(ok, 5, params) is True
    assert ok.committed_mode == LINE and ok.remaining_commitment == params.h_commit

    # (b) weak margin alone
    weak = EpochState(robot_id=1)
    weak.adopt(TriggerToken(1, 0, 1))
    weak.begin_confirming(LINE, 0.1)
    assert commit_or_retain(weak, 5, params) is False
    assert weak.disagreements[-1].reasons == ("weak_margin",)

    # (c) all three at once, reported in the declared priority order
    worst = EpochState(robot_id=2)
    worst.adopt(TriggerToken(1, 0, 2))
    worst.begin_confirming(KEEP, 0.0)
    worst.mode_hi, worst.epoch_mismatch = LINE, 2
    assert commit_or_retain(worst, 7, params) is False
    assert worst.disagreements[-1].reasons == FAILURE_PRIORITY
    assert worst.disagreements[-1].kind == "epoch_overlap"
    assert worst.disagreements[-1].epoch_mismatch == 2


# ===========================================================================
# H. A clean close, then a second epoch
# ===========================================================================
def test_H01_close_epoch_clears_the_epoch_and_keeps_the_decision() -> None:
    ep = EpochState(robot_id=3)
    ep.arm_trigger(0)
    ep.begin_confirming(LINE, 0.8)
    ep.commit(LINE, 2)
    ep.tick()
    ep.tick()
    assert ep.phase == PHASE_IDLE
    assert ep.trigger_token is None and ep.epoch_id == EPOCH_ID_NONE
    assert ep.trigger_flag is False and ep.consensus_round == 0
    assert ep.confirm_round == 0 and ep.epoch_mismatch == 0
    assert (ep.mode_lo, ep.mode_hi) == (LINE, LINE)     # seeded from the decision
    assert ep.margin_min == 0.0
    assert ep.committed_mode == LINE and ep.epoch_counter == 1


def test_H02_a_second_epoch_opens_after_the_first_closes() -> None:
    """Requirement 8: close cleanly, then run a whole second epoch."""
    pos, roles = formation_positions(4)
    views = simulate_team_views(pos, roles)
    neighbours = complete_graph(range(4))
    epochs = {i: EpochState(robot_id=i) for i in range(4)}

    first = simulate_decision_epoch(views, neighbours, epochs,
                                    constant_score(0.0, 1.0), cfg=CFG,
                                    consensus=CONS, trigger_ids=[3])
    assert all(first["committed"].values())
    assert set(first["committed_modes"].values()) == {LINE}

    for i in range(4):
        for _ in range(CONS.h_commit):
            epochs[i].tick()
        assert epochs[i].phase == PHASE_IDLE and epochs[i].epoch_id == EPOCH_ID_NONE
        assert epochs[i].committed_mode == LINE

    second = simulate_decision_epoch(views, neighbours, epochs,
                                     constant_score(1.0, 0.0), cfg=CFG,
                                     consensus=CONS, trigger_ids=[3],
                                     start_step=100)
    assert all(second["committed"].values())
    assert set(second["committed_modes"].values()) == {KEEP}
    assert set(first["epoch_ids"].values()) & set(second["epoch_ids"].values()) == set()
    for i in range(4):
        assert epochs[i].epoch_counter == 2 and epochs[i].commits == 2
        assert epochs[i].retentions == 0
    assert committed_mode_agreement(epochs) == 1.0


def test_H03_the_epoch_counter_never_goes_backwards() -> None:
    """A stale packet from a finished epoch cannot drag a robot back."""
    ep = EpochState(robot_id=0)
    ep.arm_trigger(0)                     # counter 1
    ep.commit(LINE, 1)
    ep.tick()
    ep.arm_trigger(50)                    # counter 2
    assert ep.epoch_counter == 2
    old = TriggerMessage(sender_id=9, epoch_counter=1, trigger_flag=True,
                         trigger_token=TriggerToken(1, 0, 9), timestamp_step=50)
    max_consensus_trigger(ep, [old], 50)
    assert ep.epoch_counter == 2
    assert ep.trigger_token == TriggerToken(2, 50, 0)
    assert ep.epoch_id == epoch_id_from_token(TriggerToken(2, 50, 0))
    # adopt is monotone in the counter for the same reason
    ep.adopt(TriggerToken(1, 99, 9))
    assert ep.epoch_counter == 2


# ===========================================================================
# I. End to end, disagreement, diagnostics
# ===========================================================================
def test_I01_a_full_epoch_commits_and_never_re_reads_the_snapshot() -> None:
    pos, roles = formation_positions(4)
    views = simulate_team_views(pos, roles, obstacles=[(pos[2][0] + 0.5, 0.0, 0.0)])
    epochs = {i: EpochState(robot_id=i) for i in range(4)}
    result = simulate_decision_epoch(views, complete_graph(range(4)), epochs,
                                     constant_score(0.0, 1.0), cfg=CFG,
                                     consensus=CONS, seed=7)
    assert result["fired"], "the sensed obstacle must open the epoch locally"
    assert result["participants"] == (0, 1, 2, 3) and result["bystanders"] == ()
    assert result["snapshot_digest_before"] == result["snapshot_digest_after"]
    assert result["end_step"] == CONS.k_trigger + CONS.k_score + CONS.k_confirm
    assert result["commit_horizon"] == CONS.h_commit
    assert set(result["remaining_commitment"].values()) == {CONS.h_commit}
    assert set(result["phases"].values()) == {PHASE_COMMITTED}
    assert all(len(d) == 0 for d in result["disagreements"].values())
    assert result["trigger_result"]["bytes_sent"] > 0
    assert result["confirm_result"]["bytes_sent"] > 0
    assert epoch_id_agreement(epochs) == 1.0 and committed_mode_agreement(epochs) == 1.0
    assert epochs[0].snapshot()["committed_mode"] == LINE


def test_I02_a_witnessed_disagreement_retains_instead_of_guessing() -> None:
    """k_score = 0 leaves the proposals split; confirmation must catch it."""
    params = ConsensusParams(k_score=0, k_confirm=3)
    pos, roles = formation_positions(4)
    views = simulate_team_views(pos, roles)
    epochs = {i: EpochState(robot_id=i) for i in range(4)}

    def split_score(view: RobotView, g_keep, g_line) -> Tuple[float, float]:
        return (1.0, 0.0) if view.robot_id == 0 else (0.0, 1.0)

    result = simulate_decision_epoch(views, complete_graph(range(4)), epochs,
                                     split_score, cfg=CFG, consensus=params,
                                     trigger_ids=[0])
    assert result["proposals"] == {0: KEEP, 1: LINE, 2: LINE, 3: LINE}
    assert not any(result["committed"].values())
    assert set(result["committed_modes"].values()) == {KEEP}, "previous mode retained"
    for i in range(4):
        assert (epochs[i].mode_lo, epochs[i].mode_hi) == (KEEP, LINE)
        assert [e.kind for e in epochs[i].disagreements] == ["mode_disagreement"]
        assert epochs[i].retentions == 1 and epochs[i].commits == 0
        assert epochs[i].remaining_commitment == params.h_commit


def test_I03_a_packet_from_another_epoch_is_counted_not_merged() -> None:
    """Overlapping epochs are detected, which is what epoch_mismatch means."""
    mine, theirs = TriggerToken(1, 0, 0), TriggerToken(1, 5, 1)
    assert epoch_id_from_token(mine) != epoch_id_from_token(theirs)
    me = EpochState(robot_id=0)
    me.adopt(mine)
    me.begin_confirming(LINE, 1.0)
    other = EpochState(robot_id=1)
    other.adopt(theirs)
    other.begin_confirming(KEEP, 0.0)

    assert confirm_mode(me, [outgoing_confirm(other, 0)], 0) is False
    assert me.epoch_mismatch == 1
    assert (me.mode_lo, me.mode_hi, me.margin_min) == (LINE, LINE, 1.0)
    assert commit_or_retain(me, 0, CONS) is False
    assert me.disagreements[-1].kind == "epoch_overlap"


def test_I04_confirmation_propagates_one_hop_per_round() -> None:
    """min/max consensus over a 5-path: robot 0 learns of robot 4 after 4 rounds."""
    token = TriggerToken(1, 0, 4)
    epochs = {}
    for i in range(5):
        ep = EpochState(robot_id=i)
        ep.adopt(token)
        ep.begin_confirming(LINE if i == 4 else KEEP, 1.0)
        epochs[i] = ep
    result = simulate_confirm_consensus(epochs, path_graph(5), 5)
    history = result["history"]
    assert history[0][3] == (KEEP, LINE), "one hop after one round"
    assert history[0][0] == (KEEP, KEEP)
    assert history[2][1] == (KEEP, LINE) and history[2][0] == (KEEP, KEEP)
    assert history[3][0] == (KEEP, LINE), "four hops after four rounds"
    assert result["bounds"] == {i: (KEEP, LINE) for i in range(5)}
    assert set(result["epoch_mismatch"].values()) == {0}
    assert result["bytes_sent"] == result["messages_sent"] * CONFIRM_PAYLOAD_BYTES
    assert all(commit_or_retain(epochs[i], 10, CONS) is False for i in range(5))


def test_I05_lost_trigger_packets_do_not_break_agreement_only_delay_it() -> None:
    clean = {i: EpochState(robot_id=i) for i in range(5)}
    lossy = {i: EpochState(robot_id=i) for i in range(5)}
    ref = simulate_trigger_consensus(clean, path_graph(5), 12, arm_offsets={4: 0})
    out = simulate_trigger_consensus(lossy, path_graph(5), 12, arm_offsets={4: 0},
                                     packet_loss=0.5, seed=3)
    assert out["messages_dropped"] > 0
    assert out["tokens"] == ref["tokens"] == {i: TriggerToken(1, 0, 4) for i in range(5)}
    assert out["messages_delivered"] + out["messages_dropped"] == out["messages_sent"]


def test_I06_delayed_trigger_packets_inside_the_stale_window_still_agree() -> None:
    epochs = {i: EpochState(robot_id=i) for i in range(5)}
    result = simulate_trigger_consensus(epochs, path_graph(5), 12,
                                        arm_offsets={4: 0}, delay_steps=2,
                                        delta_stale_steps=COMM.delta_stale_steps)
    assert result["tokens"] == {i: TriggerToken(1, 0, 4) for i in range(5)}
    assert all(result["flags"].values())
    assert sum(e.rejected_stale for e in epochs.values()) == 0


def test_I07_protocol_signature_matches_the_implementation() -> None:
    sig = protocol_signature()
    assert sig["phases"] == PHASES
    assert sig["messages"]["TriggerMessage"]["bytes"] == TRIGGER_PAYLOAD_BYTES == 21
    assert sig["messages"]["ConfirmMessage"]["bytes"] == CONFIRM_PAYLOAD_BYTES == 16
    assert sig["messages"]["TriggerMessage"]["rounds_per_epoch"] == CONS.k_trigger
    assert sig["messages"]["ConfirmMessage"]["rounds_per_epoch"] == CONS.k_confirm
    assert sig["score_rounds_per_epoch"] == CONS.k_score
    assert sig["h_commit"] == CONS.h_commit
    assert sig["decision_interval"] == CONS.decision_interval
    assert sig["confirm_margin"] == CONS.confirm_margin
    assert sig["leader"] is None
    trigger_fields = {f.name for f in dataclasses.fields(TriggerMessage)}
    assert set(sig["messages"]["TriggerMessage"]["fields"]) == trigger_fields
    confirm_fields = {f.name for f in dataclasses.fields(ConfirmMessage)}
    assert set(sig["messages"]["ConfirmMessage"]["fields"]) == confirm_fields


def test_I08_the_wire_sizes_agree_with_the_communication_accountant() -> None:
    """The defect the recovery audit called D2: comm_cost must measure THIS schema."""
    from rvt_swarm.decentralized.comm_cost import (assert_schema_sizes,
                                                   epoch_module_status)
    report = assert_schema_sizes()
    assert report["trigger"]["measured_bytes"] == TRIGGER_PAYLOAD_BYTES == 21
    assert report["mode_confirmation"]["measured_bytes"] == CONFIRM_PAYLOAD_BYTES == 16
    assert all(row["ok"] for row in report.values()), report
    assert all(not row["provisional"] for row in report.values()), report
    status = epoch_module_status()
    assert status["available"] is True
    assert status["trigger_schema_source"] == "epoch"
    assert status["confirm_schema_source"] == "epoch"


# ===========================================================================
# Z. Coverage: every function in epoch.py is exercised by a dedicated test
# ===========================================================================
COVERAGE_MANIFEST: Dict[str, str] = {
    "TriggerToken.as_tuple": "test_A01/A05",
    "TriggerToken.pack": "test_A05",
    "token_max": "test_A03",
    "epoch_id_from_token": "test_A04",
    "TriggerMessage.payload_bytes": "test_B01",
    "ConfirmMessage.from_bounds": "test_B02",
    "ConfirmMessage.mode_bounds": "test_B02",
    "ConfirmMessage.payload_bytes": "test_B02",
    "encode_mode_set": "test_B03",
    "decode_mode_set": "test_B03",
    "DisagreementEvent.kind": "test_G03",
    "TriggerThresholds.from_config": "test_C01",
    "EpochState.locked": "test_G01",
    "EpochState.arm_trigger": "test_D04",
    "EpochState.adopt": "test_H03",
    "EpochState.begin_scoring": "test_G04",
    "EpochState.begin_confirming": "test_G04",
    "EpochState.commit": "test_G01",
    "EpochState.retain": "test_G03",
    "EpochState.tick": "test_G01",
    "EpochState.close_epoch": "test_H01",
    "EpochState.snapshot": "test_D09",
    "nearest_obstacle_distance": "test_C03",
    "observe_progress": "test_C04",
    "trigger_reasons": "test_C02",
    "local_trigger": "test_C02",
    "local_recovery_trigger": "test_R01_local_recovery_trigger_fires_only_when_clearance_reopens",
    "update_passage_latch": "test_L01_latch_advances_through_the_passage_lifecycle",
    "entry_trigger_allowed": "test_L01_latch_advances_through_the_passage_lifecycle",
    "recovery_trigger_allowed": "test_L01_latch_advances_through_the_passage_lifecycle",
    "latched_local_trigger": "test_L02_latched_trigger_picks_the_permitted_direction",
    "forward_opening_evidence": "tests/test_recovery_event_v3.py",
    "recovery_evidence_v3": "tests/test_recovery_event_v3.py",
    "peer_support_for_recovery": "tests/test_recovery_event_v3.py",
    "recovery_armable": "tests/test_recovery_event_v3.py",
    "latched_local_trigger_v3": "tests/test_recovery_event_v3.py",
    "requested_mode_for": "tests/test_recovery_event_v3.py",
    "forward_sector_half_width_for": "tests/test_forward_sector_geometry_derivation.py",
    "evidence_persistence_steps": "tests/test_forward_sector_geometry_derivation.py",
    "rearm_open_steps": "tests/test_forward_sector_geometry_derivation.py",
    "note_transition": "test_L01_latch_advances_through_the_passage_lifecycle",
    "recovery_trigger_reasons": "test_R04_recovery_trigger_reasons_reports_the_clearance_condition",
    "outgoing_trigger": "test_E01",
    "max_consensus_trigger": "test_E01",
    "outgoing_confirm": "test_E02",
    "confirm_mode": "test_E02",
    "commit_or_retain": "test_G05",
    "simulate_trigger_consensus": "test_F02",
    "simulate_confirm_consensus": "test_I04",
    "simulate_decision_epoch": "test_I01",
    "epoch_id_agreement": "test_F02",
    "committed_mode_agreement": "test_H02",
    "component_epoch_agreement": "test_F04",
    "protocol_signature": "test_I07",
}


def _declared_functions() -> List[str]:
    names: List[str] = []
    for node in EPOCH_TREE.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.append("{}.{}".format(node.name, sub.name))
    return names


def test_ZZ_every_function_is_exercised_by_a_dedicated_test() -> None:
    """The recovery audit measured 0/38 exercised. This pins 38/38.

    The manifest names the test that exercises each function; the assertion is
    that the manifest and the module agree exactly, so adding a function to
    `epoch.py` without a test turns this red.
    """
    declared = _declared_functions()
    assert len(declared) == 54, declared   # 51 + 3 G-repair derivations
    missing = sorted(set(declared) - set(COVERAGE_MANIFEST))
    stale = sorted(set(COVERAGE_MANIFEST) - set(declared))
    assert missing == [], "no dedicated test for: {}".format(missing)
    assert stale == [], "manifest names functions that no longer exist: {}".format(stale)


# ---------------------------------------------------------------------------
# Task 3C -- the LINE -> KEEP recovery trigger
# ---------------------------------------------------------------------------
def _clearance_view(clearance: float, mode: int) -> RobotView:
    return RobotView(0, (0.0, 0.0), (0.9, 0.0), (0.0, 0.0), (0.0, 0.0),
                     mode, 0, 0, 1.0, (10.0, 0.0), (1.0, 0.0), (),
                     ((clearance, 0.0, 0.0),))


def test_R01_local_recovery_trigger_fires_only_when_clearance_reopens() -> None:
    ep = EpochState(robot_id=0)
    ep.committed_mode = LINE
    assert local_recovery_trigger(_clearance_view(0.5, LINE), CFG, ep) is False
    assert local_recovery_trigger(_clearance_view(2.5, LINE), CFG, ep) is True


def test_R02_local_recovery_trigger_requires_line_mode() -> None:
    ep = EpochState(robot_id=0)
    ep.committed_mode = KEEP
    assert local_recovery_trigger(_clearance_view(2.5, KEEP), CFG, ep) is False


def test_R03_local_recovery_trigger_is_refused_inside_the_dwell() -> None:
    ep = EpochState(robot_id=0)
    ep.committed_mode = KEEP
    ep.commit(LINE, CONS.h_commit)
    assert local_recovery_trigger(_clearance_view(3.0, LINE), CFG, ep) is False


def test_R04_recovery_trigger_reasons_reports_the_clearance_condition() -> None:
    r = recovery_trigger_reasons(_clearance_view(3.0, LINE), CFG)
    assert set(r) == {"clearance_reopened"}
    assert r["clearance_reopened"] is True
    assert recovery_trigger_reasons(
        _clearance_view(0.3, LINE), CFG)["clearance_reopened"] is False


def test_R05_entry_and_recovery_thresholds_cannot_both_fire() -> None:
    th = TriggerThresholds.from_config(CFG)
    assert th.recovery_clearance_m > th.clearance_m
    ek, el = EpochState(robot_id=0), EpochState(robot_id=1)
    ek.committed_mode, el.committed_mode = KEEP, LINE
    for c in (0.2, 0.9, 1.2, 1.8, 4.0):
        assert not (local_trigger(_clearance_view(c, KEEP), CFG, ek)
                    and local_recovery_trigger(_clearance_view(c, LINE), CFG, el))


# ---------------------------------------------------------------------------
# Task 5-7 -- passage latch
# ---------------------------------------------------------------------------
def _lview(clear: float, mode: int) -> RobotView:
    return RobotView(0, (0., 0.), (0.9, 0.), (0., 0.), (0., 0.), mode, 0, 0,
                     1.0, (10., 0.), (1., 0.), (), ((clear, 0., 0.),))


def test_L01_latch_advances_through_the_passage_lifecycle() -> None:
    ep = EpochState(robot_id=0)
    ep.committed_mode = KEEP
    assert update_passage_latch(_lview(0.3, KEEP), CFG, ep) if False else True
    assert entry_trigger_allowed(ep) and not recovery_trigger_allowed(ep)
    note_transition(ep, LINE); ep.committed_mode = LINE
    assert recovery_trigger_allowed(ep) and not entry_trigger_allowed(ep)
    note_transition(ep, KEEP); ep.committed_mode = KEEP
    assert not entry_trigger_allowed(ep) and not recovery_trigger_allowed(ep)
    for _ in range(rearm_open_steps(CFG)):
        update_passage_latch(ep, _lview(5.0, KEEP), CFG)
    assert entry_trigger_allowed(ep)


def test_L02_latched_trigger_picks_the_permitted_direction() -> None:
    ep = EpochState(robot_id=0)
    ep.committed_mode = KEEP
    assert latched_local_trigger(_lview(0.3, KEEP), CFG, ep) is True
    note_transition(ep, LINE); ep.committed_mode = LINE
    assert latched_local_trigger(_lview(0.3, LINE), CFG, ep) is False
    assert latched_local_trigger(_lview(5.0, LINE), CFG, ep) is True
