"""Phase 2 source-to-derived physical and protocol semantics."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rvt_swarm.runtime_configuration import (
    CommunicationConfig,
    ConfigurationValidationError,
    ControllerConfig,
    FormationConfig,
    MissionConfig,
    PhysicalPlatformConfig,
    ProtocolConfig,
    RuntimeConfig,
    SafetyConfig,
    component_diameter_bound,
    derive_runtime_configuration,
    lookahead_distance_meters,
    role_transition_observation_requirement_meters,
    steps_from_seconds,
)


@pytest.mark.parametrize("period", [0.15, 0.075])
def test_control_frequency_preserves_physical_durations(period: float) -> None:
    config = replace(
        RuntimeConfig(),
        physical=replace(RuntimeConfig().physical, control_period_seconds=period),
    )
    derived = config.derived
    assert derived.recovery_dwell_steps * period == pytest.approx(
        config.mission.recovery_dwell_seconds, abs=period
    )
    assert derived.commitment_steps * period == pytest.approx(
        config.protocol.commitment_seconds, abs=period
    )
    assert derived.evidence_persistence_steps * period == pytest.approx(
        config.protocol.evidence_persistence_seconds, abs=period
    )


@pytest.mark.parametrize("period,expected", [(0.15, 3), (0.10, 5)])
def test_message_age_uses_communication_period(period: float, expected: int) -> None:
    config = replace(
        RuntimeConfig(),
        communication=replace(
            RuntimeConfig().communication,
            communication_period_seconds=period,
        ),
    )
    assert config.derived.message_stale_rounds == expected
    assert config.derived.message_stale_rounds * period + 1e-12 >= 0.45


def test_control_period_does_not_change_message_age_rounds() -> None:
    base = RuntimeConfig()
    faster_control = replace(
        base,
        physical=replace(base.physical, control_period_seconds=0.05),
    )
    assert faster_control.derived.message_stale_rounds == base.derived.message_stale_rounds


@pytest.mark.parametrize("maximum", [5, 6, 8, 12, 16, 24])
def test_default_diameter_tracks_maximum_team_size_without_tighter_bound(maximum: int) -> None:
    config = RuntimeConfig(
        mission=MissionConfig(team_size=min(maximum, 6)),
        protocol=ProtocolConfig(
            maximum_team_size=maximum,
            declared_maximum_component_diameter_hops=None,
        ),
    )
    derived = config.derived
    assert component_diameter_bound(config) == maximum - 1
    assert derived.k_intent_rounds == maximum - 1
    assert derived.k_score_rounds == maximum - 1
    assert derived.k_ready_rounds == maximum - 1
    assert derived.k_confirm_rounds == maximum - 1


@pytest.mark.parametrize(
    "field",
    ["intent_rounds", "score_rounds", "readiness_rounds", "confirmation_rounds"],
)
def test_insufficient_protocol_rounds_are_rejected(field: str) -> None:
    protocol = replace(ProtocolConfig(), **{field: 4})
    config = RuntimeConfig(protocol=protocol)
    with pytest.raises(ConfigurationValidationError) as exc:
        derive_runtime_configuration(config)
    assert any(issue.code == "insufficient_rounds" for issue in exc.value.issues)


def test_bounded_delay_increases_causal_round_requirement() -> None:
    config = replace(
        RuntimeConfig(),
        communication=replace(
            RuntimeConfig().communication,
            maximum_message_delay_seconds=0.15,
        ),
    )
    derived = config.derived
    assert derived.message_delay_bound_rounds == 1
    assert derived.causal_propagation_round_bound == 10
    assert derived.k_confirm_rounds == 10


@pytest.mark.parametrize(
    "radius,obstacle_margin,robot_margin,expected_ro,expected_rr",
    [(0.18, 0.37, 0.04, 0.55, 0.40), (0.22, 0.40, 0.06, 0.62, 0.50)],
)
def test_required_clearances_derive_from_geometry_and_margins(
    radius, obstacle_margin, robot_margin, expected_ro, expected_rr
) -> None:
    config = replace(
        RuntimeConfig(),
        physical=replace(RuntimeConfig().physical, robot_radius_meters=radius),
        safety=SafetyConfig(
            obstacle_clearance_margin_meters=obstacle_margin,
            inter_robot_safety_margin_meters=robot_margin,
        ),
    )
    derived = config.derived
    assert derived.robot_obstacle_required_clearance_meters == pytest.approx(expected_ro)
    assert derived.robot_robot_required_clearance_meters == pytest.approx(expected_rr)


def test_formation_tolerance_scales_only_from_ratio_and_spacing() -> None:
    config = replace(
        RuntimeConfig(),
        formation=replace(RuntimeConfig().formation, nominal_spacing_meters=1.8),
    )
    assert config.derived.formation_tolerance_meters == pytest.approx(1.10)


def test_role_observation_requirement_uses_all_declared_source_terms() -> None:
    value = role_transition_observation_requirement_meters(
        source_role=(0.0, 0.0),
        target_role=(1.0, 0.9),
        required_obstacle_clearance_meters=0.55,
        controller_response_lateral_bound_meters=0.10,
        protocol_lateral_drift_bound_meters=0.05,
        additional_margin_meters=0.02,
    )
    assert value == pytest.approx(1.62)


def test_role_widths_scale_with_spacing_and_clearance() -> None:
    base = RuntimeConfig.for_team_size(6)
    wider_spacing = replace(
        base,
        formation=replace(base.formation, nominal_spacing_meters=1.2),
    )
    larger_robot = replace(
        base,
        physical=replace(base.physical, robot_radius_meters=0.22),
    )
    assert max(wider_spacing.derived.role_transition_observation_half_widths_meters) > max(
        base.derived.role_transition_observation_half_widths_meters
    )
    assert max(larger_robot.derived.role_transition_observation_half_widths_meters) > max(
        base.derived.role_transition_observation_half_widths_meters
    )


def test_lookahead_is_motion_protocol_based_and_sensor_capped() -> None:
    config = RuntimeConfig()
    assert lookahead_distance_meters(config) == pytest.approx(1.755)
    tiny_sensor = replace(
        config,
        sensing=replace(config.sensing, obstacle_sensing_range_meters=1.5),
    )
    assert lookahead_distance_meters(tiny_sensor) == pytest.approx(1.5)


def test_time_conversion_boundaries_are_explicit() -> None:
    assert steps_from_seconds(0.0, 0.15) == 0
    assert steps_from_seconds(0.45, 0.15) == 3
    assert steps_from_seconds(0.451, 0.15) == 4
    with pytest.raises(ValueError):
        steps_from_seconds(-0.1, 0.15)
    with pytest.raises(ValueError):
        steps_from_seconds(1.0, 0.0)


def test_derived_values_are_not_constructor_fields() -> None:
    source_fields = set(RuntimeConfig.__dataclass_fields__)
    for forbidden in (
        "recovery_dwell_steps",
        "message_stale_rounds",
        "k_intent_rounds",
        "lookahead_distance_meters",
    ):
        assert forbidden not in source_fields
