"""Role-aware topology separation under frozen Metric V3 tolerance."""

from __future__ import annotations

import pytest

from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    all_primary_separations,
    construct_primary_templates,
    topology_separation,
)

TEAM_SIZES = (5, 6, 8, 12, 16, 24)


@pytest.mark.parametrize("n", TEAM_SIZES)
def test_all_primary_topology_tubes_are_disjoint(n: int) -> None:
    config = RuntimeConfig.for_team_size(n)
    templates = construct_primary_templates(
        config.formation, robot_keys_or_team_size=n
    )
    separations = all_primary_separations(
        templates, config.derived.formation_tolerance_meters
    )
    assert tuple(
        (item.topology_a_id, item.topology_b_id) for item in separations
    ) == ((KEEP, COMPACT), (KEEP, LINE), (COMPACT, LINE))
    assert all(item.mechanically_distinct for item in separations)
    assert not any(item.tube_overlap for item in separations)
    assert all(item.normalized_maximum_distance > 0.0 for item in separations)


def test_identical_templates_are_flagged_as_overlapping_and_not_distinct() -> None:
    config = RuntimeConfig.for_team_size(6)
    keep = construct_primary_templates(
        config.formation, robot_keys_or_team_size=6
    )[0]
    separation = topology_separation(
        keep, keep, config.derived.formation_tolerance_meters
    )
    assert separation.tube_overlap
    assert not separation.mechanically_distinct


def test_frozen_tolerance_is_not_modified_by_audit() -> None:
    config = RuntimeConfig.for_team_size(5)
    before = config.derived.formation_tolerance_meters
    templates = construct_primary_templates(
        config.formation, robot_keys_or_team_size=5
    )
    all_primary_separations(templates, before)
    assert config.derived.formation_tolerance_meters == before == pytest.approx(0.55)
