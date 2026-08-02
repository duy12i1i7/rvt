import pytest

from rvt_swarm.decentralized.phase7_qualification import scaling_records
from rvt_swarm.decentralized.transition_runtime import run_phase7_transition_episode


@pytest.mark.parametrize("n", (5, 8, 12, 16, 24))
def test_latency_and_bytes_are_measured_through_n24(n):
    result = run_phase7_transition_episode(n, 0, 2, "exact_source", "complete")
    records = scaling_records((result,))
    record = records[0]
    assert record.team_size == n
    assert record.protocol_compute_median_seconds >= 0.0
    assert record.controller_compute_p99_seconds >= record.controller_compute_median_seconds
    assert record.communication_latency_seconds > 0.0
    assert record.actual_bytes == result.actual_communication_bytes


def test_message_cost_increases_with_team_size_under_complete_graph():
    small = run_phase7_transition_episode(5, 0, 2, "exact_source", "complete")
    large = run_phase7_transition_episode(24, 0, 2, "exact_source", "complete")
    assert large.actual_communication_bytes > small.actual_communication_bytes
