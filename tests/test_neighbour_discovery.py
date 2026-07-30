"""Evidence for peer-to-peer neighbour discovery.

Every test here asserts a *semantic invariant* of the discovery layer -- range
gating, staleness, duplicate/out-of-order rejection, one-hop confinement,
determinism -- rather than a numeric coincidence, so a test cannot pass by
accident if the implementation changes shape.
"""

from __future__ import annotations

import dataclasses
import inspect
from collections import deque
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pytest

from rvt_swarm.decentralized import comms
from rvt_swarm.decentralized.comms import (Beacon, NeighbourTable, OwnHistory,
                                           RadioChannel, RobotRadioState,
                                           make_radio_states,
                                           simulate_broadcast_round,
                                           simulate_local_obstacles,
                                           view_digest)
from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.decentralized.system_model import (KEEP, LINE, CommParams,
                                                  NeighbourRecord, RobotView)

GOAL = (12.0, 0.0)
MISSION_DIR = (1.0, 0.0)
SPACING = 0.9
OBSTACLE_RADIUS = 0.35


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def make_beacon(sender_id: int, seq: int, timestamp_step: int,
                position: Tuple[float, float],
                velocity: Tuple[float, float] = (0.0, 0.0),
                committed_mode: int = KEEP, epoch_id: int = 0,
                degree: int = 0, valid: bool = True) -> Beacon:
    return Beacon(
        sender_id=sender_id, timestamp_step=timestamp_step, seq=seq,
        position=position, velocity=velocity,
        role_keep=(0.0, 0.0), role_line=(0.0, 0.0),
        committed_mode=committed_mode, epoch_id=epoch_id, degree=degree,
        valid=valid,
    )


def run_trace(positions_by_step: Sequence[np.ndarray],
              params: CommParams,
              seed: int = 7,
              velocities_by_step: Optional[Sequence[np.ndarray]] = None,
              epoch_ids: Optional[Sequence[int]] = None,
              obstacles: Optional[np.ndarray] = None,
              ) -> Tuple[Dict[int, RobotView], Dict[int, RobotRadioState],
                         RadioChannel, List[Dict[int, RobotView]]]:
    """Drive `simulate_broadcast_round` over a fixed positional trace."""
    n = int(np.asarray(positions_by_step[0]).reshape(-1, 2).shape[0])
    roles = RoleAssignment.from_index(n, SPACING)
    states = make_radio_states(range(n), params)
    channel = RadioChannel(params, seed=seed)
    modes = [KEEP] * n
    epochs = list(epoch_ids) if epoch_ids is not None else [0] * n
    ssd = [0] * n
    history: List[Dict[int, RobotView]] = []
    views: Dict[int, RobotView] = {}
    for step, pos in enumerate(positions_by_step):
        pos = np.asarray(pos, dtype=np.float64).reshape(-1, 2)
        if velocities_by_step is not None:
            vel = np.asarray(velocities_by_step[step], dtype=np.float64).reshape(-1, 2)
        else:
            vel = np.zeros_like(pos)
        views = simulate_broadcast_round(
            step=step, positions=pos, velocities=vel, roles=roles,
            committed_modes=modes, epoch_ids=epochs, steps_since_decision=ssd,
            states=states, channel=channel, obstacles=obstacles,
            obstacle_radius=OBSTACLE_RADIUS, goal=GOAL,
            mission_dir=MISSION_DIR, params=params,
        )
        history.append(views)
    return views, states, channel, history


def _collect_numbers(obj, out: List[float], depth: int = 0) -> None:
    """Every scalar reachable from `obj`, following containers and objects."""
    if depth > 12 or obj is None:
        return
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float, np.integer, np.floating)):
        out.append(float(obj))
        return
    if isinstance(obj, (str, bytes, bytearray)):
        return
    if isinstance(obj, np.ndarray):
        out.extend(float(v) for v in np.asarray(obj, dtype=np.float64).ravel().tolist())
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            _collect_numbers(key, out, depth + 1)
            _collect_numbers(value, out, depth + 1)
        return
    if isinstance(obj, (list, tuple, set, frozenset, deque)):
        for value in obj:
            _collect_numbers(value, out, depth + 1)
        return
    if dataclasses.is_dataclass(obj):
        for f in dataclasses.fields(obj):
            _collect_numbers(getattr(obj, f.name), out, depth + 1)
        return
    if hasattr(obj, "__dict__"):
        for value in vars(obj).values():
            _collect_numbers(value, out, depth + 1)
        return


def reachable_numbers(*objs) -> List[float]:
    out: List[float] = []
    for obj in objs:
        _collect_numbers(obj, out)
    return out


def table_entries(table: NeighbourTable) -> List[object]:
    """White-box access to the stored records, for leakage scans."""
    return list(table._entries.values())  # noqa: SLF001


# ===========================================================================
# 1. in range -> neighbour
# ===========================================================================
def test_robot_inside_r_comm_becomes_a_neighbour():
    params = CommParams()
    pos = np.array([[0.5, 0.25], [2.5, 0.25]], dtype=np.float64)  # 2.0 m < 3.0
    views, states, channel, _ = run_trace([pos], params)

    assert np.hypot(*(pos[1] - pos[0])) < params.r_comm
    assert views[0].neighbour_ids() == (1,)
    assert views[1].neighbour_ids() == (0,)
    assert views[0].degree == 1
    assert states[0].table.degree(0) == 1
    assert channel.dropped_out_of_range == 0
    # ego-relative, and exactly p_j - p_i
    assert views[0].neighbours[0].rel_position == pytest.approx((2.0, 0.0))
    assert views[1].neighbours[0].rel_position == pytest.approx((-2.0, 0.0))


# ===========================================================================
# 2. out of range -> not a neighbour
# ===========================================================================
def test_robot_outside_r_comm_does_not_become_a_neighbour():
    params = CommParams()
    pos = np.array([[0.5, 0.25], [4.0, 0.25]], dtype=np.float64)  # 3.5 m > 3.0
    views, states, channel, _ = run_trace([pos], params)

    assert np.hypot(*(pos[1] - pos[0])) > params.r_comm
    assert views[0].neighbour_ids() == ()
    assert views[1].neighbour_ids() == ()
    assert views[0].degree == 0
    assert states[0].table.known_ids() == ()
    assert channel.dropped_out_of_range == 2   # both directions gated
    assert channel.delivered == 0


def test_range_gate_is_the_only_difference_between_the_two_cases():
    """Same trace, only the separation changes: rules out an unrelated cause."""
    params = CommParams()
    near = np.array([[0.0, 0.0], [params.r_comm - 0.01, 0.0]])
    far = np.array([[0.0, 0.0], [params.r_comm + 0.01, 0.0]])
    v_near, _, _, _ = run_trace([near], params)
    v_far, _, _, _ = run_trace([far], params)
    assert v_near[0].degree == 1
    assert v_far[0].degree == 0


# ===========================================================================
# 3. staleness
# ===========================================================================
def test_stale_neighbour_is_removed():
    params = CommParams()
    assert params.delta_stale_steps == 3
    table = NeighbourTable(0, params, own_position=(1.0, 1.0))
    assert table.ingest(make_beacon(1, seq=1, timestamp_step=0, position=(2.0, 1.0)), 0)

    for now in range(0, params.delta_stale_steps + 1):     # age 0..3 -> fresh
        assert table.degree(now) == 1, now
        assert table.neighbours(now)[0].message_age_steps == now

    now = params.delta_stale_steps + 1                      # age 4 -> stale
    assert table.neighbours(now) == ()
    assert table.degree(now) == 0
    assert table.is_stale(1, now)
    assert table.prune(now) == (1,)
    assert table.stale_pruned == 1
    # the record is retained for sequence bookkeeping, but never served
    assert table.known_ids() == (1,)
    assert table.neighbours(now) == ()


def test_beacon_that_arrives_already_stale_is_rejected():
    params = CommParams()
    table = NeighbourTable(0, params, own_position=(0.0, 0.0))
    stale = make_beacon(1, seq=1, timestamp_step=0, position=(1.0, 0.0))
    assert table.ingest(stale, now_step=params.delta_stale_steps + 1) is False
    assert table.stale_rejected == 1
    assert table.known_ids() == ()


def test_beacon_stamped_in_the_future_is_rejected():
    """A delivery decision may never be revised by future information."""
    params = CommParams()
    table = NeighbourTable(0, params)
    assert table.ingest(make_beacon(1, seq=1, timestamp_step=9,
                                    position=(1.0, 0.0)), now_step=4) is False
    assert table.future_rejected == 1
    assert table.known_ids() == ()


# ===========================================================================
# 4. duplicates
# ===========================================================================
def test_duplicate_messages_do_not_create_duplicate_neighbours():
    params = CommParams()
    table = NeighbourTable(0, params, own_position=(0.0, 0.0))
    beacon = make_beacon(1, seq=1, timestamp_step=0, position=(1.5, 0.5))

    assert table.ingest(beacon, 0) is True
    for _ in range(5):
        assert table.ingest(beacon, 0) is False

    assert len(table.neighbours(0)) == 1
    assert table.neighbours(0)[0].robot_id == 1
    assert table.duplicates_rejected == 5
    assert table.accepted == 1
    assert table.out_of_order_rejected == 0
    # a duplicate must not perturb stored state either
    assert table.neighbours(0)[0].rel_position == pytest.approx((1.5, 0.5))


# ===========================================================================
# 5. out-of-order
# ===========================================================================
def test_out_of_order_message_cannot_overwrite_newer_state():
    params = CommParams()
    table = NeighbourTable(0, params, own_position=(0.0, 0.0))

    newer = make_beacon(1, seq=5, timestamp_step=5, position=(2.0, 0.0),
                        velocity=(0.4, 0.0), epoch_id=5, committed_mode=LINE)
    older = make_beacon(1, seq=3, timestamp_step=3, position=(-9.0, -9.0),
                        velocity=(-9.0, -9.0), epoch_id=3, committed_mode=KEEP)

    assert table.ingest(newer, now_step=5) is True
    assert table.ingest(older, now_step=5) is False    # fresh enough, but older

    stored = table.neighbours(5)[0]
    # the stored state is still the NEWER one
    assert stored.rel_position == pytest.approx((2.0, 0.0))
    assert stored.rel_velocity == pytest.approx((0.4, 0.0))
    assert stored.epoch_id == 5
    assert stored.committed_mode == LINE
    assert table.out_of_order_rejected == 1
    assert table.duplicates_rejected == 0
    # and the older payload left no trace anywhere in the table
    assert -9.0 not in reachable_numbers(table_entries(table))


def test_out_of_order_rejection_is_not_a_staleness_rejection():
    """Both beacons are inside the staleness window; only seq order decides."""
    params = CommParams()
    table = NeighbourTable(0, params)
    assert table.ingest(make_beacon(1, seq=5, timestamp_step=5,
                                    position=(2.0, 0.0)), 5)
    assert table.ingest(make_beacon(1, seq=3, timestamp_step=3,
                                    position=(7.0, 7.0)), 5) is False
    assert table.stale_rejected == 0
    assert table.out_of_order_rejected == 1


# ===========================================================================
# 6. no raw state travels more than one hop
# ===========================================================================
# Chain A(0) -- B(1) -- C(2). A-C separation 5.0 m > r_comm = 3.0 m.
# C's scalars are chosen to be unmistakable so that a leak is detectable by
# value, and C's identity is checked structurally by id.
A_POS, B_POS, C_POS = (0.5, 0.25), (2.9, 0.25), (5.37, 1.38)
A_VEL, B_VEL, C_VEL = (0.11, 0.0), (0.13, 0.02), (0.7771, -0.3331)
C_EPOCH = 913
C_SCALARS = (5.37, 1.38, 0.7771, -0.3331, float(C_EPOCH))


def chain_trace(params: CommParams, steps: int = 6,
                c_pos=C_POS, c_vel=C_VEL, c_epoch=C_EPOCH):
    pos = np.array([A_POS, B_POS, c_pos], dtype=np.float64)
    vel = np.array([A_VEL, B_VEL, c_vel], dtype=np.float64)
    return run_trace([pos] * steps, params, seed=3,
                     velocities_by_step=[vel] * steps,
                     epoch_ids=[1, 4, c_epoch])


def test_chain_geometry_is_actually_two_hop():
    params = CommParams()
    a, b, c = np.array(A_POS), np.array(B_POS), np.array(C_POS)
    assert np.hypot(*(b - a)) <= params.r_comm
    assert np.hypot(*(c - b)) <= params.r_comm
    assert np.hypot(*(c - a)) > params.r_comm


def test_no_two_hop_forwarding():
    params = CommParams()
    views, states, _, _ = chain_trace(params)
    now = 5

    # B sees both; A and C see only B. The chain is genuinely two-hop.
    assert views[1].neighbour_ids() == (0, 2)
    assert views[0].neighbour_ids() == (1,)
    assert views[2].neighbour_ids() == (1,)

    # --- C's IDENTITY is absent from A, structurally ---
    assert states[0].table.known_ids() == (1,)
    assert 2 not in views[0].neighbour_ids()
    assert all(nb.robot_id != 2 for nb in views[0].neighbours)

    # --- C's STATE is absent from A, by value ---
    numbers = reachable_numbers(views[0], states[0].table.neighbours(now),
                                table_entries(states[0].table))
    for forbidden in C_SCALARS:
        assert not any(abs(v - forbidden) < 1e-12 for v in numbers), forbidden

    # sanity: the scan would have caught a leak -- B's state IS present
    assert any(abs(v - (B_POS[0] - A_POS[0])) < 1e-12 for v in numbers)

    # --- structurally, a beacon cannot carry a neighbour list at all ---
    # B's own outgoing beacon: no field of it is a container of records, so
    # forwarding third-party state is unrepresentable rather than merely absent.
    b_beacon = comms.build_beacon(
        states[1], now, B_POS, B_VEL, (0.0, 0.0), (0.0, 0.0), KEEP, 4)
    for f in dataclasses.fields(Beacon):
        value = getattr(b_beacon, f.name)
        assert isinstance(value, (int, float, bool, tuple)), f.name
        if isinstance(value, tuple):
            assert len(value) == 2 and all(isinstance(v, float) for v in value)
    assert b_beacon.degree == 2          # a scalar count, not a set of ids


# ===========================================================================
# 7. two-hop state change is invisible to robot i
# ===========================================================================
def test_two_hop_state_change_leaves_table_byte_identical():
    params = CommParams()
    now = 5

    # C' stays inside B's range and outside A's range, so B's degree -- the one
    # legitimate one-hop aggregate -- is unchanged between the two runs.
    c_pos_alt, c_vel_alt, c_epoch_alt = (5.10, 1.02), (-0.5, 0.4), 77
    a = np.array(A_POS)
    b = np.array(B_POS)
    c2 = np.array(c_pos_alt)
    assert np.hypot(*(c2 - b)) <= params.r_comm
    assert np.hypot(*(c2 - a)) > params.r_comm

    v1, s1, _, _ = chain_trace(params)
    v2, s2, _, _ = chain_trace(params, c_pos=c_pos_alt, c_vel=c_vel_alt,
                               c_epoch=c_epoch_alt)

    # C really did change, and B really did notice
    assert v2[2].position != v1[2].position
    assert v1[1].neighbours[1].rel_position != v2[1].neighbours[1].rel_position

    # ... and A saw nothing at all: byte-identical table and view
    assert s1[0].table.canonical_bytes(now) == s2[0].table.canonical_bytes(now)
    assert s1[0].table.digest(now) == s2[0].table.digest(now)
    assert comms.view_canonical_bytes(v1[0]) == comms.view_canonical_bytes(v2[0])
    assert view_digest(v1[0]) == view_digest(v2[0])
    assert s1[0].table.counters() == s2[0].table.counters()


# ===========================================================================
# 8. determinism under the same message trace
# ===========================================================================
def lossy_trace_positions(n: int, steps: int) -> List[np.ndarray]:
    base = np.array([[0.0, 0.0], [1.6, 0.4], [3.1, -0.3], [4.4, 0.8]][:n],
                    dtype=np.float64)
    drift = np.array([[0.05, 0.0], [0.04, 0.01], [0.06, -0.01], [0.03, 0.02]][:n],
                     dtype=np.float64)
    return [base + drift * float(t) for t in range(steps)]


def test_neighbour_discovery_is_deterministic_under_the_same_trace():
    params = CommParams(packet_loss=0.25, delay_steps=1)
    positions = lossy_trace_positions(4, 12)
    obstacles = np.array([[2.0, 1.2], [6.5, -3.0], [1.0, -2.4]], dtype=np.float64)

    def once():
        views, states, channel, history = run_trace(
            positions, params, seed=20000001, obstacles=obstacles)
        return (
            [tuple(sorted((i, view_digest(v)) for i, v in step_views.items()))
             for step_views in history],
            {i: st.table.digest(len(positions) - 1) for i, st in states.items()},
            {i: st.table.counters() for i, st in states.items()},
            (channel.transmitted, channel.dropped_out_of_range,
             channel.dropped_loss, channel.delivered),
        )

    first = once()
    second = once()
    assert first == second

    # the trace must actually exercise loss and range gating, or the test is void
    assert first[3][2] > 0, "no packet was lost -- loss path untested"
    assert first[3][1] > 0, "no packet was range-gated -- range path untested"
    assert any(counters["accepted"] > 0 for counters in first[2].values())


def test_delivery_draw_depends_only_on_seed_step_src_dst():
    a = comms._u01(11, 3, 0, 1)
    assert a == comms._u01(11, 3, 0, 1)
    assert a != comms._u01(12, 3, 0, 1)
    assert a != comms._u01(11, 4, 0, 1)
    assert a != comms._u01(11, 3, 1, 0)
    assert 0.0 <= a < 1.0


def test_delivery_decision_is_independent_of_unrelated_transmissions():
    """Stronger than replay determinism.

    Replaying one trace cannot tell a pure hash from a stateful RNG, because a
    stateful RNG replays identically too. This pins the actual claim: the drop
    decision for a link is a function of (seed, step, src, dst) alone, so it
    does not shift when other packets are sent first, when iteration order
    changes, or when the simulation is resumed mid-episode.
    """
    params = CommParams(packet_loss=0.5)
    here, there = (0.0, 0.0), (1.0, 0.0)

    def decisions(prefix_noise: int) -> List[bool]:
        channel = RadioChannel(params, seed=99)
        for k in range(prefix_noise):     # unrelated traffic on another link
            channel.transmit(make_beacon(9, seq=k, timestamp_step=0, position=here),
                             here, 8, there, step=100 + k)
        out: List[bool] = []
        for step in range(6):
            for src in range(3):
                for dst in range(3):
                    if src == dst:
                        continue
                    beacon = make_beacon(src, seq=step, timestamp_step=step,
                                         position=here)
                    out.append(channel.transmit(beacon, here, dst, there, step)
                               is not None)
        return out

    clean = decisions(0)
    noisy = decisions(17)
    assert clean == noisy
    assert 0 < sum(clean) < len(clean), "loss draw never varied -- test is vacuous"


def test_delayed_packet_arrives_exactly_at_send_step_plus_delay():
    params = CommParams(delay_steps=2)
    channel = RadioChannel(params, seed=1)
    beacon = make_beacon(1, seq=1, timestamp_step=4, position=(1.0, 0.0))

    assert channel.transmit(beacon, (0.0, 0.0), 0, (1.0, 0.0), step=4) == 6
    assert channel.deliver(4) == ()
    assert channel.deliver(5) == ()
    delivered = channel.deliver(6)
    assert [dst for dst, _ in delivered] == [0]
    assert channel.pending() == 0

    table = NeighbourTable(0, params)
    assert table.ingest(delivered[0][1], 6) is True
    assert table.neighbours(6)[0].message_age_steps == 2   # the delay, not zero


def test_neighbour_order_is_id_sorted_not_arrival_sorted():
    params = CommParams()
    forward = NeighbourTable(0, params)
    reverse = NeighbourTable(0, params)
    packets = [make_beacon(k, seq=1, timestamp_step=0, position=(float(k), 0.0))
               for k in (5, 2, 9, 1)]
    for beacon in packets:
        forward.ingest(beacon, 0)
    for beacon in reversed(packets):
        reverse.ingest(beacon, 0)
    assert [nb.robot_id for nb in forward.neighbours(0)] == [1, 2, 5, 9]
    assert forward.canonical_bytes(0) == reverse.canonical_bytes(0)


# ===========================================================================
# no absolute neighbour position is reachable from a RobotView
# ===========================================================================
# Dyadic coordinates and dyadic offsets, so that (x + off) - (y + off) == x - y
# EXACTLY in float64. Without that, the byte-identity assertion below would be
# testing floating-point associativity rather than the invariant it is about.
BASE_POS = np.array([[3.3125, -1.71875], [5.0625, 0.4375], [4.125, -2.1875]],
                    dtype=np.float64)
BASE_VEL = np.array([[0.203125, -0.078125], [0.53125, 0.3125],
                     [-0.1875, 0.4375]], dtype=np.float64)
POS_OFFSET = np.array([128.0, -64.0])
VEL_OFFSET = np.array([32.0, -16.0])
BIG = 15.0   # every shifted absolute exceeds this; every relative is far below


def test_neighbour_state_is_invariant_to_a_rigid_shift_of_the_whole_swarm():
    """The exact statement of "no absolute pose is stored".

    Translating every robot by a constant leaves every ego-relative quantity
    untouched but changes every absolute one. If a single absolute coordinate
    had survived into a table, the canonical bytes would differ. This cannot
    pass by numeric coincidence, unlike a value scan.
    """
    params = CommParams()
    steps = 3
    _, base_states, _, base_hist = run_trace(
        [BASE_POS] * steps, params, velocities_by_step=[BASE_VEL] * steps)
    _, shift_states, _, shift_hist = run_trace(
        [BASE_POS + POS_OFFSET] * steps, params,
        velocities_by_step=[BASE_VEL + VEL_OFFSET] * steps)

    now = steps - 1
    for i in base_states:
        assert base_states[i].table.canonical_bytes(now) == \
            shift_states[i].table.canonical_bytes(now)
        assert base_hist[now][i].neighbours == shift_hist[now][i].neighbours

    # the shift really happened: own absolute pose (which a robot IS allowed to
    # know) differs, so the invariance above is not vacuous
    assert base_hist[now][0].position != shift_hist[now][0].position
    assert base_hist[now][0].velocity != shift_hist[now][0].velocity
    assert base_hist[now][0].neighbour_ids() == (1, 2)


def test_no_absolute_neighbour_position_is_reachable_from_a_view():
    params = CommParams()
    # Every absolute coordinate exceeds BIG in magnitude while every legitimate
    # ego-relative coordinate is far below it, so a match in the scan below can
    # only be a leak and never a coincidence. Asserted, not assumed.
    pos = BASE_POS + POS_OFFSET
    vel = BASE_VEL + VEL_OFFSET
    views, states, _, _ = run_trace([pos] * 3, params,
                                    velocities_by_step=[vel] * 3)
    assert views[0].neighbour_ids() == (1, 2)

    absolute_scalars = [float(v) for v in
                        np.concatenate([pos.ravel(), vel.ravel()])]
    assert min(abs(v) for v in absolute_scalars) > BIG
    assert max(abs(float(pos[j, k] - pos[i, k]))
               for i in range(3) for j in range(3) for k in range(2)) < BIG

    for i, view in views.items():
        numbers = reachable_numbers(view, table_entries(states[i].table))
        legitimate = [abs(v) for v in numbers if abs(v) > BIG]
        # only robot i's OWN absolute pose may be large; nothing else is
        assert sorted(legitimate) == sorted(
            abs(float(v)) for v in (pos[i, 0], pos[i, 1], vel[i, 0], vel[i, 1]))
        for j in views:
            if j == i:
                continue
            for coord in (pos[j, 0], pos[j, 1], vel[j, 0], vel[j, 1]):
                assert not any(abs(v - float(coord)) < 1e-12 for v in numbers), (
                    "absolute state of robot %d reachable from view of %d" % (j, i))
        # relative state IS present -- proves the scan is not vacuous
        for nb in view.neighbours:
            assert any(abs(v - nb.rel_position[0]) < 1e-12 for v in numbers)

    # structural: NeighbourRecord has no absolute-pose field at all
    names = {f.name for f in dataclasses.fields(NeighbourRecord)}
    assert "position" not in names and "velocity" not in names
    assert {"rel_position", "rel_velocity"} <= names


# ===========================================================================
# unknown-ID / reappearing neighbour
# ===========================================================================
def test_unknown_id_is_accepted_by_creating_an_entry():
    params = CommParams()
    table = NeighbourTable(0, params)
    assert table.known_ids() == ()
    assert table.ingest(make_beacon(42, seq=1, timestamp_step=0,
                                    position=(1.0, 0.0)), 0) is True
    assert table.known_ids() == (42,)
    assert table.unknown_id_accepted == 1
    assert table.ingest(make_beacon(42, seq=2, timestamp_step=0,
                                    position=(1.1, 0.0)), 0) is True
    assert table.unknown_id_accepted == 1     # known now, not counted again


def test_reappearing_neighbour_is_readmitted_and_counted():
    params = CommParams()
    table = NeighbourTable(0, params)
    assert table.ingest(make_beacon(1, seq=1, timestamp_step=0,
                                    position=(1.0, 0.0)), 0)
    silent = params.delta_stale_steps + 2
    assert table.neighbours(silent) == ()
    table.prune(silent)
    assert table.reappeared == 0

    assert table.ingest(make_beacon(1, seq=2, timestamp_step=silent,
                                    position=(1.4, 0.2)), silent) is True
    assert table.reappeared == 1
    assert table.unknown_id_accepted == 1
    assert [nb.robot_id for nb in table.neighbours(silent)] == [1]
    assert table.neighbours(silent)[0].rel_position == pytest.approx((1.4, 0.2))

    # a replayed pre-silence packet is still rejected after readmission
    assert table.ingest(make_beacon(1, seq=1, timestamp_step=silent,
                                    position=(-5.0, -5.0)), silent) is False
    assert table.neighbours(silent)[0].rel_position == pytest.approx((1.4, 0.2))


def test_simultaneous_messages_give_an_order_independent_result():
    """Same step, same sender, two sequence numbers: final state is seq-max."""
    params = CommParams()
    lo = make_beacon(1, seq=4, timestamp_step=2, position=(1.0, 0.0))
    hi = make_beacon(1, seq=5, timestamp_step=2, position=(2.0, 0.0))

    ascending = NeighbourTable(0, params)
    ascending.ingest(lo, 2)
    ascending.ingest(hi, 2)

    descending = NeighbourTable(0, params)
    descending.ingest(hi, 2)
    descending.ingest(lo, 2)

    assert ascending.neighbours(2)[0].rel_position == pytest.approx((2.0, 0.0))
    assert descending.neighbours(2)[0].rel_position == pytest.approx((2.0, 0.0))
    assert descending.out_of_order_rejected == 1
    assert ascending.out_of_order_rejected == 0

    # different senders in one step: fully order independent, counters included
    forward = NeighbourTable(0, params)
    backward = NeighbourTable(0, params)
    batch = [make_beacon(k, seq=1, timestamp_step=0, position=(float(k), 1.0))
             for k in (3, 1, 2)]
    for beacon in batch:
        forward.ingest(beacon, 0)
    for beacon in reversed(batch):
        backward.ingest(beacon, 0)
    assert forward.canonical_bytes(0) == backward.canonical_bytes(0)
    assert forward.counters() == backward.counters()


def test_a_robot_rejects_its_own_beacon():
    params = CommParams()
    table = NeighbourTable(3, params)
    assert table.ingest(make_beacon(3, seq=1, timestamp_step=0,
                                    position=(0.0, 0.0)), 0) is False
    assert table.self_rejected == 1
    assert table.known_ids() == ()


# ===========================================================================
# obstacle gating and local_progress
# ===========================================================================
def test_obstacles_are_gated_to_r_obs_and_returned_ego_relative():
    params = CommParams()
    own = (1.0, 1.0)
    obstacles = np.array([
        [1.5, 1.0],                      # 0.5 m -> in
        [1.0, 1.0 + params.r_obs],       # exactly r_obs -> in (boundary)
        [1.0, 1.0 + params.r_obs + 1e-6],  # just outside -> out
        [9.0, 9.0],                      # far -> out
    ], dtype=np.float64)
    got = simulate_local_obstacles(own, obstacles, OBSTACLE_RADIUS, params.r_obs)
    assert len(got) == 2
    assert got[0] == pytest.approx((0.5, 0.0, OBSTACLE_RADIUS))
    assert got[1] == pytest.approx((0.0, params.r_obs, OBSTACLE_RADIUS))
    assert simulate_local_obstacles(own, None, OBSTACLE_RADIUS, params.r_obs) == ()


def test_view_obstacles_differ_per_robot_and_are_range_gated():
    params = CommParams()
    pos = np.array([[0.0, 0.0], [2.0, 0.0]], dtype=np.float64)
    obstacles = np.array([[0.4, 0.0], [8.0, 0.0]], dtype=np.float64)
    views, _, _, _ = run_trace([pos], params, obstacles=obstacles)
    assert len(views[0].obstacles) == 1 and len(views[1].obstacles) == 1
    assert list(views[0].obstacles[0]) == pytest.approx([0.4, 0.0, OBSTACLE_RADIUS])
    assert list(views[1].obstacles[0]) == pytest.approx([-1.6, 0.0, OBSTACLE_RADIUS])
    # the far obstacle is outside r_obs for both, so neither robot ever sees it
    assert all(abs(o[0] - 8.0) > 1e-9 for v in views.values() for o in v.obstacles)


def test_local_progress_uses_only_the_robots_own_history():
    hist = OwnHistory(window=5)
    for t in range(7):
        hist.push(t, (0.1 * t, 0.0))
    assert hist.progress((1.0, 0.0)) == pytest.approx(0.5)
    assert hist.progress((0.0, 1.0)) == pytest.approx(0.0)

    params = CommParams()
    steps = 8
    # robot 0 follows an identical trajectory in both runs; robot 1 does not.
    def trace(k: float):
        return [np.array([[0.05 * t, 0.0], [1.5 + k * t, 0.0]], dtype=np.float64)
                for t in range(steps)]

    _, _, _, h_a = run_trace(trace(0.0), params)
    _, _, _, h_b = run_trace(trace(0.09), params)
    progress_a = [step_views[0].local_progress for step_views in h_a]
    progress_b = [step_views[0].local_progress for step_views in h_b]
    assert progress_a == progress_b
    assert progress_a[-1] == pytest.approx(0.25)   # 5 steps x 0.05 m
    # robot 1 genuinely moved differently, so the runs are not trivially equal
    assert h_a[-1][1].position != h_b[-1][1].position


# ===========================================================================
# boundary audit: only simulate_* functions may see global arrays
# ===========================================================================
GLOBAL_PARAM_NAMES = {"positions", "velocities", "obstacles", "obs",
                      "states", "obs_dict", "all_positions"}


def test_only_simulate_prefixed_functions_take_global_state():
    offenders = []
    for name, fn in vars(comms).items():
        if not inspect.isfunction(fn) or fn.__module__ != comms.__name__:
            continue
        if name.startswith("simulate_"):
            continue
        params = set(inspect.signature(fn).parameters)
        leaked = params & GLOBAL_PARAM_NAMES
        if leaked:
            offenders.append((name, sorted(leaked)))
    assert offenders == []


def test_the_boundary_declares_itself():
    doc = simulate_broadcast_round.__doc__ or ""
    assert "SIMULATION BOUNDARY" in doc
    assert "Not deployable" in doc
    assert simulate_broadcast_round.__name__.startswith("simulate_")
    assert isinstance(simulate_broadcast_round(
        step=0,
        positions=np.array([[0.0, 0.0], [1.0, 0.0]]),
        velocities=np.zeros((2, 2)),
        roles=RoleAssignment.from_index(2, SPACING),
        committed_modes=[KEEP, KEEP], epoch_ids=[0, 0],
        steps_since_decision=[0, 0],
        states=make_radio_states(range(2), CommParams()),
        channel=RadioChannel(CommParams(), seed=0),
        obstacles=None, obstacle_radius=OBSTACLE_RADIUS,
        goal=GOAL, mission_dir=MISSION_DIR, params=CommParams(),
    )[0], RobotView)


def test_beacon_schema_is_exactly_the_declared_field_list():
    assert [f.name for f in dataclasses.fields(Beacon)] == [
        "sender_id", "timestamp_step", "seq", "position", "velocity",
        "role_keep", "role_line", "committed_mode", "epoch_id", "degree",
        "valid",
    ]
    beacon = make_beacon(1, seq=1, timestamp_step=0, position=(1.0, 2.0))
    assert len(beacon.payload_bytes()) == 49
    with pytest.raises(dataclasses.FrozenInstanceError):
        beacon.sender_id = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pinning the disclosed two-hop channel (audit finding F1)
# ---------------------------------------------------------------------------
def test_two_hop_change_reaches_robot_i_exactly_through_neighbour_degree() -> None:
    """The two-hop invariant holds for STATE and fails for DEGREE. Pin both.

    An audit showed the original two-hop test chose a displacement under which
    the shared neighbour's degree happened not to change -- the one construction
    where the unqualified claim holds. Here the moved robot deliberately leaves
    B's range, so deg_B really does change, and we assert that the degree field
    is the *only* thing that differs in A's table.
    """
    from rvt_swarm.decentralized.comms import Beacon, NeighbourTable
    from rvt_swarm.decentralized.system_model import CommParams

    cp = CommParams()

    def a_table(deg_b: int) -> NeighbourTable:
        t = NeighbourTable(0, cp)
        t.set_own_position((0.0, 0.0), (0.0, 0.0))
        t.ingest(Beacon(1, 1, 1, (1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0),
                        0, 0, deg_b, True), 1)
        return t

    # C within B's range (deg_B = 2) vs C outside it (deg_B = 1). C is out of
    # A's range in BOTH cases, so nothing about C's state can legitimately reach A.
    near, far = a_table(2).neighbours(1), a_table(1).neighbours(1)
    assert len(near) == len(far) == 1
    n, f = near[0], far[0]

    # The exception, pinned: degree differs.
    assert n.degree == 2 and f.degree == 1

    # Everything else is byte-identical -- no state, identity, or geometry leaks.
    fields = ("robot_id", "rel_position", "rel_velocity", "role_keep",
              "role_line", "committed_mode", "epoch_id", "message_age_steps",
              "link_valid")
    for attr in fields:
        assert getattr(n, attr) == getattr(f, attr), f"{attr} leaked two-hop state"

    # And the channel is declared in the contract rather than discovered later.
    from rvt_swarm.decentralized.system_model import DISCLOSED_AGGREGATE_CHANNELS
    assert "neighbour_degree" in DISCLOSED_AGGREGATE_CHANNELS
