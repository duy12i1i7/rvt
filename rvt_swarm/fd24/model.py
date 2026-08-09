"""Authoritative shared robot-local RVT-FD24 neural architecture.

This module consumes only Phase 4 ego-graph V2 records and immutable model and
runtime configuration. It contains no training loop, topology decision,
controller call, communication protocol, safety projection, or global graph
adapter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..decentralized.ego_graph_v2 import (
    EDGE_FEATURE_DIM,
    EDGE_FEATURE_SLICES,
    EDGE_TYPES,
    EGO_GRAPH_FEATURE_SCHEMA_SHA256,
    EGO_GRAPH_SCHEMA_VERSION,
    NODE_FEATURE_DIM,
    NODE_FEATURE_SLICES,
    NODE_KINDS,
    NODE_SELF,
    BatchedRobotLocalEgoGraphs,
    RobotLocalEgoGraph,
    batch_robot_local_ego_graphs,
)
from ..runtime_configuration import RuntimeConfig
from ..topology_registry import (
    PRIMARY_TOPOLOGY_IDS,
    TOPOLOGY_REGISTRY_SCHEMA_VERSION,
)
from .configuration import (
    FD24ModelConfig,
    ROBOT_LOCAL_ACTION_COMPONENTS,
    residual_action_limits,
)


FD24_MODEL_SCHEMA_VERSION = "rvt-fd24-model/v2"
FD24_MODEL_INPUT_SCHEMA_VERSION = "rvt-fd24-model-input/v2"
FD24_MODEL_OUTPUT_SCHEMA_VERSION = "rvt-fd24-model-output/v2"
FD24_TOPOLOGY_VOCABULARY: Tuple[Tuple[int, str], ...] = (
    (PRIMARY_TOPOLOGY_IDS[0], "KEEP"),
    (PRIMARY_TOPOLOGY_IDS[1], "COMPACT"),
    (PRIMARY_TOPOLOGY_IDS[2], "LINE"),
)

CANDIDATE_LOCAL_NODE_FEATURES: Tuple[str, ...] = (
    "candidate_role_offset_spacing",
    "candidate_role_displacement_spacing",
    "candidate_transition_magnitude_spacing",
    "candidate_observation_extent_range",
)


class FD24ModelContractError(ValueError):
    """Model input, output, or schema violates the FD24 local contract."""


def _candidate_feature_indices() -> Tuple[int, ...]:
    indices = []
    for name in CANDIDATE_LOCAL_NODE_FEATURES:
        block = NODE_FEATURE_SLICES[name]
        indices.extend(range(block.start, block.stop))
    return tuple(indices)


CANDIDATE_LOCAL_NODE_FEATURE_INDICES = _candidate_feature_indices()


@dataclass(frozen=True)
class FD24LocalModelBatch:
    """Closed model input around a canonical Phase 4 disjoint graph batch."""

    schema_version: str
    ego_graph_schema_version: str
    ego_feature_schema_sha256: str
    topology_registry_schema_version: str
    graph_batch: BatchedRobotLocalEgoGraphs
    runtime_config_sha256_by_graph: Tuple[str, ...]
    graph_fingerprint_by_graph: Tuple[str, ...]
    # RB16R: (cos, sin) of the mission-to-world orientation, one row per graph.
    # It comes from the same `_mission_axes` transform the ego-graph builder uses
    # and is what makes a WORLD residual output identifiable.
    mission_orientation_cos_sin: torch.Tensor = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.schema_version != FD24_MODEL_INPUT_SCHEMA_VERSION:
            raise FD24ModelContractError("unknown FD24 model-input schema")
        if self.ego_graph_schema_version != EGO_GRAPH_SCHEMA_VERSION:
            raise FD24ModelContractError("model requires rvt-ego-graph/v2")
        if self.ego_feature_schema_sha256 != EGO_GRAPH_FEATURE_SCHEMA_SHA256:
            raise FD24ModelContractError("ego feature-schema hash mismatch")
        if self.topology_registry_schema_version != TOPOLOGY_REGISTRY_SCHEMA_VERSION:
            raise FD24ModelContractError("topology-registry schema mismatch")
        batch = self.graph_batch
        if not isinstance(batch, BatchedRobotLocalEgoGraphs):
            raise FD24ModelContractError("model input requires canonical V2 batching")
        if batch.node_x.ndim != 2 or batch.node_x.shape[1] != NODE_FEATURE_DIM:
            raise FD24ModelContractError("node feature width is incompatible")
        if batch.edge_attr.ndim != 2 or batch.edge_attr.shape[1] != EDGE_FEATURE_DIM:
            raise FD24ModelContractError("edge feature width is incompatible")
        if batch.node_feature_valid_mask.shape != batch.node_x.shape:
            raise FD24ModelContractError("node feature-validity mask is missing")
        if batch.edge_feature_valid_mask.shape != batch.edge_attr.shape:
            raise FD24ModelContractError("edge feature-validity mask is missing")
        orientation = self.mission_orientation_cos_sin
        if not isinstance(orientation, torch.Tensor):
            raise FD24ModelContractError(
                "the WORLD residual output requires a declared mission orientation")
        graphs = len(self.graph_fingerprint_by_graph)
        if orientation.shape != (graphs, 2):
            raise FD24ModelContractError("mission orientation shape is invalid")
        if not bool(torch.isfinite(orientation).all()):
            raise FD24ModelContractError("mission orientation must be finite")
        norms = torch.linalg.vector_norm(orientation, dim=1)
        if not bool((norms - 1.0).abs().max() < 1e-6):
            raise FD24ModelContractError("mission orientation must be a unit vector")
        if batch.node_feature_valid_mask.dtype != torch.bool:
            raise FD24ModelContractError("node feature-validity mask must be Boolean")
        if batch.edge_feature_valid_mask.dtype != torch.bool:
            raise FD24ModelContractError("edge feature-validity mask must be Boolean")
        if batch.n_graphs < 1 or batch.root_index.shape != (batch.n_graphs,):
            raise FD24ModelContractError("one root index per graph is required")
        if len(self.runtime_config_sha256_by_graph) != batch.n_graphs:
            raise FD24ModelContractError("runtime hash count differs from graph count")
        if len(self.graph_fingerprint_by_graph) != batch.n_graphs:
            raise FD24ModelContractError("fingerprint count differs from graph count")
        if any(len(value) != 64 for value in self.runtime_config_sha256_by_graph):
            raise FD24ModelContractError("runtime configuration hash is invalid")
        if any(len(value) != 64 for value in self.graph_fingerprint_by_graph):
            raise FD24ModelContractError("graph fingerprint is invalid")
        if not bool(batch.node_valid_mask.all()) or not bool(batch.edge_valid_mask.all()):
            raise FD24ModelContractError(
                "invalid nodes and edges must be omitted, not treated as real"
            )
        if not bool(torch.isfinite(batch.node_x).all()):
            raise FD24ModelContractError("node features must be finite")
        if not bool(torch.isfinite(batch.edge_attr).all()):
            raise FD24ModelContractError("edge features must be finite")
        if not bool((batch.node_kind[batch.root_index] == NODE_SELF).all()):
            raise FD24ModelContractError("every graph root must be a SELF node")
        if batch.edge_index.numel():
            source_graph = batch.graph_index[batch.edge_index[0]]
            target_graph = batch.graph_index[batch.edge_index[1]]
            if not torch.equal(source_graph, target_graph):
                raise FD24ModelContractError("cross-ego-graph edge is prohibited")
        vocabulary_ids = {item[0] for item in FD24_TOPOLOGY_VOCABULARY}
        if not set(batch.candidate_topology_id.tolist()) <= vocabulary_ids:
            raise FD24ModelContractError("candidate topology vocabulary mismatch")
        candidate_block = NODE_FEATURE_SLICES["candidate_topology_onehot"]
        candidate_values = batch.node_x[batch.root_index, candidate_block]
        candidate_masks = batch.node_feature_valid_mask[
            batch.root_index, candidate_block
        ]
        expected_candidate_values = torch.stack([
            (batch.candidate_topology_id == topology_id).to(batch.node_x.dtype)
            for topology_id in PRIMARY_TOPOLOGY_IDS
        ], dim=1)
        if not bool(candidate_masks.all()) or not torch.equal(
            candidate_values, expected_candidate_values
        ):
            raise FD24ModelContractError(
                "root candidate features conflict with candidate topology ID"
            )

    @property
    def n_graphs(self) -> int:
        return self.graph_batch.n_graphs


def prepare_fd24_model_batch(
    graphs: Sequence[RobotLocalEgoGraph],
) -> FD24LocalModelBatch:
    """Validate and canonically batch independent robot-local V2 records."""
    if isinstance(graphs, (str, bytes)) or not isinstance(graphs, Sequence):
        raise TypeError("FD24 model batching requires a sequence of local graphs")
    if not graphs:
        raise FD24ModelContractError("at least one local graph is required")
    for graph in graphs:
        if not isinstance(graph, RobotLocalEgoGraph):
            raise FD24ModelContractError(
                "legacy global or untyped graph cannot enter the FD24 model"
            )
        if graph.schema_version != EGO_GRAPH_SCHEMA_VERSION:
            raise FD24ModelContractError("ego graph schema mismatch")
        if graph.feature_schema_sha256 != EGO_GRAPH_FEATURE_SCHEMA_SHA256:
            raise FD24ModelContractError("ego feature-schema hash mismatch")
        if graph.topology_registry_schema_version != TOPOLOGY_REGISTRY_SCHEMA_VERSION:
            raise FD24ModelContractError("topology registry mismatch")
    graph_batch = batch_robot_local_ego_graphs(graphs)
    order = graph_batch.canonical_to_input_order
    ordered = tuple(graphs[index] for index in order)
    return FD24LocalModelBatch(
        schema_version=FD24_MODEL_INPUT_SCHEMA_VERSION,
        ego_graph_schema_version=EGO_GRAPH_SCHEMA_VERSION,
        ego_feature_schema_sha256=EGO_GRAPH_FEATURE_SCHEMA_SHA256,
        topology_registry_schema_version=TOPOLOGY_REGISTRY_SCHEMA_VERSION,
        graph_batch=graph_batch,
        runtime_config_sha256_by_graph=tuple(
            graph.runtime_config_sha256 for graph in ordered
        ),
        graph_fingerprint_by_graph=tuple(graph.fingerprint() for graph in ordered),
        mission_orientation_cos_sin=torch.tensor(
            [list(graph.mission_orientation_cos_sin) for graph in ordered],
            dtype=torch.float32),
    )


@dataclass(frozen=True)
class RVTLocalCandidateOutput:
    observer_robot_id: int
    candidate_topology_id: int
    recoverability_logit: torch.Tensor
    recoverability_probability: torch.Tensor
    residual_action: torch.Tensor
    graph_fingerprint: str
    schema_version: str
    validity: bool
    encoder_embedding_optional: Optional[torch.Tensor] = None


@dataclass(frozen=True)
class RVTLocalBatchOutput:
    schema_version: str
    model_schema_version: str
    observer_robot_id: torch.Tensor
    candidate_topology_id: torch.Tensor
    recoverability_logit: torch.Tensor
    recoverability_probability: torch.Tensor
    residual_action: torch.Tensor
    validity: torch.Tensor
    graph_batch_mapping: Tuple[int, ...]
    graph_fingerprint: Tuple[str, ...]
    encoder_embedding_optional: Optional[torch.Tensor] = None

    def __post_init__(self) -> None:
        if self.schema_version != FD24_MODEL_OUTPUT_SCHEMA_VERSION:
            raise FD24ModelContractError("unknown FD24 model-output schema")
        if self.model_schema_version != FD24_MODEL_SCHEMA_VERSION:
            raise FD24ModelContractError("FD24 model schema mismatch")
        count = int(self.observer_robot_id.numel())
        if self.observer_robot_id.shape != (count,):
            raise FD24ModelContractError("observer ID output shape is invalid")
        if self.candidate_topology_id.shape != (count,):
            raise FD24ModelContractError("candidate ID output shape is invalid")
        if self.recoverability_logit.shape != (count,):
            raise FD24ModelContractError("recoverability logit shape is invalid")
        if self.recoverability_probability.shape != (count,):
            raise FD24ModelContractError("recoverability probability shape is invalid")
        if self.residual_action.shape != (
            count,
            len(ROBOT_LOCAL_ACTION_COMPONENTS),
        ):
            raise FD24ModelContractError("residual output is not one action per graph")
        if self.validity.shape != (count,) or self.validity.dtype != torch.bool:
            raise FD24ModelContractError("output validity shape is invalid")
        if len(self.graph_batch_mapping) != count:
            raise FD24ModelContractError("graph batch mapping count is invalid")
        if len(self.graph_fingerprint) != count:
            raise FD24ModelContractError("graph fingerprint count is invalid")
        finite = (
            bool(torch.isfinite(self.recoverability_logit).all())
            and bool(torch.isfinite(self.recoverability_probability).all())
            and bool(torch.isfinite(self.residual_action).all())
        )
        if not finite or not bool(self.validity.all()):
            raise FD24ModelContractError("FD24 output is not finite and valid")

    @property
    def candidate_outputs(self) -> Tuple[RVTLocalCandidateOutput, ...]:
        embeddings = self.encoder_embedding_optional
        return tuple(
            RVTLocalCandidateOutput(
                observer_robot_id=int(self.observer_robot_id[index]),
                candidate_topology_id=int(self.candidate_topology_id[index]),
                recoverability_logit=self.recoverability_logit[index],
                recoverability_probability=self.recoverability_probability[index],
                residual_action=self.residual_action[index],
                graph_fingerprint=self.graph_fingerprint[index],
                schema_version=self.schema_version,
                validity=bool(self.validity[index]),
                encoder_embedding_optional=(
                    None if embeddings is None else embeddings[index]
                ),
            )
            for index in range(self.observer_robot_id.numel())
        )


def _typed_projection(
    local_features: torch.Tensor,
    local_type_ids: torch.Tensor,
    projections: nn.ModuleList,
) -> torch.Tensor:
    candidates = torch.stack(
        [projection(local_features) for projection in projections],
        dim=1,
    )
    if local_type_ids.ndim != 1 or local_type_ids.shape[0] != local_features.shape[0]:
        raise FD24ModelContractError("typed projection kind shape is invalid")
    if local_type_ids.numel() and (
        int(local_type_ids.min()) < 0 or int(local_type_ids.max()) >= len(projections)
    ):
        raise FD24ModelContractError("typed projection kind is unknown")
    gather_index = local_type_ids.view(-1, 1, 1).expand(-1, 1, candidates.shape[-1])
    return candidates.gather(1, gather_index).squeeze(1)


def _edge_softmax_by_destination(
    scores: torch.Tensor,
    local_edge_destination: torch.Tensor,
    node_count: int,
) -> torch.Tensor:
    if scores.numel() == 0:
        return scores
    group_max = torch.full(
        (node_count,),
        float("-inf"),
        dtype=scores.dtype,
        device=scores.device,
    )
    group_max.scatter_reduce_(
        0,
        local_edge_destination,
        scores.detach(),
        reduce="amax",
        include_self=False,
    )
    shifted = torch.exp(scores - group_max[local_edge_destination])
    denominator = shifted.new_zeros(node_count).index_add_(
        0, local_edge_destination, shifted
    )
    return shifted / denominator[local_edge_destination].clamp_min(
        torch.finfo(scores.dtype).tiny
    )


class FD24LocalMessagePassingBlock(nn.Module):
    """One local typed-edge attention update with per-node normalization."""

    def __init__(self, config: FD24ModelConfig) -> None:
        super().__init__()
        hidden = config.hidden_dimension
        self.attention_slope = config.attention_leaky_relu_slope
        self.message = nn.Sequential(
            nn.Linear(hidden * 3, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
        )
        self.attention = nn.Linear(hidden, 1, bias=False)
        self.update = nn.Sequential(
            nn.Linear(hidden * 2, hidden),
            nn.ReLU(),
            nn.Dropout(config.dropout_probability),
            nn.Linear(hidden, hidden),
        )
        self.normalization = nn.LayerNorm(hidden)

    def forward(
        self,
        node_hidden: torch.Tensor,
        edge_index: torch.Tensor,
        edge_hidden: torch.Tensor,
    ) -> torch.Tensor:
        if edge_index.shape[1] == 0:
            return self.normalization(node_hidden)
        source, destination = edge_index
        message = self.message(torch.cat(
            [node_hidden[source], node_hidden[destination], edge_hidden], dim=-1
        ))
        scores = F.leaky_relu(
            self.attention(message).squeeze(-1),
            negative_slope=self.attention_slope,
        )
        weights = _edge_softmax_by_destination(
            scores, destination, node_hidden.shape[0]
        )
        aggregate = torch.zeros_like(node_hidden).index_add_(
            0, destination, message * weights.unsqueeze(-1)
        )
        update = self.update(torch.cat([node_hidden, aggregate], dim=-1))
        return self.normalization(node_hidden + update)


class FD24LocalGraphEncoder(nn.Module):
    """Shared typed encoder with root readout and no graph-level pooling."""

    def __init__(self, config: FD24ModelConfig) -> None:
        super().__init__()
        hidden = config.hidden_dimension
        node_input = NODE_FEATURE_DIM * 2
        edge_input = EDGE_FEATURE_DIM * 2
        self.node_type_projections = nn.ModuleList([
            nn.Sequential(nn.Linear(node_input, hidden), nn.ReLU())
            for _ in NODE_KINDS
        ])
        self.edge_type_projections = nn.ModuleList([
            nn.Sequential(nn.Linear(edge_input, hidden), nn.ReLU())
            for _ in EDGE_TYPES
        ])
        self.message_blocks = nn.ModuleList([
            FD24LocalMessagePassingBlock(config)
            for _ in range(config.message_passing_blocks)
        ])

    def forward(self, local_batch: FD24LocalModelBatch) -> torch.Tensor:
        if not isinstance(local_batch, FD24LocalModelBatch):
            raise FD24ModelContractError(
                "encoder accepts only closed robot-local FD24 batches"
            )
        batch = local_batch.graph_batch
        node_mask = batch.node_feature_valid_mask.to(batch.node_x.dtype)
        edge_mask = batch.edge_feature_valid_mask.to(batch.edge_attr.dtype)
        node_input = torch.cat([batch.node_x * node_mask, node_mask], dim=-1)
        edge_input = torch.cat([batch.edge_attr * edge_mask, edge_mask], dim=-1)
        node_hidden = _typed_projection(
            node_input, batch.node_kind, self.node_type_projections
        )
        edge_hidden = _typed_projection(
            edge_input, batch.edge_type, self.edge_type_projections
        )
        for block in self.message_blocks:
            node_hidden = block(node_hidden, batch.edge_index, edge_hidden)
        return node_hidden[batch.root_index]


class FD24CandidateConditioner(nn.Module):
    """Fuse root state with explicit observer-local candidate metadata."""

    def __init__(self, config: FD24ModelConfig) -> None:
        super().__init__()
        hidden = config.hidden_dimension
        candidate_dim = config.candidate_embedding_dimension
        self.topology_embedding = nn.Embedding(
            len(FD24_TOPOLOGY_VOCABULARY), candidate_dim
        )
        local_width = len(CANDIDATE_LOCAL_NODE_FEATURE_INDICES)
        self.local_metadata_projection = nn.Sequential(
            nn.Linear(local_width * 2, candidate_dim),
            nn.ReLU(),
        )
        self.fusion = nn.Sequential(
            nn.Linear(hidden + candidate_dim * 2, hidden),
            nn.ReLU(),
            nn.Dropout(config.dropout_probability),
            nn.Linear(hidden, hidden),
            nn.LayerNorm(hidden),
        )
        self.register_buffer(
            "topology_vocabulary_ids",
            torch.tensor(
                [item[0] for item in FD24_TOPOLOGY_VOCABULARY],
                dtype=torch.int64,
            ),
            persistent=True,
        )

    def _vocabulary_indices(self, topology_ids: torch.Tensor) -> torch.Tensor:
        matches = topology_ids.view(-1, 1) == self.topology_vocabulary_ids.view(1, -1)
        if not bool((matches.sum(dim=1) == 1).all()):
            raise FD24ModelContractError("candidate topology ID is ambiguous or unknown")
        return matches.to(torch.int64).argmax(dim=1)

    def forward(
        self,
        root_hidden: torch.Tensor,
        local_batch: FD24LocalModelBatch,
    ) -> torch.Tensor:
        batch = local_batch.graph_batch
        roots = batch.root_index
        indices = torch.tensor(
            CANDIDATE_LOCAL_NODE_FEATURE_INDICES,
            dtype=torch.int64,
            device=batch.node_x.device,
        )
        values = batch.node_x[roots].index_select(1, indices)
        masks = batch.node_feature_valid_mask[roots].index_select(1, indices)
        mask_values = masks.to(values.dtype)
        local = self.local_metadata_projection(torch.cat(
            [values * mask_values, mask_values], dim=-1
        ))
        vocabulary_index = self._vocabulary_indices(batch.candidate_topology_id)
        topology = self.topology_embedding(vocabulary_index)
        return self.fusion(torch.cat([root_hidden, topology, local], dim=-1))


class FD24RecoverabilityHead(nn.Module):
    """One robot-local candidate-evidence logit, never a global decision."""

    def __init__(self, hidden_dimension: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(hidden_dimension, hidden_dimension),
            nn.ReLU(),
            nn.Linear(hidden_dimension, 1),
        )

    def forward(self, conditioned: torch.Tensor) -> torch.Tensor:
        return self.network(conditioned).squeeze(-1)


MISSION_ORIENTATION_CONTEXT_DIM = 2


class FD24ResidualActionHead(nn.Module):
    """Raw robot-local residual in the WORLD frame; the parent applies the bound.

    RB16R: the encoder is mission-frame, so the conditioned representation alone
    is provably invariant to a rigid rotation of the scene while the WORLD target
    is not. The head therefore also receives the mission-to-world orientation
    `(cos, sin)` -- the same `_mission_axes` quantity the ego-graph builder
    already computes from the robot's own `RobotView.mission_dir`. Nothing else
    in the architecture sees it.
    """

    def __init__(self, hidden_dimension: int, action_dimension: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(hidden_dimension + MISSION_ORIENTATION_CONTEXT_DIM,
                      hidden_dimension),
            nn.ReLU(),
            nn.Linear(hidden_dimension, action_dimension),
        )

    def forward(self, conditioned: torch.Tensor,
                mission_orientation_cos_sin: torch.Tensor) -> torch.Tensor:
        if mission_orientation_cos_sin.shape != (conditioned.shape[0],
                                                 MISSION_ORIENTATION_CONTEXT_DIM):
            raise FD24ModelContractError(
                "residual head requires one mission orientation per row")
        return self.network(torch.cat(
            [conditioned, mission_orientation_cos_sin.to(conditioned.dtype)], dim=-1))


def bounded_residual_action(
    raw_residual: torch.Tensor,
    residual_limits: torch.Tensor,
) -> torch.Tensor:
    if raw_residual.ndim != 2:
        raise FD24ModelContractError("raw residual must have shape (graphs, action_dim)")
    if residual_limits.ndim != 1 or residual_limits.shape[0] != raw_residual.shape[1]:
        raise FD24ModelContractError("residual bound dimension is incompatible")
    if not bool(torch.isfinite(raw_residual).all()):
        raise FD24ModelContractError("raw residual must be finite")
    if not bool(torch.isfinite(residual_limits).all()) or not bool(
        (residual_limits > 0.0).all()
    ):
        raise FD24ModelContractError("residual limits must be positive and finite")
    return torch.tanh(raw_residual) * residual_limits.view(1, -1)


class RVTFD24LocalModel(nn.Module):
    """Primary shared encoder plus local evidence and residual heads."""

    def __init__(
        self,
        model_config: FD24ModelConfig,
        runtime_config: RuntimeConfig,
    ) -> None:
        super().__init__()
        if not isinstance(model_config, FD24ModelConfig):
            raise TypeError("FD24 model requires FD24ModelConfig")
        if not isinstance(runtime_config, RuntimeConfig):
            raise TypeError("FD24 model requires immutable RuntimeConfig")
        self.model_schema_version = FD24_MODEL_SCHEMA_VERSION
        self.model_config = model_config
        self.encoder = FD24LocalGraphEncoder(model_config)
        self.candidate_conditioner = FD24CandidateConditioner(model_config)
        self.recoverability_head = FD24RecoverabilityHead(
            model_config.hidden_dimension
        )
        self.residual_action_head = FD24ResidualActionHead(
            model_config.hidden_dimension,
            model_config.action_dimension,
        )
        self.register_buffer(
            "residual_action_limits",
            torch.tensor(
                residual_action_limits(model_config, runtime_config),
                dtype=torch.float32,
            ),
            persistent=True,
        )

    @property
    def action_dimension(self) -> int:
        return self.model_config.action_dimension

    def conditioned_representation(
        self,
        local_batch: FD24LocalModelBatch,
    ) -> torch.Tensor:
        root = self.encoder(local_batch)
        return self.candidate_conditioner(root, local_batch)

    def forward(
        self,
        local_batch: FD24LocalModelBatch,
        *,
        include_diagnostic_embedding: bool = False,
    ) -> RVTLocalBatchOutput:
        if include_diagnostic_embedding and not (
            self.model_config.diagnostic_embedding_enabled
        ):
            raise FD24ModelContractError(
                "diagnostic embedding output is disabled by model configuration"
            )
        conditioned = self.conditioned_representation(local_batch)
        logits = self.recoverability_head(conditioned)
        probability = torch.sigmoid(logits)
        raw_residual = self.residual_action_head(
            conditioned, local_batch.mission_orientation_cos_sin)
        residual = bounded_residual_action(
            raw_residual, self.residual_action_limits
        )
        batch = local_batch.graph_batch
        finite = (
            torch.isfinite(logits)
            & torch.isfinite(probability)
            & torch.isfinite(residual).all(dim=1)
        )
        return RVTLocalBatchOutput(
            schema_version=FD24_MODEL_OUTPUT_SCHEMA_VERSION,
            model_schema_version=FD24_MODEL_SCHEMA_VERSION,
            observer_robot_id=batch.observer_robot_id.clone(),
            candidate_topology_id=batch.candidate_topology_id.clone(),
            recoverability_logit=logits,
            recoverability_probability=probability,
            residual_action=residual,
            validity=finite,
            graph_batch_mapping=batch.canonical_to_input_order,
            graph_fingerprint=local_batch.graph_fingerprint_by_graph,
            encoder_embedding_optional=(
                conditioned if include_diagnostic_embedding else None
            ),
        )

    def parameter_counts(self) -> dict[str, int]:
        groups = {
            "encoder": self.encoder,
            "candidate_conditioner": self.candidate_conditioner,
            "recoverability_head": self.recoverability_head,
            "residual_action_head": self.residual_action_head,
        }
        report = {
            name: sum(parameter.numel() for parameter in module.parameters())
            for name, module in groups.items()
        }
        report["total"] = sum(parameter.numel() for parameter in self.parameters())
        return report


class DirectLocalActionAblationHead(nn.Module):
    """Optional full-action ablation over the same conditioned local embedding."""

    ablation_name = "direct_local_action_ablation"

    def __init__(
        self,
        hidden_dimension: int,
        action_limits: Sequence[float],
    ) -> None:
        super().__init__()
        limits = tuple(float(value) for value in action_limits)
        if len(limits) != len(ROBOT_LOCAL_ACTION_COMPONENTS):
            raise FD24ModelContractError("direct-action bound dimension is invalid")
        if any(not math.isfinite(value) or value <= 0.0 for value in limits):
            raise FD24ModelContractError("direct-action limits must be positive")
        self.network = nn.Sequential(
            nn.Linear(hidden_dimension, hidden_dimension),
            nn.ReLU(),
            nn.Linear(hidden_dimension, len(limits)),
        )
        self.register_buffer(
            "action_limits",
            torch.tensor(limits, dtype=torch.float32),
            persistent=True,
        )

    def forward(self, conditioned_local_embedding: torch.Tensor) -> torch.Tensor:
        raw = self.network(conditioned_local_embedding)
        return torch.tanh(raw) * self.action_limits.view(1, -1)
