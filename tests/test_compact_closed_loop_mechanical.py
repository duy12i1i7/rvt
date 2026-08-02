"""COMPACT receives the same frozen controller and qualification gates."""

import pytest

from rvt_swarm.decentralized.phase6_qualification import run_phase6_episode
from rvt_swarm.topology_registry import COMPACT


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
def test_compact_bounded_perturbation_stabilizes_without_retuning(n):
    result = run_phase6_episode(n, COMPACT, "combined_perturbation", 61001)
    assert result.collision_free
    assert result.dwell_completed
    assert result.final_formation_error_meters < result.initial_formation_error_meters
    assert not result.deadlock
    assert result.solver_failure_count == 0


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
def test_compact_open_translation_reaches_goal_and_final_dwell(n):
    result = run_phase6_episode(n, COMPACT, "open_translation", 61001)
    assert result.collision_free
    assert result.goal_reached
    assert result.dwell_completed
    assert not result.deadlock


def test_compact_uses_same_controller_class_and_config(phase6_input_factory):
    runtime, adapter, _, _ = phase6_input_factory(topology=COMPACT)
    assert adapter.controller.runtime_config == runtime
    assert not hasattr(adapter.controller, "compact_gain")
    assert not hasattr(adapter.controller, "topology_specific_gain")
