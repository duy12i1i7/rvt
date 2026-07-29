from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .dataset import EDGE_DIM, NODE_DIM
from .config import LEARNED_TOPOLOGY_IDS
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
        return {
            "actions": actions,
            "recoverability": None,
            "recoverability_scores": None,
            "raw_recoverability_scores": None,
            "topology_logits": None,
            "aux": None,
            "uncertainty": None,
        }


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
        return {
            "actions": actions,
            "recoverability": pooled,
            "recoverability_scores": None,
            "raw_recoverability_scores": None,
            "topology_logits": None,
            "aux": None,
            "uncertainty": None,
        }


class RVTSwarmPolicy(nn.Module):
    def __init__(self, hidden_dim: int = 128, passes: int = 3, topology_count: int | None = None):
        super().__init__()
        topology_count = topology_count or len(LEARNED_TOPOLOGY_IDS)
        self.topology_count = topology_count
        self.context_dim = NODE_DIM
        self.backbone = GraphBackbone(hidden_dim, passes)
        # Keep action learning anchored to a topology-agnostic base controller.
        # Structural topology should contribute a residual correction, not force
        # the model to relearn the whole action map for every mode.
        self.base_action_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2),
        )
        self.topology_delta_head = nn.Sequential(
            nn.Linear(hidden_dim + topology_count, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2),
        )
        # Topology via neighbourhood consensus (not plain pool→MLP)
        self.topology_consensus = TopologyConsensus(hidden_dim, topology_count)
        self.topology_refine = nn.Sequential(
            nn.Linear(topology_count + self.context_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, topology_count),
        )
        self.score_head = nn.Sequential(
            nn.Linear(hidden_dim + self.context_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, topology_count),
        )
        self.aux_head = nn.Sequential(
            nn.Linear(hidden_dim + self.context_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 4),
        )
        self.uncertainty_head = nn.Sequential(
            nn.Linear(hidden_dim + self.context_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, topology_count),
        )

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
        base = self.base_action_head(h)
        delta = self.topology_delta_head(torch.cat([h, topo_node], dim=-1))
        # Index 0 corresponds to the structural anchor `keep`. It should not
        # pay a residual penalty for the extra topology machinery.
        switch_mask = 1.0 - topo_node[:, [0]]
        return torch.tanh(base + switch_mask * delta)

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

        # Keep the control backbone focused on action quality. Topology and
        # recoverability heads learn on top of the same latent state, but they
        # do not backpropagate into the action features.
        h_aux = h.detach()
        raw_pooled = pooled_graph_features(batch["node_x"], batch["batch_index"])

        # Topology logits via neighbourhood consensus layer
        topology_votes = self.topology_consensus(
            h_aux, batch["edge_index"], batch["batch_index"]
        )
        topology_logits = topology_votes + self.topology_refine(torch.cat([topology_votes, raw_pooled], dim=-1))
        pooled = pooled_graph_features(h_aux, batch["batch_index"])
        pooled_ctx = torch.cat([pooled, raw_pooled], dim=-1)
        raw_recover_scores = self.score_head(pooled_ctx)
        aux = self.aux_head(pooled_ctx)
        uncertainty = F.softplus(self.uncertainty_head(pooled_ctx))
        adjusted_scores = uncertainty_adjusted_scores(raw_recover_scores, uncertainty)
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
            "raw_recoverability_scores": raw_recover_scores,
            "topology_logits": topology_logits,
            "aux": aux,
            "uncertainty": uncertainty,
            "node_latent": h,
        }


class RVTSimpleRankPolicy(nn.Module):
    """Simplified RVT: shared encoder + action bank + per-mode ranking score.

    Removed relative to `RVTSwarmPolicy` (each on Method-Audit-v2 evidence):
      * uncertainty head and the dispersion-scaled score adjustment
        -- uncalibrated, fitted to its own in-sample residual, and removing it
        improved every ranking metric (top-1 0.840 vs 0.827, Kendall 0.631 vs 0.596);
      * auxiliary head -- its four targets are all already input node features;
      * topology-classification head -- retained only as a separate baseline model
        (`direct_topology_classifier`), not as a component here.

    Kept: the shared graph encoder, the mode-conditioned action bank, and a single
    score head whose only job is to *rank* the candidate modes.
    """

    def __init__(self, hidden_dim: int = 128, passes: int = 3, topology_count: int | None = None):
        super().__init__()
        topology_count = topology_count or len(LEARNED_TOPOLOGY_IDS)
        self.topology_count = topology_count
        self.context_dim = NODE_DIM
        self.backbone = GraphBackbone(hidden_dim, passes)
        self.base_action_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2), nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2),
        )
        self.topology_delta_head = nn.Sequential(
            nn.Linear(hidden_dim + topology_count, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2), nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2),
        )
        self.score_head = nn.Sequential(
            nn.Linear(hidden_dim + self.context_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, topology_count),
        )

    # Action decoding is identical to the legacy model so the two remain comparable.
    decode_actions = RVTSwarmPolicy.decode_actions
    decode_all_actions = RVTSwarmPolicy.decode_all_actions
    _normalize_action_topology = RVTSwarmPolicy._normalize_action_topology

    def forward(self, batch, action_topology: int | torch.Tensor | None = None):
        h = self.backbone(batch["node_x"], batch["edge_index"], batch["edge_attr"])
        h_aux = h.detach()
        raw_pooled = pooled_graph_features(batch["node_x"], batch["batch_index"])
        pooled = pooled_graph_features(h_aux, batch["batch_index"])
        scores = self.score_head(torch.cat([pooled, raw_pooled], dim=-1))

        num_graphs = scores.shape[0]
        actions_by_topology = self.decode_all_actions(h, batch["batch_index"], num_graphs)
        if action_topology is None:
            topo = torch.argmax(scores, dim=-1)          # direct argmax selection
        else:
            topo = torch.as_tensor(action_topology, device=h.device, dtype=torch.long).view(-1)
            if topo.numel() == 1 and num_graphs > 1:
                topo = topo.expand(num_graphs)
        topo = topo.clamp(0, self.topology_count - 1)
        actions = actions_by_topology[
            torch.arange(h.shape[0], device=h.device), topo[batch["batch_index"]]
        ]
        return {
            "actions": actions,
            "actions_by_topology": actions_by_topology,
            # `recoverability_scores` carries the ranking score under the name the
            # runtime already consumes; it is NOT uncertainty-adjusted here.
            "recoverability_scores": scores,
            "raw_recoverability_scores": scores,
            "recoverability": scores.max(dim=-1, keepdim=True).values,
            "topology_logits": None,   # no classifier head
            "aux": None,               # no auxiliary head
            "uncertainty": None,       # no uncertainty head
            "node_latent": h,
        }


class DirectTopologyClassifierPolicy(RVTSwarmPolicy):
    """Baseline: action bank + hard best-mode classifier, no ranking score.

    Kept as a *baseline* rather than a component, per the audit: the classifier
    ranked modes about as well as the score head (pairwise 0.810 vs 0.814), so
    carrying both inside one model is unjustified duplication.
    """

    def forward(self, batch, action_topology: int | torch.Tensor | None = None):
        out = super().forward(batch, action_topology=action_topology)
        out["recoverability_scores"] = None
        out["raw_recoverability_scores"] = None
        out["uncertainty"] = None
        out["aux"] = None
        return out


BINARY_MODES = (0, 2)   # keep, line.  Split is REMOVED (Task 8 of the scenario gate).


class RVTBinaryRecoveryPolicy(nn.Module):
    """Pilot model: shared encoder + per-mode action head + per-mode recovery head.

    Exactly five components, per the pilot specification:
      shared graph encoder
      keep-conditioned action head          (base action head)
      line-conditioned action head          (base + conditioned residual)
      keep task-recovery probability head   (logit index 0)
      line task-recovery probability head   (logit index 1)

    Inference:  tau_hat = argmax_{tau in {keep, line}} p_task_recovery(x, tau)
    then execute the action head for tau_hat.

    Contains no split output, no uncertainty head, no auxiliary head, no
    classifier head, and no selector state of any kind.
    """

    def __init__(self, hidden_dim: int = 128, passes: int = 3):
        super().__init__()
        self.modes = BINARY_MODES
        self.topology_count = len(BINARY_MODES)
        self.context_dim = NODE_DIM
        self.backbone = GraphBackbone(hidden_dim, passes)
        self.base_action_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2), nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2))
        self.mode_action_head = nn.Sequential(
            nn.Linear(hidden_dim + self.topology_count, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2), nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2))
        # One logit per candidate mode = the two task-recovery probability heads.
        self.recovery_head = nn.Sequential(
            nn.Linear(hidden_dim + self.context_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, self.topology_count))

    def decode_actions(self, h, batch_index, mode_index):
        topo = torch.as_tensor(mode_index, device=h.device, dtype=torch.long).view(-1)
        if topo.numel() == 1 and batch_index.numel():
            topo = topo.expand(int(batch_index.max().item()) + 1)
        onehot = F.one_hot(topo.clamp(0, self.topology_count - 1),
                           num_classes=self.topology_count).to(h.dtype)
        node_onehot = onehot[batch_index]
        base = self.base_action_head(h)
        delta = self.mode_action_head(torch.cat([h, node_onehot], dim=-1))
        keep_mask = 1.0 - node_onehot[:, [0]]      # index 0 is KEEP
        return torch.tanh(base + keep_mask * delta)

    def forward(self, batch, action_topology=None):
        h = self.backbone(batch["node_x"], batch["edge_index"], batch["edge_attr"])
        pooled = pooled_graph_features(h.detach(), batch["batch_index"])
        raw_pooled = pooled_graph_features(batch["node_x"], batch["batch_index"])
        logits = self.recovery_head(torch.cat([pooled, raw_pooled], dim=-1))
        probs = torch.sigmoid(logits)
        num_graphs = logits.shape[0]

        bank = torch.stack([
            self.decode_actions(h, batch["batch_index"],
                                torch.full((num_graphs,), i, device=h.device, dtype=torch.long))
            for i in range(self.topology_count)], dim=1)

        if action_topology is None:
            sel = torch.argmax(probs, dim=-1)
        else:
            sel = torch.as_tensor(action_topology, device=h.device, dtype=torch.long).view(-1)
            if sel.numel() == 1 and num_graphs > 1:
                sel = sel.expand(num_graphs)
        sel = sel.clamp(0, self.topology_count - 1)
        actions = bank[torch.arange(h.shape[0], device=h.device), sel[batch["batch_index"]]]
        return {
            "actions": actions,
            "actions_by_topology": bank,
            "recovery_logits": logits,
            "recovery_probs": probs,
            "recoverability_scores": probs,     # runtime consumes this name
            "raw_recoverability_scores": logits,
            "recoverability": probs.max(dim=-1, keepdim=True).values,
            "topology_logits": None,
            "aux": None,
            "uncertainty": None,
            "node_latent": h,
        }


class DirectKeepLineClassifier(RVTBinaryRecoveryPolicy):
    """Baseline: identical trunk and action heads, but a 2-class softmax classifier
    over {keep, line} instead of two independent recovery-probability heads.

    This is the control that decides whether *probability prediction* adds
    anything over *direct classification* (pilot mechanism criterion)."""

    def forward(self, batch, action_topology=None):
        out = super().forward(batch, action_topology=action_topology)
        out["class_logits"] = out.pop("recovery_logits")
        probs = torch.softmax(out["class_logits"], dim=-1)
        out["recovery_probs"] = probs
        out["recoverability_scores"] = probs
        out["raw_recoverability_scores"] = out["class_logits"]
        return out


def build_model(name: str, hidden_dim: int = 128, passes: int = 3) -> nn.Module:
    if name == "rvt_binary_recovery":
        return RVTBinaryRecoveryPolicy(hidden_dim, passes)
    if name == "direct_keep_line_classifier":
        return DirectKeepLineClassifier(hidden_dim, passes)
    # Legacy names are preserved; the original implementation is untouched.
    if name in ("gnn_only", "gnn_topology_agnostic"):
        return GNNOnlyPolicy(hidden_dim, passes)
    if name == "instant_cert":
        return InstantCertPolicy(hidden_dim, passes)
    if name in ("rvt_swarm", "rvt_full_legacy"):
        return RVTSwarmPolicy(hidden_dim, passes, topology_count=len(LEARNED_TOPOLOGY_IDS))
    if name == "rvt_simple_rank":
        return RVTSimpleRankPolicy(hidden_dim, passes, topology_count=len(LEARNED_TOPOLOGY_IDS))
    if name == "direct_topology_classifier":
        return DirectTopologyClassifierPolicy(
            hidden_dim, passes, topology_count=len(LEARNED_TOPOLOGY_IDS)
        )
    if name == "fixed_keep_policy":
        # No parameters: mode is pinned to KEEP and actions come from the expert.
        raise ValueError("fixed_keep_policy is a non-learned baseline; use baselines.py")
    raise ValueError(f"Unknown model: {name}")
