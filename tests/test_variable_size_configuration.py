"""Phase 2 mechanical configuration scaling; no learned or closed-loop run."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace

import pytest

import rvt_swarm.runtime_configuration as configuration_module
from rvt_swarm.configuration_serialization import canonical_runtime_hash
from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.runtime_configuration import (
    GRAPH_FAMILIES,
    SUPPORTED_MECHANICAL_TEAM_SIZES,
    ConfigurationValidationError,
    RuntimeConfig,
    SafetyConfig,
    assess_runtime_configuration,
    graph_family_diameter,
)


@pytest.mark.parametrize("team_size", SUPPORTED_MECHANICAL_TEAM_SIZES)
@pytest.mark.parametrize("graph_family", GRAPH_FAMILIES)
def test_team_size_and_graph_family_configuration_is_mechanically_supported(
    team_size: int, graph_family: str
) -> None:
    config = RuntimeConfig.for_team_size(team_size, graph_family)
    support = assess_runtime_configuration(config)
    derived = config.derived
    roles = RoleAssignment.from_index(
        team_size, config.formation.nominal_spacing_meters
    )
    assert support.supported, support.reasons
    assert roles.n == team_size
    assert len(derived.role_transition_observation_half_widths_meters) == team_size
    assert max(derived.role_transition_observation_half_widths_meters) <= (
        config.sensing.obstacle_sensing_range_meters
    )
    assert derived.component_diameter_bound_hops == graph_family_diameter(
        team_size, graph_family
    )
    assert derived.k_intent_rounds >= derived.component_diameter_bound_hops
    assert derived.k_score_rounds >= derived.component_diameter_bound_hops
    assert derived.k_ready_rounds >= derived.component_diameter_bound_hops
    assert derived.k_confirm_rounds >= derived.component_diameter_bound_hops


@pytest.mark.parametrize("team_size", SUPPORTED_MECHANICAL_TEAM_SIZES)
def test_outer_roles_receive_wider_sectors_when_role_motion_requires_it(team_size: int) -> None:
    widths = RuntimeConfig.for_team_size(
        team_size
    ).derived.role_transition_observation_half_widths_meters
    assert max(widths) >= min(widths)
    assert len(set(round(value, 6) for value in widths)) > 1


@pytest.mark.parametrize("period", [0.15, 0.10])
def test_communication_period_sweep_is_deterministic(period: float) -> None:
    base = RuntimeConfig()
    config = replace(
        base,
        communication=replace(base.communication, communication_period_seconds=period),
    )
    assert canonical_runtime_hash(config) == canonical_runtime_hash(config)
    assert config.derived.message_stale_rounds * period + 1e-12 >= (
        config.communication.maximum_message_age_seconds
    )


@pytest.mark.parametrize("spacing", [0.9, 1.2])
def test_spacing_sweep_has_no_fixed_size_configuration_failure(spacing: float) -> None:
    base = RuntimeConfig.for_team_size(12)
    config = replace(
        base,
        formation=replace(base.formation, nominal_spacing_meters=spacing),
    )
    support = assess_runtime_configuration(config)
    assert support.supported, support.reasons


@pytest.mark.parametrize(
    "radius,obstacle_margin,robot_margin",
    [(0.18, 0.37, 0.04), (0.22, 0.40, 0.06)],
)
def test_robot_size_and_clearance_sweep_is_explicit(
    radius: float, obstacle_margin: float, robot_margin: float
) -> None:
    base = RuntimeConfig.for_team_size(8)
    config = replace(
        base,
        physical=replace(base.physical, robot_radius_meters=radius),
        safety=SafetyConfig(
            obstacle_clearance_margin_meters=obstacle_margin,
            inter_robot_safety_margin_meters=robot_margin,
        ),
    )
    support = assess_runtime_configuration(config)
    assert support.supported, support.reasons


def test_invalid_large_team_is_rejected_not_clamped_or_substituted() -> None:
    with pytest.raises(ConfigurationValidationError) as exc:
        RuntimeConfig.for_team_size(25)
    assert any(issue.code == "team_size_exceeds_maximum" for issue in exc.value.issues)


def test_configuration_implementation_has_no_n_equals_six_branch() -> None:
    tree = ast.parse(inspect.getsource(configuration_module))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        sides = [node.left] + list(node.comparators)
        if any(isinstance(side, ast.Constant) and side.value == 6 for side in sides):
            offenders.append(node.lineno)
    assert offenders == []
