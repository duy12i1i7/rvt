import pytest

from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import PRIMARY_TOPOLOGY_IDS, generate_persistent_roles
from rvt_swarm.decentralized.transition_admissibility import (
    ADMITTED_DIRECTED_PAIRS,
    assess_transition_admissibility,
)


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("source,target", ADMITTED_DIRECTED_PAIRS)
def test_all_six_registry_pairs_are_mechanically_admitted(n, source, target):
    config = RuntimeConfig.for_team_size(n)
    result = assess_transition_admissibility(
        source, target, source, generate_persistent_roles(n), config
    )
    assert result.admitted, result.reasons
    assert len(result.role_geometry) == n
    assert result.maximum_displacement_meters > 0.0
    assert result.static_swept_envelope_extent_meters <= (
        config.sensing.obstacle_sensing_range_meters
    )


@pytest.mark.parametrize("topology", PRIMARY_TOPOLOGY_IDS)
def test_source_equals_target_is_rejected_before_epoch(topology):
    config = RuntimeConfig.for_team_size(5)
    result = assess_transition_admissibility(
        topology, topology, topology, generate_persistent_roles(5), config
    )
    assert not result.admitted
    assert "source_equals_target" in result.reasons


def test_unknown_target_and_source_mismatch_are_explicit():
    config = RuntimeConfig.for_team_size(5)
    roles = generate_persistent_roles(5)
    assert "unknown_target_topology" in assess_transition_admissibility(
        0, 99, 0, roles, config
    ).reasons
    assert "source_topology_mismatch" in assess_transition_admissibility(
        0, 2, 5, roles, config
    ).reasons
