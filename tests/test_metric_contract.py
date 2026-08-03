from rvt_swarm.phase8.contracts import (
    CONTROL_METRICS,
    PRIMARY_EPISODE_METRICS,
    RECOVERABILITY_METRICS,
    SCALING_METRICS,
    metric_contract_document,
)


def test_primary_episode_metrics_are_complete_and_frozen():
    assert PRIMARY_EPISODE_METRICS == (
        "task_success",
        "episode_collision_free",
        "final_required_topology_metric_v3_dwell",
        "required_transition_sequence_success",
        "deadlock",
        "completion_time_seconds",
    )


def test_recoverability_control_and_scaling_metrics_cover_required_domains():
    assert {"Brier_score", "NLL", "AUROC", "AUPRC"} <= set(RECOVERABILITY_METRICS)
    assert "residual_action_RMSE_mps2" in CONTROL_METRICS
    assert "bytes_per_robot" in SCALING_METRICS
    assert "inference_latency_per_robot_seconds" in SCALING_METRICS


def test_metric_contract_is_canonical_hashed_and_blocks_posthoc_promotion():
    document = metric_contract_document()
    assert len(document["metric_contract_sha256"]) == 64
    assert document["promotion_rule"] == "secondary metrics cannot become primary after results"
