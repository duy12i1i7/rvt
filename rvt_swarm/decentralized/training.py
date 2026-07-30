"""Centralized training, strictly decentralized inputs (Task 9).

What centralized training is allowed to mean here, and nothing more:

  - the simulator generates team-level Recovery Event V2 labels y_tau;
  - offline evaluation may use the full state;
  - a minibatch may contain ego graphs drawn from every robot.

What it must NOT mean: the model input is never global. Each sample is a set of
N independent ego graphs, one per robot, built through the same
`simulate_broadcast_round` boundary the runtime uses, with the same r_comm
gate. There is no global graph anywhere in the pipeline, so there is no
train/deploy mismatch to argue about.

Consensus in the loss
---------------------
The loss is applied to POST-consensus logits, and the consensus simulated in
training is the same Metropolis-Hastings recursion the runtime executes, on the
same message topology. It is written as a matrix power here purely so gradients
flow:

    z^(k+1) = P z^(k),    P_ij = w_ij (j in N_i),   P_ii = 1 - sum_j w_ij

`assert_matches_runtime_consensus()` checks this against the runtime's
message-passing implementation numerically, so the equivalence is verified
rather than asserted. It holds for the NOMINAL link condition only -- lossless,
zero delay, synchronous. Under loss or delay the runtime and this matrix differ,
which is exactly why the stress test evaluates the runtime path and not this one.

A global average is NOT substituted for the distributed recursion; with
K_score=0, P is the identity and the loss falls back to purely local logits,
which is the K=0 reference arm.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from ..config import Config
from ..controllers import expert_action
from ..environment import SwarmFormationEnv
from ..layouts import build_layouts
from ..splits import TRAIN, VALIDATION, setting_episode_seeds
from .comms import RadioChannel, make_radio_states, simulate_broadcast_round
from .ego_graph import build_ego_graph
from .consensus import metropolis_weight
from .roles import RoleAssignment
from .system_model import KEEP, LINE, MODES, CommParams, ConsensusParams

PILOT_FAMILIES = ["line_corridor", "keep_line_keep", "keep_open", "ambiguous"]
TEAM_SIZES = [4, 6]
STATE_STRIDE = 12
EPISODES = {"train": 3, "val": 2}


# ---------------------------------------------------------------------------
# Differentiable consensus, identical recursion to the runtime
# ---------------------------------------------------------------------------
def consensus_matrix(adj: Sequence[Sequence[int]]) -> torch.Tensor:
    """P for one team's communication graph. Rows sum to 1 by construction."""
    n = len(adj)
    deg = [len(a) for a in adj]
    P = torch.zeros((n, n), dtype=torch.float32)
    for i in range(n):
        for j in adj[i]:
            P[i, j] = metropolis_weight(deg[i], deg[j])
        P[i, i] = 1.0 - float(P[i].sum())
    return P


def apply_consensus(q: torch.Tensor, P: torch.Tensor, k: int) -> torch.Tensor:
    """z^(K) = P^K q. q is (N, 2); returns (N, 2). k=0 is the identity."""
    z = q
    for _ in range(int(k)):
        z = P @ z
    return z


def assert_matches_runtime_consensus(seed: int = 0, tol: float = 1e-6) -> float:
    """Verify the training recursion equals the runtime's message passing.

    Returns the max absolute discrepancy. Raises if it exceeds `tol`.
    """
    from .consensus import ConsensusNode, simulate_consensus

    rng = np.random.default_rng(seed)
    worst = 0.0
    for n in (4, 6):
        for topology in ("path", "ring", "complete"):
            if topology == "path":
                adj = [[j for j in (i - 1, i + 1) if 0 <= j < n] for i in range(n)]
            elif topology == "ring":
                adj = [[(i - 1) % n, (i + 1) % n] for i in range(n)]
            else:
                adj = [[j for j in range(n) if j != i] for i in range(n)]
            q = rng.normal(size=(n, 2))
            for k in (0, 1, 2, 4, 6):
                nodes = {i: ConsensusNode.from_logits(i, q[i, 0], q[i, 1], len(adj[i]), 0)
                         for i in range(n)}
                simulate_consensus(nodes, {i: adj[i] for i in range(n)}, k,
                                   record_history=False)
                runtime = np.stack([nodes[i].z for i in range(n)])
                trained = apply_consensus(torch.tensor(q, dtype=torch.float64),
                                          consensus_matrix(adj).double(), k).numpy()
                worst = max(worst, float(np.abs(runtime - trained).max()))
    if worst > tol:
        raise AssertionError(
            f"training consensus diverges from the runtime recursion by {worst:.3e}; "
            "the model would be trained on a recursion it does not execute"
        )
    return worst


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
@dataclass
class TeamSample:
    """One labelled state: N ego graphs per mode, plus the team label."""

    ego: Dict[int, Dict[str, torch.Tensor]]   # mode -> batched ego graphs (N graphs)
    adj: List[List[int]]
    label: torch.Tensor                        # (2,) [y_keep, y_line]
    state_id: str
    family: str
    n: int
    split: str

    @property
    def P(self) -> torch.Tensor:
        if not hasattr(self, "_P"):
            object.__setattr__(self, "_P", consensus_matrix(self.adj))
        return self._P


def batch_ego(graphs: Sequence[object]) -> Dict[str, torch.Tensor]:
    """Batch per-robot EgoGraphs into one disjoint-union graph.

    Disjoint union, so no message can cross between robots' ego graphs. That
    is the structural guarantee that batching does not create a global graph.
    """
    node_x, edge_index, edge_attr, centers = [], [], [], []
    offset = 0
    for g in graphs:
        node_x.append(g.node_x)
        edge_index.append(g.edge_index + offset)
        edge_attr.append(g.edge_attr)
        centers.append(offset + g.center_index)
        offset += g.n_nodes
    return {
        "node_x": torch.cat(node_x, 0),
        "edge_index": torch.cat(edge_index, 1),
        "edge_attr": torch.cat(edge_attr, 0),
        "center_index": torch.tensor(centers, dtype=torch.long),
    }


def simulate_build_team_dataset(
    cfg: Config, split: str, labels: Dict[str, Dict[str, float]],
    comm: Optional[CommParams] = None,
) -> List[TeamSample]:
    """BOUNDARY: replays labelled episodes and emits per-robot ego graphs.

    Reads the simulator's joint state, which is why it carries the boundary
    prefix. Everything it returns is strictly per-robot.
    """
    comm = comm or CommParams()
    split_key = TRAIN if split == "train" else VALIDATION
    out: List[TeamSample] = []
    for lay in [l for l in build_layouts(split) if l.family in PILOT_FAMILIES]:
        for n in TEAM_SIZES:
            for seed in setting_episode_seeds(split_key, 0, n, EPISODES[split], 0):
                env = SwarmFormationEnv(cfg)
                obs = env.reset(n, "cluttered", seed=seed, layout=lay)
                mission = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
                roles = RoleAssignment.simulate_mission_setup_from_initial_formation(
                    obs["positions"], mission, cfg.env.nominal_spacing)
                states = make_radio_states(range(n), comm)
                channel = RadioChannel(comm, seed=int(seed))
                done, step = False, 0
                while not done:
                    if step % STATE_STRIDE == 0:
                        sid = f"{lay.layout_id}|{n}|{seed}|{step}"
                        lab = labels.get(sid)
                        if lab is not None and {"keep", "line"} <= set(lab):
                            views = simulate_broadcast_round(
                                step, obs["positions"], obs["velocities"], roles,
                                [KEEP] * n, [0] * n, [step] * n, states, channel,
                                obs["obstacles"], cfg.env.obstacle_radius,
                                (float(obs["goal"][0]), float(obs["goal"][1])),
                                mission, comm)
                            adj = [list(views[i].neighbour_ids()) for i in range(n)]
                            ego = {m: batch_ego([build_ego_graph(views[i], cfg, m)
                                                 for i in range(n)]) for m in MODES}
                            out.append(TeamSample(
                                ego=ego, adj=adj,
                                label=torch.tensor([lab["keep"], lab["line"]],
                                                   dtype=torch.float32),
                                state_id=sid, family=lay.family, n=n, split=split))
                    obs, _, done, _ = env.step(expert_action(obs, cfg, KEEP), KEEP)
                    step += 1
    return out


# ---------------------------------------------------------------------------
# Losses
# ---------------------------------------------------------------------------
def recovery_loss(z: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """L = 1/(2N) sum_i sum_tau BCE(sigmoid(z_i,tau), y_tau).

    Every robot is trained toward the TEAM label for each mode: the outcome
    being predicted is a property of the team, and each robot must predict it
    from its own local view. That is the supervision signal, and the gap
    between robots' predictions is a measured quantity, not a modelling error.
    """
    return F.binary_cross_entropy_with_logits(z, y.expand_as(z))


def decisive_classification_loss(z: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Cross-entropy over {keep, line}, MASKED to decisive states.

    keep_only -> keep, line_only -> line. both_succeed and both_fail contribute
    exactly zero: supplying an arbitrary tie-break target on non-decisive states
    is what taught the previous classifier the majority class. A batch with no
    decisive state returns exactly zero, with no NaN.
    """
    keep_only = bool(y[0] > 0.5 and y[1] <= 0.5)
    line_only = bool(y[0] <= 0.5 and y[1] > 0.5)
    if not (keep_only or line_only):
        return z.sum() * 0.0
    target = torch.zeros(z.shape[0], dtype=torch.long) if keep_only else \
        torch.ones(z.shape[0], dtype=torch.long)
    return F.cross_entropy(z, target)


def classify_team_label(y: Sequence[float]) -> str:
    keep, line = float(y[0]) > 0.5, float(y[1]) > 0.5
    if keep and not line:
        return "keep_only"
    if line and not keep:
        return "line_only"
    return "both_succeed" if keep else "both_fail"
