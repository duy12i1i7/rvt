import math

import pytest

from rvt_swarm.fd24.configuration import FD24ModelConfig
from rvt_swarm.decentralized.ego_graph_v2 import EGO_GRAPH_SCHEMA_VERSION
from rvt_swarm.phase8.targets import (
    DENSE_ACTION_SAMPLE_SCHEMA_VERSION,
    DenseActionSample,
    RESIDUAL_EXPERT_ID,
    LocalActionEvaluation,
    build_residual_action_target,
    select_counterfactual_local_action,
)
from rvt_swarm.runtime_configuration import RuntimeConfig


def _evaluation(action, progress, *, local=True, feasible=True):
    return LocalActionEvaluation(
        action, feasible, True, local, progress, 0.4, 0.2, 0.2
    )


def test_local_search_selects_meaningful_local_expert_and_builds_bounded_target():
    runtime = RuntimeConfig.for_team_size(5)
    model = FD24ModelConfig()
    base = (0.1, 0.0)
    evaluations = (
        _evaluation(base, 0.2),
        _evaluation((0.2, -0.05), 0.8),
        _evaluation((0.11, 0.0), 1.0, local=False),
    )
    expert = select_counterfactual_local_action(base, evaluations, runtime, model)
    assert expert.action_world_acceleration == (0.2, -0.05)
    target = build_residual_action_target(base, expert, runtime, model)
    assert target.expert_source == RESIDUAL_EXPERT_ID
    assert target.residual_target_world_acceleration == pytest.approx((0.1, -0.05))
    assert target.residual_bounds_world_acceleration == pytest.approx((0.15, 0.15))
    assert target.nonzero and target.finite and target.safety_projection_compatible


def test_residual_target_clips_componentwise_and_reports_saturation():
    runtime = RuntimeConfig.for_team_size(5)
    model = FD24ModelConfig()
    expert = _evaluation((0.25, 0.0), 1.0)
    target = build_residual_action_target((0.0, 0.0), expert, runtime, model)
    assert target.residual_target_world_acceleration == pytest.approx((0.15, 0.0))
    assert target.saturated
    assert math.hypot(*target.expert_action_world_acceleration) <= 0.6


def test_centralized_or_infeasible_candidates_cannot_define_primary_expert():
    runtime = RuntimeConfig.for_team_size(5)
    model = FD24ModelConfig()
    with pytest.raises(ValueError, match="no eligible"):
        select_counterfactual_local_action(
            (0.0, 0.0),
            (_evaluation((0.1, 0.0), 1.0, local=False),),
            runtime,
            model,
        )


def test_action_target_requires_two_finite_world_frame_components():
    runtime = RuntimeConfig.for_team_size(5)
    model = FD24ModelConfig()
    with pytest.raises(ValueError, match="two"):
        build_residual_action_target((0.0,), _evaluation((0.0, 0.0), 0.0), runtime, model)


def test_dense_action_sample_carries_grouping_and_configuration_provenance():
    sample = DenseActionSample(
        DENSE_ACTION_SAMPLE_SCHEMA_VERSION,
        EGO_GRAPH_SCHEMA_VERSION,
        "f" * 64,
        5,
        (0.1, 0.0),
        (0.2, -0.05),
        (0.1, -0.05),
        (0.1, 0.0),
        (("intervened", "false"),),
        "role_0",
        5,
        "F2",
        "g" * 64,
        "train",
        "episode-1",
        10,
        "a" * 40,
        (("runtime", "r" * 64), ("protocol", "p" * 64)),
    )
    assert sample.candidate_or_committed_topology == 5
    assert sample.split == "train"
