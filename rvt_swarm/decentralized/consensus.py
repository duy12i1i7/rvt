"""Leaderless finite-round peer-to-peer consensus over keep/line scores.

Every robot runs the identical update

    z_i^(k+1) = z_i^(k) + sum_{j in N_i} w_ij [ z_j^(k) - z_i^(k) ]

with Metropolis-Hastings weights w_ij = 1 / (1 + max(deg_i, deg_j)). There is no
leader, no aggregator, no all-reduce, and no object that holds every robot's
value with authority: `simulate_consensus` is a scheduler that ticks each
`ConsensusNode` in turn, and each node touches only messages addressed to it.

Why Metropolis-Hastings: the weights need only deg_i and deg_j, and deg_j
arrives in the neighbour's own message, so no robot ever needs graph-wide
degree information. The weights are symmetric (max is symmetric), so on a
connected symmetric graph the update is average-preserving and converges to the
mean of the initial values -- a property the tests check directly rather than
assume.

Self-weight w_ii = 1 - sum_j w_ij is automatically in (0, 1] because
sum_j w_ij <= deg_i / (1 + deg_i) < 1, so the update is a proper convex
combination and cannot diverge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .guards import offline_diagnostic
from .system_model import KEEP, LINE, MODES, ConsensusParams

# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScoreMessage:
    """The only payload exchanged during score consensus.

    Deliberately minimal: no ego graph, no raw robot state, no obstacle data.
    A two-hop robot can influence robot i only by changing a one-hop
    neighbour's `z`, never by reaching robot i directly.
    """

    sender_id: int
    epoch_id: int
    round_index: int
    z_keep: float
    z_line: float
    degree: int
    timestamp_step: int

    def value(self) -> np.ndarray:
        return np.array([self.z_keep, self.z_line], dtype=np.float64)


def metropolis_weight(deg_i: int, deg_j: int) -> float:
    """w_ij = 1 / (1 + max(deg_i, deg_j)). Symmetric by construction."""
    return 1.0 / (1.0 + max(int(deg_i), int(deg_j)))


# ---------------------------------------------------------------------------
# Per-robot consensus node
# ---------------------------------------------------------------------------
@dataclass
class ConsensusNode:
    """Robot i's consensus state. Holds only robot i's own values.

    `degree` is robot i's own one-hop degree, known from its neighbour table.
    """

    robot_id: int
    z: np.ndarray                       # (2,) [keep, line]
    degree: int
    epoch_id: int
    round_index: int = 0
    params: ConsensusParams = field(default_factory=ConsensusParams)
    # diagnostics
    rejected_stale: int = 0
    rejected_epoch: int = 0
    rejected_duplicate: int = 0
    rejected_round: int = 0
    applied: int = 0
    missing: int = 0
    _seen: set = field(default_factory=set)

    @classmethod
    def from_logits(cls, robot_id: int, q_keep: float, q_line: float,
                    degree: int, epoch_id: int,
                    params: Optional[ConsensusParams] = None) -> "ConsensusNode":
        """z_i^(0) = q_i, the robot's own pre-consensus ego-graph logits."""
        return cls(robot_id=robot_id,
                   z=np.array([float(q_keep), float(q_line)], dtype=np.float64),
                   degree=int(degree), epoch_id=int(epoch_id),
                   params=params or ConsensusParams())

    def outgoing(self, now_step: int) -> ScoreMessage:
        return ScoreMessage(self.robot_id, self.epoch_id, self.round_index,
                            float(self.z[0]), float(self.z[1]),
                            self.degree, now_step)

    def accept(self, msg: ScoreMessage, now_step: int, delta_stale_steps: int) -> bool:
        """Admission control. Rejection is silent and lossless: the round simply
        applies fewer neighbour terms, which leaves z_i unchanged by that
        neighbour. A missing update is never replaced with future information.
        """
        if msg.sender_id == self.robot_id:
            return False
        if msg.epoch_id != self.epoch_id:
            self.rejected_epoch += 1
            return False
        if now_step - msg.timestamp_step > delta_stale_steps:
            self.rejected_stale += 1
            return False
        if msg.round_index != self.round_index:
            # Only same-round values may be mixed; an off-round value would
            # blend iterates from different points of the recursion.
            self.rejected_round += 1
            return False
        key = (msg.sender_id, msg.epoch_id, msg.round_index)
        if key in self._seen:
            self.rejected_duplicate += 1
            return False
        self._seen.add(key)
        return True

    def step(self, inbox: Sequence[ScoreMessage], now_step: int,
             delta_stale_steps: int) -> np.ndarray:
        """One consensus round using only messages delivered to robot i."""
        delta = np.zeros(2, dtype=np.float64)
        n_applied = 0
        for msg in sorted(inbox, key=lambda m: m.sender_id):   # deterministic order
            if not self.accept(msg, now_step, delta_stale_steps):
                continue
            w = metropolis_weight(self.degree, msg.degree)
            delta += w * (msg.value() - self.z)
            n_applied += 1
        self.missing += max(0, self.degree - n_applied)
        self.applied += n_applied
        self.z = self.z + delta
        self.round_index += 1
        return self.z

    def decide(self) -> int:
        """tau_i = argmax_tau z_i,tau, with deterministic tie-breaking.

        Ties resolve to KEEP -- the conservative choice, since keep is the
        default committed mode and a tie carries no evidence for switching.
        Recorded explicitly because an undeclared tie rule was the exact defect
        that produced the degenerate top-1 metric in the previous pilot.
        """
        return LINE if self.z[1] > self.z[0] else KEEP

    def margin(self) -> float:
        return float(abs(self.z[1] - self.z[0]))


# ---------------------------------------------------------------------------
# Simulation harness (NOT deployable -- it is the scheduler + radio)
# ---------------------------------------------------------------------------
def simulate_consensus(
    nodes: Dict[int, ConsensusNode],
    neighbours_of: Dict[int, Sequence[int]],
    k_rounds: int,
    *,
    start_step: int = 0,
    delta_stale_steps: int = 3,
    packet_loss: float = 0.0,
    delay_steps: int = 0,
    seed: int = 0,
    async_offsets: Optional[Dict[int, int]] = None,
    record_history: bool = True,
) -> Dict[str, object]:
    """Run k_rounds of leaderless consensus. Simulation boundary.

    This function schedules and delivers; it never computes a value on behalf of
    a robot. Every value change happens inside `ConsensusNode.step`, which sees
    only that robot's inbox.
    """
    rng = np.random.default_rng(seed)
    history: List[Dict[int, np.ndarray]] = []
    pending: List[Tuple[int, int, ScoreMessage]] = []   # (deliver_step, dst, msg)
    offsets = async_offsets or {}

    if record_history:
        history.append({i: n.z.copy() for i, n in nodes.items()})

    for k in range(k_rounds):
        now = start_step + k
        # -- every robot broadcasts its own current value to its one-hop set --
        for i, node in nodes.items():
            if offsets.get(i, 0) > k:
                continue                      # this robot has not started yet
            msg = node.outgoing(now)
            for j in neighbours_of.get(i, ()):
                if packet_loss > 0.0 and rng.random() < packet_loss:
                    continue                  # dropped; never resent from the future
                pending.append((now + delay_steps, j, msg))

        # -- deliver what has arrived by now --
        inboxes: Dict[int, List[ScoreMessage]] = {i: [] for i in nodes}
        still: List[Tuple[int, int, ScoreMessage]] = []
        for deliver_step, dst, msg in pending:
            if deliver_step <= now and dst in inboxes:
                inboxes[dst].append(msg)
            else:
                still.append((deliver_step, dst, msg))
        pending = still

        for i, node in nodes.items():
            if offsets.get(i, 0) > k:
                continue
            node.step(inboxes[i], now, delta_stale_steps)

        if record_history:
            history.append({i: n.z.copy() for i, n in nodes.items()})

    return {
        "nodes": nodes,
        "history": history,
        "decisions": {i: n.decide() for i, n in nodes.items()},
        "residual": consensus_residual(nodes),
        "max_pairwise_gap": max_pairwise_gap(nodes),
        "rounds": k_rounds,
    }


# ---------------------------------------------------------------------------
# Diagnostics (offline analysis only)
# ---------------------------------------------------------------------------
@offline_diagnostic
def connected_components(neighbours_of: Dict[int, Sequence[int]]) -> List[List[int]]:
    """Offline diagnostic. No robot computes this; it exists so the report can
    state agreement per component instead of overclaiming swarm-wide agreement.
    """
    seen: set = set()
    out: List[List[int]] = []
    for start in sorted(neighbours_of):
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in neighbours_of.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        out.append(sorted(comp))
    return out


@offline_diagnostic
def consensus_residual(nodes: Dict[int, ConsensusNode]) -> float:
    """Max deviation of any robot's value from the mean value. 0 == agreement."""
    if not nodes:
        return 0.0
    Z = np.stack([n.z for n in nodes.values()])
    return float(np.abs(Z - Z.mean(axis=0)).max())


@offline_diagnostic
def max_pairwise_gap(nodes: Dict[int, ConsensusNode]) -> float:
    if len(nodes) < 2:
        return 0.0
    Z = np.stack([n.z for n in nodes.values()])
    return float((Z.max(axis=0) - Z.min(axis=0)).max())


@offline_diagnostic
def agreement_rate(decisions: Dict[int, int]) -> float:
    """1.0 iff every robot committed to the same mode."""
    return 1.0 if len(set(decisions.values())) <= 1 else 0.0


@offline_diagnostic
def component_agreement(decisions: Dict[int, int],
                        components: Sequence[Sequence[int]]) -> float:
    """Mean over components of whether that component agreed internally.

    This is the honest metric when G_c is disconnected: robots that cannot
    communicate are not expected to agree, and counting them as a failure of
    the consensus algorithm would misattribute a connectivity fact.
    """
    if not components:
        return 1.0
    ok = [1.0 if len({decisions[i] for i in comp if i in decisions}) <= 1 else 0.0
          for comp in components]
    return float(np.mean(ok)) if ok else 1.0
