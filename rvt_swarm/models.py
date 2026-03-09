from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .dataset import EDGE_DIM, NODE_DIM
from .config import TOPOLOGY_ACTIONS


class GraphLayer(nn.Module):
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.edge_mlp = nn.Sequential(
            nn.Linear(hidden_dim * 2 + EDGE_DIM, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.node_mlp = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor, edge_attr: torch.Tensor) -> torch.Tensor:
        src, dst = edge_index
        m = self.edge_mlp(torch.cat([h[src], h[dst], edge_attr], dim=-1))
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
    def __init__(self, hidden_dim: int = 128, passes: int = 3, topology_count: int | None = None, aux_grad_scale: float = 0.3):
        super().__init__()
        topology_count = topology_count or len(TOPOLOGY_ACTIONS)
        self.aux_grad_scale = aux_grad_scale
        self.backbone = GraphBackbone(hidden_dim, passes)
        # Deeper action head for better control quality
        self.action_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2),
            nn.Tanh(),
        )
        # Direct formation-error-to-action residual (skip connection)
        self.form_residual = nn.Sequential(
            nn.Linear(2, 32),
            nn.ReLU(),
            nn.Linear(32, 2),
            nn.Tanh(),
        )
        self.topology_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, topology_count))
        self.score_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, topology_count))
        self.aux_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 4))
        self.uncertainty_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, topology_count))

    def forward(self, batch):
        h = self.backbone(batch["node_x"], batch["edge_index"], batch["edge_attr"])
        # Action head gets full gradient flow — no residual shortcut
        actions = self.action_head(h)

        # Auxiliary heads get scaled gradients to protect backbone for actions
        h_aux = grad_scale(h, self.aux_grad_scale)
        pooled = pooled_graph_features(h_aux, batch["batch_index"])

        topology_logits = self.topology_head(pooled)
        recover_scores = self.score_head(pooled)
        aux = self.aux_head(pooled)
        uncertainty = F.softplus(self.uncertainty_head(pooled))
        adjusted_scores = recover_scores - 0.25 * uncertainty
        recoverability = adjusted_scores.max(dim=-1, keepdim=True).values
        return {
            "actions": actions,
            "recoverability": recoverability,
            "recoverability_scores": adjusted_scores,
            "topology_logits": topology_logits,
            "aux": aux,
            "uncertainty": uncertainty,
        }


def build_model(name: str, hidden_dim: int = 128, passes: int = 3, aux_grad_scale: float = 0.3) -> nn.Module:
    if name == "gnn_only":
        return GNNOnlyPolicy(hidden_dim, passes)
    if name == "instant_cert":
        return InstantCertPolicy(hidden_dim, passes)
    if name == "rvt_swarm":
        return RVTSwarmPolicy(hidden_dim, passes, aux_grad_scale=aux_grad_scale)
    raise ValueError(f"Unknown model: {name}")
