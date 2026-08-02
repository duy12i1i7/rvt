"""Structured mechanical validity certificates for primary topologies."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rvt_swarm.runtime_configuration import (
    FormationConfig,
    PhysicalPlatformConfig,
    RuntimeConfig,
    SafetyConfig,
)
from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    generate_persistent_roles,
    validate_topology_configuration,
)

TEAM_SIZES = (5, 6, 8, 12, 16, 24)


@pytest.mark.parametrize("n", TEAM_SIZES)
@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_required_mechanical_matrix_is_supported(n: int, topology_id: int) -> None:
    result = validate_topology_configuration(
        topology_id, RuntimeConfig.for_team_size(n)
    )
    assert result.supported, result.errors
    assert result.team_size == n
    assert result.minimum_clearance_meters == pytest.approx(0.9)
    assert result.graph_statistics.connected
    assert result.required_sensor_extent_meters <= 3.0


@pytest.mark.parametrize("spacing", (0.72, 1.08))
@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_two_formation_spacings_remain_mechanically_valid(
    spacing: float, topology_id: int,
) -> None:
    base = RuntimeConfig.for_team_size(8)
    config = replace(
        base,
        formation=FormationConfig(nominal_spacing_meters=spacing),
    )
    result = validate_topology_configuration(topology_id, config)
    assert result.supported, result.errors
    assert result.minimum_clearance_meters == pytest.approx(spacing)


@pytest.mark.parametrize(
    "physical,safety",
    [
        (PhysicalPlatformConfig(robot_radius_meters=0.16), SafetyConfig(inter_robot_safety_margin_meters=0.03)),
        (PhysicalPlatformConfig(robot_radius_meters=0.22), SafetyConfig(inter_robot_safety_margin_meters=0.06)),
    ],
)
def test_two_robot_geometry_configs_are_checked_without_tuning(
    physical: PhysicalPlatformConfig, safety: SafetyConfig,
) -> None:
    base = RuntimeConfig.for_team_size(8)
    config = replace(base, physical=physical, safety=safety)
    for topology_id in (KEEP, COMPACT, LINE):
        result = validate_topology_configuration(topology_id, config)
        assert result.supported, result.errors


def test_role_count_mismatch_returns_structured_unsupported_result() -> None:
    config = RuntimeConfig.for_team_size(6)
    result = validate_topology_configuration(
        KEEP, config, role_set=generate_persistent_roles(5)
    )
    assert not result.supported
    assert {issue.code for issue in result.errors} == {"role_count_mismatch"}


def test_spacing_below_declared_clearance_is_explicitly_rejected() -> None:
    base = RuntimeConfig.for_team_size(6)
    # Construction remains pure; validity must reject rather than clamp spacing.
    config = replace(
        base,
        formation=FormationConfig(nominal_spacing_meters=0.3),
    )
    result = validate_topology_configuration(COMPACT, config)
    assert not result.supported
    assert "nominal_clearance_violation" in {issue.code for issue in result.errors}
    assert result.minimum_clearance_meters == pytest.approx(0.3)


def test_compact_status_is_mechanical_not_closed_loop() -> None:
    result = validate_topology_configuration(
        COMPACT, RuntimeConfig.for_team_size(6)
    )
    assert result.supported
    assert result.controller_compatibility_status == \
        "mechanically-compatible-pending-phase6-qualification"
    assert {warning.code for warning in result.warnings} == {
        "forced_topology_qualification_pending"
    }
