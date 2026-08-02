from functools import lru_cache

import pytest

from rvt_swarm.decentralized.transition_admissibility import ADMITTED_DIRECTED_PAIRS
from rvt_swarm.decentralized.transition_runtime import (
    PHASE7_OPEN_SPACE_FIXTURES,
    run_phase7_transition_episode,
)


TEAM_SIZES = (5, 6, 8, 12, 16, 24)


@lru_cache(maxsize=None)
def _episode(n, source, target, fixture):
    return run_phase7_transition_episode(n, source, target, fixture, "path")


@pytest.mark.parametrize("n", TEAM_SIZES)
@pytest.mark.parametrize("source,target", ADMITTED_DIRECTED_PAIRS)
@pytest.mark.parametrize("fixture", PHASE7_OPEN_SPACE_FIXTURES)
def test_complete_open_space_matrix_is_explicit_and_collision_free(
    n, source, target, fixture
):
    result = _episode(n, source, target, fixture)
    assert set(result.first_readiness_state_by_robot.values()) == {"SAFE"}
    assert result.collision_free
    assert not result.partial_commitment
    assert result.no_op_epoch_count == 0
    assert result.actual_communication_bytes > 0
    assert result.actual_communication_bytes == sum(result.bytes_by_phase.values())
    assert result.learned_model_calls == 0
    if result.transition_success:
        assert result.mode_epoch_count == 1
        assert result.dwell_completion_step is not None
    else:
        assert result.abort_or_timeout in {
            "safety_projection_failure",
            "transition_or_dwell_timeout",
        }
        assert result.mode_epoch_count == 1


def test_open_space_gate_rates_are_reported_without_hiding_failed_cells():
    results = [
        _episode(n, source, target, fixture)
        for n in TEAM_SIZES
        for source, target in ADMITTED_DIRECTED_PAIRS
        for fixture in PHASE7_OPEN_SPACE_FIXTURES
    ]
    assert len(results) == 144
    assert sum(result.collision_free for result in results) == 144
    failed = [result for result in results if not result.transition_success]
    assert failed
    assert all(result.abort_or_timeout is not None for result in failed)
