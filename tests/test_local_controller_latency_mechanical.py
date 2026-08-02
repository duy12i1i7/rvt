"""Mechanical controller-stack latency remains below the control period."""

import pytest

from rvt_swarm.decentralized.phase6_qualification import benchmark_phase6_controller_stack
from rvt_swarm.runtime_configuration import RuntimeConfig


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
def test_bounded_degree_median_latency_is_below_control_period(n):
    result = benchmark_phase6_controller_stack(n, dense_communication=False, iterations=5)
    assert result.per_robot_latency_median_seconds < (
        RuntimeConfig.for_team_size(n).physical.control_period_seconds
    )
    assert result.per_robot_latency_p95_seconds >= result.per_robot_latency_median_seconds
    assert result.peak_memory_bytes > 0


def test_dense_n24_is_explicit_diagnostic_stress():
    result = benchmark_phase6_controller_stack(24, dense_communication=True, iterations=3)
    assert result.dense_communication
    assert result.local_degree_median == 23
    assert result.simulator_aggregate_median_seconds > 0.0
