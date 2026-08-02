"""Forced-topology controller construction and closed loop through N=24."""

import numpy as np
import pytest

from rvt_swarm.decentralized.phase6_qualification import run_phase6_episode
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("topology", (KEEP, COMPACT, LINE))
def test_one_robot_action_shape_is_independent_of_team_size(
    phase6_input_factory, n, topology
):
    runtime, adapter, view, _ = phase6_input_factory(n=n, topology=topology)
    output = adapter.evaluate(view, 0.0)
    assert np.asarray(output.projected_action).shape == (2,)
    assert np.isfinite(output.projected_action).all()
    assert np.linalg.norm(output.projected_action) <= (
        runtime.physical.maximum_acceleration_meters_per_second_squared + 1e-12
    )


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("topology", (KEEP, COMPACT, LINE))
def test_exact_initialization_closed_loop_mechanical_cell(n, topology):
    result = run_phase6_episode(n, topology, "exact_topology", 61001)
    assert result.valid_initial_condition
    assert result.collision_free
    assert result.dwell_completed
    assert result.goal_reached
    assert not result.deadlock
    assert not result.numerical_failure
    assert result.solver_failure_count == 0
