"""A3 -- the capacity-matched non-message-passing mechanism control.

A3 exists for exactly one causal contrast: does ITERATIVE MESSAGE PASSING over
the ego graph contribute, once capacity and available information are held
fixed? It is therefore built to differ from M2 in the message-passing mechanism
and in nothing else that can be held constant.

  * Same admitted inputs as M2, same forbidden inputs.
  * Same candidate-topology conditioning: the candidate id is embedded at the
    same width, so A3 is NOT a topology-blinded model. Topology blinding is A2's
    contrast, not this one.
  * Neighbor information IS available, through permutation-invariant pooling of
    one-hop neighbor node features and incident edge features. Removing neighbor
    information entirely would confound "no message passing" with "no neighbors".
  * edge_index is used ONLY to identify one-hop incidence to the root. There is
    no propagation between non-root nodes and no iterated round of exchange.
  * Same depth (3 blocks), activation, normalization, dropout and dtype as M2.

A3 never participates in SELECT-R family selection. It is a mechanism control
trained on TRAIN-R under the frozen recipe and used only in the mechanism study.
"""
from __future__ import annotations

import torch
from torch import nn

from rvt_swarm.decentralized.ego_graph_v2 import NODE_FEATURE_DIM

EDGE_FEATURE_DIM = 19
CANDIDATE_EMBEDDING_DIMENSION = 16      # identical to M2
CANDIDATE_TABLE_SIZE = 2                # COMPACT and LINE
BLOCKS = 3                              # identical to M2
HIDDEN_DIMENSION = 184                  # chosen to match M2's parameter count
DROPOUT_PROBABILITY = 0.0               # identical to M2
M2_RECOVERABILITY_PATH_PARAMETERS = 262529
CAPACITY_MATCH_TOLERANCE_FRACTION = 0.02

# node_x concatenated with its validity mask, mirroring M2's node_input width
_NODE_INPUT = NODE_FEATURE_DIM * 2
_EDGE_INPUT = EDGE_FEATURE_DIM * 2
# root, neighbor mean, neighbor max, edge mean, edge max, candidate embedding
INPUT_DIMENSION = _NODE_INPUT * 3 + _EDGE_INPUT * 2 + CANDIDATE_EMBEDDING_DIMENSION


class _Block(nn.Module):
    """LayerNorm -> Linear -> ReLU -> Linear, residual. No neighbor exchange."""

    def __init__(self, width: int) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(width)
        self.fc1 = nn.Linear(width, width)
        self.fc2 = nn.Linear(width, width)
        self.act = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.fc2(self.act(self.fc1(self.norm(x))))


class A3PooledLocalModel(nn.Module):
    """Permutation-invariant pooled local predictor with message passing removed."""

    def __init__(self, width: int = HIDDEN_DIMENSION) -> None:
        super().__init__()
        self.candidate_embedding = nn.Embedding(CANDIDATE_TABLE_SIZE,
                                                CANDIDATE_EMBEDDING_DIMENSION)
        self.project = nn.Linear(INPUT_DIMENSION, width)
        self.blocks = nn.ModuleList(_Block(width) for _ in range(BLOCKS))
        self.head_norm = nn.LayerNorm(width)
        self.head = nn.Linear(width, 1)

    def forward(self, features: torch.Tensor, candidate_index: torch.Tensor) -> torch.Tensor:
        h = self.project(torch.cat([features, self.candidate_embedding(candidate_index)], dim=-1))
        for block in self.blocks:
            h = block(h)
        return self.head(self.head_norm(h)).squeeze(-1)


def parameter_count(width: int = HIDDEN_DIMENSION) -> int:
    return sum(p.numel() for p in A3PooledLocalModel(width).parameters())


def capacity_match_report(width: int = HIDDEN_DIMENSION) -> dict:
    n = parameter_count(width)
    delta = n - M2_RECOVERABILITY_PATH_PARAMETERS
    fraction = delta / M2_RECOVERABILITY_PATH_PARAMETERS
    return {
        "a3_parameters": n,
        "m2_recoverability_path_parameters": M2_RECOVERABILITY_PATH_PARAMETERS,
        "absolute_difference": delta,
        "relative_difference": fraction,
        "tolerance_fraction": CAPACITY_MATCH_TOLERANCE_FRACTION,
        "within_tolerance": abs(fraction) <= CAPACITY_MATCH_TOLERANCE_FRACTION,
        "hidden_dimension": width,
        "input_dimension": INPUT_DIMENSION,
    }
