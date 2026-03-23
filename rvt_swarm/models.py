from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .dataset import EDGE_DIM, NODE_DIM
from .config import TOPOLOGY_ACTIONS
from .utils import uncertainty_adjusted_scores


def _edge_softmax(logits: torch.Tensor, dst: torch.Tensor, n_nodes: int) -> torch.Tensor:
    """Per-destination softmax for graph attention (no torch-geometric dep)."""
    # Numerically-stable: subtract per-group max (detached — only for stability)
    with torch.no_grad():
        group_max = torch.full((n_nodes,), float("-inf"), device=logits.device, dtype=logits.dtype)
        group_max.scatter_reduce_(0, dst, logits, reduce="amax", include_self=False)
    shifted = (logits - group_max[dst]).exp()
    denom = shifted.new_zeros(n_nodes).index_add_(0, dst, shifted)
    return shifted / denom[dst].clamp_min(1e-8)


class GraphLayer(nn.Module):
    """Graph attention layer — attention-weighted message passing."""

    def __init__(self, hidden_dim: int):
        super().__init__()
        self.edge_mlp = nn.Sequential(
            nn.Linear(hidden_dim * 2 + EDGE_DIM, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        # Attention scoring: learned scalar weight per edge message
        self.attn_fc = nn.Sequential(
            nn.Linear(hidden_dim, 1, bias=False),
        )
        self.node_mlp = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor, edge_attr: torch.Tensor) -> torch.Tensor:
        src, dst = edge_index
        m = self.edge_mlp(torch.cat([h[src], h[dst], edge_attr], dim=-1))
        # Attention-weighted aggregation (graph-transformer style)
        alpha = _edge_softmax(
            F.leaky_relu(self.attn_fc(m).squeeze(-1), 0.2),
            dst, h.shape[0],
        )
        m = m * alpha.unsqueeze(-1)
        agg = torch.zeros_like(h)
        agg.index_add_(0, dst, m)
        return h + self.node_mlp(torch.cat([h, agg], dim=-1))


class GraphBackbone(nn.Module):
    def __init__(self, hidden_dim: int = 128, passes: int = 3):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(NODE_DIM, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, hidden_dim))
        self.layers = nn.ModuleList([GraphLayer(hidden_dim) for _ in range(passes)])

    def forward(self, node_x: torch.Tensor, edge_index: torch.Tensor, edge_attr: torch.Tensor) -> torch.Tensor:
        h = self.enc(node_x)
        for layer in self.layers:
            h = layer(h, edge_index, edge_attr)
        return h


def pooled_graph_features(h: torch.Tensor, batch_index: torch.Tensor) -> torch.Tensor:
    num_graphs = int(batch_index.max().item()) + 1 if batch_index.numel() else 1
    pooled = torch.zeros((num_graphs, h.shape[-1]), device=h.device, dtype=h.dtype)
    counts = torch.zeros((num_graphs, 1), device=h.device, dtype=h.dtype)
    pooled.index_add_(0, batch_index, h)
    counts.index_add_(0, batch_index, torch.ones((h.shape[0], 1), device=h.device, dtype=h.dtype))
    return pooled / counts.clamp_min(1.0)


class TopologyConsensus(nn.Module):
    """Neighbourhood-agreement layer for topological actions.

    Each node first casts a per-node topology vote, then votes are shared
    among neighbours so that adjacent robots reach agreement before pooling
    to graph-level logits.  This prevents incoherent split patterns
    (docs: "consensus layer: neighborhood agreement cho topological action").
    """

    def __init__(self, hidden_dim: int, n_topologies: int):
        super().__init__()
        self.node_vote = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, n_topologies),
        )
        self.agree = nn.Sequential(
            nn.Linear(n_topologies * 3, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, n_topologies),
        )

    def forward(
        self,
        h: torch.Tensor,
        edge_index: torch.Tensor,
        batch_index: torch.Tensor,
    ) -> torch.Tensor:
        # Step 1: per-node topology vote
        votes = self.node_vote(h)  # (N_total, n_topo)

        # Step 2: aggregate neighbour votes
        src, dst = edge_index
        nbr_sum = torch.zeros_like(votes)
        counts = torch.zeros(votes.shape[0], 1, device=votes.device)
        nbr_sum.index_add_(0, dst, votes[src])
        counts.index_add_(0, dst, torch.ones(src.shape[0], 1, device=votes.device))
        nbr_mean = nbr_sum / counts.clamp_min(1.0)

        # Step 3: consensus — combine self vote, neighbour mean, and spread
        nbr_var = torch.zeros_like(votes)
        nbr_var.index_add_(0, dst, (votes[src] - nbr_mean[dst]) ** 2)
        nbr_std = (nbr_var / counts.clamp_min(1.0) + 1e-6).sqrt()  # eps for grad stability
        agreed = self.agree(torch.cat([votes, nbr_mean, nbr_std], dim=-1))

        # Step 4: pool to graph level
        return pooled_graph_features(agreed, batch_index)


class GNNOnlyPolicy(nn.Module):
    def __init__(self, hidden_dim: int = 128, passes: int = 3):
        super().__init__()
        self.backbone = GraphBackbone(hidden_dim, passes)
        self.action_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 2), nn.Tanh())

    def forward(self, batch):
        h = self.backbone(batch["node_x"], batch["edge_index"], batch["edge_attr"])
        actions = self.action_head(h)
        return {"actions": actions, "recoverability": None, "recoverability_scores": None, "topology_logits": None, "aux": None, "uncertainty": None}


class InstantCertPolicy(nn.Module):
    def __init__(self, hidden_dim: int = 128, passes: int = 3):
        super().__init__()
        self.backbone = GraphBackbone(hidden_dim, passes)
        self.action_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 2), nn.Tanh())
        self.cert_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 1))

    def forward(self, batch):
        h = self.backbone(batch["node_x"], batch["edge_index"], batch["edge_attr"])
        actions = self.action_head(h)
        instant = self.cert_head(h)
        pooled = pooled_graph_features(instant, batch["batch_index"])
        return {"actions": actions, "recoverability": pooled, "recoverability_scores": None, "topology_logits": None, "aux": None, "uncertainty": None}


class _GradScale(torch.autograd.Function):
    """Scale gradients in backward pass to protect backbone from auxiliary losses."""

    @staticmethod
    def forward(ctx, x, scale):
        ctx.scale = scale
        return x.clone()

    @staticmethod
    def backward(ctx, grad):
        return grad * ctx.scale, None


def grad_scale(x: torch.Tensor, scale: float) -> torch.Tensor:
    return _GradScale.apply(x, scale)


class RVTSwarmPolicy(nn.Module):
    def __init__(self, hidden_dim: int = 128, passes: int = 3, topology_count: int | None = None):
        super().__init__()
        topology_count = topology_count or len(TOPOLOGY_ACTIONS)
        self.topology_count = topology_count
        # Auxiliary gradients weaken automatically as the backbone gets deeper.
        self.aux_grad_scale = 1.0 / max(float(passes + 1), 1.0)
        self.backbone = GraphBackbone(hidden_dim, passes)
        # Condition the control primitive on the chosen topology so that
        # "u_i" and "tau_i" remain coupled, as required by the project docs.
        self.action_head = nn.Sequential(
            nn.Linear(hidden_dim + topology_count, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2),
            nn.Tanh(),
        )
        # Topology via neighbourhood consensus (not plain pool→MLP)
        self.topology_consensus = TopologyConsensus(hidden_dim, topology_count)
        self.score_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, topology_count))
        self.aux_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 4))
        self.uncertainty_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, topology_count))

    def _normalize_action_topology(
        self,
        action_topology: int | torch.Tensor | None,
        topology_logits: torch.Tensor,
    ) -> torch.Tensor:
        if action_topology is None:
            action_topology = torch.argmax(topology_logits, dim=-1)
        topo = torch.as_tensor(action_topology, device=topology_logits.device, dtype=torch.long).view(-1)
        if topo.numel() == 1 and topology_logits.shape[0] > 1:
            topo = topo.expand(topology_logits.shape[0])
        if topo.numel() != topology_logits.shape[0]:
            raise ValueError("Action topology count must match batch graph count")
        return topo.clamp_(0, self.topology_count - 1)

    def decode_actions(
        self,
        h: torch.Tensor,
        batch_index: torch.Tensor,
        action_topology: int | torch.Tensor,
    ) -> torch.Tensor:
        topo = torch.as_tensor(action_topology, device=h.device, dtype=torch.long).view(-1)
        if topo.numel() == 1 and batch_index.numel():
            topo = topo.expand(int(batch_index.max().item()) + 1)
        topo_onehot = F.one_hot(topo.clamp(0, self.topology_count - 1), num_classes=self.topology_count).to(h.dtype)
        topo_node = topo_onehot[batch_index]
        return self.action_head(torch.cat([h, topo_node], dim=-1))

    def decode_all_actions(
        self,
        h: torch.Tensor,
        batch_index: torch.Tensor,
        num_graphs: int,
    ) -> torch.Tensor:
        action_bank = []
        for topo_idx in range(self.topology_count):
            topo = torch.full((num_graphs,), topo_idx, device=h.device, dtype=torch.long)
            action_bank.append(self.decode_actions(h, batch_index, topo))
        return torch.stack(action_bank, dim=1)

    def forward(self, batch, action_topology: int | torch.Tensor | None = None):
        h = self.backbone(batch["node_x"], batch["edge_index"], batch["edge_attr"])

        # Auxiliary heads get scaled gradients to protect backbone for actions
        h_aux = grad_scale(h, self.aux_grad_scale)

        # Topology logits via neighbourhood consensus layer
        topology_logits = self.topology_consensus(
            h_aux, batch["edge_index"], batch["batch_index"]
        )
        pooled = pooled_graph_features(h_aux, batch["batch_index"])
        recover_scores = self.score_head(pooled)
        aux = self.aux_head(pooled)
        uncertainty = F.softplus(self.uncertainty_head(pooled))
        adjusted_scores = uncertainty_adjusted_scores(recover_scores, uncertainty)
        recoverability = adjusted_scores.max(dim=-1, keepdim=True).values
        num_graphs = topology_logits.shape[0]
        actions_by_topology = self.decode_all_actions(h, batch["batch_index"], num_graphs)
        topo = self._normalize_action_topology(action_topology, topology_logits)
        node_topology = topo[batch["batch_index"]]
        actions = actions_by_topology[
            torch.arange(h.shape[0], device=h.device),
            node_topology,
        ]
        return {
            "actions": actions,
            "actions_by_topology": actions_by_topology,
            "recoverability": recoverability,
            "recoverability_scores": adjusted_scores,
            "topology_logits": topology_logits,
            "aux": aux,
            "uncertainty": uncertainty,
            "node_latent": h,
        }


def build_model(name: str, hidden_dim: int = 128, passes: int = 3) -> nn.Module:
    if name == "gnn_only":
        return GNNOnlyPolicy(hidden_dim, passes)
    if name == "instant_cert":
        return InstantCertPolicy(hidden_dim, passes)
    if name == "rvt_swarm":
        return RVTSwarmPolicy(hidden_dim, passes)
    raise ValueError(f"Unknown model: {name}")
