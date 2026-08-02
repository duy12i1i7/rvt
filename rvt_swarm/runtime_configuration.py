"""Authoritative immutable configuration for deployable RVT runtime code.

Only source quantities live in the configuration hierarchy. Step counts,
round bounds, clearances, tolerances, observation widths, and lookahead are
materialized by :func:`derive_runtime_configuration` and are never loaded as
independent runtime settings.

This module intentionally defines no training or evaluation configuration.
Deployable modules can import it without importing an offline configuration
type as a side effect.
"""

from __future__ import annotations

import math
import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Optional, Tuple


RUNTIME_CONFIGURATION_SCHEMA_VERSION = "rvt-runtime-configuration/v1"
DERIVATION_VERSION = "rvt-runtime-derivations/v1"

SUPPORTED_MECHANICAL_TEAM_SIZES: Tuple[int, ...] = (5, 6, 8, 12, 16, 24)
GRAPH_FAMILIES: Tuple[str, ...] = ("path", "ring", "star", "complete")
TEMPORARY_DISCONNECTION_POLICIES: Tuple[str, ...] = (
    "retain_current_topology_and_abort_epoch",
)


@dataclass(frozen=True)
class PhysicalPlatformConfig:
    """Measured platform properties in SI units."""

    robot_radius_meters: float = 0.18
    maximum_speed_meters_per_second: float = 0.9
    maximum_acceleration_meters_per_second_squared: float = 0.6
    control_period_seconds: float = 0.15


@dataclass(frozen=True)
class MissionConfig:
    """Immutable mission assumptions shared by all robots."""

    team_size: int = 6
    recovery_dwell_seconds: float = 3.0
    shared_frame_id: str = "mission"
    heading_alignment: str = "predeclared_goal_direction"


@dataclass(frozen=True)
class FormationConfig:
    """Persistent-role formation requirements."""

    nominal_spacing_meters: float = 0.9
    # 0.55 / 0.9. The ratio is the source; 0.55 m is derived and frozen at the
    # nominal spacing.
    formation_tolerance_ratio: float = 11.0 / 18.0
    spacing_margin_meters: float = 0.05


@dataclass(frozen=True)
class SensingConfig:
    """Local sensor-envelope assumptions."""

    obstacle_sensing_range_meters: float = 3.0
    peer_sensing_range_meters: float = 4.0
    lidar_number_of_rays: int = 36
    lidar_field_of_view_radians: float = 4.712389


@dataclass(frozen=True)
class CommunicationConfig:
    """One-hop communication source values and simulator link settings."""

    communication_range_meters: float = 3.0
    communication_period_seconds: float = 0.15
    maximum_message_age_seconds: float = 0.45
    maximum_message_delay_seconds: float = 0.0
    symmetric_links: bool = True
    packet_loss_probability: float = 0.0
    asynchronous_offset_seconds: float = 0.0


@dataclass(frozen=True)
class ProtocolConfig:
    """Correctness assumptions and physical-time lifecycle requirements.

    A round count set to ``None`` is derived from the causal diameter bound.
    An explicit count is permitted only when it is at least that bound.
    """

    maximum_team_size: int = 24
    declared_maximum_component_diameter_hops: Optional[int] = 5
    intent_rounds: Optional[int] = None
    score_rounds: Optional[int] = None
    readiness_rounds: Optional[int] = None
    confirmation_rounds: Optional[int] = None
    evidence_persistence_seconds: float = 0.45
    event_collection_seconds: float = 0.0
    commitment_seconds: float = 1.5
    rearm_inactive_seconds: float = 3.75
    decision_reference_seconds: float = 3.75
    minimum_confirmation_margin: float = 0.0
    duplicate_sequence_horizon: int = 64
    peer_support_required_for_origination: bool = False
    temporary_disconnection_policy: str = (
        "retain_current_topology_and_abort_epoch"
    )


@dataclass(frozen=True)
class ControllerConfig:
    """Frozen local-controller design parameters."""

    goal_gain: float = 1.0
    formation_gain: float = 1.0
    damping_gain: float = 1.0
    robot_clearance_gain: float = 1.0
    robot_ttc_gain: float = 1.0
    obstacle_clearance_gain: float = 1.0
    obstacle_ttc_gain: float = 1.0
    velocity_consensus_gain: float = 1.0
    progress_window_seconds: float = 0.75
    # The frozen detector adds no extra lateral envelope beyond role motion and
    # collision clearance. These explicit zero assumptions preserve that
    # geometry; they are not a safe-expansion certificate.
    transition_response_lateral_bound_meters: float = 0.0
    protocol_lateral_drift_bound_meters: float = 0.0


@dataclass(frozen=True)
class SafetyConfig:
    """Geometric safety margins from which center clearances are derived."""

    # Includes the frozen 0.35 m obstacle radius plus 0.02 m surface margin.
    obstacle_clearance_margin_meters: float = 0.37
    inter_robot_safety_margin_meters: float = 0.04
    transition_observation_margin_meters: float = 0.0


@dataclass(frozen=True)
class ModelConfig:
    """Shape of the preserved decentralized ego selector."""

    hidden_dimension: int = 96
    message_passing_steps: int = 3
    attention_leaky_relu_slope: float = 0.2
    input_schema_version: str = "decentralized-ego-v1"


@dataclass(frozen=True)
class RuntimeConfig:
    """Closed, hashable hierarchy available to deployable code."""

    physical: PhysicalPlatformConfig = field(default_factory=PhysicalPlatformConfig)
    mission: MissionConfig = field(default_factory=MissionConfig)
    formation: FormationConfig = field(default_factory=FormationConfig)
    sensing: SensingConfig = field(default_factory=SensingConfig)
    communication: CommunicationConfig = field(default_factory=CommunicationConfig)
    protocol: ProtocolConfig = field(default_factory=ProtocolConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    model: ModelConfig = field(default_factory=ModelConfig)

    def __post_init__(self) -> None:
        issues = _basic_validation_issues(self)
        if issues:
            raise ConfigurationValidationError(issues)

    @classmethod
    def for_team_size(
        cls,
        team_size: int,
        graph_family: str = "path",
    ) -> "RuntimeConfig":
        diameter = graph_family_diameter(team_size, graph_family)
        config = cls(
            mission=MissionConfig(team_size=team_size),
            protocol=ProtocolConfig(
                declared_maximum_component_diameter_hops=diameter,
            ),
        )
        require_supported_configuration(config)
        return config

    @property
    def derived(self) -> "DerivedRuntimeConfig":
        return derive_runtime_configuration(self)


@dataclass(frozen=True)
class DerivedRuntimeConfig:
    """All runtime quantities computed from one :class:`RuntimeConfig`."""

    derivation_version: str
    formation_tolerance_meters: float
    robot_obstacle_required_clearance_meters: float
    robot_robot_required_clearance_meters: float
    minimum_formation_scale: float
    recovery_dwell_steps: int
    commitment_steps: int
    evidence_persistence_steps: int
    event_collection_rounds: int
    message_stale_rounds: int
    message_delay_bound_rounds: int
    rearm_inactive_steps: int
    decision_reference_steps: int
    progress_window_steps: int
    component_diameter_bound_hops: int
    causal_propagation_round_bound: int
    k_intent_rounds: int
    k_score_rounds: int
    k_ready_rounds: int
    k_confirm_rounds: int
    role_transition_observation_half_widths_meters: Tuple[float, ...]
    maximum_observable_transition_half_width_meters: float
    lookahead_distance_meters: float


@dataclass(frozen=True)
class ConfigurationIssue:
    code: str
    field_path: str
    message: str


@dataclass(frozen=True)
class ConfigurationSupport:
    supported: bool
    team_size: int
    reasons: Tuple[ConfigurationIssue, ...]
    canonical_component_diameter_hops: int


class ConfigurationValidationError(ValueError):
    """Structured early failure for an invalid runtime configuration."""

    def __init__(self, issues: Tuple[ConfigurationIssue, ...]) -> None:
        self.issues = tuple(issues)
        detail = "; ".join(
            f"{issue.field_path} [{issue.code}]: {issue.message}"
            for issue in self.issues
        )
        super().__init__(detail)


def canonical_runtime_source(config: RuntimeConfig) -> dict[str, object]:
    """Deployment-safe canonical source values for hashing and manifests."""
    if not isinstance(config, RuntimeConfig):
        raise TypeError("canonical runtime source requires RuntimeConfig")
    return asdict(config)


def canonical_runtime_hash(config: RuntimeConfig) -> str:
    """SHA-256 over immutable runtime source values, excluding derived data."""
    payload = json.dumps(
        canonical_runtime_source(config),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def steps_from_seconds(seconds: float, period_seconds: float) -> int:
    """Convert nonnegative physical time to periods using a stable ceiling."""
    if not math.isfinite(seconds) or seconds < 0.0:
        raise ValueError("seconds must be finite and nonnegative")
    if not math.isfinite(period_seconds) or period_seconds <= 0.0:
        raise ValueError("period_seconds must be finite and positive")
    return int(math.ceil(seconds / period_seconds - 1e-12))


def graph_family_diameter(team_size: int, graph_family: str) -> int:
    """Exact connected-graph diameter for mechanical graph fixtures."""
    if isinstance(team_size, bool) or not isinstance(team_size, int):
        raise TypeError("team_size must be an integer")
    if team_size <= 0:
        raise ValueError("team_size must be positive")
    if graph_family not in GRAPH_FAMILIES:
        raise ValueError(
            f"unsupported graph family {graph_family!r}; expected {GRAPH_FAMILIES}"
        )
    if team_size == 1:
        return 0
    if graph_family == "path":
        return team_size - 1
    if graph_family == "ring":
        return team_size // 2
    if graph_family == "star":
        return 1 if team_size == 2 else 2
    return 1


def component_diameter_bound(config: RuntimeConfig) -> int:
    declared = config.protocol.declared_maximum_component_diameter_hops
    if declared is not None:
        return int(declared)
    return int(config.protocol.maximum_team_size) - 1


def causal_propagation_round_bound(config: RuntimeConfig) -> int:
    """Diameter bound under bounded whole-round message delivery delay."""
    delay_rounds = steps_from_seconds(
        config.communication.maximum_message_delay_seconds,
        config.communication.communication_period_seconds,
    )
    return component_diameter_bound(config) * (delay_rounds + 1)


def _validated_rounds(explicit: Optional[int], minimum: int, field_name: str) -> int:
    if explicit is None:
        return minimum
    if isinstance(explicit, bool) or not isinstance(explicit, int):
        raise ConfigurationValidationError((ConfigurationIssue(
            "unit_mismatch", f"protocol.{field_name}",
            "round count must be an integer or null",
        ),))
    if explicit < minimum:
        raise ConfigurationValidationError((ConfigurationIssue(
            "insufficient_rounds", f"protocol.{field_name}",
            f"configured {explicit} rounds is below required bound {minimum}",
        ),))
    return explicit


def role_transition_observation_requirement_meters(
    source_role: Tuple[float, float],
    target_role: Tuple[float, float],
    required_obstacle_clearance_meters: float,
    controller_response_lateral_bound_meters: float,
    protocol_lateral_drift_bound_meters: float,
    additional_margin_meters: float,
) -> float:
    """Lateral half-width covering one role's prospective transition region."""
    lateral_displacement = abs(float(target_role[1]) - float(source_role[1]))
    return (
        lateral_displacement
        + required_obstacle_clearance_meters
        + controller_response_lateral_bound_meters
        + protocol_lateral_drift_bound_meters
        + additional_margin_meters
    )


def lookahead_distance_meters(config: RuntimeConfig, speed: Optional[float] = None) -> float:
    """Longitudinal reaction distance capped by the local sensing envelope."""
    physical = config.physical
    velocity = (
        physical.maximum_speed_meters_per_second
        if speed is None else float(speed)
    )
    if velocity < 0.0 or velocity > physical.maximum_speed_meters_per_second:
        raise ValueError("speed must be within the configured platform bounds")
    braking = velocity * velocity / (
        2.0 * physical.maximum_acceleration_meters_per_second_squared
    )
    derived = _derive_without_lookahead(config)
    protocol_time = (
        config.protocol.evidence_persistence_seconds
        + config.protocol.event_collection_seconds
        + derived.k_intent_rounds
        * config.communication.communication_period_seconds
    )
    required = (
        braking
        + velocity * protocol_time
        + config.safety.transition_observation_margin_meters
    )
    return min(config.sensing.obstacle_sensing_range_meters, required)


def _derive_without_lookahead(config: RuntimeConfig) -> DerivedRuntimeConfig:
    physical = config.physical
    communication = config.communication
    protocol = config.protocol
    formation = config.formation
    safety = config.safety
    controller = config.controller

    tolerance = (
        formation.formation_tolerance_ratio * formation.nominal_spacing_meters
    )
    # Decimal SI inputs are normalized to picometer precision so equivalent
    # source decompositions serialize identically (for example 2*0.18+0.04).
    robot_obstacle = round(
        physical.robot_radius_meters + safety.obstacle_clearance_margin_meters,
        12,
    )
    robot_robot = round(
        2.0 * physical.robot_radius_meters
        + safety.inter_robot_safety_margin_meters,
        12,
    )
    min_scale = min(
        max(
            (robot_robot + formation.spacing_margin_meters)
            / formation.nominal_spacing_meters,
            0.0,
        ),
        1.0,
    )
    diameter = component_diameter_bound(config)
    causal = causal_propagation_round_bound(config)
    intent = _validated_rounds(protocol.intent_rounds, causal, "intent_rounds")
    score = _validated_rounds(protocol.score_rounds, causal, "score_rounds")
    ready = _validated_rounds(protocol.readiness_rounds, causal, "readiness_rounds")
    confirm = _validated_rounds(
        protocol.confirmation_rounds, causal, "confirmation_rounds"
    )

    from .decentralized.roles import RoleAssignment
    from .decentralized.system_model import KEEP, LINE

    roles = RoleAssignment.from_index(
        config.mission.team_size, formation.nominal_spacing_meters
    )
    widths = tuple(
        role_transition_observation_requirement_meters(
            tuple(roles.role_of(robot_id, LINE)),
            tuple(roles.role_of(robot_id, KEEP)),
            robot_obstacle,
            controller.transition_response_lateral_bound_meters,
            controller.protocol_lateral_drift_bound_meters,
            safety.transition_observation_margin_meters,
        )
        for robot_id in range(config.mission.team_size)
    )

    return DerivedRuntimeConfig(
        derivation_version=DERIVATION_VERSION,
        formation_tolerance_meters=tolerance,
        robot_obstacle_required_clearance_meters=robot_obstacle,
        robot_robot_required_clearance_meters=robot_robot,
        minimum_formation_scale=min_scale,
        recovery_dwell_steps=steps_from_seconds(
            config.mission.recovery_dwell_seconds, physical.control_period_seconds
        ),
        commitment_steps=steps_from_seconds(
            protocol.commitment_seconds, physical.control_period_seconds
        ),
        evidence_persistence_steps=steps_from_seconds(
            protocol.evidence_persistence_seconds,
            physical.control_period_seconds,
        ),
        event_collection_rounds=steps_from_seconds(
            protocol.event_collection_seconds,
            communication.communication_period_seconds,
        ),
        message_stale_rounds=steps_from_seconds(
            communication.maximum_message_age_seconds,
            communication.communication_period_seconds,
        ),
        message_delay_bound_rounds=steps_from_seconds(
            communication.maximum_message_delay_seconds,
            communication.communication_period_seconds,
        ),
        rearm_inactive_steps=steps_from_seconds(
            protocol.rearm_inactive_seconds, physical.control_period_seconds
        ),
        decision_reference_steps=steps_from_seconds(
            protocol.decision_reference_seconds, physical.control_period_seconds
        ),
        progress_window_steps=steps_from_seconds(
            controller.progress_window_seconds, physical.control_period_seconds
        ),
        component_diameter_bound_hops=diameter,
        causal_propagation_round_bound=causal,
        k_intent_rounds=intent,
        k_score_rounds=score,
        k_ready_rounds=ready,
        k_confirm_rounds=confirm,
        role_transition_observation_half_widths_meters=widths,
        maximum_observable_transition_half_width_meters=(
            config.sensing.obstacle_sensing_range_meters
        ),
        lookahead_distance_meters=0.0,
    )


def derive_runtime_configuration(config: RuntimeConfig) -> DerivedRuntimeConfig:
    support = assess_runtime_configuration(config)
    if not support.supported:
        raise ConfigurationValidationError(support.reasons)
    partial = _derive_without_lookahead(config)
    return replace(
        partial,
        lookahead_distance_meters=lookahead_distance_meters(config),
    )


def _is_finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _basic_validation_issues(config: RuntimeConfig) -> Tuple[ConfigurationIssue, ...]:
    issues = []

    def positive(path: str, value: object) -> None:
        if not _is_finite_number(value) or float(value) <= 0.0:
            issues.append(ConfigurationIssue(
                "invalid_positive_quantity", path,
                "value must be a finite positive number in its declared unit",
            ))

    def nonnegative(path: str, value: object) -> None:
        if not _is_finite_number(value) or float(value) < 0.0:
            issues.append(ConfigurationIssue(
                "invalid_nonnegative_quantity", path,
                "value must be a finite nonnegative number in its declared unit",
            ))

    if isinstance(config.mission.team_size, bool) or not isinstance(
        config.mission.team_size, int
    ):
        issues.append(ConfigurationIssue(
            "unit_mismatch", "mission.team_size", "team_size must be an integer",
        ))
    elif config.mission.team_size <= 0:
        issues.append(ConfigurationIssue(
            "invalid_team_size", "mission.team_size", "team_size must be > 0",
        ))

    if isinstance(config.protocol.maximum_team_size, bool) or not isinstance(
        config.protocol.maximum_team_size, int
    ):
        issues.append(ConfigurationIssue(
            "unit_mismatch", "protocol.maximum_team_size",
            "maximum_team_size must be an integer",
        ))
    elif config.protocol.maximum_team_size <= 0:
        issues.append(ConfigurationIssue(
            "invalid_team_size", "protocol.maximum_team_size",
            "maximum_team_size must be > 0",
        ))
    elif (
        isinstance(config.mission.team_size, int)
        and not isinstance(config.mission.team_size, bool)
        and config.mission.team_size > config.protocol.maximum_team_size
    ):
        issues.append(ConfigurationIssue(
            "team_size_exceeds_maximum", "mission.team_size",
            f"team_size {config.mission.team_size} exceeds maximum_team_size "
            f"{config.protocol.maximum_team_size}",
        ))

    positive("physical.robot_radius_meters", config.physical.robot_radius_meters)
    positive(
        "physical.maximum_speed_meters_per_second",
        config.physical.maximum_speed_meters_per_second,
    )
    positive(
        "physical.maximum_acceleration_meters_per_second_squared",
        config.physical.maximum_acceleration_meters_per_second_squared,
    )
    positive(
        "physical.control_period_seconds", config.physical.control_period_seconds
    )
    positive(
        "formation.nominal_spacing_meters",
        config.formation.nominal_spacing_meters,
    )
    positive(
        "formation.formation_tolerance_ratio",
        config.formation.formation_tolerance_ratio,
    )
    nonnegative(
        "formation.spacing_margin_meters", config.formation.spacing_margin_meters
    )
    positive(
        "sensing.obstacle_sensing_range_meters",
        config.sensing.obstacle_sensing_range_meters,
    )
    positive(
        "sensing.peer_sensing_range_meters",
        config.sensing.peer_sensing_range_meters,
    )
    positive(
        "communication.communication_range_meters",
        config.communication.communication_range_meters,
    )
    positive(
        "communication.communication_period_seconds",
        config.communication.communication_period_seconds,
    )
    nonnegative(
        "communication.maximum_message_age_seconds",
        config.communication.maximum_message_age_seconds,
    )
    nonnegative(
        "communication.maximum_message_delay_seconds",
        config.communication.maximum_message_delay_seconds,
    )
    nonnegative(
        "communication.asynchronous_offset_seconds",
        config.communication.asynchronous_offset_seconds,
    )
    if not 0.0 <= config.communication.packet_loss_probability <= 1.0:
        issues.append(ConfigurationIssue(
            "invalid_probability", "communication.packet_loss_probability",
            "packet loss probability must be within [0, 1]",
        ))

    for name in (
        "recovery_dwell_seconds",
    ):
        nonnegative(f"mission.{name}", getattr(config.mission, name))
    for name in (
        "evidence_persistence_seconds",
        "event_collection_seconds",
        "commitment_seconds",
        "rearm_inactive_seconds",
        "decision_reference_seconds",
        "minimum_confirmation_margin",
    ):
        nonnegative(f"protocol.{name}", getattr(config.protocol, name))
    positive(
        "controller.progress_window_seconds",
        config.controller.progress_window_seconds,
    )
    for name in (
        "transition_response_lateral_bound_meters",
        "protocol_lateral_drift_bound_meters",
    ):
        nonnegative(f"controller.{name}", getattr(config.controller, name))
    for name in (
        "obstacle_clearance_margin_meters",
        "inter_robot_safety_margin_meters",
        "transition_observation_margin_meters",
    ):
        nonnegative(f"safety.{name}", getattr(config.safety, name))

    declared = config.protocol.declared_maximum_component_diameter_hops
    if declared is not None:
        if isinstance(declared, bool) or not isinstance(declared, int):
            issues.append(ConfigurationIssue(
                "unit_mismatch",
                "protocol.declared_maximum_component_diameter_hops",
                "diameter must be an integer number of hops or null",
            ))
        elif declared < 0:
            issues.append(ConfigurationIssue(
                "invalid_diameter",
                "protocol.declared_maximum_component_diameter_hops",
                "diameter must be nonnegative",
            ))
        elif declared > config.protocol.maximum_team_size - 1:
            issues.append(ConfigurationIssue(
                "invalid_diameter",
                "protocol.declared_maximum_component_diameter_hops",
                "diameter cannot exceed maximum_team_size - 1",
            ))

    if config.protocol.temporary_disconnection_policy not in (
        TEMPORARY_DISCONNECTION_POLICIES
    ):
        issues.append(ConfigurationIssue(
            "unsupported_disconnection_policy",
            "protocol.temporary_disconnection_policy",
            f"expected one of {TEMPORARY_DISCONNECTION_POLICIES}",
        ))
    if not config.mission.shared_frame_id:
        issues.append(ConfigurationIssue(
            "missing_frame", "mission.shared_frame_id",
            "shared frame identifier must be nonempty",
        ))
    if config.model.hidden_dimension <= 0 or config.model.message_passing_steps <= 0:
        issues.append(ConfigurationIssue(
            "invalid_model_shape", "model",
            "hidden dimension and message-passing steps must be positive",
        ))
    if not 0.0 < config.model.attention_leaky_relu_slope < 1.0:
        issues.append(ConfigurationIssue(
            "invalid_model_parameter", "model.attention_leaky_relu_slope",
            "attention slope must be within (0, 1)",
        ))
    return tuple(issues)


def assess_runtime_configuration(config: RuntimeConfig) -> ConfigurationSupport:
    issues = list(_basic_validation_issues(config))
    if issues:
        diameter = max(component_diameter_bound(config), 0)
        return ConfigurationSupport(
            False, config.mission.team_size, tuple(issues), diameter
        )

    diameter = component_diameter_bound(config)
    if diameter < config.mission.team_size - 1 and (
        config.protocol.declared_maximum_component_diameter_hops is None
    ):
        issues.append(ConfigurationIssue(
            "diameter_under_covers_team",
            "protocol.declared_maximum_component_diameter_hops",
            "implicit diameter must cover the configured team",
        ))

    try:
        causal = causal_propagation_round_bound(config)
        for field_name in (
            "intent_rounds",
            "score_rounds",
            "readiness_rounds",
            "confirmation_rounds",
        ):
            _validated_rounds(
                getattr(config.protocol, field_name), causal, field_name
            )
    except ConfigurationValidationError as exc:
        issues.extend(exc.issues)

    derived = None
    if not issues:
        try:
            derived = _derive_without_lookahead(config)
        except (ValueError, KeyError) as exc:
            issues.append(ConfigurationIssue(
                "topology_construction_failure", "mission.team_size", str(exc)
            ))

    if derived is not None:
        if (
            derived.robot_robot_required_clearance_meters
            > config.formation.nominal_spacing_meters
        ):
            issues.append(ConfigurationIssue(
                "formation_spacing_below_clearance",
                "formation.nominal_spacing_meters",
                "nominal spacing must not be below required robot clearance",
            ))
        widest = max(
            derived.role_transition_observation_half_widths_meters,
            default=0.0,
        )
        if widest > config.sensing.obstacle_sensing_range_meters:
            issues.append(ConfigurationIssue(
                "sensor_envelope_unsupported",
                "sensing.obstacle_sensing_range_meters",
                f"required transition half-width {widest:.6g} m exceeds "
                f"R_obs {config.sensing.obstacle_sensing_range_meters:.6g} m",
            ))

        from .decentralized.formation_metric_v3 import delta_n
        from .decentralized.roles import RoleAssignment

        roles = RoleAssignment.from_index(
            config.mission.team_size,
            config.formation.nominal_spacing_meters,
        )
        if roles.n != config.mission.team_size:
            issues.append(ConfigurationIssue(
                "persistent_role_count_mismatch", "mission.team_size",
                "constructed persistent-role count does not match team_size",
            ))
        gap = delta_n(roles)
        if gap <= 2.0 * derived.formation_tolerance_meters:
            issues.append(ConfigurationIssue(
                "topology_tubes_not_disjoint", "formation.formation_tolerance_ratio",
                f"KEEP/LINE delta {gap:.6g} m does not exceed twice tolerance",
            ))

    return ConfigurationSupport(
        supported=not issues,
        team_size=config.mission.team_size,
        reasons=tuple(issues),
        canonical_component_diameter_hops=diameter,
    )


def require_supported_configuration(config: RuntimeConfig) -> RuntimeConfig:
    support = assess_runtime_configuration(config)
    if not support.supported:
        raise ConfigurationValidationError(support.reasons)
    return config


def runtime_config_from_legacy(
    legacy_config: object,
    team_size: Optional[int] = None,
) -> RuntimeConfig:
    """Materialize a frozen runtime config from the deprecated broad config.

    This is a simulation/offline migration boundary. Deployable modules receive
    the returned object, never the mutable legacy object.
    """
    if isinstance(legacy_config, RuntimeConfig):
        if team_size is None or team_size == legacy_config.mission.team_size:
            return legacy_config
        mission = replace(legacy_config.mission, team_size=team_size)
        diameter = min(
            team_size - 1,
            legacy_config.protocol.maximum_team_size - 1,
        )
        protocol = replace(
            legacy_config.protocol,
            declared_maximum_component_diameter_hops=diameter,
        )
        return require_supported_configuration(replace(
            legacy_config, mission=mission, protocol=protocol
        ))

    nested = getattr(legacy_config, "runtime", None)
    if isinstance(nested, RuntimeConfig):
        return runtime_config_from_legacy(nested, team_size)

    env = getattr(legacy_config, "env", legacy_config)
    required = (
        "robot_radius", "max_speed", "max_accel", "dt", "nominal_spacing",
        "formation_tolerance", "spacing_margin", "lidar_range",
        "sensing_radius", "lidar_num_rays", "lidar_fov", "min_ro_distance",
        "min_rr_distance",
    )
    missing = tuple(name for name in required if not hasattr(env, name))
    if missing:
        raise TypeError(
            "expected RuntimeConfig or legacy environment fields; missing "
            + ", ".join(missing)
        )

    radius = float(env.robot_radius)
    spacing = float(env.nominal_spacing)
    tolerance = float(env.formation_tolerance)
    configured_team_size = 6 if team_size is None else int(team_size)
    diameter = configured_team_size - 1
    config = RuntimeConfig(
        physical=PhysicalPlatformConfig(
            robot_radius_meters=radius,
            maximum_speed_meters_per_second=float(env.max_speed),
            maximum_acceleration_meters_per_second_squared=float(env.max_accel),
            control_period_seconds=float(env.dt),
        ),
        mission=MissionConfig(team_size=configured_team_size),
        formation=FormationConfig(
            nominal_spacing_meters=spacing,
            formation_tolerance_ratio=tolerance / spacing,
            spacing_margin_meters=float(env.spacing_margin),
        ),
        sensing=SensingConfig(
            obstacle_sensing_range_meters=float(env.lidar_range),
            peer_sensing_range_meters=float(env.sensing_radius),
            lidar_number_of_rays=int(env.lidar_num_rays),
            lidar_field_of_view_radians=float(env.lidar_fov),
        ),
        protocol=ProtocolConfig(
            declared_maximum_component_diameter_hops=diameter,
        ),
        safety=SafetyConfig(
            obstacle_clearance_margin_meters=float(env.min_ro_distance) - radius,
            inter_robot_safety_margin_meters=(
                float(env.min_rr_distance) - 2.0 * radius
            ),
        ),
    )
    return require_supported_configuration(config)


DEFAULT_RUNTIME_CONFIG = RuntimeConfig()
