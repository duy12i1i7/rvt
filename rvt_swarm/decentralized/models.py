"""Fully decentralized keep/line selector models.

Two models, one shared trunk design, differing only in head and loss:

  decentralized_direct_selector    masked decisive-state classification
  decentralized_recovery_selector  BCE against Recovery Event V2 labels

Both consume a *mode-conditioned ego graph* G_i(tau) and emit one scalar per
candidate mode, q_i,tau = f_theta(G_i(tau), tau). Two graphs are built per
robot per decision (one per mode) and the same weights score both, so the
mode enters through the input rather than through a separate head -- which is
what makes the two candidate scores commensurable and the consensus meaningful.

The readout is the CENTER NODE embedding, h[center_index], not a pooled
aggregate. This matters for the decentralization claim:

  - Pooling over the whole swarm graph is prohibited and is the exact defect
    that made the previous model non-decentralized
    (`models.RVTBinaryRecoveryPolicy` calls `pooled_graph_features` over
    `batch_index`, producing ONE logit per team).
  - Pooling over robot i's own EGO graph would be permitted -- an ego graph
    contains only local information -- but the center-node readout is stronger
    still: it needs no pooling operator at all, so "no global pooling" is
    structurally true rather than argued.

Message passing aggregates with `index_add_` (a sum) under an edge-softmax, so
the readout is invariant to neighbour ordering by construction.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..runtime_configuration import DEFAULT_RUNTIME_CONFIG
from .ego_graph import EDGE_DIM, FEATURE_DIM
from .system_model import KEEP, LINE, MODES


def _edge_softmax(scores: torch.Tensor, dst: torch.Tensor, n_nodes: int) -> torch.Tensor:
    """Softmax over the incoming edges of each node. Permutation invariant."""
    # A robot can legitimately have NO edges: under heavy packet loss it may
    # hear nobody and sense no obstacle, leaving a one-node ego graph. It must
    # still produce a score from its own features rather than crash, so the
    # empty case returns early instead of calling max() on an empty tensor.
    if scores.numel() == 0:
        return scores
    # Shift by the global max for numerical stability. A per-node max would be
    # marginally tighter but needs a scatter-max; the global shift is exactly
    # equivalent mathematically (the constant cancels within each node's
    # denominator) and keeps permutation invariance obvious.
    shifted = torch.exp(scores - scores.max().detach())
    denom = shifted.new_zeros(n_nodes).index_add_(0, dst, shifted)
    return shifted / denom[dst].clamp_min(1e-9)


class EgoLayer(nn.Module):
    """One message-passing round over a single robot's ego graph."""

    def __init__(self, hidden_dim: int, edge_dim: int) -> None:
        super().__init__()
        self.edge_mlp = nn.Sequential(
            nn.Linear(hidden_dim * 2 + edge_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim), nn.ReLU(),
        )
        self.attn = nn.Linear(hidden_dim, 1, bias=False)
        self.node_mlp = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor,
                edge_attr: torch.Tensor) -> torch.Tensor:
        src, dst = edge_index
        m = self.edge_mlp(torch.cat([h[src], h[dst], edge_attr], dim=-1))
        alpha = _edge_softmax(
            F.leaky_relu(
                self.attn(m).squeeze(-1),
                DEFAULT_RUNTIME_CONFIG.model.attention_leaky_relu_slope,
            ),
            dst,
            h.shape[0],
        )
        agg = torch.zeros_like(h).index_add_(0, dst, m * alpha.unsqueeze(-1))
        return h + self.node_mlp(torch.cat([h, agg], dim=-1))


class EgoTrunk(nn.Module):
    """Shared-weight encoder. Identical parameters on every robot."""

    def __init__(
        self,
        hidden_dim: int = DEFAULT_RUNTIME_CONFIG.model.hidden_dimension,
        passes: int = DEFAULT_RUNTIME_CONFIG.model.message_passing_steps,
    ) -> None:
        super().__init__()
        self.enc = nn.Sequential(
            nn.Linear(FEATURE_DIM, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.layers = nn.ModuleList([EgoLayer(hidden_dim, EDGE_DIM) for _ in range(passes)])

    def forward(self, node_x: torch.Tensor, edge_index: torch.Tensor,
                edge_attr: torch.Tensor, center_index: torch.Tensor) -> torch.Tensor:
        h = self.enc(node_x)
        for layer in self.layers:
            h = layer(h, edge_index, edge_attr)
        return h[center_index]          # center-node readout: no pooling operator


class _SelectorBase(nn.Module):
    """Trunk + a 1-scalar head, applied once per candidate mode."""

    def __init__(
        self,
        hidden_dim: int = DEFAULT_RUNTIME_CONFIG.model.hidden_dimension,
        passes: int = DEFAULT_RUNTIME_CONFIG.model.message_passing_steps,
    ) -> None:
        super().__init__()
        self.trunk = EgoTrunk(hidden_dim, passes)
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def score(self, g: Dict[str, torch.Tensor]) -> torch.Tensor:
        """q for one mode-conditioned ego-graph batch. Returns (B,)."""
        z = self.trunk(g["node_x"], g["edge_index"], g["edge_attr"], g["center_index"])
        return self.head(z).squeeze(-1)

    def forward(self, ego_keep: Dict[str, torch.Tensor],
                ego_line: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        q = torch.stack([self.score(ego_keep), self.score(ego_line)], dim=-1)  # (B,2)
        return self._heads(q)

    def _heads(self, q: torch.Tensor) -> Dict[str, torch.Tensor]:
        raise NotImplementedError


class DecentralizedRecoverySelector(_SelectorBase):
    """q_i,tau -> P(task recovery under mode tau), two INDEPENDENT sigmoids.

    Independent, not softmax: both modes can succeed (both_succeed) or both
    fail (both_fail), so the two events are not mutually exclusive and a
    softmax would impose a false constraint. Trained with BCE against Recovery
    Event V2 labels -- a proper scoring rule, so the outputs are calibrated
    probabilities and post-consensus comparison is meaningful.

    No uncertainty head, no auxiliary head, no action head, no split output,
    no shaped rollout utility, no pairwise-ranking loss.
    """

    def _heads(self, q: torch.Tensor) -> Dict[str, torch.Tensor]:
        return {"logits": q, "recovery_logits": q, "recovery_probs": torch.sigmoid(q)}


class DecentralizedDirectSelector(_SelectorBase):
    """q_i,tau -> a 2-way choice over {keep, line}.

    Trained with cross-entropy MASKED TO DECISIVE STATES only: keep_only ->
    keep, line_only -> line, and both_succeed / both_fail contribute exactly
    zero. Supplying an arbitrary tie-break target on non-decisive states is what
    taught the previous classifier the majority class; it is not repeated here.
    """

    def _heads(self, q: torch.Tensor) -> Dict[str, torch.Tensor]:
        return {"logits": q, "class_logits": q, "class_probs": torch.softmax(q, dim=-1)}


SELECTORS = {
    "decentralized_direct_selector": DecentralizedDirectSelector,
    "decentralized_recovery_selector": DecentralizedRecoverySelector,
}


def build_selector(
    name: str,
    hidden_dim: int = DEFAULT_RUNTIME_CONFIG.model.hidden_dimension,
    passes: int = DEFAULT_RUNTIME_CONFIG.model.message_passing_steps,
) -> _SelectorBase:
    if name not in SELECTORS:
        raise ValueError(f"unknown selector {name!r}; choose from {sorted(SELECTORS)}")
    return SELECTORS[name](hidden_dim=hidden_dim, passes=passes)


def parameter_report() -> Dict[str, int]:
    """Both selectors share the trunk design, so capacity is comparable by
    construction. No padding parameters are added to force exact equality --
    the heads differ only in how the same two scalars are interpreted, so the
    counts are in fact identical, and that is a consequence of the design
    rather than a target that was engineered.
    """
    return {name: sum(p.numel() for p in build_selector(name).parameters())
            for name in SELECTORS}
