"""Forced-topology adapter from received local data to the Phase 6 controller."""

from __future__ import annotations

import math
from typing import Optional, Tuple

from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from ..topology_registry import PRIMARY_TOPOLOGY_IDS
from .ego_graph_v2 import RobotLocalTopologyMetadata
from .local_control_types import (
    LOCAL_CONTROLLER_INPUT_SCHEMA_VERSION,
    LocalObstacleControlState,
    LocalPeerControlState,
    RobotLocalControllerInput,
    RobotLocalControllerOutput,
)
from .robot_local_controller import RobotLocalController
from .system_model import CentralizedAccessError, RobotView


class ForcedTopologyRuntimeAdapter:
    """Bind one robot and one immutable topology for diagnostic qualification."""

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        local_topology_metadata: RobotLocalTopologyMetadata,
        forced_topology_id: int,
        controller: Optional[RobotLocalController] = None,
    ) -> None:
        if not isinstance(runtime_config, RuntimeConfig):
            raise TypeError("forced-topology adapter requires RuntimeConfig")
        if not isinstance(local_topology_metadata, RobotLocalTopologyMetadata):
            raise TypeError("adapter requires robot-local topology metadata")
        if forced_topology_id not in PRIMARY_TOPOLOGY_IDS:
            raise ValueError("forced topology must be KEEP, COMPACT or LINE")
        self.runtime_config = runtime_config
        self.local_topology_metadata = local_topology_metadata
        self.forced_topology_id = int(forced_topology_id)
        self.controller = controller or RobotLocalController(runtime_config)
        self.runtime_config_sha256 = canonical_runtime_hash(runtime_config)
        # Fail at construction if this robot has no declared local slice.
        self.local_topology_metadata.candidate(self.forced_topology_id)

    def build_input(
        self,
        view: RobotView,
        timestamp_seconds: float,
    ) -> RobotLocalControllerInput:
        if not isinstance(view, RobotView):
            raise CentralizedAccessError(
                "forced-topology adapter accepts RobotView only, never joint state"
            )
        if view.robot_id != self.local_topology_metadata.observer_robot_id:
            raise ValueError("RobotView observer does not match local topology metadata")
        if not math.isfinite(timestamp_seconds) or timestamp_seconds < 0.0:
            raise ValueError("controller timestamp must be finite and nonnegative")
        communication_period = (
            self.runtime_config.communication.communication_period_seconds
        )
        peer_states = tuple(sorted((
            LocalPeerControlState(
                peer_robot_id=peer.robot_id,
                relative_position_meters=tuple(map(float, peer.rel_position)),
                relative_velocity_meters_per_second=tuple(
                    map(float, peer.rel_velocity)
                ),
                message_age_seconds=(
                    float(peer.message_age_steps) * communication_period
                ),
                valid=bool(peer.link_valid),
            )
            for peer in view.neighbours
        ), key=lambda item: item.peer_robot_id))
        own_velocity = tuple(map(float, view.velocity))
        canonical_obstacles = sorted(
            (
                float(entry[0]),
                float(entry[1]),
                float(entry[2]),
            )
            for entry in view.obstacles
        )
        obstacle_states = tuple(
            LocalObstacleControlState(
                source_key=f"local-obstacle:{index}",
                relative_center_meters=(center_x, center_y),
                radius_meters=radius,
                relative_velocity_meters_per_second=(
                    -own_velocity[0],
                    -own_velocity[1],
                ),
            )
            for index, (center_x, center_y, radius) in enumerate(canonical_obstacles)
        )
        return RobotLocalControllerInput(
            schema_version=LOCAL_CONTROLLER_INPUT_SCHEMA_VERSION,
            observer_robot_id=view.robot_id,
            observer_role_id=self.local_topology_metadata.observer_role_id,
            timestamp_seconds=float(timestamp_seconds),
            own_position_meters=tuple(map(float, view.position)),
            own_velocity_meters_per_second=own_velocity,
            forced_topology_id=self.forced_topology_id,
            shared_goal_origin_meters=tuple(map(float, view.goal)),
            mission_direction=tuple(map(float, view.mission_dir)),
            local_topology=self.local_topology_metadata.candidate(
                self.forced_topology_id
            ),
            peer_states=peer_states,
            obstacle_states=obstacle_states,
            runtime_config_sha256=self.runtime_config_sha256,
            validity=True,
        )

    def evaluate(
        self,
        view: RobotView,
        timestamp_seconds: float,
    ) -> RobotLocalControllerOutput:
        return self.controller.evaluate(self.build_input(view, timestamp_seconds))


def forced_topology_runtime_signature() -> Tuple[Tuple[str, str], ...]:
    return (
        ("input", "one RobotView plus one mission-setup local topology slice"),
        ("output", "one observer action"),
        ("topology", "bound once at adapter construction"),
        ("learned_model", "absent"),
        ("joint_action", "absent"),
    )
