"""M1 -- the frozen local, non-graph baseline.

The 56-dimensional input is not a design choice made here. It is derived
mechanically from ``NODE_FEATURE_DEFINITIONS``: every block whose ``applies_to``
contains ``NODE_SELF``, expanded through ``NODE_FEATURE_SLICES``, gives 25
columns; those 25 masked values, their 25 validity masks, and six frozen local
aggregates make 56. The derivation is then checked against the frozen M1 input
contract, so a drift in either the feature schema or the contract is a loud
failure rather than a silent re-specification.

Values are fed as ``value * mask`` concatenated with ``mask`` -- byte-identical
to what ``FD24LocalGraphEncoder`` feeds its node projection. That is deliberate:
it makes any measured M2 - M1 difference attributable to graph structure and not
to a difference in preprocessing.

Counts use the parameter-free saturating map ``c / (1 + c)``. It needs no
reference constant, so M1 introduces no new normalization constant, and it is
invertible on the integers, which is what makes the missing-value sentinels in
the range aggregates unambiguous: a reader can always recover P and O exactly and
therefore always distinguish "no peer observed" from "a peer at the range
boundary".
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence, Tuple

import torch
import torch.nn as nn

from ..decentralized.ego_graph_v2 import (
    NODE_FEATURE_DEFINITIONS, NODE_FEATURE_SLICES, NODE_OBSTACLE, NODE_PEER,
    NODE_SELF, RobotLocalEgoGraph,
)

M1_HIDDEN_WIDTH = 32
M1_AGGREGATE_COUNT = 6
M1_AGGREGATE_NAMES: Tuple[str, ...] = (
    "fresh_peer_count_saturating",
    "observed_obstacle_token_count_saturating",
    "minimum_observed_obstacle_range",
    "mean_fresh_peer_range",
    "maximum_peer_message_age",
    "peer_topology_conflict_count_saturating",
)


class M1ContractError(ValueError):
    """An M1 input-contract violation that must fail closed."""


def _self_columns() -> Tuple[Tuple[int, ...], Tuple[str, ...]]:
    columns, names = [], []
    for definition in NODE_FEATURE_DEFINITIONS:
        if NODE_SELF not in definition.applies_to:
            continue
        block = NODE_FEATURE_SLICES[definition.name]
        for offset, column in enumerate(range(block.start, block.stop)):
            columns.append(column)
            names.append(f"{definition.name}[{offset}]")
    return tuple(columns), tuple(names)


M1_SELF_COLUMNS, M1_SELF_FIELD_NAMES = _self_columns()
M1_INPUT_DIMENSION = 2 * len(M1_SELF_COLUMNS) + M1_AGGREGATE_COUNT

_DISTANCE_RANGE = NODE_FEATURE_SLICES["distance_range"].start
_PEER_MESSAGE_AGE = NODE_FEATURE_SLICES["peer_message_age_limit"].start
_PEER_TOPOLOGY_CONFLICT = NODE_FEATURE_SLICES["peer_topology_conflict"].start


def verify_against_frozen_contract(contract: Mapping[str, Any]) -> None:
    """The derivation must equal the frozen contract, field for field."""
    if int(contract["input_dimension"]) != M1_INPUT_DIMENSION:
        raise M1ContractError(
            f"frozen M1 dimension {contract['input_dimension']} != derived "
            f"{M1_INPUT_DIMENSION}")
    if tuple(contract["self_column_indices_into_node_x"]) != M1_SELF_COLUMNS:
        raise M1ContractError("frozen M1 column indices differ from the derivation")
    if tuple(contract["ordered_value_fields"]) != M1_SELF_FIELD_NAMES:
        raise M1ContractError("frozen M1 field ordering differs from the derivation")
    frozen_aggregates = tuple(item["name"] for item in contract["aggregates"])
    if frozen_aggregates != M1_AGGREGATE_NAMES:
        raise M1ContractError("frozen M1 aggregate ordering differs from the derivation")


def _saturating(count: torch.Tensor) -> torch.Tensor:
    return count / (1.0 + count)


def m1_features(graph: RobotLocalEgoGraph) -> torch.Tensor:
    """The frozen 56-dimensional local vector for one robot-local graph."""
    if not isinstance(graph, RobotLocalEgoGraph):
        raise M1ContractError("M1 features require a RobotLocalEgoGraph")
    node_x = graph.node_x.to(torch.float32)
    mask = graph.node_feature_valid_mask
    root = int(graph.root_index)
    if int(graph.node_kind[root]) != NODE_SELF:
        raise M1ContractError("the graph root must be a SELF node")

    columns = torch.tensor(M1_SELF_COLUMNS, dtype=torch.int64)
    values = node_x[root].index_select(0, columns)
    masks = mask[root].index_select(0, columns).to(torch.float32)

    kind = graph.node_kind
    peers = torch.nonzero(kind == NODE_PEER, as_tuple=False).flatten()
    obstacles = torch.nonzero(kind == NODE_OBSTACLE, as_tuple=False).flatten()
    peer_count = torch.tensor(float(peers.numel()), dtype=torch.float32)
    obstacle_count = torch.tensor(float(obstacles.numel()), dtype=torch.float32)

    if obstacles.numel():
        minimum_obstacle_range = node_x[obstacles, _DISTANCE_RANGE].min()
    else:
        # No obstacle observed. 1.0 is the sensing-range boundary; aggregate 1
        # records the exact count, so this sentinel is never ambiguous.
        minimum_obstacle_range = torch.tensor(1.0, dtype=torch.float32)
    if peers.numel():
        mean_peer_range = node_x[peers, _DISTANCE_RANGE].mean()
        maximum_message_age = node_x[peers, _PEER_MESSAGE_AGE].max()
        conflicts = node_x[peers, _PEER_TOPOLOGY_CONFLICT].sum()
    else:
        mean_peer_range = torch.tensor(1.0, dtype=torch.float32)
        maximum_message_age = torch.tensor(0.0, dtype=torch.float32)
        conflicts = torch.tensor(0.0, dtype=torch.float32)

    aggregates = torch.stack([
        _saturating(peer_count),
        _saturating(obstacle_count),
        minimum_obstacle_range.to(torch.float32),
        mean_peer_range.to(torch.float32),
        maximum_message_age.to(torch.float32),
        _saturating(conflicts),
    ])
    features = torch.cat([values * masks, masks, aggregates]).to(torch.float32)
    if features.numel() != M1_INPUT_DIMENSION:
        raise M1ContractError("M1 produced the wrong input width")
    if not bool(torch.isfinite(features).all()):
        raise M1ContractError("M1 features must be finite")
    return features


def m1_feature_batch(graphs: Sequence[RobotLocalEgoGraph]) -> torch.Tensor:
    if not graphs:
        raise M1ContractError("M1 requires at least one robot-local graph")
    return torch.stack([m1_features(graph) for graph in graphs])


class M1LocalPredictor(nn.Module):
    """One hidden layer, width 32. No message passing, no candidate embedding.

    Topology conditioning still reaches M1: the candidate query is present in the
    root ``candidate_topology_onehot`` columns and in the four candidate-derived
    root features, all of which are inside the frozen 25.
    """

    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(M1_INPUT_DIMENSION, M1_HIDDEN_WIDTH),
            nn.ReLU(),
            nn.Linear(M1_HIDDEN_WIDTH, 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        if features.ndim != 2 or features.shape[1] != M1_INPUT_DIMENSION:
            raise M1ContractError("M1 input must be (rows, 56)")
        if features.dtype != torch.float32:
            raise M1ContractError("M1 requires float32 input")
        return self.network(features).squeeze(-1)

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())
