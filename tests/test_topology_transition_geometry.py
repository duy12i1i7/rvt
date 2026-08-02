"""Static topology-transition geometry metadata, without readiness protocol."""

from __future__ import annotations

import inspect

import pytest

from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    construct_primary_templates,
    transition_geometry,
)

TRANSITIONS = (
    (KEEP, COMPACT), (COMPACT, KEEP),
    (KEEP, LINE), (LINE, KEEP),
    (COMPACT, LINE), (LINE, COMPACT),
)


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("source_id,target_id", TRANSITIONS)
def test_forward_reverse_transition_displacements_are_exact_opposites(
    n: int, source_id: int, target_id: int,
) -> None:
    config = RuntimeConfig.for_team_size(n)
    templates = {
        item.topology_id: item
        for item in construct_primary_templates(
            config.formation, robot_keys_or_team_size=n
        )
    }
    forward = transition_geometry(templates[source_id], templates[target_id], config)
    reverse = transition_geometry(templates[target_id], templates[source_id], config)
    assert forward.team_size == reverse.team_size == n
    for first, second in zip(forward.roles, reverse.roles):
        assert first.role_id == second.role_id
        assert first.displacement[0] == pytest.approx(-second.displacement[0])
        assert first.displacement[1] == pytest.approx(-second.displacement[1])
        assert first.magnitude_meters == pytest.approx(second.magnitude_meters)
        assert first.swept_segment == tuple(reversed(second.swept_segment))


def test_transition_metadata_contains_only_static_segments_and_bounds() -> None:
    config = RuntimeConfig.for_team_size(6)
    keep, compact, _ = construct_primary_templates(
        config.formation, robot_keys_or_team_size=6
    )
    transition = transition_geometry(keep, compact, config)
    assert transition.maximum_role_displacement_meters > 0.0
    assert transition.maximum_required_observation_extent_meters <= \
        config.sensing.obstacle_sensing_range_meters
    source = inspect.getsource(transition_geometry)
    for forbidden in (
        "readiness", "consensus", "SAFE", "UNSAFE", "future_trajectory",
        "protocol_phase", "state_machine",
    ):
        assert forbidden not in source
