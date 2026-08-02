"""Authoritative robot-local ego graph V2 for future deployable inference.

The builder accepts one :class:`RobotView`, one robot-local topology slice, an
immutable runtime configuration, and a candidate topology ID. It has no input
for joint state, complete graphs, complete templates, maps, labels, or outcomes.

The preserved Phase 1 selector continues to consume ``ego_graph.py`` V1 until
Phase 5 reconstructs its heads. This module changes no action or topology
decision in Phase 4.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
import torch

from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from ..topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    PRIMARY_TOPOLOGY_IDS,
    TOPOLOGY_REGISTRY_SCHEMA_VERSION,
    PersistentRoleSet,
    construct_primary_templates,
)
from .system_model import CentralizedAccessError, NeighbourRecord, RobotView


EGO_GRAPH_SCHEMA_VERSION = "rvt-ego-graph/v2"
EGO_GRAPH_NORMALIZATION_VERSION = "rvt-ego-normalization/v1"
EGO_GRAPH_SERIALIZATION_VERSION = "rvt-ego-graph-serialization/v1"

NODE_SELF = 0
NODE_PEER = 1
NODE_OBSTACLE = 2
NODE_KINDS: Tuple[int, ...] = (NODE_SELF, NODE_PEER, NODE_OBSTACLE)

EDGE_SELF_TO_PEER = 0
EDGE_PEER_TO_SELF = 1
EDGE_SELF_TO_OBSTACLE = 2
EDGE_OBSTACLE_TO_SELF = 3
EDGE_TYPES: Tuple[int, ...] = (
    EDGE_SELF_TO_PEER,
    EDGE_PEER_TO_SELF,
    EDGE_SELF_TO_OBSTACLE,
    EDGE_OBSTACLE_TO_SELF,
)

_EPS = 1e-9
Vec2 = Tuple[float, float]


class EgoGraphV2Error(ValueError):
    """Invalid local graph input, schema, or tensor structure."""


class EgoGraphSerializationError(EgoGraphV2Error):
    """Serialized graph is unknown, incomplete, inconsistent, or tampered."""


class EgoGraphMigrationError(EgoGraphV2Error):
    """A legacy graph cannot be reinterpreted safely as V2."""


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    width: int
    node_or_edge: str
    applies_to: Tuple[int, ...]
    units: str
    normalization: str
    runtime_source: str
    missing_data: str


NODE_FEATURE_DEFINITIONS: Tuple[FeatureDefinition, ...] = (
    FeatureDefinition("node_kind_onehot", 3, "node", NODE_KINDS, "onehot", "none", "local schema", "always valid"),
    FeatureDefinition("relative_position_spacing", 2, "node", NODE_KINDS, "dimensionless", "mission-frame vector / nominal spacing", "own origin, peer message, or local obstacle", "self is exact zero"),
    FeatureDefinition("relative_velocity_speed", 2, "node", (NODE_PEER, NODE_OBSTACLE), "dimensionless", "mission-frame relative velocity / maximum speed", "fresh peer message or local obstacle tracker", "zero with feature mask false"),
    FeatureDefinition("distance_range", 1, "node", NODE_KINDS, "dimensionless", "peer range / R_comm or obstacle clearance / R_obs", "local message or sensor", "self is exact zero"),
    FeatureDefinition("bearing_cos_sin", 2, "node", (NODE_PEER, NODE_OBSTACLE), "dimensionless", "mission-frame unit bearing", "local relative position", "zero with feature mask false at zero range"),
    FeatureDefinition("committed_topology_onehot", 3, "node", (NODE_SELF, NODE_PEER), "onehot", "KEEP, COMPACT, LINE scientific order", "local memory or peer message", "invalid topology rejects peer or graph"),
    FeatureDefinition("candidate_topology_onehot", 3, "node", (NODE_SELF,), "onehot", "KEEP, COMPACT, LINE scientific order", "candidate query", "always valid on root"),
    FeatureDefinition("candidate_role_offset_spacing", 2, "node", (NODE_SELF, NODE_PEER), "dimensionless", "template-frame offset / nominal spacing", "robot-local topology slice", "peer value masked unless candidate nominal neighbour"),
    FeatureDefinition("candidate_role_displacement_spacing", 2, "node", (NODE_SELF,), "dimensionless", "candidate minus committed own role / nominal spacing", "robot-local topology slice", "always valid on root"),
    FeatureDefinition("candidate_transition_magnitude_spacing", 1, "node", (NODE_SELF,), "dimensionless", "own candidate displacement norm / nominal spacing", "robot-local topology slice", "always valid on root"),
    FeatureDefinition("candidate_observation_extent_range", 1, "node", (NODE_SELF,), "dimensionless", "own lateral transition envelope / R_obs", "local geometry and immutable safety configuration", "always valid on root"),
    FeatureDefinition("goal_vector_spacing", 2, "node", (NODE_SELF,), "dimensionless", "mission-frame goal-relative vector / nominal spacing", "own pose and shared goal", "always valid on root"),
    FeatureDefinition("goal_distance_spacing", 1, "node", (NODE_SELF,), "dimensionless", "goal distance / nominal spacing", "own pose and shared goal", "always valid on root"),
    FeatureDefinition("self_velocity_speed", 2, "node", (NODE_SELF,), "dimensionless", "mission-frame own velocity / maximum speed", "own odometry", "always valid on root"),
    FeatureDefinition("local_progress_spacing", 1, "node", (NODE_SELF,), "dimensionless", "own history progress / nominal spacing", "local lifecycle memory", "zero is a valid value"),
    FeatureDefinition("decision_age_reference", 1, "node", (NODE_SELF,), "dimensionless", "steps since decision / configured reference steps", "local lifecycle memory", "clamped to [0,1]"),
    FeatureDefinition("peer_message_age_limit", 1, "node", (NODE_PEER,), "dimensionless", "message age / maximum message age", "fresh one-hop message", "stale messages omitted"),
    FeatureDefinition("peer_role_known", 1, "node", (NODE_PEER,), "boolean", "none", "robot-local candidate topology slice", "zero when peer is not a candidate nominal neighbour"),
    FeatureDefinition("peer_topology_conflict", 1, "node", (NODE_PEER,), "boolean", "none", "own and sender committed topology IDs", "zero when commitments agree"),
    FeatureDefinition("obstacle_radius_range", 1, "node", (NODE_OBSTACLE,), "dimensionless", "radius / R_obs", "local obstacle primitive", "invalid radius omits node"),
    FeatureDefinition("obstacle_confidence", 1, "node", (NODE_OBSTACLE,), "probability", "already [0,1]", "local sensor", "invalid confidence omits node"),
    FeatureDefinition("obstacle_age_control_period", 1, "node", (NODE_OBSTACLE,), "dimensionless", "observation age / control period", "local sensor timestamp", "older than one control period omitted"),
)

EDGE_FEATURE_DEFINITIONS: Tuple[FeatureDefinition, ...] = (
    FeatureDefinition("edge_type_onehot", 4, "edge", EDGE_TYPES, "onehot", "none", "local graph construction", "always valid"),
    FeatureDefinition("relative_position_spacing", 2, "edge", EDGE_TYPES, "dimensionless", "destination minus source in mission frame / nominal spacing", "local message or sensor", "always valid"),
    FeatureDefinition("relative_velocity_speed", 2, "edge", EDGE_TYPES, "dimensionless", "destination minus source velocity / maximum speed", "local message or sensor", "zero with feature mask false"),
    FeatureDefinition("distance_range", 1, "edge", EDGE_TYPES, "dimensionless", "communication range or observation range", "local message or sensor", "always valid"),
    FeatureDefinition("bearing_cos_sin", 2, "edge", EDGE_TYPES, "dimensionless", "unit edge direction in mission frame", "local geometry", "zero with feature mask false at zero range"),
    FeatureDefinition("nominal_formation_relation", 1, "edge", (EDGE_SELF_TO_PEER, EDGE_PEER_TO_SELF), "boolean", "none", "robot-local candidate topology slice", "zero for non-nominal peers"),
    FeatureDefinition("desired_pairwise_offset_spacing", 2, "edge", (EDGE_SELF_TO_PEER, EDGE_PEER_TO_SELF), "dimensionless", "candidate desired offset / nominal spacing", "robot-local candidate topology slice", "masked for non-nominal peers"),
    FeatureDefinition("formation_residual_spacing", 2, "edge", (EDGE_SELF_TO_PEER, EDGE_PEER_TO_SELF), "dimensionless", "actual minus candidate desired offset / nominal spacing", "fresh peer state and local topology slice", "masked for non-nominal peers"),
    FeatureDefinition("candidate_topology_onehot", 3, "edge", (EDGE_SELF_TO_PEER, EDGE_PEER_TO_SELF), "onehot", "KEEP, COMPACT, LINE scientific order", "candidate query", "masked on obstacle edges"),
)


def _feature_layout(
    definitions: Sequence[FeatureDefinition],
) -> Tuple[Dict[str, slice], int]:
    layout: Dict[str, slice] = {}
    cursor = 0
    for definition in definitions:
        if definition.name in layout:
            raise RuntimeError(f"duplicate feature name {definition.name}")
        layout[definition.name] = slice(cursor, cursor + definition.width)
        cursor += definition.width
    return layout, cursor


NODE_FEATURE_SLICES, NODE_FEATURE_DIM = _feature_layout(NODE_FEATURE_DEFINITIONS)
EDGE_FEATURE_SLICES, EDGE_FEATURE_DIM = _feature_layout(EDGE_FEATURE_DEFINITIONS)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _feature_schema_payload() -> Dict[str, object]:
    return {
        "schema_version": EGO_GRAPH_SCHEMA_VERSION,
        "normalization_version": EGO_GRAPH_NORMALIZATION_VERSION,
        "primary_topology_order": list(PRIMARY_TOPOLOGY_IDS),
        "node_features": [asdict(item) for item in NODE_FEATURE_DEFINITIONS],
        "edge_features": [asdict(item) for item in EDGE_FEATURE_DEFINITIONS],
    }


EGO_GRAPH_FEATURE_SCHEMA_SHA256 = hashlib.sha256(
    _canonical_json(_feature_schema_payload()).encode("ascii")
).hexdigest()


@dataclass(frozen=True)
class LocalFormationNeighbour:
    peer_robot_id: int
    peer_role_id: str
    candidate_role_offset_meters: Vec2
    desired_offset_from_observer_meters: Vec2


@dataclass(frozen=True)
class LocalCandidateTopologySlice:
    topology_id: int
    own_role_offset_meters: Vec2
    formation_neighbours: Tuple[LocalFormationNeighbour, ...]

    def neighbour(self, peer_robot_id: int) -> Optional[LocalFormationNeighbour]:
        for item in self.formation_neighbours:
            if item.peer_robot_id == int(peer_robot_id):
                return item
        return None


@dataclass(frozen=True)
class RobotLocalTopologyMetadata:
    """Static mission-setup slice; contains no complete topology template."""

    topology_registry_schema_version: str
    observer_robot_id: int
    observer_role_id: str
    team_size: int
    candidates: Tuple[LocalCandidateTopologySlice, ...]

    def candidate(self, topology_id: int) -> LocalCandidateTopologySlice:
        for item in self.candidates:
            if item.topology_id == int(topology_id):
                return item
        raise EgoGraphV2Error(f"topology {topology_id} is unavailable locally")


def _integer_robot_id(robot_key: str) -> int:
    prefix = "int:"
    if not robot_key.startswith(prefix):
        raise EgoGraphV2Error(
            "the current RobotView adapter requires integer robot keys; "
            "string-key transport is not implemented"
        )
    return int(robot_key[len(prefix):])


def prepare_robot_local_topology_metadata(
    role_set: PersistentRoleSet,
    root_key: object,
    formation_config: object,
) -> RobotLocalTopologyMetadata:
    """Mission-setup boundary that reduces full static templates to one slice."""
    observer = role_set.role_for_robot(root_key)
    observer_robot_id = _integer_robot_id(observer.robot_key)
    templates = construct_primary_templates(formation_config, role_set=role_set)
    by_role = {role.role_id: role for role in role_set.roles}
    candidates = []
    for template in templates:
        own = template.offset(observer.role_id)
        neighbours = []
        for peer_role_id in template.neighbour_role_ids(observer.role_id):
            peer_role = by_role[peer_role_id]
            peer_offset = template.offset(peer_role_id)
            neighbours.append(LocalFormationNeighbour(
                peer_robot_id=_integer_robot_id(peer_role.robot_key),
                peer_role_id=peer_role_id,
                candidate_role_offset_meters=peer_offset,
                desired_offset_from_observer_meters=(
                    float(peer_offset[0] - own[0]),
                    float(peer_offset[1] - own[1]),
                ),
            ))
        candidates.append(LocalCandidateTopologySlice(
            topology_id=template.topology_id,
            own_role_offset_meters=own,
            formation_neighbours=tuple(sorted(
                neighbours, key=lambda item: item.peer_robot_id
            )),
        ))
    return RobotLocalTopologyMetadata(
        topology_registry_schema_version=TOPOLOGY_REGISTRY_SCHEMA_VERSION,
        observer_robot_id=observer_robot_id,
        observer_role_id=observer.role_id,
        team_size=role_set.team_size,
        candidates=tuple(candidates),
    )


@dataclass(frozen=True)
class LocalObstacleObservation:
    """One locally visible obstacle primitive; no map-level identity exists."""

    relative_center_meters: Vec2
    radius_meters: float
    relative_velocity_meters_per_second: Optional[Vec2] = None
    confidence: float = 1.0
    age_seconds: float = 0.0
    valid: bool = True


@dataclass(frozen=True)
class RobotLocalEgoGraph:
    schema_version: str
    normalization_version: str
    feature_schema_sha256: str
    topology_registry_schema_version: str
    runtime_config_sha256: str
    observer_robot_id: int
    observer_role_id: str
    observation_timestamp_seconds: float
    lifecycle_id: int
    committed_topology_id: int
    candidate_topology_id: int
    node_x: torch.Tensor
    node_feature_valid_mask: torch.Tensor
    node_valid_mask: torch.Tensor
    node_kind: torch.Tensor
    node_source_key: Tuple[str, ...]
    edge_index: torch.Tensor
    edge_attr: torch.Tensor
    edge_feature_valid_mask: torch.Tensor
    edge_valid_mask: torch.Tensor
    edge_type: torch.Tensor
    root_index: int = 0

    def __post_init__(self) -> None:
        if self.schema_version != EGO_GRAPH_SCHEMA_VERSION:
            raise EgoGraphV2Error("ego-graph schema mismatch")
        if self.normalization_version != EGO_GRAPH_NORMALIZATION_VERSION:
            raise EgoGraphV2Error("ego-graph normalization mismatch")
        if self.feature_schema_sha256 != EGO_GRAPH_FEATURE_SCHEMA_SHA256:
            raise EgoGraphV2Error("ego-graph feature schema mismatch")
        if self.topology_registry_schema_version != TOPOLOGY_REGISTRY_SCHEMA_VERSION:
            raise EgoGraphV2Error("topology registry schema mismatch")
        if len(self.runtime_config_sha256) != 64:
            raise EgoGraphV2Error("runtime configuration hash is invalid")
        if not math.isfinite(self.observation_timestamp_seconds) or self.observation_timestamp_seconds < 0.0:
            raise EgoGraphV2Error("observation timestamp must be finite and nonnegative")
        if self.lifecycle_id < 0:
            raise EgoGraphV2Error("lifecycle ID must be nonnegative")
        if self.committed_topology_id not in PRIMARY_TOPOLOGY_IDS or self.candidate_topology_id not in PRIMARY_TOPOLOGY_IDS:
            raise EgoGraphV2Error("graph topology ID is not primary")
        if self.node_x.ndim != 2 or self.node_x.shape[1] != NODE_FEATURE_DIM:
            raise EgoGraphV2Error("node tensor has wrong shape")
        n_nodes = int(self.node_x.shape[0])
        if n_nodes < 1 or self.root_index != 0:
            raise EgoGraphV2Error("graph must have root node zero")
        if self.node_feature_valid_mask.shape != self.node_x.shape or self.node_feature_valid_mask.dtype != torch.bool:
            raise EgoGraphV2Error("node feature mask has wrong shape or dtype")
        if self.node_valid_mask.shape != (n_nodes,) or self.node_valid_mask.dtype != torch.bool:
            raise EgoGraphV2Error("node validity mask has wrong shape or dtype")
        if self.node_kind.shape != (n_nodes,) or self.node_kind.dtype != torch.int64:
            raise EgoGraphV2Error("node kind tensor has wrong shape or dtype")
        if len(self.node_source_key) != n_nodes:
            raise EgoGraphV2Error("node source-key count is wrong")
        if int(self.node_kind[0]) != NODE_SELF or int((self.node_kind == NODE_SELF).sum()) != 1:
            raise EgoGraphV2Error("graph must contain exactly one self node at root")
        if not bool(self.node_valid_mask.all()):
            raise EgoGraphV2Error("single graphs omit invalid nodes rather than padding")
        if self.edge_index.ndim != 2 or self.edge_index.shape[0] != 2 or self.edge_index.dtype != torch.int64:
            raise EgoGraphV2Error("edge index has wrong shape or dtype")
        n_edges = int(self.edge_index.shape[1])
        if self.edge_attr.shape != (n_edges, EDGE_FEATURE_DIM):
            raise EgoGraphV2Error("edge tensor has wrong shape")
        if self.edge_feature_valid_mask.shape != self.edge_attr.shape or self.edge_feature_valid_mask.dtype != torch.bool:
            raise EgoGraphV2Error("edge feature mask has wrong shape or dtype")
        if self.edge_valid_mask.shape != (n_edges,) or self.edge_valid_mask.dtype != torch.bool:
            raise EgoGraphV2Error("edge validity mask has wrong shape or dtype")
        if self.edge_type.shape != (n_edges,) or self.edge_type.dtype != torch.int64:
            raise EgoGraphV2Error("edge type tensor has wrong shape or dtype")
        if not bool(self.edge_valid_mask.all()):
            raise EgoGraphV2Error("single graphs omit invalid edges rather than padding")
        if n_edges and (int(self.edge_index.min()) < 0 or int(self.edge_index.max()) >= n_nodes):
            raise EgoGraphV2Error("edge endpoint is outside the graph")
        if not bool(torch.isfinite(self.node_x).all()) or not bool(torch.isfinite(self.edge_attr).all()):
            raise EgoGraphV2Error("graph tensors must be finite")

    @property
    def n_nodes(self) -> int:
        return int(self.node_x.shape[0])

    @property
    def n_edges(self) -> int:
        return int(self.edge_index.shape[1])

    @property
    def n_peer_nodes(self) -> int:
        return int((self.node_kind == NODE_PEER).sum())

    @property
    def n_obstacle_nodes(self) -> int:
        return int((self.node_kind == NODE_OBSTACLE).sum())

    def fingerprint(self) -> str:
        return hashlib.sha256(dump_robot_local_ego_graph(self).encode("ascii")).hexdigest()


def _topology_onehot(topology_id: int) -> Tuple[float, float, float]:
    if int(topology_id) not in PRIMARY_TOPOLOGY_IDS:
        raise EgoGraphV2Error(f"topology {topology_id} is not primary")
    return tuple(
        1.0 if item == int(topology_id) else 0.0
        for item in PRIMARY_TOPOLOGY_IDS
    )  # type: ignore[return-value]


def _mission_axes(mission_direction: Vec2) -> Tuple[Vec2, Vec2]:
    dx, dy = float(mission_direction[0]), float(mission_direction[1])
    norm = math.hypot(dx, dy)
    if not math.isfinite(norm) or norm < _EPS:
        raise EgoGraphV2Error("mission direction must be finite and nonzero")
    longitudinal = (dx / norm, dy / norm)
    lateral = (-longitudinal[1], longitudinal[0])
    return longitudinal, lateral


def _to_mission(vector: Vec2, axes: Tuple[Vec2, Vec2]) -> Vec2:
    x, y = float(vector[0]), float(vector[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise EgoGraphV2Error("local vector must be finite")
    ex, ey = axes
    return (x * ex[0] + y * ex[1], x * ey[0] + y * ey[1])


def _unit(vector: Vec2) -> Vec2:
    norm = math.hypot(vector[0], vector[1])
    if norm < _EPS:
        return (0.0, 0.0)
    return (vector[0] / norm, vector[1] / norm)


def _set_feature(
    row: list[float],
    mask: list[bool],
    layout: object,
    name: str,
    values: Sequence[float],
    *,
    valid: bool = True,
) -> None:
    if not isinstance(layout, Mapping):
        raise TypeError("feature layout must be a local schema mapping")
    block = layout[name]
    if block.stop - block.start != len(values):
        raise RuntimeError(f"feature {name} received wrong width")
    row[block] = [float(value) for value in values]
    mask[block] = [bool(valid)] * len(values)


def _valid_peer_record(
    observer_robot_id: int,
    record: object,
    config: RuntimeConfig,
) -> bool:
    if not isinstance(record, NeighbourRecord):
        return False
    try:
        robot_id = int(record.robot_id)
        age = int(record.message_age_steps)
        committed_mode = int(record.committed_mode)
    except (TypeError, ValueError):
        return False
    if isinstance(record.robot_id, bool) or robot_id < 0 or robot_id == observer_robot_id:
        return False
    if not bool(record.link_valid):
        return False
    if age < 0 or age > config.derived.message_stale_rounds:
        return False
    try:
        dx, dy = float(record.rel_position[0]), float(record.rel_position[1])
    except (TypeError, ValueError, IndexError):
        return False
    if not math.isfinite(dx) or not math.isfinite(dy):
        return False
    if math.hypot(dx, dy) > config.communication.communication_range_meters + 1e-9:
        return False
    if committed_mode not in PRIMARY_TOPOLOGY_IDS:
        return False
    return True


def _peer_signature(record: NeighbourRecord) -> Tuple[object, ...]:
    velocity: object
    if record.rel_velocity is None:  # type: ignore[comparison-overlap]
        velocity = None
    else:
        try:
            velocity = (float(record.rel_velocity[0]), float(record.rel_velocity[1]))
        except (TypeError, ValueError, IndexError):
            velocity = None
    return (
        int(record.robot_id),
        int(record.message_age_steps),
        float(record.rel_position[0]),
        float(record.rel_position[1]),
        velocity,
        int(record.committed_mode),
        int(record.epoch_id),
        bool(record.link_valid),
    )


def _canonical_peers(view: RobotView, config: RuntimeConfig) -> Tuple[NeighbourRecord, ...]:
    grouped: Dict[int, list[NeighbourRecord]] = {}
    for record in view.neighbours:
        if _valid_peer_record(int(view.robot_id), record, config):
            grouped.setdefault(int(record.robot_id), []).append(record)
    admitted = []
    for robot_id in sorted(grouped):
        records = grouped[robot_id]
        freshest_age = min(int(item.message_age_steps) for item in records)
        freshest = [item for item in records if int(item.message_age_steps) == freshest_age]
        signatures = {_peer_signature(item) for item in freshest}
        if len(signatures) != 1:
            continue
        admitted.append(freshest[0])
    return tuple(admitted)


def _coerce_obstacle(entry: object) -> Optional[LocalObstacleObservation]:
    if isinstance(entry, LocalObstacleObservation):
        return entry
    if isinstance(entry, Sequence) and not isinstance(entry, (str, bytes)):
        if len(entry) == 3:
            return LocalObstacleObservation(
                (float(entry[0]), float(entry[1])), float(entry[2])
            )
        if len(entry) == 5:
            return LocalObstacleObservation(
                (float(entry[0]), float(entry[1])),
                float(entry[2]),
                (float(entry[3]), float(entry[4])),
            )
    return None


def _obstacle_signature(item: LocalObstacleObservation) -> Tuple[object, ...]:
    velocity = item.relative_velocity_meters_per_second
    return (
        float(item.relative_center_meters[0]),
        float(item.relative_center_meters[1]),
        float(item.radius_meters),
        None if velocity is None else (float(velocity[0]), float(velocity[1])),
        float(item.confidence),
        float(item.age_seconds),
        bool(item.valid),
    )


def _canonical_obstacles(
    entries: Sequence[object], config: RuntimeConfig,
) -> Tuple[LocalObstacleObservation, ...]:
    unique: Dict[Tuple[object, ...], LocalObstacleObservation] = {}
    for entry in entries:
        try:
            observation = _coerce_obstacle(entry)
        except (TypeError, ValueError, IndexError):
            continue
        if observation is None or not observation.valid:
            continue
        try:
            ox = float(observation.relative_center_meters[0])
            oy = float(observation.relative_center_meters[1])
            radius = float(observation.radius_meters)
            confidence = float(observation.confidence)
            age = float(observation.age_seconds)
        except (TypeError, ValueError, IndexError):
            continue
        if not all(math.isfinite(value) for value in (ox, oy, radius, confidence, age)):
            continue
        if radius < 0.0 or not 0.0 <= confidence <= 1.0 or age < 0.0:
            continue
        if age > config.physical.control_period_seconds + 1e-12:
            continue
        if math.hypot(ox, oy) > config.sensing.obstacle_sensing_range_meters + 1e-9:
            continue
        velocity = observation.relative_velocity_meters_per_second
        if velocity is not None:
            try:
                if not all(math.isfinite(float(value)) for value in velocity):
                    observation = LocalObstacleObservation(
                        observation.relative_center_meters,
                        observation.radius_meters,
                        None,
                        observation.confidence,
                        observation.age_seconds,
                        observation.valid,
                    )
            except (TypeError, ValueError):
                observation = LocalObstacleObservation(
                    observation.relative_center_meters,
                    observation.radius_meters,
                    None,
                    observation.confidence,
                    observation.age_seconds,
                    observation.valid,
                )
        unique[_obstacle_signature(observation)] = observation
    return tuple(unique[key] for key in sorted(unique, key=repr))


@dataclass(frozen=True)
class _EdgeGeometry:
    node_index: int
    node_kind: int
    relative_position_mission: Vec2
    relative_velocity_mission: Optional[Vec2]
    distance_meters: float
    distance_scale_meters: float
    desired_offset_template: Optional[Vec2]


def build_robot_local_ego_graph(
    view: RobotView,
    runtime_config: RuntimeConfig,
    local_topology: RobotLocalTopologyMetadata,
    candidate_topology_id: int,
    observation_step: int,
) -> RobotLocalEgoGraph:
    """Build one canonical graph from exactly one robot's permitted inputs."""
    if not isinstance(view, RobotView):
        if isinstance(view, (dict, np.ndarray, torch.Tensor, list, tuple)):
            raise CentralizedAccessError(
                "ego graph V2 accepts one RobotView, never joint state or obs"
            )
        raise TypeError("ego graph V2 requires RobotView")
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("ego graph V2 requires immutable RuntimeConfig")
    if not isinstance(local_topology, RobotLocalTopologyMetadata):
        raise TypeError("ego graph V2 requires robot-local topology metadata")
    if isinstance(observation_step, bool) or not isinstance(observation_step, int) or observation_step < 0:
        raise EgoGraphV2Error("observation step must be a nonnegative integer")
    if int(view.robot_id) != local_topology.observer_robot_id:
        raise EgoGraphV2Error("RobotView observer does not match local topology slice")
    if runtime_config.mission.team_size != local_topology.team_size:
        raise EgoGraphV2Error("runtime team size does not match local topology slice")
    if local_topology.topology_registry_schema_version != TOPOLOGY_REGISTRY_SCHEMA_VERSION:
        raise EgoGraphV2Error("local topology registry schema mismatch")
    if int(view.committed_mode) not in PRIMARY_TOPOLOGY_IDS:
        raise EgoGraphV2Error("observer committed topology is not primary")
    candidate = local_topology.candidate(int(candidate_topology_id))
    committed = local_topology.candidate(int(view.committed_mode))

    spacing = runtime_config.formation.nominal_spacing_meters
    max_speed = runtime_config.physical.maximum_speed_meters_per_second
    comm_range = runtime_config.communication.communication_range_meters
    obs_range = runtime_config.sensing.obstacle_sensing_range_meters
    axes = _mission_axes((float(view.mission_dir[0]), float(view.mission_dir[1])))

    rows: list[list[float]] = []
    row_masks: list[list[bool]] = []
    kinds: list[int] = []
    source_keys: list[str] = []
    geometries: list[_EdgeGeometry] = []

    self_row = [0.0] * NODE_FEATURE_DIM
    self_mask = [False] * NODE_FEATURE_DIM
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "node_kind_onehot", (1.0, 0.0, 0.0))
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "relative_position_spacing", (0.0, 0.0))
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "distance_range", (0.0,))
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "committed_topology_onehot", _topology_onehot(int(view.committed_mode)))
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "candidate_topology_onehot", _topology_onehot(candidate.topology_id))
    own_candidate = candidate.own_role_offset_meters
    displacement = (
        own_candidate[0] - committed.own_role_offset_meters[0],
        own_candidate[1] - committed.own_role_offset_meters[1],
    )
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "candidate_role_offset_spacing", (own_candidate[0] / spacing, own_candidate[1] / spacing))
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "candidate_role_displacement_spacing", (displacement[0] / spacing, displacement[1] / spacing))
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "candidate_transition_magnitude_spacing", (math.hypot(*displacement) / spacing,))
    observation_extent = (
        abs(displacement[1])
        + runtime_config.physical.robot_radius_meters
        + runtime_config.safety.obstacle_clearance_margin_meters
        + runtime_config.controller.transition_response_lateral_bound_meters
        + runtime_config.controller.protocol_lateral_drift_bound_meters
        + runtime_config.safety.transition_observation_margin_meters
    )
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "candidate_observation_extent_range", (observation_extent / obs_range,))
    goal_world = (
        float(view.goal[0]) - float(view.position[0]),
        float(view.goal[1]) - float(view.position[1]),
    )
    goal_mission = _to_mission(goal_world, axes)
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "goal_vector_spacing", (goal_mission[0] / spacing, goal_mission[1] / spacing))
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "goal_distance_spacing", (math.hypot(*goal_mission) / spacing,))
    self_velocity = _to_mission((float(view.velocity[0]), float(view.velocity[1])), axes)
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "self_velocity_speed", (self_velocity[0] / max_speed, self_velocity[1] / max_speed))
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "local_progress_spacing", (float(view.local_progress) / spacing,))
    decision_reference = max(runtime_config.derived.decision_reference_steps, 1)
    decision_age = min(max(float(view.steps_since_decision) / decision_reference, 0.0), 1.0)
    _set_feature(self_row, self_mask, NODE_FEATURE_SLICES, "decision_age_reference", (decision_age,))
    rows.append(self_row)
    row_masks.append(self_mask)
    kinds.append(NODE_SELF)
    source_keys.append(f"robot:{int(view.robot_id)}")

    for peer in _canonical_peers(view, runtime_config):
        rel_world = (float(peer.rel_position[0]), float(peer.rel_position[1]))
        rel_mission = _to_mission(rel_world, axes)
        distance = math.hypot(*rel_mission)
        bearing = _unit(rel_mission)
        velocity_mission: Optional[Vec2] = None
        if peer.rel_velocity is not None:  # type: ignore[comparison-overlap]
            try:
                velocity_mission = _to_mission(
                    (float(peer.rel_velocity[0]), float(peer.rel_velocity[1])), axes
                )
            except (TypeError, ValueError, IndexError, EgoGraphV2Error):
                velocity_mission = None
        formation_neighbour = candidate.neighbour(int(peer.robot_id))

        row = [0.0] * NODE_FEATURE_DIM
        mask = [False] * NODE_FEATURE_DIM
        _set_feature(row, mask, NODE_FEATURE_SLICES, "node_kind_onehot", (0.0, 1.0, 0.0))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "relative_position_spacing", (rel_mission[0] / spacing, rel_mission[1] / spacing))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "distance_range", (distance / comm_range,))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "bearing_cos_sin", bearing, valid=distance >= _EPS)
        _set_feature(row, mask, NODE_FEATURE_SLICES, "relative_velocity_speed", (0.0, 0.0) if velocity_mission is None else (velocity_mission[0] / max_speed, velocity_mission[1] / max_speed), valid=velocity_mission is not None)
        _set_feature(row, mask, NODE_FEATURE_SLICES, "committed_topology_onehot", _topology_onehot(int(peer.committed_mode)))
        if formation_neighbour is not None:
            peer_offset = formation_neighbour.candidate_role_offset_meters
            _set_feature(row, mask, NODE_FEATURE_SLICES, "candidate_role_offset_spacing", (peer_offset[0] / spacing, peer_offset[1] / spacing))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "peer_message_age_limit", (float(peer.message_age_steps) / max(runtime_config.derived.message_stale_rounds, 1),))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "peer_role_known", (1.0 if formation_neighbour is not None else 0.0,))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "peer_topology_conflict", (1.0 if int(peer.committed_mode) != int(view.committed_mode) else 0.0,))
        rows.append(row)
        row_masks.append(mask)
        kinds.append(NODE_PEER)
        source_keys.append(f"robot:{int(peer.robot_id)}")
        geometries.append(_EdgeGeometry(
            node_index=len(rows) - 1,
            node_kind=NODE_PEER,
            relative_position_mission=rel_mission,
            relative_velocity_mission=velocity_mission,
            distance_meters=distance,
            distance_scale_meters=comm_range,
            desired_offset_template=(
                None if formation_neighbour is None
                else formation_neighbour.desired_offset_from_observer_meters
            ),
        ))

    for obstacle_index, obstacle in enumerate(_canonical_obstacles(view.obstacles, runtime_config)):
        center_world = (
            float(obstacle.relative_center_meters[0]),
            float(obstacle.relative_center_meters[1]),
        )
        center_mission = _to_mission(center_world, axes)
        center_distance = math.hypot(*center_mission)
        clearance = max(center_distance - float(obstacle.radius_meters), 0.0)
        scale = 0.0 if center_distance < _EPS else clearance / center_distance
        closest = (center_mission[0] * scale, center_mission[1] * scale)
        bearing = _unit(center_mission)
        velocity_mission = None
        if obstacle.relative_velocity_meters_per_second is not None:
            velocity_mission = _to_mission(
                obstacle.relative_velocity_meters_per_second, axes
            )

        row = [0.0] * NODE_FEATURE_DIM
        mask = [False] * NODE_FEATURE_DIM
        _set_feature(row, mask, NODE_FEATURE_SLICES, "node_kind_onehot", (0.0, 0.0, 1.0))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "relative_position_spacing", (closest[0] / spacing, closest[1] / spacing))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "relative_velocity_speed", (0.0, 0.0) if velocity_mission is None else (velocity_mission[0] / max_speed, velocity_mission[1] / max_speed), valid=velocity_mission is not None)
        _set_feature(row, mask, NODE_FEATURE_SLICES, "distance_range", (clearance / obs_range,))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "bearing_cos_sin", bearing, valid=center_distance >= _EPS)
        _set_feature(row, mask, NODE_FEATURE_SLICES, "obstacle_radius_range", (float(obstacle.radius_meters) / obs_range,))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "obstacle_confidence", (float(obstacle.confidence),))
        _set_feature(row, mask, NODE_FEATURE_SLICES, "obstacle_age_control_period", (float(obstacle.age_seconds) / runtime_config.physical.control_period_seconds,))
        rows.append(row)
        row_masks.append(mask)
        kinds.append(NODE_OBSTACLE)
        source_keys.append(f"obstacle-local:{obstacle_index:04d}")
        geometries.append(_EdgeGeometry(
            node_index=len(rows) - 1,
            node_kind=NODE_OBSTACLE,
            relative_position_mission=closest,
            relative_velocity_mission=velocity_mission,
            distance_meters=clearance,
            distance_scale_meters=obs_range,
            desired_offset_template=None,
        ))

    edge_src: list[int] = []
    edge_dst: list[int] = []
    edge_rows: list[list[float]] = []
    edge_masks: list[list[bool]] = []
    edge_types: list[int] = []

    def add_edge(geometry: _EdgeGeometry, reverse: bool) -> None:
        if geometry.node_kind == NODE_PEER:
            edge_type = EDGE_PEER_TO_SELF if reverse else EDGE_SELF_TO_PEER
        else:
            edge_type = EDGE_OBSTACLE_TO_SELF if reverse else EDGE_SELF_TO_OBSTACLE
        sign = -1.0 if reverse else 1.0
        actual = (
            sign * geometry.relative_position_mission[0],
            sign * geometry.relative_position_mission[1],
        )
        velocity = geometry.relative_velocity_mission
        directed_velocity = None if velocity is None else (sign * velocity[0], sign * velocity[1])
        desired = geometry.desired_offset_template
        directed_desired = None if desired is None else (sign * desired[0], sign * desired[1])

        row = [0.0] * EDGE_FEATURE_DIM
        mask = [False] * EDGE_FEATURE_DIM
        type_onehot = tuple(1.0 if item == edge_type else 0.0 for item in EDGE_TYPES)
        _set_feature(row, mask, EDGE_FEATURE_SLICES, "edge_type_onehot", type_onehot)
        _set_feature(row, mask, EDGE_FEATURE_SLICES, "relative_position_spacing", (actual[0] / spacing, actual[1] / spacing))
        _set_feature(row, mask, EDGE_FEATURE_SLICES, "relative_velocity_speed", (0.0, 0.0) if directed_velocity is None else (directed_velocity[0] / max_speed, directed_velocity[1] / max_speed), valid=directed_velocity is not None)
        _set_feature(row, mask, EDGE_FEATURE_SLICES, "distance_range", (geometry.distance_meters / geometry.distance_scale_meters,))
        _set_feature(row, mask, EDGE_FEATURE_SLICES, "bearing_cos_sin", _unit(actual), valid=geometry.distance_meters >= _EPS)
        if geometry.node_kind == NODE_PEER:
            nominal = directed_desired is not None
            _set_feature(row, mask, EDGE_FEATURE_SLICES, "nominal_formation_relation", (1.0 if nominal else 0.0,))
            _set_feature(row, mask, EDGE_FEATURE_SLICES, "candidate_topology_onehot", _topology_onehot(candidate.topology_id))
            _set_feature(row, mask, EDGE_FEATURE_SLICES, "desired_pairwise_offset_spacing", (0.0, 0.0) if directed_desired is None else (directed_desired[0] / spacing, directed_desired[1] / spacing), valid=nominal)
            _set_feature(row, mask, EDGE_FEATURE_SLICES, "formation_residual_spacing", (0.0, 0.0) if directed_desired is None else ((actual[0] - directed_desired[0]) / spacing, (actual[1] - directed_desired[1]) / spacing), valid=nominal)
        edge_src.append(geometry.node_index if reverse else 0)
        edge_dst.append(0 if reverse else geometry.node_index)
        edge_rows.append(row)
        edge_masks.append(mask)
        edge_types.append(edge_type)

    for geometry in geometries:
        add_edge(geometry, False)
        add_edge(geometry, True)

    node_x = torch.tensor(rows, dtype=torch.float32).reshape(-1, NODE_FEATURE_DIM)
    node_mask = torch.tensor(row_masks, dtype=torch.bool).reshape(-1, NODE_FEATURE_DIM)
    if edge_rows:
        edge_index = torch.tensor((edge_src, edge_dst), dtype=torch.int64)
        edge_attr = torch.tensor(edge_rows, dtype=torch.float32)
        edge_feature_mask = torch.tensor(edge_masks, dtype=torch.bool)
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.int64)
        edge_attr = torch.zeros((0, EDGE_FEATURE_DIM), dtype=torch.float32)
        edge_feature_mask = torch.zeros((0, EDGE_FEATURE_DIM), dtype=torch.bool)

    return RobotLocalEgoGraph(
        schema_version=EGO_GRAPH_SCHEMA_VERSION,
        normalization_version=EGO_GRAPH_NORMALIZATION_VERSION,
        feature_schema_sha256=EGO_GRAPH_FEATURE_SCHEMA_SHA256,
        topology_registry_schema_version=TOPOLOGY_REGISTRY_SCHEMA_VERSION,
        runtime_config_sha256=canonical_runtime_hash(runtime_config),
        observer_robot_id=int(view.robot_id),
        observer_role_id=local_topology.observer_role_id,
        observation_timestamp_seconds=(
            observation_step * runtime_config.physical.control_period_seconds
        ),
        lifecycle_id=int(view.epoch_id),
        committed_topology_id=int(view.committed_mode),
        candidate_topology_id=candidate.topology_id,
        node_x=node_x,
        node_feature_valid_mask=node_mask,
        node_valid_mask=torch.ones((len(rows),), dtype=torch.bool),
        node_kind=torch.tensor(kinds, dtype=torch.int64),
        node_source_key=tuple(source_keys),
        edge_index=edge_index,
        edge_attr=edge_attr,
        edge_feature_valid_mask=edge_feature_mask,
        edge_valid_mask=torch.ones((len(edge_rows),), dtype=torch.bool),
        edge_type=torch.tensor(edge_types, dtype=torch.int64),
    )


@dataclass(frozen=True)
class BatchedRobotLocalEgoGraphs:
    node_x: torch.Tensor
    node_feature_valid_mask: torch.Tensor
    node_valid_mask: torch.Tensor
    node_kind: torch.Tensor
    edge_index: torch.Tensor
    edge_attr: torch.Tensor
    edge_feature_valid_mask: torch.Tensor
    edge_valid_mask: torch.Tensor
    edge_type: torch.Tensor
    graph_index: torch.Tensor
    edge_graph_index: torch.Tensor
    root_index: torch.Tensor
    candidate_topology_id: torch.Tensor
    observer_robot_id: torch.Tensor
    canonical_to_input_order: Tuple[int, ...]

    @property
    def n_graphs(self) -> int:
        return int(self.root_index.numel())


def batch_robot_local_ego_graphs(
    graphs: Sequence[RobotLocalEgoGraph],
) -> BatchedRobotLocalEgoGraphs:
    """Canonical disjoint union; no padding and no cross-graph edge."""
    if not graphs:
        raise EgoGraphV2Error("at least one ego graph is required for batching")
    for graph in graphs:
        if not isinstance(graph, RobotLocalEgoGraph):
            raise TypeError("batching accepts RobotLocalEgoGraph only")
    order = tuple(sorted(
        range(len(graphs)),
        key=lambda index: (
            graphs[index].observer_robot_id,
            graphs[index].observation_timestamp_seconds,
            graphs[index].lifecycle_id,
            graphs[index].candidate_topology_id,
            graphs[index].fingerprint(),
        ),
    ))
    ordered = tuple(graphs[index] for index in order)
    node_x = []
    node_masks = []
    node_valid = []
    node_kind = []
    edge_index = []
    edge_attr = []
    edge_masks = []
    edge_valid = []
    edge_type = []
    graph_index = []
    edge_graph_index = []
    roots = []
    offset = 0
    for graph_id, graph in enumerate(ordered):
        node_x.append(graph.node_x)
        node_masks.append(graph.node_feature_valid_mask)
        node_valid.append(graph.node_valid_mask)
        node_kind.append(graph.node_kind)
        edge_index.append(graph.edge_index + offset)
        edge_attr.append(graph.edge_attr)
        edge_masks.append(graph.edge_feature_valid_mask)
        edge_valid.append(graph.edge_valid_mask)
        edge_type.append(graph.edge_type)
        graph_index.append(torch.full((graph.n_nodes,), graph_id, dtype=torch.int64))
        edge_graph_index.append(torch.full((graph.n_edges,), graph_id, dtype=torch.int64))
        roots.append(offset + graph.root_index)
        offset += graph.n_nodes
    result = BatchedRobotLocalEgoGraphs(
        node_x=torch.cat(node_x, dim=0),
        node_feature_valid_mask=torch.cat(node_masks, dim=0),
        node_valid_mask=torch.cat(node_valid, dim=0),
        node_kind=torch.cat(node_kind, dim=0),
        edge_index=torch.cat(edge_index, dim=1),
        edge_attr=torch.cat(edge_attr, dim=0),
        edge_feature_valid_mask=torch.cat(edge_masks, dim=0),
        edge_valid_mask=torch.cat(edge_valid, dim=0),
        edge_type=torch.cat(edge_type, dim=0),
        graph_index=torch.cat(graph_index, dim=0),
        edge_graph_index=torch.cat(edge_graph_index, dim=0),
        root_index=torch.tensor(roots, dtype=torch.int64),
        candidate_topology_id=torch.tensor(
            [graph.candidate_topology_id for graph in ordered], dtype=torch.int64
        ),
        observer_robot_id=torch.tensor(
            [graph.observer_robot_id for graph in ordered], dtype=torch.int64
        ),
        canonical_to_input_order=order,
    )
    if result.edge_index.numel():
        source_graph = result.graph_index[result.edge_index[0]]
        target_graph = result.graph_index[result.edge_index[1]]
        if not torch.equal(source_graph, target_graph):
            raise EgoGraphV2Error("batch construction created a cross-graph edge")
    return result


def tensor_memory_bytes(graph: RobotLocalEgoGraph | BatchedRobotLocalEgoGraphs) -> int:
    total = 0
    for value in vars(graph).values():
        if isinstance(value, torch.Tensor):
            total += value.numel() * value.element_size()
    return int(total)


def _tensor_payload(value: object) -> object:
    if not isinstance(value, torch.Tensor):
        raise TypeError("graph tensor payload requires a local tensor")
    return value.detach().cpu().tolist()


def _graph_payload_without_hash(graph: RobotLocalEgoGraph) -> Dict[str, object]:
    return {
        "serialization_version": EGO_GRAPH_SERIALIZATION_VERSION,
        "schema_version": graph.schema_version,
        "normalization_version": graph.normalization_version,
        "feature_schema_sha256": graph.feature_schema_sha256,
        "topology_registry_schema_version": graph.topology_registry_schema_version,
        "runtime_config_sha256": graph.runtime_config_sha256,
        "units": {
            "node_features": [item.units for item in NODE_FEATURE_DEFINITIONS],
            "edge_features": [item.units for item in EDGE_FEATURE_DEFINITIONS],
            "observation_timestamp_seconds": "s",
        },
        "metadata": {
            "observer_robot_id": graph.observer_robot_id,
            "observer_role_id": graph.observer_role_id,
            "observation_timestamp_seconds": graph.observation_timestamp_seconds,
            "lifecycle_id": graph.lifecycle_id,
            "committed_topology_id": graph.committed_topology_id,
            "candidate_topology_id": graph.candidate_topology_id,
            "root_index": graph.root_index,
            "node_source_key": list(graph.node_source_key),
        },
        "tensors": {
            "node_x": _tensor_payload(graph.node_x),
            "node_feature_valid_mask": _tensor_payload(graph.node_feature_valid_mask),
            "node_valid_mask": _tensor_payload(graph.node_valid_mask),
            "node_kind": _tensor_payload(graph.node_kind),
            "edge_index": _tensor_payload(graph.edge_index),
            "edge_attr": _tensor_payload(graph.edge_attr),
            "edge_feature_valid_mask": _tensor_payload(graph.edge_feature_valid_mask),
            "edge_valid_mask": _tensor_payload(graph.edge_valid_mask),
            "edge_type": _tensor_payload(graph.edge_type),
        },
    }


def dump_robot_local_ego_graph(graph: RobotLocalEgoGraph) -> str:
    if not isinstance(graph, RobotLocalEgoGraph):
        raise TypeError("serialization requires RobotLocalEgoGraph")
    payload = _graph_payload_without_hash(graph)
    content_hash = hashlib.sha256(_canonical_json(payload).encode("ascii")).hexdigest()
    payload["content_sha256"] = content_hash
    return _canonical_json(payload) + "\n"


def _strict_object(raw: object, fields: set[str], path: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise EgoGraphSerializationError(f"{path} must be an object")
    actual = set(raw)
    if actual - fields:
        raise EgoGraphSerializationError(
            f"{path} has unknown fields: {sorted(actual - fields)}"
        )
    if fields - actual:
        raise EgoGraphSerializationError(
            f"{path} is missing fields: {sorted(fields - actual)}"
        )
    return raw


def load_robot_local_ego_graph(
    payload: str, runtime_config: RuntimeConfig,
) -> RobotLocalEgoGraph:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise EgoGraphSerializationError(f"invalid ego-graph JSON: {exc}") from exc
    if isinstance(raw, Mapping) and raw.get("schema_version") != EGO_GRAPH_SCHEMA_VERSION:
        raise EgoGraphMigrationError(
            "legacy or unknown graph schema cannot be converted without the "
            "original RobotView and local topology metadata"
        )
    root_fields = {
        "serialization_version", "schema_version", "normalization_version",
        "feature_schema_sha256", "topology_registry_schema_version",
        "runtime_config_sha256", "units", "metadata", "tensors",
        "content_sha256",
    }
    root = _strict_object(raw, root_fields, "graph")
    if root["serialization_version"] != EGO_GRAPH_SERIALIZATION_VERSION:
        raise EgoGraphSerializationError("ego-graph serialization version mismatch")
    if root["normalization_version"] != EGO_GRAPH_NORMALIZATION_VERSION:
        raise EgoGraphSerializationError("ego-graph normalization version mismatch")
    if root["feature_schema_sha256"] != EGO_GRAPH_FEATURE_SCHEMA_SHA256:
        raise EgoGraphSerializationError("ego-graph feature schema hash mismatch")
    if root["topology_registry_schema_version"] != TOPOLOGY_REGISTRY_SCHEMA_VERSION:
        raise EgoGraphSerializationError("topology registry version mismatch")
    if root["runtime_config_sha256"] != canonical_runtime_hash(runtime_config):
        raise EgoGraphSerializationError("runtime configuration hash mismatch")
    content = dict(root)
    supplied_hash = content.pop("content_sha256")
    expected_hash = hashlib.sha256(_canonical_json(content).encode("ascii")).hexdigest()
    if supplied_hash != expected_hash:
        raise EgoGraphSerializationError("ego-graph content hash mismatch")
    units = _strict_object(
        root["units"],
        {"node_features", "edge_features", "observation_timestamp_seconds"},
        "graph.units",
    )
    if list(units["node_features"]) != [item.units for item in NODE_FEATURE_DEFINITIONS] or list(units["edge_features"]) != [item.units for item in EDGE_FEATURE_DEFINITIONS] or units["observation_timestamp_seconds"] != "s":
        raise EgoGraphSerializationError("ego-graph units mismatch")
    metadata = _strict_object(
        root["metadata"],
        {
            "observer_robot_id", "observer_role_id",
            "observation_timestamp_seconds", "lifecycle_id",
            "committed_topology_id", "candidate_topology_id", "root_index",
            "node_source_key",
        },
        "graph.metadata",
    )
    tensors = _strict_object(
        root["tensors"],
        {
            "node_x", "node_feature_valid_mask", "node_valid_mask",
            "node_kind", "edge_index", "edge_attr",
            "edge_feature_valid_mask", "edge_valid_mask", "edge_type",
        },
        "graph.tensors",
    )
    try:
        graph = RobotLocalEgoGraph(
            schema_version=EGO_GRAPH_SCHEMA_VERSION,
            normalization_version=EGO_GRAPH_NORMALIZATION_VERSION,
            feature_schema_sha256=EGO_GRAPH_FEATURE_SCHEMA_SHA256,
            topology_registry_schema_version=TOPOLOGY_REGISTRY_SCHEMA_VERSION,
            runtime_config_sha256=str(root["runtime_config_sha256"]),
            observer_robot_id=int(metadata["observer_robot_id"]),
            observer_role_id=str(metadata["observer_role_id"]),
            observation_timestamp_seconds=float(metadata["observation_timestamp_seconds"]),
            lifecycle_id=int(metadata["lifecycle_id"]),
            committed_topology_id=int(metadata["committed_topology_id"]),
            candidate_topology_id=int(metadata["candidate_topology_id"]),
            root_index=int(metadata["root_index"]),
            node_source_key=tuple(str(item) for item in metadata["node_source_key"]),
            node_x=torch.tensor(tensors["node_x"], dtype=torch.float32),
            node_feature_valid_mask=torch.tensor(tensors["node_feature_valid_mask"], dtype=torch.bool),
            node_valid_mask=torch.tensor(tensors["node_valid_mask"], dtype=torch.bool),
            node_kind=torch.tensor(tensors["node_kind"], dtype=torch.int64),
            edge_index=torch.tensor(tensors["edge_index"], dtype=torch.int64).reshape(2, -1),
            edge_attr=torch.tensor(tensors["edge_attr"], dtype=torch.float32).reshape(-1, EDGE_FEATURE_DIM),
            edge_feature_valid_mask=torch.tensor(tensors["edge_feature_valid_mask"], dtype=torch.bool).reshape(-1, EDGE_FEATURE_DIM),
            edge_valid_mask=torch.tensor(tensors["edge_valid_mask"], dtype=torch.bool),
            edge_type=torch.tensor(tensors["edge_type"], dtype=torch.int64),
        )
    except (TypeError, ValueError, RuntimeError, EgoGraphV2Error) as exc:
        raise EgoGraphSerializationError(f"invalid ego-graph tensors: {exc}") from exc
    if dump_robot_local_ego_graph(graph) != _canonical_json(dict(root)) + "\n":
        raise EgoGraphSerializationError("ego-graph record is not canonical or was altered")
    return graph


def migrate_legacy_ego_graph_schema(schema_version: str) -> None:
    """Reject tensor-only conversion; rebuilding requires original local inputs."""
    if schema_version == EGO_GRAPH_SCHEMA_VERSION:
        return
    raise EgoGraphMigrationError(
        f"schema {schema_version!r} cannot be reinterpreted as "
        f"{EGO_GRAPH_SCHEMA_VERSION}; rebuild from RobotView and local topology metadata"
    )
