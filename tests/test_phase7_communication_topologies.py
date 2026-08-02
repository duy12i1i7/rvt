from functools import lru_cache

import pytest

from rvt_swarm.decentralized.transition_runtime import (
    PHASE7_GRAPH_FAMILIES,
    run_phase7_transition_episode,
)


TEAM_SIZES = (5, 8, 12, 16, 24)


@lru_cache(maxsize=None)
def _episode(n, family):
    return run_phase7_transition_episode(n, 0, 2, "exact_source", family)


@pytest.mark.parametrize("n", TEAM_SIZES)
@pytest.mark.parametrize("family", PHASE7_GRAPH_FAMILIES)
def test_complete_communication_topology_matrix(n, family):
    result = _episode(n, family)
    assert result.k_intent >= result.configured_diameter_bound
    assert result.k_score >= result.configured_diameter_bound
    assert result.k_ready >= result.configured_diameter_bound
    assert result.k_confirm >= result.configured_diameter_bound
    assert not result.partial_commitment
    assert result.actual_communication_bytes > 0
    if family == "temporary_disconnection":
        assert result.assumption_violation is not None
        assert result.mode_epoch_count == 0
    else:
        assert result.propagation_completion_seconds is not None
        assert result.score_agreement_completion_seconds is not None
        assert result.all_ready_time_seconds is not None
        assert result.confirmation_time_seconds is not None
        assert result.mode_epoch_count == 1


def test_zero_peer_graph_is_detected_as_invalid_connectedness():
    from rvt_swarm.decentralized.transition_messages import TransitionIntent
    from rvt_swarm.decentralized.transition_protocol import (
        evaluate_intent_propagation,
        flood_transition_messages,
    )
    members = tuple(range(5))
    intent = TransitionIntent.create(
        1, 0, 0, 2, "externally_forced_diagnostic", 0.0, 100.0
    )
    flood = flood_transition_messages(
        members, {0: (intent,)}, {i: () for i in members}, 4
    )
    assert not evaluate_intent_propagation(
        flood, members, now_seconds=1.0, maximum_age_seconds=100.0
    ).agreed
