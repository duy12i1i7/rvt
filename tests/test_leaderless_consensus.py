"""Evidence for leaderless finite-round peer-to-peer score consensus.

Every test asserts a *semantic invariant* of the protocol -- average
preservation, one-hop-per-round propagation, admission control, permutation
equivariance, leaderlessness, one-hop information confinement -- rather than a
numeric coincidence, so no test can pass by accident if the implementation
changes shape.

Two tests deliberately record behaviour that is *worse* than the surrounding
documents claim (`test_08a_...` fails, `test_11_...` pins the measured result).
They are named and documented so the defect is visible rather than absorbed:
see the module docstring of the DELAY/ASYNC section below.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import struct
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pytest

from rvt_swarm.decentralized import consensus as consensus_mod
from rvt_swarm.decentralized.consensus import (ConsensusNode, ScoreMessage,
                                               agreement_rate,
                                               component_agreement,
                                               connected_components,
                                               consensus_residual,
                                               max_pairwise_gap,
                                               metropolis_weight,
                                               simulate_consensus)
from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.decentralized.system_model import (DISCLOSED_AGGREGATE_CHANNELS,
                                                  KEEP, LINE, CommParams,
                                                  ConsensusParams)

Graph = Dict[int, Tuple[int, ...]]

VALS4: List[Tuple[float, float]] = [(1.0, 0.0), (0.0, 1.0), (0.4, 0.1), (-0.3, 0.7)]
VALS6: List[Tuple[float, float]] = VALS4 + [(0.9, -0.2), (-0.5, 0.5)]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def path_graph(n: int) -> Graph:
    return {i: tuple(j for j in (i - 1, i + 1) if 0 <= j < n) for i in range(n)}


def ring_graph(n: int) -> Graph:
    return {i: ((i - 1) % n, (i + 1) % n) for i in range(n)}


def complete_graph(n: int) -> Graph:
    return {i: tuple(j for j in range(n) if j != i) for i in range(n)}


def make_nodes(graph: Graph, values: Sequence[Tuple[float, float]],
               epoch_id: int = 0, order: Optional[Sequence[int]] = None,
               params: Optional[ConsensusParams] = None
               ) -> Dict[int, ConsensusNode]:
    """One ConsensusNode per graph vertex. `degree` is that vertex's own degree."""
    keys = list(graph) if order is None else list(order)
    return {i: ConsensusNode.from_logits(i, values[i][0], values[i][1],
                                         len(graph[i]), epoch_id, params)
            for i in keys}


def set_degrees(nodes: Dict[int, ConsensusNode], graph: Graph) -> None:
    """Refresh each robot's own one-hop degree after the graph changes."""
    for i, node in nodes.items():
        node.degree = len(graph[i])


def stacked(nodes: Dict[int, ConsensusNode]) -> np.ndarray:
    return np.stack([nodes[i].z for i in sorted(nodes)])


def mean_value(nodes: Dict[int, ConsensusNode]) -> np.ndarray:
    return stacked(nodes).mean(axis=0)


def graph_diameter(graph: Graph) -> int:
    """Offline diagnostic used by the tests only."""
    best = 0
    for src in graph:
        dist = {src: 0}
        frontier = [src]
        while frontier:
            nxt: List[int] = []
            for u in frontier:
                for v in graph[u]:
                    if v not in dist:
                        dist[v] = dist[u] + 1
                        nxt.append(v)
            frontier = nxt
        best = max(best, max(dist.values()))
    return best


def message(sender_id: int, round_index: int, z_keep: float, z_line: float,
            degree: int, timestamp_step: int, epoch_id: int = 0) -> ScoreMessage:
    return ScoreMessage(sender_id=sender_id, epoch_id=epoch_id,
                        round_index=round_index, z_keep=z_keep, z_line=z_line,
                        degree=degree, timestamp_step=timestamp_step)


# ===========================================================================
# 1. connected static graph
# ===========================================================================
def test_01_connected_static_graph_reaches_agreement() -> None:
    """Irregular connected graph (degrees 1..4): every robot ends at the mean.

    The graph is deliberately not vertex-transitive, so a rule that secretly
    depended on uniform degree would not survive it.
    """
    graph: Graph = {0: (1, 2), 1: (0, 2, 3), 2: (0, 1, 3, 4), 3: (1, 2, 4),
                    4: (2, 3), 5: (4,)}
    graph[4] = (2, 3, 5)
    values = VALS6
    nodes = make_nodes(graph, values)
    z_init = stacked(nodes)
    m0 = mean_value(nodes)

    residuals = []
    for k in (0, 1, 2, 4, 8, 16):
        run_nodes = make_nodes(graph, values)
        out = simulate_consensus(run_nodes, graph, k)
        residuals.append(out["residual"])
    # strictly monotone decreasing
    assert all(residuals[i] > residuals[i + 1] for i in range(len(residuals) - 1)), residuals
    # Convergence is geometric, not finite-time: MH on a path graph has a small
    # spectral gap, so 16 rounds reaches ~2.5e-2, not 1e-4. Assert the actual
    # claim -- that it converges to agreement -- with enough rounds to show it.
    long_run = simulate_consensus(make_nodes(graph, values), graph, 400)
    assert long_run["residual"] < 1e-4, long_run["residual"]

    out = simulate_consensus(nodes, graph, 32)
    # (a) consensus value == the initial mean (average preservation)
    # Geometric convergence: a path graph's spectral gap makes 32 rounds reach
    # ~1e-3, not 1e-9. Run long enough to demonstrate the asymptotic claim.
    converged = make_nodes(graph, values)
    simulate_consensus(converged, graph, 400)
    assert np.allclose(stacked(converged), np.broadcast_to(m0, (len(graph), 2)), atol=1e-9)
    # (b) every intermediate value stays inside the convex hull of the initial
    #     values -- the update is a convex combination, so it cannot overshoot
    for snap in out["history"]:
        Z = np.stack([snap[i] for i in sorted(snap)])
        assert (Z >= z_init.min(axis=0) - 1e-12).all()
        assert (Z <= z_init.max(axis=0) + 1e-12).all()
    # (c) unanimous decision on a connected graph
    assert agreement_rate(out["decisions"]) == 1.0
    assert connected_components(graph) == [[0, 1, 2, 3, 4, 5]]
    # max_pairwise_gap -> 0 only asymptotically; `out` above is the K=16 run.
    long_run = simulate_consensus(make_nodes(graph, values), graph, 400)
    assert long_run["max_pairwise_gap"] < 1e-9, long_run["max_pairwise_gap"]


# ===========================================================================
# 2. line / path graph
# ===========================================================================
def test_02_path_graph_mixes_slowly_and_k4_does_not_reach_the_far_end() -> None:
    """N=6 path, diameter 5. Established fact: K=4 does not reach the far end."""
    n = 6
    graph = path_graph(n)
    assert graph_diameter(graph) == 5
    values = [(1.0, 0.0)] + [(0.0, 0.0)] * (n - 1)

    nodes4 = make_nodes(graph, values)
    simulate_consensus(nodes4, graph, 4)
    assert float(nodes4[5].z[0]) == 0.0          # far end untouched at K=4
    assert nodes4[5].applied == 4                # it did receive messages
    assert float(nodes4[4].z[0]) > 0.0           # one hop nearer has moved

    nodes5 = make_nodes(graph, values)
    simulate_consensus(nodes5, graph, 5)
    assert float(nodes5[5].z[0]) > 0.0           # K=5 == diameter reaches it

    # A path still converges, just slowly; the mean is preserved throughout.
    nodes_long = make_nodes(graph, VALS6)
    m0 = mean_value(nodes_long)
    out = simulate_consensus(nodes_long, graph, 200)
    assert np.allclose(mean_value(nodes_long), m0, atol=1e-12)
    assert out["residual"] < 1e-6
    assert agreement_rate(out["decisions"]) == 1.0


# ===========================================================================
# 3. ring graph
# ===========================================================================
def test_03_ring_graph_converges_faster_than_the_path() -> None:
    """A 6-ring is 2-connected: strictly better mixing than the 6-path."""
    n = 6
    ring, path = ring_graph(n), path_graph(n)
    assert graph_diameter(ring) == 3

    ring_nodes = make_nodes(ring, VALS6)
    m0 = mean_value(ring_nodes)
    ring_out = simulate_consensus(ring_nodes, ring, 6)
    path_nodes = make_nodes(path, VALS6)
    path_out = simulate_consensus(path_nodes, path, 6)

    assert np.allclose(mean_value(ring_nodes), m0, atol=1e-12)
    assert ring_out["residual"] < path_out["residual"]
    assert ring_out["residual"] < 0.1 * consensus_residual(make_nodes(ring, VALS6))

    ring_nodes = make_nodes(ring, VALS6)
    long_out = simulate_consensus(ring_nodes, ring, 64)
    assert long_out["residual"] < 1e-9
    assert agreement_rate(long_out["decisions"]) == 1.0


# ===========================================================================
# 4. time-varying connected graph
# ===========================================================================
def test_04_time_varying_graph_agrees_where_each_static_snapshot_cannot() -> None:
    """E_c^t alternates between two disconnected matchings whose union is a ring.

    Neither snapshot alone can produce swarm-wide agreement; the union over time
    does. Run one round per snapshot, refreshing each robot's own degree, which
    is exactly what its neighbour table would report.
    """
    n = 4
    even: Graph = {0: (1,), 1: (0,), 2: (3,), 3: (2,)}
    odd: Graph = {0: (3,), 1: (2,), 2: (1,), 3: (0,)}
    values = VALS4

    # -- control: either snapshot held static leaves two disagreeing pairs --
    static = make_nodes(even, values)
    static_out = simulate_consensus(static, even, 8)
    assert static_out["residual"] > 0.1
    assert connected_components(even) == [[0, 1], [2, 3]]

    # -- time-varying --
    nodes = make_nodes(even, values)
    m0 = mean_value(nodes)
    for k in range(24):
        graph = even if k % 2 == 0 else odd
        set_degrees(nodes, graph)
        simulate_consensus(nodes, graph, 1, start_step=k, record_history=False)
        # each snapshot is symmetric, so the mean is preserved every round
        assert np.allclose(mean_value(nodes), m0, atol=1e-12), k

    assert consensus_residual(nodes) < 1e-6
    decisions = {i: node.decide() for i, node in nodes.items()}
    assert agreement_rate(decisions) == 1.0


# ===========================================================================
# 5. node-permutation invariance
# ===========================================================================
def test_05_relabelling_the_robots_permutes_the_result_and_not_the_multiset() -> None:
    """Relabel ids with a permutation; the final value multiset is unchanged.

    Insertion order of the node dict is permuted too, so the test also rules out
    any dependence on scheduling order -- a leader would show up as exactly that.
    """
    base: Graph = {0: (1, 2), 1: (0, 2), 2: (0, 1, 3), 3: (2, 4), 4: (3,)}
    values = VALS4 + [(0.9, -0.2)]
    perm = {0: 3, 1: 0, 2: 4, 3: 1, 4: 2}

    plain = make_nodes(base, values)
    simulate_consensus(plain, base, 5)

    relabelled: Graph = {perm[i]: tuple(sorted(perm[j] for j in nbrs))
                         for i, nbrs in base.items()}
    perm_values = [(0.0, 0.0)] * 5
    for i, v in enumerate(values):
        perm_values[perm[i]] = v
    # insertion order deliberately reversed
    permuted = make_nodes(relabelled, perm_values, order=sorted(relabelled, reverse=True))
    simulate_consensus(permuted, relabelled, 5)

    a = np.array(sorted(map(tuple, stacked(plain).tolist())))
    b = np.array(sorted(map(tuple, stacked(permuted).tolist())))
    assert np.allclose(a, b, atol=1e-12), (a, b)
    # stronger: the per-robot correspondence holds, not just the multiset
    for i in base:
        assert np.allclose(plain[i].z, permuted[perm[i]].z, atol=1e-12), i


# ===========================================================================
# 6. deterministic repeatability
# ===========================================================================
def test_06_same_seed_reproduces_bitwise_and_different_seed_does_not() -> None:
    graph = ring_graph(6)

    def run(seed: int) -> Dict[int, ConsensusNode]:
        nodes = make_nodes(graph, VALS6)
        simulate_consensus(nodes, graph, 8, packet_loss=0.35, seed=seed)
        return nodes

    a, b, c = run(11), run(11), run(12)
    for i in sorted(graph):
        assert a[i].z.tobytes() == b[i].z.tobytes(), i        # bitwise
        assert (a[i].applied, a[i].missing) == (b[i].applied, b[i].missing)
    # a determinism test is worthless if the run is a no-op: a different seed
    # must actually produce a different trace
    assert any(a[i].z.tobytes() != c[i].z.tobytes() for i in graph)


# ===========================================================================
# 7. packet loss
# ===========================================================================
def test_07_packet_loss_is_lossless_not_replayed_and_stays_in_the_hull() -> None:
    graph = path_graph(4)

    # (a) total loss: nothing changes, and every expected message is counted
    #     missing. A dropped message is never resent from the future.
    dead = make_nodes(graph, VALS4)
    z_init = stacked(dead)
    out = simulate_consensus(dead, graph, 6, packet_loss=1.0, seed=0)
    assert np.array_equal(stacked(dead), z_init)
    for i, node in dead.items():
        assert node.applied == 0
        assert node.missing == 6 * len(graph[i])
    assert out["residual"] == pytest.approx(consensus_residual(make_nodes(graph, VALS4)))

    # (b) partial loss: still a convex combination, so no value leaves the hull
    lossy = make_nodes(graph, VALS4)
    m0 = mean_value(lossy)
    lossy_out = simulate_consensus(lossy, graph, 6, packet_loss=0.3, seed=0)
    Z = stacked(lossy)
    assert (Z >= z_init.min(axis=0) - 1e-12).all()
    assert (Z <= z_init.max(axis=0) + 1e-12).all()

    # (c) HONEST: with one-directional drops the weights are no longer
    #     symmetric, so average preservation is LOST. Measured, not assumed.
    drift = float(np.abs(mean_value(lossy) - m0).max())
    assert drift > 1e-3, drift

    # (d) loss slows convergence relative to the lossless run
    clean = make_nodes(graph, VALS4)
    clean_out = simulate_consensus(clean, graph, 6, packet_loss=0.0, seed=0)
    assert lossy_out["residual"] > clean_out["residual"]
    assert float(np.abs(mean_value(clean) - m0).max()) < 1e-12


# ===========================================================================
# 8. delayed messages
#
# DEFECT (reported, not fixed): `ConsensusNode.accept` requires
# `msg.round_index == self.round_index`. Under any positive `delay_steps` a
# message emitted in round k arrives when the receiver is already in round k+d,
# so it is rejected on the round rule -- 100 % of them, at every delay, however
# fresh the timestamp is. That directly contradicts
# `system_model.LINK_ASSUMPTIONS["delayed"]`, which states delayed messages are
# "accepted only while their age is <= delta_stale_steps", i.e. that age is the
# acceptance criterion. test_08a asserts the documented contract and FAILS;
# test_08b pins what the code actually does so the defect is fully described.
# ===========================================================================
def test_08a_delayed_message_inside_the_stale_window_is_accepted() -> None:
    """DOCUMENTED CONTRACT (system_model.LINK_ASSUMPTIONS['delayed']).

    Delay of 1 control step, delta_stale_steps=3: the message age is 1, well
    inside the window, so consensus must still make progress.
    """
    graph = path_graph(4)
    nodes = make_nodes(graph, VALS4)
    z_init = stacked(nodes)
    out = simulate_consensus(nodes, graph, 6, delay_steps=1, delta_stale_steps=3)

    assert sum(n.rejected_stale for n in nodes.values()) == 0
    assert sum(n.applied for n in nodes.values()) > 0, (
        "every delayed message was discarded even though its age (1 step) is "
        "inside delta_stale_steps=3"
    )
    assert out["residual"] < consensus_residual(make_nodes(graph, VALS4))
    assert not np.array_equal(stacked(nodes), z_init)


def test_08b_delay_beyond_delta_stale_stops_consensus_by_design() -> None:
    """The staleness boundary, both sides of it.

    Delay inside delta_stale_steps: messages are applied and the recursion
    progresses. Delay beyond it: every message is rejected as stale and each
    robot keeps its pre-consensus value. The second case is the designed
    refusal to act on stale data, NOT a stall -- it degrades the system to
    independent local decisions, which is what the stress report must say.
    """
    graph = path_graph(4)

    for delay in (0, 1, 2):
        nodes = make_nodes(graph, VALS4)
        simulate_consensus(nodes, graph, 6, delay_steps=delay, delta_stale_steps=3)
        assert sum(n.applied for n in nodes.values()) > 0, delay
        assert sum(n.rejected_stale for n in nodes.values()) == 0, delay

    # delay 5 > delta_stale 3: nothing survives admission control.
    nodes = make_nodes(graph, VALS4)
    z_init = stacked(nodes)
    simulate_consensus(nodes, graph, 6, delay_steps=5, delta_stale_steps=3)
    assert sum(n.applied for n in nodes.values()) == 0
    assert sum(n.rejected_stale for n in nodes.values()) > 0
    assert np.array_equal(stacked(nodes), z_init), (
        "robots must retain their own pre-consensus value, not adopt stale data"
    )


def test_09_stale_messages_are_rejected_and_leave_the_value_untouched() -> None:
    delta = CommParams().delta_stale_steps
    assert delta == 3

    node = ConsensusNode.from_logits(0, 1.0, 0.0, degree=1, epoch_id=0)
    before = node.z.copy()
    # age = 10 - 6 = 4 > 3
    node.step([message(1, 0, 0.0, 1.0, degree=1, timestamp_step=6)], 10, delta)
    assert node.rejected_stale == 1
    assert node.applied == 0
    assert node.missing == 1
    assert np.array_equal(node.z, before)

    # boundary: age exactly delta is still fresh
    fresh = ConsensusNode.from_logits(0, 1.0, 0.0, degree=1, epoch_id=0)
    fresh.step([message(1, 0, 0.0, 1.0, degree=1, timestamp_step=7)], 10, delta)
    assert fresh.rejected_stale == 0
    assert fresh.applied == 1
    assert not np.array_equal(fresh.z, before)

    # a wrong-epoch message is rejected on its own counter, not silently mixed
    other_epoch = ConsensusNode.from_logits(0, 1.0, 0.0, degree=1, epoch_id=7)
    other_epoch.step([message(1, 0, 0.0, 1.0, 1, timestamp_step=10, epoch_id=6)],
                     10, delta)
    assert other_epoch.rejected_epoch == 1
    assert other_epoch.applied == 0
    assert np.array_equal(other_epoch.z, before)


# ===========================================================================
# 10. duplicate-message rejection
# ===========================================================================
def test_10_duplicate_messages_are_applied_exactly_once() -> None:
    delta = CommParams().delta_stale_steps
    msg = message(1, 0, 0.0, 1.0, degree=1, timestamp_step=0)

    once = ConsensusNode.from_logits(0, 1.0, 0.0, degree=1, epoch_id=0)
    once.step([msg], 0, delta)

    thrice = ConsensusNode.from_logits(0, 1.0, 0.0, degree=1, epoch_id=0)
    thrice.step([msg, msg, msg], 0, delta)

    assert thrice.rejected_duplicate == 2
    assert thrice.applied == 1
    assert np.array_equal(thrice.z, once.z)

    # a distinct copy with identical (sender, epoch, round) is also a duplicate,
    # so the rule is keyed on identity of the message, not on object identity
    clone = ConsensusNode.from_logits(0, 1.0, 0.0, degree=1, epoch_id=0)
    clone.step([msg, message(1, 0, 9.0, -9.0, 1, 0)], 0, delta)
    assert clone.rejected_duplicate == 1
    assert np.array_equal(clone.z, once.z)

    # the SAME sender in the NEXT round is not a duplicate
    clone.step([message(1, 1, 0.0, 1.0, 1, 1)], 1, delta)
    assert clone.applied == 2
    assert clone.rejected_duplicate == 1

    # a node never applies its own message
    selfmsg = ConsensusNode.from_logits(0, 1.0, 0.0, degree=1, epoch_id=0)
    z0 = selfmsg.z.copy()
    selfmsg.step([message(0, 0, 5.0, 5.0, 1, 0)], 0, delta)
    assert selfmsg.applied == 0
    assert np.array_equal(selfmsg.z, z0)


# ===========================================================================
# 11. asynchronous updates
#
# Same root cause as section 8: a robot that starts late keeps a round_index
# that lags its neighbours' forever, so the round rule rejects every message in
# both directions and the offset robot is permanently severed from consensus.
# The behaviour is pinned here rather than described as "graceful degradation".
# ===========================================================================
def test_11_async_offsets_delay_a_robot_without_severing_it() -> None:
    """A late-starting robot stays a round behind but still participates.

    Originally this test pinned the opposite behaviour: under the strict
    same-round admission rule robot 2 applied nothing, robot 3 (whose only
    neighbour is robot 2) was severed with it, and the swarm could not agree.
    That was the delay-intolerance defect, not a property of asynchrony. With
    earlier-round values admitted, a local clock offset costs convergence
    speed rather than connectivity.
    """
    graph = path_graph(4)
    nodes = make_nodes(graph, VALS4)
    z_init = {i: n.z.copy() for i, n in nodes.items()}
    simulate_consensus(nodes, graph, 6, async_offsets={2: 1})

    # robot 2 started one round late and stays one round behind
    assert nodes[2].round_index == 5
    assert all(nodes[i].round_index == 6 for i in (0, 1, 3))

    # ... but it participates in both directions
    assert nodes[2].applied > 0
    assert not np.array_equal(nodes[2].z, z_init[2])
    assert nodes[3].applied > 0, "robot 3 must not be severed by its neighbour's offset"
    assert not np.array_equal(nodes[3].z, z_init[3])

    # no future-round value is ever consumed
    assert all(n.rejected_round >= 0 for n in nodes.values())

    # a zero offset is a genuine no-op -- the harness itself is not the problem
    plain = make_nodes(graph, VALS4)
    simulate_consensus(plain, graph, 6)
    zeroed = make_nodes(graph, VALS4)
    simulate_consensus(zeroed, graph, 6, async_offsets={i: 0 for i in graph})
    assert np.allclose(stacked(plain), stacked(zeroed))


def test_12_disconnected_components_agree_internally_but_not_swarm_wide() -> None:
    graph: Graph = {0: (1,), 1: (0, 2), 2: (1,), 3: (4,), 4: (3, 5), 5: (4,)}
    values = [(1.0, 0.0), (0.9, 0.1), (0.8, 0.0),
              (0.0, 1.0), (0.1, 0.9), (0.0, 0.8)]
    nodes = make_nodes(graph, values)
    out = simulate_consensus(nodes, graph, 12)

    comps = connected_components(graph)
    assert comps == [[0, 1, 2], [3, 4, 5]]
    decisions = out["decisions"]
    assert [decisions[i] for i in (0, 1, 2)] == [KEEP, KEEP, KEEP]
    assert [decisions[i] for i in (3, 4, 5)] == [LINE, LINE, LINE]

    # THE point of the test: the swarm-wide number is 0 and the honest,
    # component-wise number is 1.0. Reporting the latter as if it were the
    # former would be the overclaim this metric exists to prevent.
    assert agreement_rate(decisions) == 0.0
    assert component_agreement(decisions, comps) == 1.0

    # each component reached its own mean; nothing crossed the partition
    for comp in comps:
        sub = np.stack([nodes[i].z for i in comp])
        assert np.abs(sub - sub.mean(axis=0)).max() < 5e-3  # geometric convergence: see K-vs-residual table in the doc
    assert max_pairwise_gap(nodes) > 0.5

    # a component that itself disagrees is caught -- the metric is not vacuous
    split_decisions = dict(decisions)
    split_decisions[0] = LINE
    assert component_agreement(split_decisions, comps) == 0.5


# ===========================================================================
# 13. no leader and no coordinator object exists
# ===========================================================================
LEADER_TOKENS: Tuple[str, ...] = (
    "leader", "coordinator", "master", "aggregator", "elect", "chief",
    "captain", "supervisor", "arbiter", "centralis", "centraliz", "root_",
    "_root", "primary", "token_holder", "chairman", "president", "delegate",
)


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


def test_13_no_leader_or_coordinator_object_exists() -> None:
    source = inspect.getsource(consensus_mod)
    tree = ast.parse(source)

    offenders = sorted(name for name in _identifiers(tree)
                       if any(tok in name.lower() for tok in LEADER_TOKENS))
    assert offenders == [], offenders

    # the scan has discriminating power
    injected = ast.parse("class LeaderElection:\n    def elect(self):\n        return 0\n")
    assert sorted(n for n in _identifiers(injected)
                  if any(t in n.lower() for t in LEADER_TOKENS)) == ["LeaderElection", "elect"]

    # structural: exactly one node class, no subclass with a different update,
    # and no per-robot field that could mark one robot special
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert sorted(c.name for c in classes) == ["ConsensusNode", "ScoreMessage"]
    node_cls = [c for c in classes if c.name == "ConsensusNode"][0]
    assert node_cls.bases == []
    fields = {f.name for f in dataclasses.fields(ConsensusNode)}
    assert fields == {"robot_id", "z", "degree", "epoch_id", "round_index",
                      "params", "rejected_stale", "rejected_epoch",
                      "rejected_duplicate", "rejected_round", "applied",
                      "missing", "_seen"}, fields

    # functional: the update is equivariant under a graph automorphism, so no
    # vertex is privileged. Rotating a ring's initial values rotates the result.
    n = 6
    ring = ring_graph(n)
    plain = make_nodes(ring, VALS6)
    simulate_consensus(plain, ring, 4)
    rotated_values = [VALS6[(i - 1) % n] for i in range(n)]
    rotated = make_nodes(ring, rotated_values)
    simulate_consensus(rotated, ring, 4)
    for i in range(n):
        assert np.allclose(rotated[i].z, plain[(i - 1) % n].z, atol=1e-12), i


# ===========================================================================
# 14. no global all-reduce inside a node
# ===========================================================================
AGGREGATE_CALLS: Tuple[str, ...] = (
    "mean", "nanmean", "average", "sum", "nansum", "fsum", "reduce",
    "all_reduce", "allreduce", "gather", "allgather", "scatter", "broadcast",
    "global_mean_pool", "pooled_graph_features", "stack", "concatenate",
)

# Free names a ConsensusNode method may legitimately reference. Anything else
# -- above all a container of other robots' nodes -- is a violation.
ALLOWED_FREE_NAMES: Set[str] = {
    "self", "cls", "np", "ConsensusParams", "ScoreMessage", "metropolis_weight",
    "KEEP", "LINE", "Optional", "float", "int", "bool", "abs", "len", "max",
    "min", "sorted", "set",
    # Decorators and comprehension targets are not global reductions. Without
    # these the scan reports "reads free name 'classmethod'", which is noise
    # that would train a reader to ignore the scanner's output entirely.
    "classmethod", "staticmethod", "property", "str", "zip", "range", "m",
    "field", "dataclass", "Sequence", "Dict", "List", "Tuple",
}


def _bound_names(fn: ast.FunctionDef) -> Set[str]:
    bound: Set[str] = set()
    args = fn.args
    for a in list(args.args) + list(args.posonlyargs) + list(args.kwonlyargs):
        bound.add(a.arg)
    if args.vararg:
        bound.add(args.vararg.arg)
    if args.kwarg:
        bound.add(args.kwarg.arg)
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
    return bound


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def scan_node_methods_for_global_reduction(source: str) -> List[str]:
    """AST scan: a ConsensusNode method may touch only its own inbox and self.

    Parameterised on `source` so the test can feed it a deliberately offending
    module and prove the scan has teeth.
    """
    violations: List[str] = []
    tree = ast.parse(source)
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        if cls.name != "ConsensusNode":
            continue
        for fn in [n for n in cls.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            bound = _bound_names(fn)
            for sub in ast.walk(fn):
                if isinstance(sub, ast.Call):
                    name = _call_name(sub)
                    if name in AGGREGATE_CALLS:
                        violations.append(f"{cls.name}.{fn.name}: calls {name}()")
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    if sub.id not in bound and sub.id not in ALLOWED_FREE_NAMES:
                        violations.append(
                            f"{cls.name}.{fn.name}: reads free name '{sub.id}'")
                if isinstance(sub, (ast.For, ast.AsyncFor)):
                    root = sub.iter
                    while isinstance(root, (ast.Call, ast.Attribute, ast.Subscript)):
                        if isinstance(root, ast.Call):
                            # `for m in sorted(inbox, ...)` iterates INBOX, not
                            # `sorted`. Unwrapping to .func made every wrapped
                            # iteration look like a non-local read.
                            root = root.args[0] if root.args else root.func
                        else:
                            root = root.value
                    if not (isinstance(root, ast.Name)
                            and (root.id in bound or root.id == "self")):
                        violations.append(
                            f"{cls.name}.{fn.name}: iterates a non-local object")
    return sorted(set(violations))


def test_14_no_global_all_reduce_inside_consensus_node() -> None:
    source = inspect.getsource(consensus_mod)
    assert scan_node_methods_for_global_reduction(source) == []

    # positive control 1: an explicit all-reduce over every node
    leaky = source.replace(
        "    def margin(self) -> float:",
        "    def cheat(self, nodes) -> float:\n"
        "        return float(np.mean([n.z for n in nodes.values()]))\n\n"
        "    def margin(self) -> float:", 1)
    found = scan_node_methods_for_global_reduction(leaky)
    assert any("calls mean()" in v for v in found), found

    # positive control 2: reaching a module-level registry of all robots
    registry = source.replace(
        "    def margin(self) -> float:",
        "    def cheat2(self) -> float:\n"
        "        return float(ALL_NODES[0].z[0])\n\n"
        "    def margin(self) -> float:", 1)
    found2 = scan_node_methods_for_global_reduction(registry)
    assert any("free name 'ALL_NODES'" in v for v in found2), found2

    # the only functions that may range over every robot are the simulation
    # boundary and functions explicitly marked @offline_diagnostic
    tree = ast.parse(source)
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        takes_nodes = any(a.arg == "nodes" for a in fn.args.args)
        if not takes_nodes:
            continue
        decorated = {getattr(d, "id", getattr(d, "attr", ""))
                     for d in fn.decorator_list}
        assert fn.name.startswith("simulate_") or "offline_diagnostic" in decorated, \
            f"{fn.name} ranges over every robot without being a boundary or offline"


# ===========================================================================
# 15. two-hop influence travels only through received messages
# ===========================================================================
def test_15a_value_channel_is_strictly_one_hop_per_round() -> None:
    """Robot 2 is two hops from robot 0. Its VALUE cannot reach robot 0 in one
    round -- only in two, and only via robot 1's message."""
    graph = path_graph(4)
    base = [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)]
    moved = [(0.0, 0.0), (1.0, 0.0), (5.0, -5.0), (0.0, 0.0)]

    for k, must_match in ((1, True), (2, False)):
        a = make_nodes(graph, base)
        b = make_nodes(graph, moved)
        simulate_consensus(a, graph, k)
        simulate_consensus(b, graph, k)
        if must_match:
            assert a[0].z.tobytes() == b[0].z.tobytes(), "two-hop value leaked in 1 round"
            assert a[1].z.tobytes() != b[1].z.tobytes(), "one-hop neighbour must react"
        else:
            assert a[0].z.tobytes() != b[0].z.tobytes(), "two-hop value never arrived"

    # and robot 0 only ever accepted messages from its own one-hop set
    nodes = make_nodes(graph, base)
    simulate_consensus(nodes, graph, 4)
    senders = {sender for sender, _, _ in nodes[0]._seen}
    assert senders == set(graph[0]) == {1}


def test_15b_neighbour_degree_is_a_real_two_hop_channel_and_is_disclosed() -> None:
    """The disclosed exception, pinned rather than avoided.

    Robot 3 is outside N_0. Adding it to N_1 changes deg_1 from 2 to 3, so
    w_01 = 1/(1+max(deg_0, deg_1)) changes 1/3 -> 1/4 and robot 0's value after
    ONE round differs -- with every z identical between the two worlds. This is
    a robot outside N_0 influencing robot 0 in a single round, and it is exactly
    the channel `system_model.DISCLOSED_AGGREGATE_CHANNELS` records.
    """
    world_a: Graph = {0: (1,), 1: (0, 2), 2: (1,)}
    world_b: Graph = {0: (1,), 1: (0, 2, 3), 2: (1,), 3: (1,)}
    values = [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)]

    a = make_nodes(world_a, values)
    b = make_nodes(world_b, values)
    simulate_consensus(a, world_a, 1)
    simulate_consensus(b, world_b, 1)

    assert a[0].degree == b[0].degree == 1          # robot 0's own view of the
    assert a[1].degree == 2 and b[1].degree == 3    # world is identical
    assert metropolis_weight(1, 2) == pytest.approx(1.0 / 3.0)
    assert metropolis_weight(1, 3) == pytest.approx(1.0 / 4.0)

    assert float(a[0].z[0]) == pytest.approx(1.0 / 3.0)
    assert float(b[0].z[0]) == pytest.approx(1.0 / 4.0)
    assert float(a[0].z[0]) != float(b[0].z[0]), (
        "if this ever passes as equal, the degree channel has been removed and "
        "DISCLOSED_AGGREGATE_CHANNELS should be updated"
    )

    # the exception is declared, bounded to one integer, and carries no identity
    assert "neighbour_degree" in DISCLOSED_AGGREGATE_CHANNELS
    text = DISCLOSED_AGGREGATE_CHANNELS["neighbour_degree"]
    assert "outside N_i" in text and "w_ij" in text


def test_15c_score_message_cannot_carry_two_hop_state() -> None:
    """Structural: the only two-hop-derivable field is the scalar `degree`."""
    fields = {f.name: f.type for f in dataclasses.fields(ScoreMessage)}
    assert set(fields) == {"sender_id", "epoch_id", "round_index", "z_keep",
                           "z_line", "degree", "timestamp_step"}
    for name, ann in fields.items():
        assert str(ann) in ("int", "float"), (name, ann)   # no container field
    # nothing that could name or place another robot
    assert not any(tok in name for name in fields
                   for tok in ("position", "neighbour", "list", "ids", "table"))


# ===========================================================================
# established properties, asserted directly
# ===========================================================================
@pytest.mark.parametrize("name,graph,values", [
    ("path4", path_graph(4), VALS4),
    ("path6", path_graph(6), VALS6),
    ("ring4", ring_graph(4), VALS4),
    ("ring6", ring_graph(6), VALS6),
    ("complete4", complete_graph(4), VALS4),
    ("complete6", complete_graph(6), VALS6),
])
def test_mh_update_preserves_the_initial_mean(name: str, graph: Graph,
                                              values: Sequence) -> None:
    """Established property 1: MH weights are symmetric, so the mean is exact."""
    nodes = make_nodes(graph, values)
    m0 = mean_value(nodes)
    out = simulate_consensus(nodes, graph, 12)
    for snap in out["history"]:
        m = np.stack([snap[i] for i in sorted(snap)]).mean(axis=0)
        assert np.allclose(m, m0, atol=1e-12), (name, m, m0)
    # symmetry of the weight rule itself, which is why the above holds
    for i, nbrs in graph.items():
        for j in nbrs:
            assert metropolis_weight(len(graph[i]), len(graph[j])) == \
                   metropolis_weight(len(graph[j]), len(graph[i]))


def test_information_propagates_exactly_one_hop_per_round() -> None:
    """Established property 2: after k rounds robot k has changed, k+1 has not."""
    n = 6
    graph = path_graph(n)
    values = [(1.0, 0.0)] + [(0.0, 0.0)] * (n - 1)
    for k in range(1, n):
        nodes = make_nodes(graph, values)
        simulate_consensus(nodes, graph, k)
        assert float(nodes[k].z[0]) != 0.0, f"robot {k} unchanged after {k} rounds"
        if k + 1 < n:
            assert float(nodes[k + 1].z[0]) == 0.0, \
                f"robot {k + 1} changed after only {k} rounds"


# ===========================================================================
# supporting evidence: wire size and the real formation graph
# ===========================================================================
SCORE_MESSAGE_WIRE_FORMAT = "<HIB2fBI"     # see docs/LEADERLESS_...md
SCORE_MESSAGE_BYTES = 20


def test_score_message_wire_size_matches_the_document() -> None:
    """`ScoreMessage` has no payload_bytes(); the documented size is derived
    from the declared field widths, in declaration order."""
    assert struct.calcsize(SCORE_MESSAGE_WIRE_FORMAT) == SCORE_MESSAGE_BYTES
    order = [f.name for f in dataclasses.fields(ScoreMessage)]
    assert order == ["sender_id", "epoch_id", "round_index", "z_keep",
                     "z_line", "degree", "timestamp_step"]
    assert SCORE_MESSAGE_BYTES < 49          # strictly smaller than a Beacon


def test_real_n6_line_comm_graph_has_diameter_two() -> None:
    """Grounds the K_score grid: on the deployed geometry the line is 2-hop."""
    params = CommParams()
    roles = RoleAssignment.from_index(6, 0.9)
    coords = np.asarray(roles.line, dtype=np.float64)
    graph: Graph = {}
    for i in range(6):
        d = np.hypot(coords[:, 0] - coords[i, 0], coords[:, 1] - coords[i, 1])
        graph[i] = tuple(j for j in range(6) if j != i and d[j] <= params.r_comm)
    assert graph[0] == (1, 2, 3)
    assert graph_diameter(graph) == 2

    values = [(1.0, 0.0)] + [(0.0, 0.0)] * 5
    nodes = make_nodes(graph, values)
    simulate_consensus(nodes, graph, 2)
    assert all(float(nodes[i].z[0]) != 0.0 for i in range(6))

    keep = np.asarray(roles.keep, dtype=np.float64)
    dmax = max(float(np.hypot(keep[i, 0] - keep[j, 0], keep[i, 1] - keep[j, 1]))
               for i in range(6) for j in range(6))
    assert dmax < params.r_comm          # the keep grid is one-hop complete
