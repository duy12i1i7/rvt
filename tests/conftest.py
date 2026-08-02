"""Shared mechanical fixtures for the Phase 4 ego-graph V2 tests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

import pytest

from rvt_swarm.decentralized.ego_graph_v2 import (
    LocalObstacleObservation,
    RobotLocalTopologyMetadata,
    prepare_robot_local_topology_metadata,
)
from rvt_swarm.decentralized.system_model import NeighbourRecord, RobotView
from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import (
    KEEP,
    PersistentRoleSet,
    TopologyTemplate,
    construct_primary_templates,
    generate_persistent_roles,
)

Vec2 = Tuple[float, float]


def _rotate(vector: Vec2, mission: Vec2) -> Vec2:
    norm = math.hypot(*mission)
    c, s = mission[0] / norm, mission[1] / norm
    return (
        c * vector[0] - s * vector[1],
        s * vector[0] + c * vector[1],
    )


@dataclass(frozen=True)
class EgoV2Case:
    config: RuntimeConfig
    roles: PersistentRoleSet
    templates: Tuple[TopologyTemplate, ...]
    local_topology: RobotLocalTopologyMetadata
    view: RobotView
    observation_step: int


@pytest.fixture
def ego_v2_factory():
    def factory(
        *,
        n: int = 6,
        root: int = 0,
        peer_ids: Optional[Sequence[int]] = None,
        peer_local_positions: Optional[Mapping[int, Vec2]] = None,
        obstacles: Sequence[object] = (),
        committed_topology: int = KEEP,
        peer_topologies: Optional[Mapping[int, int]] = None,
        peer_ages: Optional[Mapping[int, int]] = None,
        peer_links: Optional[Mapping[int, bool]] = None,
        mission: Vec2 = (1.0, 0.0),
        origin: Vec2 = (2.0, -1.0),
        own_velocity_local: Vec2 = (0.2, -0.1),
        goal_local: Vec2 = (10.0, 0.5),
        observation_step: int = 7,
        robot_keys: Optional[Sequence[int]] = None,
    ) -> EgoV2Case:
        config = RuntimeConfig.for_team_size(n)
        keys = tuple(range(n)) if robot_keys is None else tuple(robot_keys)
        roles = generate_persistent_roles(keys)
        templates = construct_primary_templates(config.formation, role_set=roles)
        by_topology = {item.topology_id: item for item in templates}
        local = prepare_robot_local_topology_metadata(
            roles, root, config.formation
        )
        if peer_ids is None:
            peer_ids = tuple(
                item.peer_robot_id
                for item in local.candidate(committed_topology).formation_neighbours
            )
        peer_topologies = peer_topologies or {}
        peer_ages = peer_ages or {}
        peer_links = peer_links or {}
        peer_local_positions = peer_local_positions or {}
        keep = by_topology[0]
        line = by_topology[2]
        root_role = roles.role_for_robot(root)
        neighbours = []
        for index, peer_id in enumerate(peer_ids):
            peer_role = roles.role_for_robot(peer_id)
            angle = 2.0 * math.pi * index / max(len(peer_ids), 1)
            default_local = (
                1.0 + 0.15 * math.cos(angle),
                0.75 * math.sin(angle),
            )
            relative_world = _rotate(
                peer_local_positions.get(peer_id, default_local), mission
            )
            relative_velocity = _rotate(
                (0.03 * (index + 1), -0.02 * index), mission
            )
            neighbours.append(NeighbourRecord(
                robot_id=peer_id,
                rel_position=relative_world,
                rel_velocity=relative_velocity,
                role_keep=keep.offset(peer_role.role_id),
                role_line=line.offset(peer_role.role_id),
                committed_mode=peer_topologies.get(peer_id, committed_topology),
                epoch_id=4,
                message_age_steps=peer_ages.get(peer_id, 0),
                degree=2,
                link_valid=peer_links.get(peer_id, True),
            ))

        local_obstacles = []
        for entry in obstacles:
            if isinstance(entry, LocalObstacleObservation):
                velocity = entry.relative_velocity_meters_per_second
                local_obstacles.append(LocalObstacleObservation(
                    relative_center_meters=_rotate(
                        entry.relative_center_meters, mission
                    ),
                    radius_meters=entry.radius_meters,
                    relative_velocity_meters_per_second=(
                        None if velocity is None else _rotate(velocity, mission)
                    ),
                    confidence=entry.confidence,
                    age_seconds=entry.age_seconds,
                    valid=entry.valid,
                ))
            else:
                values = tuple(entry)
                center = _rotate((float(values[0]), float(values[1])), mission)
                if len(values) == 3:
                    local_obstacles.append((center[0], center[1], float(values[2])))
                elif len(values) == 5:
                    velocity = _rotate((float(values[3]), float(values[4])), mission)
                    local_obstacles.append((
                        center[0], center[1], float(values[2]),
                        velocity[0], velocity[1],
                    ))
                else:
                    local_obstacles.append(entry)

        own_velocity = _rotate(own_velocity_local, mission)
        goal_world_offset = _rotate(goal_local, mission)
        view = RobotView(
            robot_id=root,
            position=origin,
            velocity=own_velocity,
            role_keep=keep.offset(root_role.role_id),
            role_line=line.offset(root_role.role_id),
            committed_mode=committed_topology,
            epoch_id=3,
            steps_since_decision=5,
            local_progress=0.3,
            goal=(origin[0] + goal_world_offset[0], origin[1] + goal_world_offset[1]),
            mission_dir=mission,
            neighbours=tuple(neighbours),
            obstacles=tuple(local_obstacles),
        )
        return EgoV2Case(
            config, roles, templates, local, view, observation_step
        )

    return factory
