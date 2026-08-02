"""Immutable Phase 6 robot-local controller input and output contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from ..decentralized.ego_graph_v2 import LocalCandidateTopologySlice
from ..topology_registry import PRIMARY_TOPOLOGY_IDS


LOCAL_CONTROLLER_INPUT_SCHEMA_VERSION = "rvt-local-controller-input/v1"
LOCAL_CONTROLLER_OUTPUT_SCHEMA_VERSION = "rvt-local-controller-output/v1"
Vec2 = Tuple[float, float]


class LocalControllerContractError(ValueError):
    """A local controller value is incomplete, nonfinite, or incompatible."""


def _finite_vector(value: Vec2, field_name: str) -> None:
    if not isinstance(value, tuple) or len(value) != 2:
        raise LocalControllerContractError(f"{field_name} must be a two-tuple")
    if any(not math.isfinite(float(component)) for component in value):
        raise LocalControllerContractError(f"{field_name} must be finite")


@dataclass(frozen=True)
class LocalPeerControlState:
    """One received one-hop peer record in observer-relative coordinates."""

    peer_robot_id: int
    relative_position_meters: Vec2
    relative_velocity_meters_per_second: Vec2
    message_age_seconds: float
    valid: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.peer_robot_id, bool) or self.peer_robot_id < 0:
            raise LocalControllerContractError("peer robot ID must be nonnegative")
        _finite_vector(self.relative_position_meters, "peer relative position")
        _finite_vector(self.relative_velocity_meters_per_second, "peer relative velocity")
        if not math.isfinite(self.message_age_seconds) or self.message_age_seconds < 0.0:
            raise LocalControllerContractError("peer message age must be nonnegative")
        if not isinstance(self.valid, bool):
            raise LocalControllerContractError("peer validity must be Boolean")


@dataclass(frozen=True)
class LocalObstacleControlState:
    """One locally observed circular obstacle with no map-level identity."""

    source_key: str
    relative_center_meters: Vec2
    radius_meters: float
    relative_velocity_meters_per_second: Vec2
    observation_age_seconds: float = 0.0
    confidence: float = 1.0
    valid: bool = True

    def __post_init__(self) -> None:
        if not self.source_key:
            raise LocalControllerContractError("obstacle source key must be nonempty")
        _finite_vector(self.relative_center_meters, "obstacle relative center")
        _finite_vector(
            self.relative_velocity_meters_per_second,
            "obstacle relative velocity",
        )
        if not math.isfinite(self.radius_meters) or self.radius_meters < 0.0:
            raise LocalControllerContractError("obstacle radius must be nonnegative")
        if (
            not math.isfinite(self.observation_age_seconds)
            or self.observation_age_seconds < 0.0
        ):
            raise LocalControllerContractError("obstacle age must be nonnegative")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise LocalControllerContractError("obstacle confidence must be in [0, 1]")
        if not isinstance(self.valid, bool):
            raise LocalControllerContractError("obstacle validity must be Boolean")


@dataclass(frozen=True)
class RobotLocalControllerInput:
    """Closed one-robot input; no complete template or joint state is accepted."""

    schema_version: str
    observer_robot_id: int
    observer_role_id: str
    timestamp_seconds: float
    own_position_meters: Vec2
    own_velocity_meters_per_second: Vec2
    forced_topology_id: int
    shared_goal_origin_meters: Vec2
    mission_direction: Vec2
    local_topology: LocalCandidateTopologySlice
    peer_states: Tuple[LocalPeerControlState, ...]
    obstacle_states: Tuple[LocalObstacleControlState, ...]
    runtime_config_sha256: str
    validity: bool = True

    def __post_init__(self) -> None:
        if self.schema_version != LOCAL_CONTROLLER_INPUT_SCHEMA_VERSION:
            raise LocalControllerContractError("unknown local-controller input schema")
        if isinstance(self.observer_robot_id, bool) or self.observer_robot_id < 0:
            raise LocalControllerContractError("observer robot ID must be nonnegative")
        if not self.observer_role_id:
            raise LocalControllerContractError("observer role ID must be nonempty")
        if not math.isfinite(self.timestamp_seconds) or self.timestamp_seconds < 0.0:
            raise LocalControllerContractError("timestamp must be finite and nonnegative")
        _finite_vector(self.own_position_meters, "own position")
        _finite_vector(self.own_velocity_meters_per_second, "own velocity")
        _finite_vector(self.shared_goal_origin_meters, "shared goal origin")
        _finite_vector(self.mission_direction, "mission direction")
        if math.hypot(*self.mission_direction) <= 0.0:
            raise LocalControllerContractError("mission direction must be nonzero")
        if self.forced_topology_id not in PRIMARY_TOPOLOGY_IDS:
            raise LocalControllerContractError("forced topology is not primary")
        if not isinstance(self.local_topology, LocalCandidateTopologySlice):
            raise LocalControllerContractError("registry local topology slice is required")
        if self.local_topology.topology_id != self.forced_topology_id:
            raise LocalControllerContractError("local topology conflicts with forced topology")
        if any(not isinstance(item, LocalPeerControlState) for item in self.peer_states):
            raise LocalControllerContractError("peer state type is invalid")
        if any(
            not isinstance(item, LocalObstacleControlState)
            for item in self.obstacle_states
        ):
            raise LocalControllerContractError("obstacle state type is invalid")
        peer_ids = tuple(item.peer_robot_id for item in self.peer_states)
        if len(set(peer_ids)) != len(peer_ids):
            raise LocalControllerContractError("peer robot IDs must be unique")
        obstacle_keys = tuple(item.source_key for item in self.obstacle_states)
        if len(set(obstacle_keys)) != len(obstacle_keys):
            raise LocalControllerContractError("obstacle source keys must be unique")
        if len(self.runtime_config_sha256) != 64:
            raise LocalControllerContractError("runtime configuration hash is invalid")
        if not isinstance(self.validity, bool) or not self.validity:
            raise LocalControllerContractError("controller input must be explicitly valid")


@dataclass(frozen=True)
class LocalConstraintDiagnostic:
    source_key: str
    threat_kind: str
    outward_normal: Vec2
    lower_bound_meters_per_second_squared: float
    current_distance_meters: float
    required_clearance_meters: float
    stale_or_uncertain: bool
    active_for_proposed_action: bool


@dataclass(frozen=True)
class LocalSafetyProjectionResult:
    projected_action: Vec2
    intervened: bool
    infeasible: bool
    solver_failed: bool
    status: str
    constraints: Tuple[LocalConstraintDiagnostic, ...]
    active_constraint_count: int


@dataclass(frozen=True)
class RobotLocalControllerOutput:
    schema_version: str
    observer_robot_id: int
    forced_topology_id: int
    formation_term: Vec2
    goal_term: Vec2
    damping_term: Vec2
    obstacle_term: Vec2
    base_action: Vec2
    projected_action: Vec2
    projection_intervened: bool
    projection_infeasible: bool
    projection_solver_failed: bool
    projection_status: str
    active_constraints: Tuple[LocalConstraintDiagnostic, ...]
    saturation_state: str
    diagnostics: Tuple[Tuple[str, float], ...]
    validity: bool

    def __post_init__(self) -> None:
        if self.schema_version != LOCAL_CONTROLLER_OUTPUT_SCHEMA_VERSION:
            raise LocalControllerContractError("unknown local-controller output schema")
        for field_name in (
            "formation_term",
            "goal_term",
            "damping_term",
            "obstacle_term",
            "base_action",
            "projected_action",
        ):
            _finite_vector(getattr(self, field_name), field_name)
        if self.forced_topology_id not in PRIMARY_TOPOLOGY_IDS:
            raise LocalControllerContractError("output topology is not primary")
        if not self.validity:
            raise LocalControllerContractError("controller output is invalid")
