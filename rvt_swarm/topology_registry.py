"""Authoritative immutable topology registry and mechanical geometry contract.

The registry owns topology identity, persistent role construction, template
geometry, nominal formation graphs, pairwise offsets, mechanical validity,
transition geometry, serialization, and explicit legacy migration.

Full templates are mission-setup/evaluation objects. Deployable control consumes
only :class:`RuntimeTopologyRoleView`, which contains one role and its local
formation-neighbour offsets. No function in this module accepts joint runtime
state or chooses a topology.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple


TOPOLOGY_REGISTRY_SCHEMA_VERSION = "rvt-topology-registry/v1"
TOPOLOGY_DEFINITION_SERIALIZATION_VERSION = "rvt-topology-definition/v1"
PERSISTENT_ROLE_SCHEMA_VERSION = "rvt-persistent-roles/v1"
TOPOLOGY_TEMPLATE_SCHEMA_VERSION = "rvt-topology-template/v1"
TOPOLOGY_MIGRATION_SCHEMA_VERSION = "rvt-topology-migration/v1"

# KEEP and LINE preserve the selected decentralized runtime IDs. COMPACT uses a
# previously unused ID so legacy value 1 (retired SPLIT or COMPRESS action) can
# never be reinterpreted silently.
KEEP = 0
LINE = 2
COMPACT = 5
PRIMARY_TOPOLOGY_IDS: Tuple[int, ...] = (KEEP, COMPACT, LINE)

Vec2 = Tuple[float, float]
Edge = Tuple[str, str]


class TopologyRegistryError(ValueError):
    """Base error for invalid registry construction or lookup."""


class TopologySerializationError(TopologyRegistryError):
    """Serialized role/template data is unknown, incomplete, or tampered."""


class LegacyTopologyMigrationError(TopologyRegistryError):
    """Legacy topology semantics cannot be resolved without guessing."""


@dataclass(frozen=True)
class PersistentRole:
    role_id: str
    robot_key: str
    ordinal: int

    def __post_init__(self) -> None:
        if not self.role_id or not self.robot_key:
            raise TopologyRegistryError("role_id and robot_key must be nonempty")
        if not isinstance(self.ordinal, int) or self.ordinal < 0:
            raise TopologyRegistryError("role ordinal must be a nonnegative integer")


@dataclass(frozen=True)
class PersistentRoleSet:
    schema_version: str
    roles: Tuple[PersistentRole, ...]

    def __post_init__(self) -> None:
        if self.schema_version != PERSISTENT_ROLE_SCHEMA_VERSION:
            raise TopologyRegistryError("unsupported persistent-role schema")
        role_ids = tuple(role.role_id for role in self.roles)
        robot_keys = tuple(role.robot_key for role in self.roles)
        ordinals = tuple(role.ordinal for role in self.roles)
        if len(set(role_ids)) != len(role_ids):
            raise TopologyRegistryError("persistent role IDs must be unique")
        if len(set(robot_keys)) != len(robot_keys):
            raise TopologyRegistryError("robot keys must be unique")
        if ordinals != tuple(range(len(self.roles))):
            raise TopologyRegistryError("role ordinals must be contiguous and ordered")

    @property
    def team_size(self) -> int:
        return len(self.roles)

    def role_for_robot(self, robot_key: object) -> PersistentRole:
        key = _canonical_robot_key(robot_key)
        for role in self.roles:
            if role.robot_key == key:
                return role
        raise TopologyRegistryError(f"unknown robot key {robot_key!r}")

    def role(self, role_id: str) -> PersistentRole:
        for role in self.roles:
            if role.role_id == role_id:
                return role
        raise TopologyRegistryError(f"unknown persistent role {role_id!r}")


@dataclass(frozen=True)
class RoleGeometry:
    role_id: str
    ordinal: int
    offset: Vec2


@dataclass(frozen=True)
class GraphStatistics:
    node_count: int
    edge_count: int
    average_degree: float
    maximum_degree: int
    diameter_hops: int
    connected: bool


@dataclass(frozen=True)
class ControllerCompatibilityMetadata:
    status: str
    pairwise_controller_supported: bool
    qualification_scope: str
    notes: str


@dataclass(frozen=True)
class TopologyTemplate:
    schema_version: str
    registry_schema_version: str
    topology_id: int
    canonical_name: str
    serialization_version: str
    nominal_spacing_meters: float
    roles: Tuple[RoleGeometry, ...]
    edges: Tuple[Edge, ...]

    def __post_init__(self) -> None:
        if self.schema_version != TOPOLOGY_TEMPLATE_SCHEMA_VERSION:
            raise TopologyRegistryError("unsupported topology-template schema")
        if self.registry_schema_version != TOPOLOGY_REGISTRY_SCHEMA_VERSION:
            raise TopologyRegistryError("topology template has wrong registry schema")
        if not math.isfinite(self.nominal_spacing_meters) or \
                self.nominal_spacing_meters <= 0.0:
            raise TopologyRegistryError("nominal spacing must be finite and positive")
        ids = tuple(role.role_id for role in self.roles)
        if len(ids) == 0 or len(set(ids)) != len(ids):
            raise TopologyRegistryError("template roles must be nonempty and unique")
        if tuple(role.ordinal for role in self.roles) != tuple(range(len(ids))):
            raise TopologyRegistryError("template role ordinals are invalid")
        valid_ids = set(ids)
        for a, b in self.edges:
            if a == b or a not in valid_ids or b not in valid_ids:
                raise TopologyRegistryError("nominal graph contains an invalid edge")
            if a > b:
                raise TopologyRegistryError("nominal graph edges must be canonical")
        if tuple(sorted(set(self.edges))) != self.edges:
            raise TopologyRegistryError("nominal graph edges must be sorted and unique")

    @property
    def team_size(self) -> int:
        return len(self.roles)

    @property
    def role_ids(self) -> Tuple[str, ...]:
        return tuple(role.role_id for role in self.roles)

    def role(self, role_id: str) -> RoleGeometry:
        for role in self.roles:
            if role.role_id == role_id:
                return role
        raise TopologyRegistryError(
            f"role {role_id!r} does not exist in {self.canonical_name}"
        )

    def offset(self, role_id: str) -> Vec2:
        return self.role(role_id).offset

    def neighbour_role_ids(self, role_id: str) -> Tuple[str, ...]:
        self.role(role_id)
        neighbours = []
        for a, b in self.edges:
            if a == role_id:
                neighbours.append(b)
            elif b == role_id:
                neighbours.append(a)
        return tuple(sorted(neighbours))


@dataclass(frozen=True)
class RuntimeNeighbourGeometry:
    role_id: str
    desired_offset_world: Vec2


@dataclass(frozen=True)
class RuntimeTopologyRoleView:
    """Static robot-local geometry supplied at mission setup."""

    role_id: str
    committed_topology_id: int
    own_template_offset: Vec2
    formation_neighbours: Tuple[RuntimeNeighbourGeometry, ...]


@dataclass(frozen=True)
class TopologySeparation:
    topology_a_id: int
    topology_b_id: int
    team_size: int
    maximum_role_distance_meters: float
    rms_role_distance_meters: float
    normalized_maximum_distance: float
    tube_overlap: bool
    mechanically_distinct: bool


@dataclass(frozen=True)
class RoleTransitionGeometry:
    role_id: str
    source_offset: Vec2
    target_offset: Vec2
    displacement: Vec2
    magnitude_meters: float
    longitudinal_component_meters: float
    lateral_component_meters: float
    swept_segment: Tuple[Vec2, Vec2]
    required_observation_extent_meters: float


@dataclass(frozen=True)
class TopologyTransitionGeometry:
    source_topology_id: int
    target_topology_id: int
    team_size: int
    roles: Tuple[RoleTransitionGeometry, ...]
    maximum_role_displacement_meters: float
    maximum_required_observation_extent_meters: float


@dataclass(frozen=True)
class TopologyIssue:
    code: str
    field_path: str
    message: str


@dataclass(frozen=True)
class TopologyValidityResult:
    supported: bool
    topology_id: int
    canonical_name: str
    team_size: int
    errors: Tuple[TopologyIssue, ...]
    warnings: Tuple[TopologyIssue, ...]
    minimum_clearance_meters: float
    width_meters: float
    length_meters: float
    graph_statistics: GraphStatistics
    distinguishability_statistics: Tuple[TopologySeparation, ...]
    required_sensor_extent_meters: float
    controller_compatibility_status: str


@dataclass(frozen=True)
class LegacyTopologyMigrationResult:
    migration_schema_version: str
    source_vocabulary: str
    source_value: str
    supported: bool
    canonical_topology_id: Optional[int]
    canonical_name: Optional[str]
    semantic_equivalence: str
    disposition: str
    message: str


RoleGenerator = Callable[[PersistentRoleSet, float], Tuple[Vec2, ...]]
GraphGenerator = Callable[[PersistentRoleSet], Tuple[Edge, ...]]


@dataclass(frozen=True)
class TopologyDefinition:
    topology_id: int
    canonical_name: str
    aliases: Tuple[str, ...]
    semantic_description: str
    role_generator: RoleGenerator
    nominal_neighbour_graph_generator: GraphGenerator
    local_pairwise_offset_generator: Callable[[Vec2, Vec2, Vec2], Vec2]
    physical_validity_checker: Callable[..., TopologyValidityResult]
    transition_geometry_provider: Callable[..., TopologyTransitionGeometry]
    controller_compatibility_metadata: ControllerCompatibilityMetadata
    metric_template_provider: Callable[[TopologyTemplate], Tuple[Vec2, ...]]
    serialization_version: str


def _canonical_robot_key(robot_key: object) -> str:
    if isinstance(robot_key, bool):
        raise TopologyRegistryError("boolean robot keys are not supported")
    if isinstance(robot_key, int):
        if robot_key < 0:
            raise TopologyRegistryError("integer robot keys must be nonnegative")
        return f"int:{robot_key:020d}"
    if isinstance(robot_key, str) and robot_key:
        return "str:" + robot_key
    raise TopologyRegistryError("robot keys must be nonnegative integers or strings")


def generate_persistent_roles(
    robot_keys_or_team_size: int | Sequence[object],
) -> PersistentRoleSet:
    """Generate stable roles from robot identity, independent of input order."""
    if isinstance(robot_keys_or_team_size, bool):
        raise TopologyRegistryError("team size must be an integer")
    if isinstance(robot_keys_or_team_size, int):
        if robot_keys_or_team_size <= 0:
            raise TopologyRegistryError("team size must be positive")
        keys = tuple(_canonical_robot_key(i) for i in range(robot_keys_or_team_size))
    else:
        keys = tuple(_canonical_robot_key(key) for key in robot_keys_or_team_size)
        if not keys:
            raise TopologyRegistryError("at least one robot key is required")
    if len(set(keys)) != len(keys):
        raise TopologyRegistryError("robot keys must be unique")
    ordered = tuple(sorted(keys))
    width = max(4, len(str(len(ordered) - 1)))
    roles = tuple(
        PersistentRole(
            role_id=f"role-{ordinal:0{width}d}",
            robot_key=key,
            ordinal=ordinal,
        )
        for ordinal, key in enumerate(ordered)
    )
    return PersistentRoleSet(PERSISTENT_ROLE_SCHEMA_VERSION, roles)


def _centered(points: Sequence[Vec2]) -> Tuple[Vec2, ...]:
    if not points:
        raise TopologyRegistryError("a topology template cannot be empty")
    mean_x = math.fsum(point[0] for point in points) / len(points)
    mean_y = math.fsum(point[1] for point in points) / len(points)
    return tuple((float(x - mean_x), float(y - mean_y)) for x, y in points)


def _grid_offsets(role_set: PersistentRoleSet, spacing: float, columns: int) \
        -> Tuple[Vec2, ...]:
    if columns <= 0:
        raise TopologyRegistryError("grid columns must be positive")
    n = role_set.team_size
    rows = int(math.ceil(n / columns))
    raw = []
    for ordinal in range(n):
        row, column = divmod(ordinal, columns)
        raw.append((
            (row - (rows - 1) / 2.0) * spacing,
            -(column - (columns - 1) / 2.0) * spacing,
        ))
    return _centered(raw)


def _keep_offsets(role_set: PersistentRoleSet, spacing: float) -> Tuple[Vec2, ...]:
    columns = max(2, int(math.ceil(math.sqrt(role_set.team_size))))
    return _grid_offsets(role_set, spacing, columns)


def _compact_offsets(
    role_set: PersistentRoleSet, spacing: float
) -> Tuple[Vec2, ...]:
    columns = 1 if role_set.team_size == 1 else 2
    return _grid_offsets(role_set, spacing, columns)


def _line_offsets(role_set: PersistentRoleSet, spacing: float) -> Tuple[Vec2, ...]:
    n = role_set.team_size
    return tuple(
        ((role.ordinal - (n - 1) / 2.0) * spacing, 0.0)
        for role in role_set.roles
    )


def _canonical_edge(role_a: str, role_b: str) -> Edge:
    if role_a == role_b:
        raise TopologyRegistryError("self edges are not permitted")
    return (role_a, role_b) if role_a < role_b else (role_b, role_a)


def _grid_edges(role_set: PersistentRoleSet, columns: int) -> Tuple[Edge, ...]:
    n = role_set.team_size
    role_ids = tuple(role.role_id for role in role_set.roles)
    edges = set()
    for ordinal in range(n):
        row, column = divmod(ordinal, columns)
        right = ordinal + 1
        below = ordinal + columns
        if column + 1 < columns and right < n and right // columns == row:
            edges.add(_canonical_edge(role_ids[ordinal], role_ids[right]))
        if below < n:
            edges.add(_canonical_edge(role_ids[ordinal], role_ids[below]))
    return tuple(sorted(edges))


def _keep_graph(role_set: PersistentRoleSet) -> Tuple[Edge, ...]:
    columns = max(2, int(math.ceil(math.sqrt(role_set.team_size))))
    return _grid_edges(role_set, columns)


def _compact_graph(role_set: PersistentRoleSet) -> Tuple[Edge, ...]:
    return _grid_edges(role_set, 1 if role_set.team_size == 1 else 2)


def _line_graph(role_set: PersistentRoleSet) -> Tuple[Edge, ...]:
    role_ids = tuple(role.role_id for role in role_set.roles)
    return tuple(
        _canonical_edge(role_ids[index], role_ids[index + 1])
        for index in range(len(role_ids) - 1)
    )


def _rotation(mission_direction: Vec2) -> Tuple[Vec2, Vec2]:
    dx, dy = float(mission_direction[0]), float(mission_direction[1])
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        dx, dy, norm = 1.0, 0.0, 1.0
    c, s = dx / norm, dy / norm
    return ((c, -s), (s, c))


def rotate_template_vector(vector: Vec2, mission_direction: Vec2) -> Vec2:
    matrix = _rotation(mission_direction)
    x, y = float(vector[0]), float(vector[1])
    return (
        float(matrix[0][0] * x + matrix[0][1] * y),
        float(matrix[1][0] * x + matrix[1][1] * y),
    )


def local_pairwise_offset(
    role_i_offset: Vec2,
    role_j_offset: Vec2,
    mission_direction: Vec2,
) -> Vec2:
    difference = (
        float(role_j_offset[0]) - float(role_i_offset[0]),
        float(role_j_offset[1]) - float(role_i_offset[1]),
    )
    return rotate_template_vector(difference, mission_direction)


def metric_template_offsets(template: TopologyTemplate) -> Tuple[Vec2, ...]:
    """Full centered template for offline Metric V3/evaluation only."""
    return tuple(role.offset for role in template.roles)


def _compatibility(topology_id: int) -> ControllerCompatibilityMetadata:
    if topology_id in (KEEP, LINE):
        return ControllerCompatibilityMetadata(
            status="verified-existing-pairwise-base",
            pairwise_controller_supported=True,
            qualification_scope="pre-phase3-keep-line",
            notes="Registry geometry is semantically equivalent to the selected base.",
        )
    return ControllerCompatibilityMetadata(
        status="mechanically-compatible-pending-phase6-qualification",
        pairwise_controller_supported=True,
        qualification_scope="mechanical-only",
        notes="Uses the same pairwise offset law and frozen gains; no closed-loop claim.",
    )


def construct_topology(
    topology: int | str,
    formation_config: Optional[object] = None,
    *,
    role_set: Optional[PersistentRoleSet] = None,
    robot_keys_or_team_size: Optional[int | Sequence[object]] = None,
) -> TopologyTemplate:
    definition = get_topology_definition(topology)
    if formation_config is None:
        from .runtime_configuration import DEFAULT_RUNTIME_CONFIG
        formation_config = DEFAULT_RUNTIME_CONFIG.formation
    spacing = float(getattr(formation_config, "nominal_spacing_meters"))
    if not math.isfinite(spacing) or spacing <= 0.0:
        raise TopologyRegistryError("formation spacing must be finite and positive")
    if role_set is None:
        if robot_keys_or_team_size is None:
            raise TopologyRegistryError("role_set or robot_keys_or_team_size is required")
        role_set = generate_persistent_roles(robot_keys_or_team_size)
    elif robot_keys_or_team_size is not None:
        raise TopologyRegistryError("provide role_set or robot keys, not both")
    offsets = definition.role_generator(role_set, spacing)
    if len(offsets) != role_set.team_size:
        raise TopologyRegistryError("role generator returned the wrong role count")
    roles = tuple(
        RoleGeometry(role.role_id, role.ordinal, tuple(map(float, offsets[role.ordinal])))
        for role in role_set.roles
    )
    edges = definition.nominal_neighbour_graph_generator(role_set)
    return TopologyTemplate(
        schema_version=TOPOLOGY_TEMPLATE_SCHEMA_VERSION,
        registry_schema_version=TOPOLOGY_REGISTRY_SCHEMA_VERSION,
        topology_id=definition.topology_id,
        canonical_name=definition.canonical_name,
        serialization_version=definition.serialization_version,
        nominal_spacing_meters=spacing,
        roles=roles,
        edges=edges,
    )


@dataclass(frozen=True)
class _FormationSpacingView:
    nominal_spacing_meters: float


def construct_topology_from_spacing(
    topology: int | str,
    team_size: int,
    nominal_spacing_meters: float,
    *,
    role_set: Optional[PersistentRoleSet] = None,
) -> TopologyTemplate:
    """Convenience adapter for compatibility modules with a scalar spacing."""
    roles = role_set or generate_persistent_roles(team_size)
    if roles.team_size != team_size:
        raise TopologyRegistryError("role count does not match team size")
    return construct_topology(
        topology,
        _FormationSpacingView(float(nominal_spacing_meters)),
        role_set=roles,
    )


def construct_primary_templates(
    formation_config: Optional[object] = None,
    *,
    role_set: Optional[PersistentRoleSet] = None,
    robot_keys_or_team_size: Optional[int | Sequence[object]] = None,
) -> Tuple[TopologyTemplate, ...]:
    if role_set is None:
        if robot_keys_or_team_size is None:
            raise TopologyRegistryError("role_set or robot keys are required")
        role_set = generate_persistent_roles(robot_keys_or_team_size)
    elif robot_keys_or_team_size is not None:
        raise TopologyRegistryError("provide role_set or robot keys, not both")
    return tuple(
        construct_topology(topology_id, formation_config, role_set=role_set)
        for topology_id in PRIMARY_TOPOLOGY_IDS
    )


def template_world_positions(
    template: TopologyTemplate,
    origin_world: Vec2,
    mission_direction: Vec2,
) -> Tuple[Vec2, ...]:
    ox, oy = float(origin_world[0]), float(origin_world[1])
    return tuple(
        (ox + rotated[0], oy + rotated[1])
        for rotated in (
            rotate_template_vector(role.offset, mission_direction)
            for role in template.roles
        )
    )


def runtime_local_view(
    template: TopologyTemplate,
    role_id: str,
    mission_direction: Vec2,
) -> RuntimeTopologyRoleView:
    own = template.offset(role_id)
    neighbours = tuple(
        RuntimeNeighbourGeometry(
            neighbour_id,
            local_pairwise_offset(own, template.offset(neighbour_id), mission_direction),
        )
        for neighbour_id in template.neighbour_role_ids(role_id)
    )
    return RuntimeTopologyRoleView(
        role_id=role_id,
        committed_topology_id=template.topology_id,
        own_template_offset=own,
        formation_neighbours=neighbours,
    )


def graph_statistics(template: TopologyTemplate) -> GraphStatistics:
    adjacency: Dict[str, set[str]] = {role_id: set() for role_id in template.role_ids}
    for a, b in template.edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    n = template.team_size
    if n == 1:
        return GraphStatistics(1, 0, 0.0, 0, 0, True)
    visited = set()
    stack = [template.role_ids[0]]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(adjacency[current] - visited)
    connected = len(visited) == n
    diameter = 0
    if connected:
        for source in template.role_ids:
            distances = {source: 0}
            queue = [source]
            for current in queue:
                for neighbour in sorted(adjacency[current]):
                    if neighbour not in distances:
                        distances[neighbour] = distances[current] + 1
                        queue.append(neighbour)
            diameter = max(diameter, max(distances.values(), default=0))
    degrees = tuple(len(adjacency[role_id]) for role_id in template.role_ids)
    return GraphStatistics(
        node_count=n,
        edge_count=len(template.edges),
        average_degree=float(math.fsum(degrees) / n),
        maximum_degree=max(degrees, default=0),
        diameter_hops=diameter if connected else -1,
        connected=connected,
    )


def template_extents(template: TopologyTemplate) -> Tuple[float, float]:
    xs = tuple(role.offset[0] for role in template.roles)
    ys = tuple(role.offset[1] for role in template.roles)
    return float(max(ys) - min(ys)), float(max(xs) - min(xs))


def minimum_nominal_clearance(template: TopologyTemplate) -> float:
    minimum = math.inf
    for i, role_i in enumerate(template.roles):
        for role_j in template.roles[i + 1:]:
            dx = role_j.offset[0] - role_i.offset[0]
            dy = role_j.offset[1] - role_i.offset[1]
            minimum = min(minimum, math.hypot(dx, dy))
    return 0.0 if template.team_size == 1 else float(minimum)


def topology_separation(
    template_a: TopologyTemplate,
    template_b: TopologyTemplate,
    formation_tolerance_meters: float,
) -> TopologySeparation:
    if template_a.role_ids != template_b.role_ids:
        raise TopologyRegistryError("topology separation requires identical role IDs")
    if template_a.team_size != template_b.team_size:
        raise TopologyRegistryError("topology separation requires equal team size")
    if not math.isfinite(formation_tolerance_meters) or \
            formation_tolerance_meters < 0.0:
        raise TopologyRegistryError("formation tolerance must be finite and nonnegative")
    distances = tuple(
        math.hypot(
            role_b.offset[0] - role_a.offset[0],
            role_b.offset[1] - role_a.offset[1],
        )
        for role_a, role_b in zip(template_a.roles, template_b.roles)
    )
    maximum = max(distances, default=0.0)
    rms = math.sqrt(math.fsum(value * value for value in distances) / len(distances))
    spacing = template_a.nominal_spacing_meters
    overlap = maximum <= 2.0 * formation_tolerance_meters
    return TopologySeparation(
        topology_a_id=template_a.topology_id,
        topology_b_id=template_b.topology_id,
        team_size=template_a.team_size,
        maximum_role_distance_meters=float(maximum),
        rms_role_distance_meters=float(rms),
        normalized_maximum_distance=float(maximum / spacing),
        tube_overlap=bool(overlap),
        mechanically_distinct=bool(maximum > 1e-9),
    )


def all_primary_separations(
    templates: Sequence[TopologyTemplate],
    formation_tolerance_meters: float,
) -> Tuple[TopologySeparation, ...]:
    by_id = {template.topology_id: template for template in templates}
    required = set(PRIMARY_TOPOLOGY_IDS)
    if set(by_id) != required:
        raise TopologyRegistryError("primary separation requires exactly three templates")
    pairs = ((KEEP, COMPACT), (KEEP, LINE), (COMPACT, LINE))
    return tuple(
        topology_separation(by_id[a], by_id[b], formation_tolerance_meters)
        for a, b in pairs
    )


def transition_geometry(
    source: TopologyTemplate,
    target: TopologyTemplate,
    runtime_config: Optional[object] = None,
) -> TopologyTransitionGeometry:
    if source.role_ids != target.role_ids:
        raise TopologyRegistryError("transition templates must share persistent roles")
    if runtime_config is None:
        from .runtime_configuration import DEFAULT_RUNTIME_CONFIG
        runtime_config = DEFAULT_RUNTIME_CONFIG
    physical = getattr(runtime_config, "physical")
    controller = getattr(runtime_config, "controller")
    safety = getattr(runtime_config, "safety")
    clearance = float(
        physical.robot_radius_meters
        + safety.obstacle_clearance_margin_meters
    )
    extra = (
        float(controller.transition_response_lateral_bound_meters)
        + float(controller.protocol_lateral_drift_bound_meters)
        + float(safety.transition_observation_margin_meters)
    )
    roles = []
    for source_role, target_role in zip(source.roles, target.roles):
        dx = target_role.offset[0] - source_role.offset[0]
        dy = target_role.offset[1] - source_role.offset[1]
        roles.append(RoleTransitionGeometry(
            role_id=source_role.role_id,
            source_offset=source_role.offset,
            target_offset=target_role.offset,
            displacement=(float(dx), float(dy)),
            magnitude_meters=float(math.hypot(dx, dy)),
            longitudinal_component_meters=float(dx),
            lateral_component_meters=float(dy),
            swept_segment=(source_role.offset, target_role.offset),
            required_observation_extent_meters=float(abs(dy) + clearance + extra),
        ))
    return TopologyTransitionGeometry(
        source_topology_id=source.topology_id,
        target_topology_id=target.topology_id,
        team_size=source.team_size,
        roles=tuple(roles),
        maximum_role_displacement_meters=max(
            (role.magnitude_meters for role in roles), default=0.0
        ),
        maximum_required_observation_extent_meters=max(
            (role.required_observation_extent_meters for role in roles), default=0.0
        ),
    )


def validate_topology_configuration(
    topology: int | str,
    runtime_config: object,
    *,
    role_set: Optional[PersistentRoleSet] = None,
    scientific_comparison: bool = True,
) -> TopologyValidityResult:
    definition = get_topology_definition(topology)
    mission = getattr(runtime_config, "mission")
    protocol = getattr(runtime_config, "protocol")
    formation = getattr(runtime_config, "formation")
    sensing = getattr(runtime_config, "sensing")
    team_size = int(mission.team_size)
    errors: list[TopologyIssue] = []
    warnings: list[TopologyIssue] = []
    if team_size <= 0:
        errors.append(TopologyIssue("invalid_team_size", "mission.team_size", "team size must be positive"))
    if team_size > int(protocol.maximum_team_size):
        errors.append(TopologyIssue(
            "team_size_exceeds_maximum", "mission.team_size",
            "team size exceeds configured maximum_team_size",
        ))
    if role_set is None and team_size > 0:
        role_set = generate_persistent_roles(team_size)
    if role_set is not None and role_set.team_size != team_size:
        errors.append(TopologyIssue(
            "role_count_mismatch", "persistent_roles",
            "persistent role count does not match mission team size",
        ))
    empty_graph = GraphStatistics(max(team_size, 0), 0, 0.0, 0, -1, False)
    if errors or role_set is None:
        return TopologyValidityResult(
            False, definition.topology_id, definition.canonical_name, team_size,
            tuple(errors), tuple(warnings), 0.0, 0.0, 0.0, empty_graph,
            tuple(), 0.0, definition.controller_compatibility_metadata.status,
        )
    try:
        templates = construct_primary_templates(formation, role_set=role_set)
        template_by_id = {item.topology_id: item for item in templates}
        template = template_by_id[definition.topology_id]
    except (TopologyRegistryError, ValueError) as exc:
        errors.append(TopologyIssue("construction_failure", "topology", str(exc)))
        return TopologyValidityResult(
            False, definition.topology_id, definition.canonical_name, team_size,
            tuple(errors), tuple(warnings), 0.0, 0.0, 0.0, empty_graph,
            tuple(), 0.0, definition.controller_compatibility_metadata.status,
        )

    if len(template.roles) != team_size:
        errors.append(TopologyIssue("role_count_mismatch", "template.roles", "wrong template role count"))
    if len(set(template.role_ids)) != team_size:
        errors.append(TopologyIssue("duplicate_role_id", "template.roles", "template role IDs are not unique"))
    for role in template.roles:
        if not all(math.isfinite(value) for value in role.offset):
            errors.append(TopologyIssue("nonfinite_offset", f"template.roles.{role.role_id}", "role offset is nonfinite"))
    centroid_x = math.fsum(role.offset[0] for role in template.roles) / team_size
    centroid_y = math.fsum(role.offset[1] for role in template.roles) / team_size
    if math.hypot(centroid_x, centroid_y) > 1e-9:
        errors.append(TopologyIssue("template_not_centered", "template.roles", "template centroid exceeds tolerance"))

    minimum_clearance = minimum_nominal_clearance(template)
    physical = getattr(runtime_config, "physical")
    safety = getattr(runtime_config, "safety")
    required_clearance = float(
        2.0 * physical.robot_radius_meters
        + safety.inter_robot_safety_margin_meters
    )
    if team_size > 1 and minimum_clearance < required_clearance:
        errors.append(TopologyIssue(
            "nominal_clearance_violation", "formation.nominal_spacing_meters",
            f"minimum {minimum_clearance:.6g} m is below required {required_clearance:.6g} m",
        ))
    stats = graph_statistics(template)
    if not stats.connected:
        errors.append(TopologyIssue("nominal_graph_disconnected", "template.edges", "nominal formation graph is disconnected"))

    for a, b in template.edges:
        d_ab = local_pairwise_offset(template.offset(a), template.offset(b), (1.0, 0.0))
        d_ba = local_pairwise_offset(template.offset(b), template.offset(a), (1.0, 0.0))
        if math.hypot(d_ab[0] + d_ba[0], d_ab[1] + d_ba[1]) > 1e-9:
            errors.append(TopologyIssue("pairwise_offset_inconsistent", "template.edges", "edge offsets are not antisymmetric"))
            break

    tolerance = float(
        formation.formation_tolerance_ratio
        * formation.nominal_spacing_meters
    )
    separations = all_primary_separations(templates, tolerance)
    if scientific_comparison:
        for separation in separations:
            if definition.topology_id not in (
                separation.topology_a_id, separation.topology_b_id
            ):
                continue
            if not separation.mechanically_distinct:
                errors.append(TopologyIssue("topologies_identical", "topology", "primary topology pair is identical"))
            if separation.tube_overlap:
                errors.append(TopologyIssue(
                    "topology_tubes_overlap", "formation.formation_tolerance_ratio",
                    f"topology pair {separation.topology_a_id}/{separation.topology_b_id} overlaps",
                ))

    transitions = tuple(
        transition_geometry(template, other, runtime_config)
        for other in templates
        if other.topology_id != template.topology_id
    )
    sensor_extent = max(
        (item.maximum_required_observation_extent_meters for item in transitions),
        default=0.0,
    )
    if sensor_extent > float(sensing.obstacle_sensing_range_meters):
        errors.append(TopologyIssue(
            "sensor_envelope_unsupported", "sensing.obstacle_sensing_range_meters",
            f"required lateral extent {sensor_extent:.6g} m exceeds R_obs",
        ))
    if definition.topology_id == COMPACT:
        warnings.append(TopologyIssue(
            "forced_topology_qualification_pending", "controller",
            "COMPACT is mechanically compatible but awaits Phase 6 qualification",
        ))
    width, length = template_extents(template)
    return TopologyValidityResult(
        supported=not errors,
        topology_id=definition.topology_id,
        canonical_name=definition.canonical_name,
        team_size=team_size,
        errors=tuple(errors),
        warnings=tuple(warnings),
        minimum_clearance_meters=minimum_clearance,
        width_meters=width,
        length_meters=length,
        graph_statistics=stats,
        distinguishability_statistics=tuple(
            item for item in separations
            if definition.topology_id in (item.topology_a_id, item.topology_b_id)
        ),
        required_sensor_extent_meters=sensor_extent,
        controller_compatibility_status=(
            definition.controller_compatibility_metadata.status
        ),
    )


def _strict_object(raw: object, expected: set[str], path: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise TopologySerializationError(f"{path} must be an object")
    actual = set(raw)
    unknown = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unknown:
        raise TopologySerializationError(f"{path} has unknown fields: {unknown}")
    if missing:
        raise TopologySerializationError(f"{path} is missing fields: {missing}")
    return raw


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True,
        separators=(",", ":"), sort_keys=True,
    )


def dump_persistent_roles(role_set: PersistentRoleSet) -> str:
    payload = {
        "schema_version": PERSISTENT_ROLE_SCHEMA_VERSION,
        "roles": [asdict(role) for role in role_set.roles],
    }
    return _canonical_json(payload) + "\n"


def load_persistent_roles(payload: str) -> PersistentRoleSet:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TopologySerializationError(f"invalid role JSON: {exc}") from exc
    root = _strict_object(raw, {"schema_version", "roles"}, "roles")
    if root["schema_version"] != PERSISTENT_ROLE_SCHEMA_VERSION:
        raise TopologySerializationError("persistent-role schema mismatch")
    if not isinstance(root["roles"], list):
        raise TopologySerializationError("roles.roles must be a list")
    roles = []
    for index, item in enumerate(root["roles"]):
        role = _strict_object(item, {"role_id", "robot_key", "ordinal"}, f"roles[{index}]")
        roles.append(PersistentRole(
            role_id=str(role["role_id"]),
            robot_key=str(role["robot_key"]),
            ordinal=int(role["ordinal"]),
        ))
    return PersistentRoleSet(PERSISTENT_ROLE_SCHEMA_VERSION, tuple(roles))


def _template_payload(
    template: TopologyTemplate,
    role_set: PersistentRoleSet,
) -> Dict[str, object]:
    source = {
        "topology_id": template.topology_id,
        "canonical_name": template.canonical_name,
        "nominal_spacing_meters": template.nominal_spacing_meters,
        "persistent_roles": [asdict(role) for role in role_set.roles],
    }
    derived = {
        "roles": [asdict(role) for role in template.roles],
        "edges": [list(edge) for edge in template.edges],
    }
    source_hash = hashlib.sha256(_canonical_json(source).encode("ascii")).hexdigest()
    return {
        "schema_version": TOPOLOGY_TEMPLATE_SCHEMA_VERSION,
        "registry_schema_version": TOPOLOGY_REGISTRY_SCHEMA_VERSION,
        "definition_serialization_version": template.serialization_version,
        "source_sha256": source_hash,
        "units": {"nominal_spacing_meters": "m", "offset": "m"},
        "source": source,
        "derived": derived,
    }


def dump_topology_template(
    template: TopologyTemplate,
    role_set: PersistentRoleSet,
) -> str:
    if template.role_ids != tuple(role.role_id for role in role_set.roles):
        raise TopologySerializationError("role set does not match topology template")
    return _canonical_json(_template_payload(template, role_set)) + "\n"


def load_topology_template(payload: str) -> Tuple[TopologyTemplate, PersistentRoleSet]:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TopologySerializationError(f"invalid template JSON: {exc}") from exc
    root_fields = {
        "schema_version", "registry_schema_version",
        "definition_serialization_version", "source_sha256", "units",
        "source", "derived",
    }
    root = _strict_object(raw, root_fields, "template")
    if root["schema_version"] != TOPOLOGY_TEMPLATE_SCHEMA_VERSION:
        raise TopologySerializationError("topology-template schema mismatch")
    if root["registry_schema_version"] != TOPOLOGY_REGISTRY_SCHEMA_VERSION:
        raise TopologySerializationError("topology-registry schema mismatch")
    units = _strict_object(root["units"], {"nominal_spacing_meters", "offset"}, "units")
    if units != {"nominal_spacing_meters": "m", "offset": "m"}:
        raise TopologySerializationError("topology-template units mismatch")
    source = _strict_object(
        root["source"],
        {"topology_id", "canonical_name", "nominal_spacing_meters", "persistent_roles"},
        "source",
    )
    expected_hash = hashlib.sha256(
        _canonical_json(dict(source)).encode("ascii")
    ).hexdigest()
    if root["source_sha256"] != expected_hash:
        raise TopologySerializationError("topology source hash mismatch")
    roles_json = _canonical_json({
        "schema_version": PERSISTENT_ROLE_SCHEMA_VERSION,
        "roles": source["persistent_roles"],
    })
    role_set = load_persistent_roles(roles_json)

    from .runtime_configuration import FormationConfig
    formation = FormationConfig(
        nominal_spacing_meters=float(source["nominal_spacing_meters"])
    )
    template = construct_topology(
        int(source["topology_id"]), formation, role_set=role_set
    )
    if source["canonical_name"] != template.canonical_name:
        raise TopologySerializationError("topology ID/name mismatch")
    if root["definition_serialization_version"] != template.serialization_version:
        raise TopologySerializationError("topology definition version mismatch")
    expected = _template_payload(template, role_set)
    if _canonical_json(raw) != _canonical_json(expected):
        raise TopologySerializationError("derived topology geometry was tampered")
    return template, role_set


def migrate_legacy_topology(
    value: int | str,
    source_vocabulary: str,
) -> LegacyTopologyMigrationResult:
    vocabularies: Dict[str, Dict[object, object]] = {
        TOPOLOGY_REGISTRY_SCHEMA_VERSION: {
            KEEP: KEEP, COMPACT: COMPACT, LINE: LINE,
            "keep": KEEP, "compact": COMPACT, "line": LINE,
        },
        "decentralized-binary-v1": {
            0: KEEP, 2: LINE, 1: "retired-split",
            "keep": KEEP, "line": LINE, "split": "retired-split",
        },
        "centralized-actions-v1": {
            0: KEEP, 1: "compress-action", 2: LINE,
            3: "retired-split", 4: "recover-action",
            "keep": KEEP, "compress": "compress-action", "line": LINE,
            "split": "retired-split", "split_hint": "retired-split",
            "recover": "recover-action",
        },
        "legacy-structural-id-v1": {
            0: KEEP, 2: LINE, 3: "retired-split",
            "keep": KEEP, "line": LINE, "split": "retired-split",
        },
        "legacy-structural-head-v1": {
            0: KEEP, 1: LINE, 2: "retired-split",
        },
        "binary-keep-line-head-v1": {0: KEEP, 1: LINE},
        "legacy-name-aliases-v1": {
            "grid": KEEP, "nominal": KEEP,
            "two_column": COMPACT, "reduced_footprint": COMPACT,
            "single_file": LINE,
        },
    }
    if source_vocabulary not in vocabularies:
        raise LegacyTopologyMigrationError(
            f"unknown legacy topology vocabulary {source_vocabulary!r}"
        )
    normalized: object = value.lower() if isinstance(value, str) else value
    mapped = vocabularies[source_vocabulary].get(normalized, "unknown")
    if isinstance(mapped, int):
        definition = get_topology_definition(mapped)
        equivalence = (
            "exact-primary-topology" if mapped in (KEEP, LINE)
            else "explicit-canonical-topology"
        )
        return LegacyTopologyMigrationResult(
            TOPOLOGY_MIGRATION_SCHEMA_VERSION,
            source_vocabulary,
            str(value),
            True,
            definition.topology_id,
            definition.canonical_name,
            equivalence,
            "migrated",
            "legacy value mapped through an explicit versioned vocabulary",
        )
    messages = {
        "retired-split": "SPLIT is retired and has no primary topology mapping",
        "compress-action": "COMPRESS is a scale action, not canonical COMPACT",
        "recover-action": "RECOVER is a lifecycle action, not a topology",
        "unknown": "legacy value is unknown in the declared vocabulary",
    }
    return LegacyTopologyMigrationResult(
        TOPOLOGY_MIGRATION_SCHEMA_VERSION,
        source_vocabulary,
        str(value),
        False,
        None,
        None,
        "not-equivalent",
        str(mapped),
        messages[str(mapped)],
    )


def checkpoint_topology_vocabulary(metadata: Mapping[str, object]) -> str:
    explicit = metadata.get("topology_vocabulary_version")
    if explicit is not None:
        value = str(explicit)
        migrate_legacy_topology(0, value)
        return value
    method = str(metadata.get("method", metadata.get("model_name", "")))
    if method in {
        "rvt_binary_recovery", "direct_keep_line_classifier",
        "decentralized_direct_selector", "decentralized_recovery_selector",
    }:
        return "binary-keep-line-head-v1"
    if method in {"rvt_swarm", "rvt_simple_rank", "direct_topology_classifier"}:
        return "legacy-structural-head-v1"
    raise LegacyTopologyMigrationError(
        "checkpoint has no explicit or recognized topology vocabulary; "
        "tensor width is not sufficient provenance"
    )


def _registry_definitions() -> Tuple[TopologyDefinition, ...]:
    common = dict(
        local_pairwise_offset_generator=local_pairwise_offset,
        physical_validity_checker=validate_topology_configuration,
        transition_geometry_provider=transition_geometry,
        metric_template_provider=metric_template_offsets,
        serialization_version=TOPOLOGY_DEFINITION_SERIALIZATION_VERSION,
    )
    return (
        TopologyDefinition(
            topology_id=KEEP,
            canonical_name="keep",
            aliases=("grid", "nominal"),
            semantic_description="Nominal square-like mission formation.",
            role_generator=_keep_offsets,
            nominal_neighbour_graph_generator=_keep_graph,
            controller_compatibility_metadata=_compatibility(KEEP),
            **common,
        ),
        TopologyDefinition(
            topology_id=COMPACT,
            canonical_name="compact",
            aliases=("two_column", "reduced_footprint"),
            semantic_description="Reduced-width two-column mission-aligned block.",
            role_generator=_compact_offsets,
            nominal_neighbour_graph_generator=_compact_graph,
            controller_compatibility_metadata=_compatibility(COMPACT),
            **common,
        ),
        TopologyDefinition(
            topology_id=LINE,
            canonical_name="line",
            aliases=("single_file",),
            semantic_description="Highly elongated single file along mission direction.",
            role_generator=_line_offsets,
            nominal_neighbour_graph_generator=_line_graph,
            controller_compatibility_metadata=_compatibility(LINE),
            **common,
        ),
    )


_DEFINITIONS = _registry_definitions()


def iter_topology_definitions() -> Tuple[TopologyDefinition, ...]:
    """Return the fixed scientific order; dictionary order is never consulted."""
    return _DEFINITIONS


def get_topology_definition(topology: int | str) -> TopologyDefinition:
    for definition in _DEFINITIONS:
        if topology == definition.topology_id or topology == definition.canonical_name:
            return definition
    raise TopologyRegistryError(
        f"unknown canonical topology {topology!r}; aliases require explicit migration"
    )


def topology_registry_fingerprint() -> str:
    payload = tuple(
        {
            "topology_id": definition.topology_id,
            "canonical_name": definition.canonical_name,
            "aliases": definition.aliases,
            "semantic_description": definition.semantic_description,
            "serialization_version": definition.serialization_version,
            "controller": asdict(definition.controller_compatibility_metadata),
        }
        for definition in _DEFINITIONS
    )
    return hashlib.sha256(_canonical_json(payload).encode("ascii")).hexdigest()
