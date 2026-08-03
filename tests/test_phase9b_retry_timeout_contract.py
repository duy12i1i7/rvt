"""Only one byte-identical infrastructure retry is permitted."""

from pathlib import Path

import pytest

from rvt_swarm.phase9b.budget import build_generation_budget_manifest
from rvt_swarm.phase9b.policy import GenerationAttempt, plan_infrastructure_retry


ROOT = Path(__file__).resolve().parents[1]


def _attempt():
    return GenerationAttempt("job-a", 17, "a" * 64, "b" * 64, "results/job-a")


@pytest.mark.parametrize(
    "reason",
    ("collision", "rollout_failure", "simulator_timeout", "protocol_failure",
     "safety_projection_failure", "residual_expert_infeasibility", "invalid_candidate_outcome"),
)
def test_scientific_failures_never_authorize_retry(reason):
    with pytest.raises(ValueError, match="never authorize"):
        plan_infrastructure_retry(_attempt(), reason)


def test_infrastructure_retry_preserves_scientific_identity():
    planned = plan_infrastructure_retry(_attempt(), "worker_crash")
    assert planned.original.job_id == planned.retry.job_id
    assert planned.original.seed == planned.retry.seed
    assert planned.original.input_sha256 == planned.retry.input_sha256
    assert planned.original.configuration_sha256 == planned.retry.configuration_sha256
    assert planned.original.output_destination == planned.retry.output_destination
    assert planned.attempts_logged == (0, 1)
    assert planned.scientific_denominator_delta == 0
    with pytest.raises(ValueError, match="at most one"):
        plan_infrastructure_retry(planned.retry, "worker_crash")


def test_wall_clock_timeouts_are_exact():
    timeout = build_generation_budget_manifest(ROOT)["timeout_contract"]
    assert timeout["wall_clock_seconds"] == {
        "source_trajectory_episode_job": 600,
        "counterfactual_candidate_replica_job": 900,
        "residual_action_cell_generation_job": 1800,
        "shard_finalization_job": 600,
    }
    assert timeout["simulator_semantic_timeout"] == "frozen_phase8_family_horizon"
