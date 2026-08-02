"""Variable-N topology construction and mission-frame mechanics."""

from __future__ import annotations

import inspect
import math

import numpy as np
import pytest

from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.runtime_configuration import FormationConfig, RuntimeConfig
from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    construct_primary_templates,
    construct_topology,
    construct_topology_from_spacing,
    generate_persistent_roles,
    template_extents,
    template_world_positions,
)

TEAM_SIZES = (5, 6, 8, 12, 16, 24)


@pytest.mark.parametrize("n", TEAM_SIZES)
@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_every_primary_template_constructs_for_required_team_sizes(
    n: int, topology_id: int,
) -> None:
    config = RuntimeConfig.for_team_size(n)
    template = construct_topology(
        topology_id, config.formation, robot_keys_or_team_size=n
    )
    assert template.team_size == n
    assert len(set(template.role_ids)) == n


@pytest.mark.parametrize("n", TEAM_SIZES)
def test_templates_are_centered_to_numerical_tolerance(n: int) -> None:
    templates = construct_primary_templates(
        RuntimeConfig.for_team_size(n).formation,
        robot_keys_or_team_size=n,
    )
    for template in templates:
        mean_x = math.fsum(role.offset[0] for role in template.roles) / n
        mean_y = math.fsum(role.offset[1] for role in template.roles) / n
        assert mean_x == pytest.approx(0.0, abs=1e-12)
        assert mean_y == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("n", TEAM_SIZES)
def test_compact_is_narrower_than_keep_and_shorter_than_line(n: int) -> None:
    keep, compact, line = construct_primary_templates(
        RuntimeConfig.for_team_size(n).formation,
        robot_keys_or_team_size=n,
    )
    keep_width, _ = template_extents(keep)
    compact_width, compact_length = template_extents(compact)
    line_width, line_length = template_extents(line)
    assert compact_width < keep_width
    assert line_width == pytest.approx(0.0)
    assert compact_length < line_length


@pytest.mark.parametrize("n", TEAM_SIZES)
def test_keep_uses_square_like_grid_and_line_uses_nominal_single_file(n: int) -> None:
    spacing = 0.9
    keep = construct_topology_from_spacing(KEEP, n, spacing)
    line = construct_topology_from_spacing(LINE, n, spacing)
    keep_width, keep_length = template_extents(keep)
    line_width, line_length = template_extents(line)
    assert keep_width > 0.0
    assert keep_length <= keep_width + spacing
    assert line_width == pytest.approx(0.0)
    assert line_length == pytest.approx((n - 1) * spacing)


@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_translation_changes_only_world_origin(topology_id: int) -> None:
    template = construct_topology_from_spacing(topology_id, 8, 0.9)
    base = template_world_positions(template, (0.0, 0.0), (1.0, 0.0))
    moved = template_world_positions(template, (3.2, -7.1), (1.0, 0.0))
    for first, second in zip(base, moved):
        assert second[0] - first[0] == pytest.approx(3.2)
        assert second[1] - first[1] == pytest.approx(-7.1)


@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_rotation_is_equivariant_and_preserves_distances(topology_id: int) -> None:
    template = construct_topology_from_spacing(topology_id, 8, 0.9)
    horizontal = template_world_positions(template, (0.0, 0.0), (1.0, 0.0))
    vertical = template_world_positions(template, (0.0, 0.0), (0.0, 1.0))
    for (x, y), (rx, ry) in zip(horizontal, vertical):
        assert rx == pytest.approx(-y)
        assert ry == pytest.approx(x)
        assert math.hypot(rx, ry) == pytest.approx(math.hypot(x, y))


def test_reflected_input_order_does_not_change_robot_to_role_geometry() -> None:
    keys = tuple(f"robot-{index}" for index in range(8))
    config = RuntimeConfig.for_team_size(8)
    first_roles = generate_persistent_roles(keys)
    second_roles = generate_persistent_roles(tuple(reversed(keys)))
    first = construct_topology(KEEP, config.formation, role_set=first_roles)
    second = construct_topology(KEEP, config.formation, role_set=second_roles)
    assert first == second


@pytest.mark.parametrize("spacing", (0.72, 1.08))
@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_offsets_scale_with_formation_spacing(spacing: float, topology_id: int) -> None:
    baseline = construct_topology_from_spacing(topology_id, 12, 0.9)
    scaled = construct_topology(
        topology_id,
        FormationConfig(nominal_spacing_meters=spacing),
        robot_keys_or_team_size=12,
    )
    ratio = spacing / 0.9
    for first, second in zip(baseline.roles, scaled.roles):
        assert second.offset[0] == pytest.approx(first.offset[0] * ratio)
        assert second.offset[1] == pytest.approx(first.offset[1] * ratio)


def test_generators_have_no_fixed_team_size_branch_or_map_coordinates() -> None:
    import rvt_swarm.topology_registry as registry

    source = inspect.getsource(registry)
    assert "team_size == 6" not in source
    assert "team_size in (5, 6" not in source
    assert "corridor_x" not in source
    assert "obstacle_map" not in source


@pytest.mark.parametrize("n", TEAM_SIZES)
def test_keep_line_adapters_preserve_pre_phase3_semantics(n: int) -> None:
    spacing = 0.9
    roles = RoleAssignment.from_index(n, spacing)
    keep = construct_topology_from_spacing(KEEP, n, spacing)
    line = construct_topology_from_spacing(LINE, n, spacing)

    columns = max(2, int(math.ceil(math.sqrt(n))))
    rows = int(math.ceil(n / columns))
    legacy_keep = np.asarray([
        (
            (row - (rows - 1) / 2.0) * spacing,
            -(column - (columns - 1) / 2.0) * spacing,
        )
        for row, column in (divmod(index, columns) for index in range(n))
    ])
    legacy_keep -= legacy_keep.mean(axis=0)
    legacy_line = np.asarray([
        ((index - (n - 1) / 2.0) * spacing, 0.0)
        for index in range(n)
    ])

    registry_keep = np.asarray([role.offset for role in keep.roles])
    registry_line = np.asarray([role.offset for role in line.roles])
    assert registry_keep == pytest.approx(legacy_keep)
    assert registry_line == pytest.approx(legacy_line)
    assert roles.keep == pytest.approx(registry_keep)
    assert roles.line == pytest.approx(registry_line)
