"""Phase 2 authoritative configuration and validation contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from rvt_swarm.configuration import EvaluationConfig, ExperimentConfiguration
from rvt_swarm.configuration_serialization import canonical_runtime_hash
from rvt_swarm.runtime_configuration import (
    DEFAULT_RUNTIME_CONFIG,
    ConfigurationValidationError,
    FormationConfig,
    MissionConfig,
    PhysicalPlatformConfig,
    ProtocolConfig,
    RuntimeConfig,
    SensingConfig,
    assess_runtime_configuration,
)


def test_runtime_configuration_and_every_section_are_frozen_and_hashable() -> None:
    config = RuntimeConfig()
    with pytest.raises(FrozenInstanceError):
        config.mission = MissionConfig(team_size=8)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        config.physical.robot_radius_meters = 0.2  # type: ignore[misc]
    assert isinstance(hash(config), int)


def test_default_preserves_frozen_physical_and_mission_values() -> None:
    config = DEFAULT_RUNTIME_CONFIG
    derived = config.derived
    assert config.physical.robot_radius_meters == pytest.approx(0.18)
    assert config.physical.maximum_speed_meters_per_second == pytest.approx(0.9)
    assert config.physical.maximum_acceleration_meters_per_second_squared == pytest.approx(0.6)
    assert config.physical.control_period_seconds == pytest.approx(0.15)
    assert config.formation.nominal_spacing_meters == pytest.approx(0.9)
    assert config.sensing.obstacle_sensing_range_meters == pytest.approx(3.0)
    assert derived.formation_tolerance_meters == pytest.approx(0.55)
    assert derived.robot_robot_required_clearance_meters == pytest.approx(0.40)
    assert derived.robot_obstacle_required_clearance_meters == pytest.approx(0.55)
    assert config.mission.recovery_dwell_seconds == pytest.approx(3.0)


def test_evaluation_wrapper_cannot_mutate_runtime_configuration() -> None:
    wrapper = ExperimentConfiguration()
    before = canonical_runtime_hash(wrapper.runtime)
    with pytest.raises(FrozenInstanceError):
        wrapper.runtime = RuntimeConfig.for_team_size(8)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        wrapper.evaluation.episodes_per_setting = 10  # type: ignore[misc]
    assert canonical_runtime_hash(wrapper.runtime) == before


@pytest.mark.parametrize("team_size", [0, -1, 1.5, True])
def test_invalid_team_size_fails_early_without_clamping(team_size) -> None:
    with pytest.raises(ConfigurationValidationError) as exc:
        RuntimeConfig(mission=MissionConfig(team_size=team_size))
    assert exc.value.issues
    assert any("team_size" in issue.field_path for issue in exc.value.issues)


def test_team_size_above_maximum_fails_with_structured_reason() -> None:
    with pytest.raises(ConfigurationValidationError) as exc:
        RuntimeConfig(
            mission=MissionConfig(team_size=25),
            protocol=ProtocolConfig(maximum_team_size=24),
        )
    assert any(issue.code == "team_size_exceeds_maximum" for issue in exc.value.issues)


def test_formation_spacing_below_clearance_is_explicitly_unsupported() -> None:
    config = replace(
        RuntimeConfig(),
        formation=FormationConfig(nominal_spacing_meters=0.3),
    )
    support = assess_runtime_configuration(config)
    assert not support.supported
    assert any(issue.code == "formation_spacing_below_clearance" for issue in support.reasons)


def test_sensor_envelope_failure_is_structured_not_silently_clipped() -> None:
    config = replace(
        RuntimeConfig.for_team_size(24),
        sensing=SensingConfig(obstacle_sensing_range_meters=1.0),
    )
    support = assess_runtime_configuration(config)
    assert not support.supported
    assert any(issue.code == "sensor_envelope_unsupported" for issue in support.reasons)


def test_practical_unit_mismatch_bool_for_radius_is_rejected() -> None:
    with pytest.raises(ConfigurationValidationError) as exc:
        RuntimeConfig(physical=PhysicalPlatformConfig(robot_radius_meters=True))
    assert any(issue.code == "invalid_positive_quantity" for issue in exc.value.issues)


def test_semantically_equal_configs_have_equal_identity_and_hash() -> None:
    left = RuntimeConfig()
    right = RuntimeConfig(
        physical=PhysicalPlatformConfig(),
        mission=MissionConfig(),
    )
    assert left == right
    assert hash(left) == hash(right)
    assert canonical_runtime_hash(left) == canonical_runtime_hash(right)


def test_evaluation_values_are_not_members_of_runtime_config() -> None:
    runtime_fields = set(RuntimeConfig.__dataclass_fields__)
    evaluation_fields = set(EvaluationConfig.__dataclass_fields__)
    assert runtime_fields.isdisjoint(evaluation_fields)
    assert "episodes_per_setting" not in runtime_fields
    assert "maximum_control_steps" not in runtime_fields

