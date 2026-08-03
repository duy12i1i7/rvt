"""Robot-local role-space execution for an agreed topology transition."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Tuple

from ..runtime_configuration import RuntimeConfig
from ..topology_registry import (
    PRIMARY_TOPOLOGY_IDS,
    PersistentRoleSet,
    construct_topology,
)
from .ego_graph_v2 import (
    LocalCandidateTopologySlice,
    LocalFormationNeighbour,
    RobotLocalTopologyMetadata,
)
from .forced_topology_runtime import ForcedTopologyRuntimeAdapter
from .local_control_types import RobotLocalControllerInput, RobotLocalControllerOutput, Vec2
from .system_model import RobotView


TRANSITION_EXECUTION_SCHEMA_VERSION = "rvt-role-space-transition-executor/v1"


@dataclass(frozen=True)
class TransitionMotionProfile:
    """Shortest rest-to-rest profile under the frozen physical limits."""

    maximum_displacement_meters: float
    velocity_limit_meters_per_second: float
    acceleration_limit_meters_per_second_squared: float
    acceleration_time_seconds: float
    cruise_time_seconds: float
    duration_seconds: float
    profile_kind: str

    def progress(self, elapsed_seconds: float) -> float:
        if not math.isfinite(elapsed_seconds):
            raise ValueError("transition elapsed time must be finite")
        if elapsed_seconds <= 0.0:
            return 0.0
        if elapsed_seconds >= self.duration_seconds:
            return 1.0
        distance = self.maximum_displacement_meters
        acceleration = self.acceleration_limit_meters_per_second_squared
        acceleration_time = self.acceleration_time_seconds
        cruise_time = self.cruise_time_seconds
        if elapsed_seconds <= acceleration_time:
            travelled = 0.5 * acceleration * elapsed_seconds ** 2
        elif elapsed_seconds <= acceleration_time + cruise_time:
            acceleration_distance = 0.5 * acceleration * acceleration_time ** 2
            travelled = acceleration_distance + self.velocity_limit_meters_per_second * (
                elapsed_seconds - acceleration_time
            )
        else:
            remaining = self.duration_seconds - elapsed_seconds
            travelled = distance - 0.5 * acceleration * remaining ** 2
        return min(max(float(travelled / distance), 0.0), 1.0)


def derive_transition_motion_profile(
    maximum_displacement_meters: float,
    runtime_config: RuntimeConfig,
) -> TransitionMotionProfile:
    """Derive one pair/N-independent motion law from geometry and platform bounds."""
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("transition motion profile requires RuntimeConfig")
    displacement = float(maximum_displacement_meters)
    if not math.isfinite(displacement) or displacement <= 0.0:
        raise ValueError("maximum transition displacement must be finite and positive")
    velocity = runtime_config.physical.maximum_speed_meters_per_second
    acceleration = (
        runtime_config.physical.maximum_acceleration_meters_per_second_squared
    )
    switching_distance = velocity ** 2 / acceleration
    if displacement <= switching_distance:
        acceleration_time = math.sqrt(displacement / acceleration)
        cruise_time = 0.0
        duration = 2.0 * acceleration_time
        profile_kind = "triangular"
        profile_velocity = acceleration * acceleration_time
    else:
        acceleration_time = velocity / acceleration
        cruise_time = (displacement - switching_distance) / velocity
        duration = 2.0 * acceleration_time + cruise_time
        profile_kind = "trapezoidal"
        profile_velocity = velocity
    return TransitionMotionProfile(
        maximum_displacement_meters=displacement,
        velocity_limit_meters_per_second=float(profile_velocity),
        acceleration_limit_meters_per_second_squared=float(acceleration),
        acceleration_time_seconds=float(acceleration_time),
        cruise_time_seconds=float(cruise_time),
        duration_seconds=float(duration),
        profile_kind=profile_kind,
    )


@dataclass(frozen=True)
class LocalTransitionNeighbourPath:
    peer_robot_id: int
    peer_role_id: str
    source_role_offset_meters: Vec2
    target_role_offset_meters: Vec2


@dataclass(frozen=True)
class RobotLocalRoleSpacePath:
    """Static local path: own role plus target-graph neighbours only."""

    observer_robot_id: int
    observer_role_id: str
    source_topology_id: int
    target_topology_id: int
    source_role_offset_meters: Vec2
    target_role_offset_meters: Vec2
    target_graph_neighbours: Tuple[LocalTransitionNeighbourPath, ...]

    def intermediate_topology(self, progress: float) -> LocalCandidateTopologySlice:
        value = float(progress)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("transition progress must be within [0, 1]")

        def interpolate(source: Vec2, target: Vec2) -> Vec2:
            return (
                float(source[0] + value * (target[0] - source[0])),
                float(source[1] + value * (target[1] - source[1])),
            )

        own = interpolate(
            self.source_role_offset_meters,
            self.target_role_offset_meters,
        )
        neighbours = []
        for item in self.target_graph_neighbours:
            peer = interpolate(
                item.source_role_offset_meters,
                item.target_role_offset_meters,
            )
            neighbours.append(LocalFormationNeighbour(
                peer_robot_id=item.peer_robot_id,
                peer_role_id=item.peer_role_id,
                candidate_role_offset_meters=peer,
                desired_offset_from_observer_meters=(
                    float(peer[0] - own[0]),
                    float(peer[1] - own[1]),
                ),
            ))
        return LocalCandidateTopologySlice(
            topology_id=self.target_topology_id,
            own_role_offset_meters=own,
            formation_neighbours=tuple(neighbours),
        )


def prepare_robot_local_role_space_path(
    role_set: PersistentRoleSet,
    root_key: object,
    formation_config: object,
    source_topology_id: int,
    target_topology_id: int,
) -> RobotLocalRoleSpacePath:
    """Mission-setup reduction from immutable templates to one local path."""
    if source_topology_id not in PRIMARY_TOPOLOGY_IDS:
        raise ValueError("unknown source topology")
    if target_topology_id not in PRIMARY_TOPOLOGY_IDS:
        raise ValueError("unknown target topology")
    if source_topology_id == target_topology_id:
        raise ValueError("role-space path requires different topologies")
    observer = role_set.role_for_robot(root_key)
    source = construct_topology(
        source_topology_id, formation_config, role_set=role_set
    )
    target = construct_topology(
        target_topology_id, formation_config, role_set=role_set
    )
    role_by_id = {role.role_id: role for role in role_set.roles}
    neighbours = []
    for peer_role_id in target.neighbour_role_ids(observer.role_id):
        peer = role_by_id[peer_role_id]
        if not peer.robot_key.startswith("int:"):
            raise ValueError("transition runtime requires integer robot keys")
        neighbours.append(LocalTransitionNeighbourPath(
            peer_robot_id=int(peer.robot_key[len("int:"):]),
            peer_role_id=peer_role_id,
            source_role_offset_meters=source.offset(peer_role_id),
            target_role_offset_meters=target.offset(peer_role_id),
        ))
    if not observer.robot_key.startswith("int:"):
        raise ValueError("transition runtime requires integer robot keys")
    return RobotLocalRoleSpacePath(
        observer_robot_id=int(observer.robot_key[len("int:"):]),
        observer_role_id=observer.role_id,
        source_topology_id=source_topology_id,
        target_topology_id=target_topology_id,
        source_role_offset_meters=source.offset(observer.role_id),
        target_role_offset_meters=target.offset(observer.role_id),
        target_graph_neighbours=tuple(sorted(
            neighbours, key=lambda item: item.peer_robot_id
        )),
    )


class RobotLocalTransitionExecutor:
    """Apply agreed-clock progress to one robot's static local role path."""

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        local_topology_metadata: RobotLocalTopologyMetadata,
        local_path: RobotLocalRoleSpacePath,
        motion_profile: TransitionMotionProfile,
        commitment_timestamp_seconds: float,
    ) -> None:
        if local_topology_metadata.observer_robot_id != local_path.observer_robot_id:
            raise ValueError("transition path does not belong to adapter observer")
        if not math.isfinite(commitment_timestamp_seconds):
            raise ValueError("commitment timestamp must be finite")
        self.runtime_config = runtime_config
        self.local_path = local_path
        self.motion_profile = motion_profile
        self.commitment_timestamp_seconds = float(commitment_timestamp_seconds)
        self.adapter = ForcedTopologyRuntimeAdapter(
            runtime_config,
            local_topology_metadata,
            local_path.target_topology_id,
        )

    def progress(self, timestamp_seconds: float) -> float:
        return self.motion_profile.progress(
            float(timestamp_seconds) - self.commitment_timestamp_seconds
        )

    def build_input(
        self,
        view: RobotView,
        timestamp_seconds: float,
    ) -> RobotLocalControllerInput:
        controller_input = self.adapter.build_input(view, timestamp_seconds)
        return replace(
            controller_input,
            local_topology=self.local_path.intermediate_topology(
                self.progress(timestamp_seconds)
            ),
        )

    def evaluate(
        self,
        view: RobotView,
        timestamp_seconds: float,
    ) -> RobotLocalControllerOutput:
        return self.adapter.controller.evaluate(
            self.build_input(view, timestamp_seconds)
        )
