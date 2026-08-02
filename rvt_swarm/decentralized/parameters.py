"""Compatibility facade for the authoritative runtime configuration.

The active source hierarchy is :mod:`rvt_swarm.runtime_configuration`. The
three `*Params` records remain as frozen projections so historical scripts,
tests, and manifests can be reproduced without retaining a second deployable
source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from ..runtime_configuration import (
    DEFAULT_RUNTIME_CONFIG,
    CommunicationConfig,
    ControllerConfig,
    FormationConfig,
    MissionConfig,
    PhysicalPlatformConfig,
    ProtocolConfig,
    RuntimeConfig,
    SafetyConfig,
    SensingConfig,
    assess_runtime_configuration,
    component_diameter_bound,
    derive_runtime_configuration,
    lookahead_distance_meters,
    role_transition_observation_requirement_meters,
    runtime_config_from_legacy,
    steps_from_seconds,
)

Vec2 = Tuple[float, float]


@dataclass(frozen=True)
class PlatformParams:
    """Deprecated flat projection of platform, sensing, and communication."""

    robot_radius: float
    collision_clearance_obstacle: float
    collision_clearance_robot: float
    max_speed: float
    max_accel: float
    obstacle_sensor_range: float
    communication_range: float
    control_period: float
    communication_period: float

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "PlatformParams":
        derived = config.derived
        return cls(
            robot_radius=config.physical.robot_radius_meters,
            collision_clearance_obstacle=(
                derived.robot_obstacle_required_clearance_meters
            ),
            collision_clearance_robot=(
                derived.robot_robot_required_clearance_meters
            ),
            max_speed=config.physical.maximum_speed_meters_per_second,
            max_accel=(
                config.physical.maximum_acceleration_meters_per_second_squared
            ),
            obstacle_sensor_range=config.sensing.obstacle_sensing_range_meters,
            communication_range=config.communication.communication_range_meters,
            control_period=config.physical.control_period_seconds,
            communication_period=(
                config.communication.communication_period_seconds
            ),
        )

    @classmethod
    def from_env_config(cls, env: object) -> "PlatformParams":
        return cls.from_runtime_config(runtime_config_from_legacy(env))


@dataclass(frozen=True)
class MissionParams:
    """Deprecated flat projection of formation and mission requirements."""

    nominal_spacing: float = DEFAULT_RUNTIME_CONFIG.formation.nominal_spacing_meters
    formation_tolerance: float = (
        DEFAULT_RUNTIME_CONFIG.formation.formation_tolerance_ratio
        * DEFAULT_RUNTIME_CONFIG.formation.nominal_spacing_meters
    )
    recovery_dwell_seconds: float = (
        DEFAULT_RUNTIME_CONFIG.mission.recovery_dwell_seconds
    )
    safety_margin: float = (
        DEFAULT_RUNTIME_CONFIG.safety.transition_observation_margin_meters
    )

    @property
    def formation_tolerance_ratio(self) -> float:
        return self.formation_tolerance / self.nominal_spacing

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "MissionParams":
        return cls(
            nominal_spacing=config.formation.nominal_spacing_meters,
            formation_tolerance=config.derived.formation_tolerance_meters,
            recovery_dwell_seconds=config.mission.recovery_dwell_seconds,
            safety_margin=config.safety.transition_observation_margin_meters,
        )


@dataclass(frozen=True)
class ProtocolParams:
    """Deprecated flat projection of protocol source assumptions."""

    max_team_size: int = DEFAULT_RUNTIME_CONFIG.mission.team_size
    max_component_diameter: Optional[int] = None
    max_message_age_seconds: float = (
        DEFAULT_RUNTIME_CONFIG.communication.maximum_message_age_seconds
    )
    evidence_persistence_seconds: float = (
        DEFAULT_RUNTIME_CONFIG.protocol.evidence_persistence_seconds
    )
    event_collection_seconds: float = (
        DEFAULT_RUNTIME_CONFIG.protocol.event_collection_seconds
    )
    commitment_seconds: float = (
        DEFAULT_RUNTIME_CONFIG.protocol.commitment_seconds
    )
    rearm_inactive_seconds: float = (
        DEFAULT_RUNTIME_CONFIG.protocol.rearm_inactive_seconds
    )
    connectivity_assumption: str = (
        "Each connected component must satisfy the declared temporal diameter "
        "and delay bound. Swarm-wide commitment additionally requires all "
        "configured persistent role IDs in that temporal component."
    )

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "ProtocolParams":
        declared = config.protocol.declared_maximum_component_diameter_hops
        implicit = config.mission.team_size - 1
        return cls(
            max_team_size=config.mission.team_size,
            max_component_diameter=(None if declared == implicit else declared),
            max_message_age_seconds=(
                config.communication.maximum_message_age_seconds
            ),
            evidence_persistence_seconds=(
                config.protocol.evidence_persistence_seconds
            ),
            event_collection_seconds=config.protocol.event_collection_seconds,
            commitment_seconds=config.protocol.commitment_seconds,
            rearm_inactive_seconds=config.protocol.rearm_inactive_seconds,
        )


def _runtime_from_params(
    platform: PlatformParams,
    mission: MissionParams,
    protocol: ProtocolParams,
    team_size: Optional[int] = None,
) -> RuntimeConfig:
    n = protocol.max_team_size if team_size is None else int(team_size)
    maximum_team_size = max(int(protocol.max_team_size), n)
    return RuntimeConfig(
        physical=PhysicalPlatformConfig(
            robot_radius_meters=platform.robot_radius,
            maximum_speed_meters_per_second=platform.max_speed,
            maximum_acceleration_meters_per_second_squared=platform.max_accel,
            control_period_seconds=platform.control_period,
        ),
        mission=MissionConfig(
            team_size=n,
            recovery_dwell_seconds=mission.recovery_dwell_seconds,
        ),
        formation=FormationConfig(
            nominal_spacing_meters=mission.nominal_spacing,
            formation_tolerance_ratio=(
                mission.formation_tolerance / mission.nominal_spacing
            ),
        ),
        sensing=SensingConfig(
            obstacle_sensing_range_meters=platform.obstacle_sensor_range,
            peer_sensing_range_meters=max(
                platform.communication_range,
                platform.obstacle_sensor_range,
            ),
        ),
        communication=CommunicationConfig(
            communication_range_meters=platform.communication_range,
            communication_period_seconds=platform.communication_period,
            maximum_message_age_seconds=protocol.max_message_age_seconds,
        ),
        protocol=ProtocolConfig(
            maximum_team_size=maximum_team_size,
            declared_maximum_component_diameter_hops=(
                protocol.max_component_diameter
                if protocol.max_component_diameter is not None
                else maximum_team_size - 1
            ),
            evidence_persistence_seconds=protocol.evidence_persistence_seconds,
            event_collection_seconds=protocol.event_collection_seconds,
            commitment_seconds=protocol.commitment_seconds,
            rearm_inactive_seconds=protocol.rearm_inactive_seconds,
        ),
        controller=ControllerConfig(),
        safety=SafetyConfig(
            obstacle_clearance_margin_meters=(
                platform.collision_clearance_obstacle - platform.robot_radius
            ),
            inter_robot_safety_margin_meters=(
                platform.collision_clearance_robot - 2.0 * platform.robot_radius
            ),
            transition_observation_margin_meters=mission.safety_margin,
        ),
    )


def derived_recovery_dwell_steps(m: MissionParams, p: PlatformParams) -> int:
    return steps_from_seconds(m.recovery_dwell_seconds, p.control_period)


def derived_evidence_persistence_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.evidence_persistence_seconds, p.control_period)


def derived_event_collection_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.event_collection_seconds, p.communication_period)


def derived_commitment_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.commitment_seconds, p.control_period)


def derived_max_message_age_steps(c: ProtocolParams, p: PlatformParams) -> int:
    """Freshness is counted in communication periods, not control periods."""
    return steps_from_seconds(c.max_message_age_seconds, p.communication_period)


def derived_rearm_inactive_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.rearm_inactive_seconds, p.control_period)


def derived_component_diameter(c: ProtocolParams) -> int:
    if c.max_component_diameter is not None:
        return int(c.max_component_diameter)
    return int(c.max_team_size) - 1


def derived_k_trigger(c: ProtocolParams) -> int:
    return derived_component_diameter(c)


def derived_forward_sector_half_width(
    own_keep_role: Vec2,
    own_line_role: Vec2,
    platform: PlatformParams,
    mission: MissionParams,
) -> float:
    return role_transition_observation_requirement_meters(
        own_line_role,
        own_keep_role,
        platform.collision_clearance_obstacle,
        0.0,
        0.0,
        mission.safety_margin,
    )


def forward_sector_observable(half_width: float, platform: PlatformParams) -> bool:
    return 0.0 < half_width <= platform.obstacle_sensor_range


def derived_lookahead_distance(
    platform: PlatformParams,
    mission: MissionParams,
    protocol: ProtocolParams,
    speed: Optional[float] = None,
) -> float:
    config = _runtime_from_params(platform, mission, protocol)
    return lookahead_distance_meters(config, speed)


@dataclass(frozen=True)
class ConfigurationSupport:
    supported: bool
    team_size: int
    reasons: Tuple[str, ...]
    delta_n: float
    k_trigger: int


def check_team_size(
    n: int,
    platform: PlatformParams,
    mission: MissionParams,
    protocol: ProtocolParams,
) -> ConfigurationSupport:
    from .formation_metric_v3 import delta_n
    from .roles import RoleAssignment

    roles = RoleAssignment.from_index(max(int(n), 1), mission.nominal_spacing)
    gap = delta_n(roles)
    config = _runtime_from_params(platform, mission, protocol, team_size=n)
    support = assess_runtime_configuration(config)
    return ConfigurationSupport(
        supported=support.supported,
        team_size=n,
        reasons=tuple(
            f"{issue.code}: {issue.message}" for issue in support.reasons
        ),
        delta_n=gap,
        k_trigger=component_diameter_bound(config),
    )


def normalized_ratios(
    platform: PlatformParams,
    mission: MissionParams,
) -> Dict[str, float]:
    spacing = mission.nominal_spacing
    return {
        "formation_tolerance_ratio": mission.formation_tolerance / spacing,
        "sensor_range_ratio": platform.obstacle_sensor_range / spacing,
        "communication_range_ratio": platform.communication_range / spacing,
        "collision_clearance_ratio": (
            platform.collision_clearance_obstacle / spacing
        ),
        "robot_radius_ratio": platform.robot_radius / spacing,
    }


def default_parameters(env: Optional[object] = None):
    config = (
        DEFAULT_RUNTIME_CONFIG
        if env is None else runtime_config_from_legacy(env)
    )
    return (
        PlatformParams.from_runtime_config(config),
        MissionParams.from_runtime_config(config),
        ProtocolParams.from_runtime_config(config),
    )


__all__ = [
    "ConfigurationSupport",
    "MissionParams",
    "PlatformParams",
    "ProtocolParams",
    "check_team_size",
    "default_parameters",
    "derived_commitment_steps",
    "derived_component_diameter",
    "derived_event_collection_steps",
    "derived_evidence_persistence_steps",
    "derived_forward_sector_half_width",
    "derived_k_trigger",
    "derived_lookahead_distance",
    "derived_max_message_age_steps",
    "derived_rearm_inactive_steps",
    "derived_recovery_dwell_steps",
    "forward_sector_observable",
    "normalized_ratios",
    "steps_from_seconds",
]
