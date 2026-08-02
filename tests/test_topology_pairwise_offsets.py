"""Robot-local pairwise formation offset contract."""

from __future__ import annotations

import inspect
import math

import pytest

from rvt_swarm.runtime_configuration import FormationConfig, RuntimeConfig
from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    construct_topology,
    local_pairwise_offset,
    runtime_local_view,
)


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_pairwise_offsets_are_antisymmetric_on_every_edge(
    n: int, topology_id: int,
) -> None:
    template = construct_topology(
        topology_id,
        RuntimeConfig.for_team_size(n).formation,
        robot_keys_or_team_size=n,
    )
    for a, b in template.edges:
        forward = local_pairwise_offset(template.offset(a), template.offset(b), (0.6, 0.8))
        reverse = local_pairwise_offset(template.offset(b), template.offset(a), (0.6, 0.8))
        assert forward[0] == pytest.approx(-reverse[0])
        assert forward[1] == pytest.approx(-reverse[1])


@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_pairwise_offsets_are_cycle_consistent(topology_id: int) -> None:
    template = construct_topology(
        topology_id,
        RuntimeConfig.for_team_size(8).formation,
        robot_keys_or_team_size=8,
    )
    a, b, c = template.role_ids[:3]
    ab = local_pairwise_offset(template.offset(a), template.offset(b), (1.0, 0.0))
    bc = local_pairwise_offset(template.offset(b), template.offset(c), (1.0, 0.0))
    ca = local_pairwise_offset(template.offset(c), template.offset(a), (1.0, 0.0))
    assert ab[0] + bc[0] + ca[0] == pytest.approx(0.0)
    assert ab[1] + bc[1] + ca[1] == pytest.approx(0.0)


def test_local_view_contains_only_own_role_and_nominal_neighbour_offsets() -> None:
    template = construct_topology(
        COMPACT,
        RuntimeConfig.for_team_size(8).formation,
        robot_keys_or_team_size=8,
    )
    role_id = template.role_ids[3]
    view = runtime_local_view(template, role_id, (1.0, 0.0))
    assert view.role_id == role_id
    assert view.own_template_offset == template.offset(role_id)
    assert tuple(item.role_id for item in view.formation_neighbours) == \
        template.neighbour_role_ids(role_id)
    assert not hasattr(view, "template")
    assert not hasattr(view, "all_positions")
    assert not hasattr(view, "joint_state")


def test_local_access_signature_has_no_runtime_joint_state() -> None:
    parameters = inspect.signature(runtime_local_view).parameters
    assert "positions" not in parameters
    assert "velocities" not in parameters
    assert "joint_state" not in parameters


@pytest.mark.parametrize("topology_id", (KEEP, COMPACT, LINE))
def test_pairwise_offsets_scale_with_spacing(topology_id: int) -> None:
    base = construct_topology(
        topology_id, FormationConfig(nominal_spacing_meters=0.9),
        robot_keys_or_team_size=8,
    )
    scaled = construct_topology(
        topology_id, FormationConfig(nominal_spacing_meters=1.08),
        robot_keys_or_team_size=8,
    )
    a, b = base.edges[0]
    first = local_pairwise_offset(base.offset(a), base.offset(b), (1.0, 0.0))
    second = local_pairwise_offset(scaled.offset(a), scaled.offset(b), (1.0, 0.0))
    assert second[0] == pytest.approx(first[0] * 1.2)
    assert second[1] == pytest.approx(first[1] * 1.2)
    assert math.hypot(*second) == pytest.approx(math.hypot(*first) * 1.2)
