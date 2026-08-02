"""Registry-derived Phase 7 topology-pair admissibility."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from ..runtime_configuration import RuntimeConfig
from ..topology_registry import (
    PRIMARY_TOPOLOGY_IDS,
    PersistentRoleSet,
    RoleTransitionGeometry,
    TopologyRegistryError,
    construct_topology,
    get_topology_definition,
    graph_statistics,
    transition_geometry,
    validate_topology_configuration,
)


ADMITTED_DIRECTED_PAIRS: Tuple[Tuple[int, int], ...] = tuple(
    (source, target)
    for source in PRIMARY_TOPOLOGY_IDS
    for target in PRIMARY_TOPOLOGY_IDS
    if source != target
)


@dataclass(frozen=True)
class TransitionAdmissibilityResult:
    admitted: bool
    source_topology: int
    target_topology: int
    committed_topology: int
    team_size: int
    reasons: Tuple[str, ...]
    role_geometry: Tuple[RoleTransitionGeometry, ...]
    maximum_displacement_meters: float
    maximum_lateral_displacement_meters: float
    maximum_longitudinal_displacement_meters: float
    static_swept_envelope_extent_meters: float
    source_graph_diameter_hops: int
    target_graph_diameter_hops: int
    nominal_graph_changed: bool
    expected_physical_use: str
    known_limitation: str


def _use(source: int, target: int) -> str:
    source_name = get_topology_definition(source).canonical_name
    target_name = get_topology_definition(target).canonical_name
    return f"mechanical reconfiguration from {source_name} to {target_name}"


def assess_transition_admissibility(
    source_topology: int,
    target_topology: int,
    committed_topology: int,
    role_set: PersistentRoleSet,
    runtime_config: RuntimeConfig,
) -> TransitionAdmissibilityResult:
    reasons = []
    empty = TransitionAdmissibilityResult(
        admitted=False,
        source_topology=int(source_topology),
        target_topology=int(target_topology),
        committed_topology=int(committed_topology),
        team_size=getattr(role_set, "team_size", 0),
        reasons=(),
        role_geometry=(),
        maximum_displacement_meters=0.0,
        maximum_lateral_displacement_meters=0.0,
        maximum_longitudinal_displacement_meters=0.0,
        static_swept_envelope_extent_meters=0.0,
        source_graph_diameter_hops=-1,
        target_graph_diameter_hops=-1,
        nominal_graph_changed=False,
        expected_physical_use="unsupported request",
        known_limitation="admissibility is mechanical and does not authorize safety",
    )
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("transition admissibility requires RuntimeConfig")
    if not isinstance(role_set, PersistentRoleSet):
        return TransitionAdmissibilityResult(
            **{**empty.__dict__, "reasons": ("invalid_persistent_roles",)}
        )
    if source_topology not in PRIMARY_TOPOLOGY_IDS:
        reasons.append("unknown_source_topology")
    if target_topology not in PRIMARY_TOPOLOGY_IDS:
        reasons.append("unknown_target_topology")
    if committed_topology not in PRIMARY_TOPOLOGY_IDS:
        reasons.append("unknown_committed_topology")
    if source_topology == target_topology:
        reasons.append("source_equals_target")
    if committed_topology != source_topology:
        reasons.append("source_topology_mismatch")
    if role_set.team_size != runtime_config.mission.team_size:
        reasons.append("persistent_role_count_mismatch")
    if reasons:
        return TransitionAdmissibilityResult(
            **{**empty.__dict__, "reasons": tuple(reasons)}
        )
    try:
        source_validity = validate_topology_configuration(
            source_topology, runtime_config, role_set=role_set,
            scientific_comparison=False,
        )
        target_validity = validate_topology_configuration(
            target_topology, runtime_config, role_set=role_set,
            scientific_comparison=False,
        )
        if not source_validity.supported:
            reasons.append("unsupported_source_geometry")
        if not target_validity.supported:
            reasons.append("unsupported_target_geometry")
        source = construct_topology(
            source_topology, runtime_config.formation, role_set=role_set
        )
        target = construct_topology(
            target_topology, runtime_config.formation, role_set=role_set
        )
        geometry = transition_geometry(source, target, runtime_config)
        if not all(
            math.isfinite(value)
            for role in geometry.roles
            for value in (*role.source_offset, *role.target_offset, *role.displacement)
        ):
            reasons.append("nonfinite_transition_geometry")
        if (
            geometry.maximum_required_observation_extent_meters
            > runtime_config.sensing.obstacle_sensing_range_meters + 1e-12
        ):
            reasons.append("unsupported_observation_extent")
        source_graph = graph_statistics(source)
        target_graph = graph_statistics(target)
    except (TopologyRegistryError, ValueError) as exc:
        return TransitionAdmissibilityResult(
            **{
                **empty.__dict__,
                "reasons": ("topology_construction_failure", str(exc)),
            }
        )
    maximum_lateral = max(
        (abs(role.lateral_component_meters) for role in geometry.roles),
        default=0.0,
    )
    maximum_longitudinal = max(
        (abs(role.longitudinal_component_meters) for role in geometry.roles),
        default=0.0,
    )
    return TransitionAdmissibilityResult(
        admitted=not reasons,
        source_topology=source_topology,
        target_topology=target_topology,
        committed_topology=committed_topology,
        team_size=role_set.team_size,
        reasons=tuple(reasons),
        role_geometry=geometry.roles,
        maximum_displacement_meters=geometry.maximum_role_displacement_meters,
        maximum_lateral_displacement_meters=float(maximum_lateral),
        maximum_longitudinal_displacement_meters=float(maximum_longitudinal),
        static_swept_envelope_extent_meters=(
            geometry.maximum_required_observation_extent_meters
        ),
        source_graph_diameter_hops=source_graph.diameter_hops,
        target_graph_diameter_hops=target_graph.diameter_hops,
        nominal_graph_changed=source.edges != target.edges,
        expected_physical_use=_use(source_topology, target_topology),
        known_limitation=(
            "mechanical registry support only; local readiness and closed-loop "
            "qualification remain mandatory"
        ),
    )


def find_role_transition(
    result: TransitionAdmissibilityResult,
    role_id: str,
) -> Optional[RoleTransitionGeometry]:
    for role in result.role_geometry:
        if role.role_id == role_id:
            return role
    return None
